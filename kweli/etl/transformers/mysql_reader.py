"""
MySQL streaming reader for ETL pipeline.

Reads data from MySQL in chunks, yielding Polars DataFrames
to maintain compatibility with the CSV reader interface.

Supports two modes:
1. STREAMING (default, recommended): Uses unbuffered cursor with fetchmany()
   - Single table scan, O(N) total time
   - Best for tables without indexes
   - Ties up connection during streaming

2. OFFSET: Uses LIMIT/OFFSET pagination
   - O(N²) total time due to repeated scans
   - Only use if streaming causes connection issues
"""

from __future__ import annotations

import os
import time
from typing import TYPE_CHECKING

import mysql.connector
import polars as pl
from mysql.connector import pooling

from kweli.etl.utils.logger import get_logger

if TYPE_CHECKING:
    from collections.abc import Iterator

    from structlog.types import FilteringBoundLogger

# MySQL error codes for retryable errors
RETRYABLE_ERRORS = {
    2003,  # Can't connect to MySQL server
    2006,  # MySQL server has gone away
    2013,  # Lost connection to MySQL server during query
    2055,  # Lost connection to MySQL server at 'reading initial communication packet'
}


class MySQLStreamReader:
    """
    Stream data from MySQL database in chunks, yielding Polars DataFrames.

    This class provides the same interface as StreamingCSVReader to allow
    seamless switching between CSV and MySQL data sources.

    Supports two reading modes:
    - "streaming" (default): Uses unbuffered cursor with fetchmany() for O(N) performance
    - "offset": Uses LIMIT/OFFSET pagination (slower, O(N²) for tables without indexes)

    Attributes:
        host: MySQL server hostname
        database: Database name
        table: Table name to read from
        user: MySQL username
        password: MySQL password
        port: MySQL port (default 3306)
        chunk_size: Number of rows per chunk
        use_ssl: Whether to use SSL connection (default True for RDS)
        read_mode: "streaming" (default) or "offset"
        max_retries: Maximum retry attempts for transient failures
        retry_delay: Initial delay between retries (exponential backoff)
    """

    def __init__(
        self,
        host: str | None = None,
        database: str | None = None,
        table: str = "impact_learners_profile",
        user: str | None = None,
        password: str | None = None,
        port: int = 3306,
        chunk_size: int = 10000,  # Larger chunks are fine with streaming mode
        use_ssl: bool = True,
        connection_timeout: int = 120,  # Connection establishment timeout
        read_timeout: int = 3600,  # 1 hour - streaming keeps connection open
        pool_size: int = 3,
        max_retries: int = 3,
        retry_delay: float = 5.0,
        read_mode: str = "streaming",  # "streaming" or "offset"
        logger: FilteringBoundLogger | None = None,
    ) -> None:
        """
        Initialize MySQL stream reader.

        Args:
            host: MySQL server hostname (default: from MYSQL_HOST env)
            database: Database name (default: from MYSQL_DATABASE env)
            table: Table name to read from
            user: MySQL username (default: from MYSQL_USER env)
            password: MySQL password (default: from MYSQL_PASSWORD env)
            port: MySQL port (default: from MYSQL_PORT env or 3306)
            chunk_size: Number of rows per chunk
            use_ssl: Whether to use SSL connection
            connection_timeout: Connection timeout in seconds
            read_timeout: Read timeout (1 hour default for streaming)
            pool_size: Connection pool size
            max_retries: Maximum retry attempts for transient failures
            retry_delay: Initial delay between retries (exponential backoff)
            read_mode: "streaming" (recommended) or "offset"
            logger: Optional structured logger
        """
        self.host = host or os.getenv("MYSQL_HOST", "")
        self.database = database or os.getenv("MYSQL_DATABASE", "")
        self.table = table or os.getenv("MYSQL_TABLE", "impact_learners_profile")
        self.user = user or os.getenv("MYSQL_USER", "")
        self.password = password or os.getenv("MYSQL_PASSWORD", "")
        self.port = port or int(os.getenv("MYSQL_PORT", "3306"))
        self.chunk_size = chunk_size
        self.use_ssl = use_ssl
        self.connection_timeout = connection_timeout
        self.read_timeout = read_timeout
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.read_mode = read_mode.lower()
        self.logger = logger or get_logger(__name__)

        # Validate required fields
        if not self.host:
            raise ValueError("MySQL host is required (set MYSQL_HOST env var)")
        if not self.database:
            raise ValueError("MySQL database is required (set MYSQL_DATABASE env var)")
        if not self.user:
            raise ValueError("MySQL user is required (set MYSQL_USER env var)")
        if not self.password:
            raise ValueError("MySQL password is required (set MYSQL_PASSWORD env var)")

        # Connection pool for efficient resource management
        self._pool: pooling.MySQLConnectionPool | None = None
        self._pool_size = pool_size

        # Cache for metadata
        self._columns: list[str] | None = None
        self._total_rows: int | None = None

        # Validate read_mode
        if self.read_mode not in ("streaming", "offset"):
            raise ValueError(f"read_mode must be 'streaming' or 'offset', got: {self.read_mode}")

        self.logger.info(
            "Initialized MySQL reader",
            host=self.host,
            database=self.database,
            table=self.table,
            chunk_size=self.chunk_size,
            read_mode=self.read_mode,
        )

    def _get_pool(self) -> pooling.MySQLConnectionPool:
        """Get or create the connection pool."""
        if self._pool is None:
            self._pool = pooling.MySQLConnectionPool(
                pool_name="etl_pool",
                pool_size=self._pool_size,
                host=self.host,
                port=self.port,
                database=self.database,
                user=self.user,
                password=self.password,
                ssl_disabled=not self.use_ssl,
                connection_timeout=self.connection_timeout,
                use_pure=True,  # Pure Python for better compatibility
            )
        return self._pool

    def _get_connection(self) -> mysql.connector.MySQLConnection:
        """Get a connection from the pool."""
        return self._get_pool().get_connection()

    def get_columns(self) -> list[str]:
        """
        Get column names from the table.

        Returns:
            List of column names in order
        """
        if self._columns is not None:
            return self._columns

        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(f"DESCRIBE `{self.table}`")
            self._columns = [row[0] for row in cursor.fetchall()]
            cursor.close()
        finally:
            conn.close()

        self.logger.debug("Retrieved columns", count=len(self._columns))
        return self._columns

    def get_total_rows(self) -> int:
        """
        Get total number of rows in the table.

        Returns:
            Total row count
        """
        if self._total_rows is not None:
            return self._total_rows

        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(f"SELECT COUNT(*) FROM `{self.table}`")
            result = cursor.fetchone()
            self._total_rows = result[0] if result else 0
            cursor.close()
        finally:
            conn.close()

        self.logger.info("Total rows in table", count=self._total_rows)
        return self._total_rows

    def _execute_with_retry(
        self,
        query: str,
        offset: int,
    ) -> list[dict]:
        """
        Execute a query with retry logic for transient failures.

        Args:
            query: SQL query to execute
            offset: Current offset (for logging)

        Returns:
            List of row dictionaries

        Raises:
            mysql.connector.Error: If all retries fail
        """
        last_error = None

        for attempt in range(self.max_retries + 1):
            conn = None
            try:
                # Create fresh connection for each attempt
                conn = mysql.connector.connect(
                    host=self.host,
                    port=self.port,
                    database=self.database,
                    user=self.user,
                    password=self.password,
                    ssl_disabled=not self.use_ssl,
                    connection_timeout=self.connection_timeout,
                    use_pure=True,
                )

                cursor = conn.cursor(dictionary=True)
                cursor.execute(query)
                rows = cursor.fetchall()
                cursor.close()
                return rows

            except mysql.connector.Error as e:
                last_error = e
                error_code = e.errno if hasattr(e, "errno") else 0

                if error_code in RETRYABLE_ERRORS and attempt < self.max_retries:
                    delay = self.retry_delay * (2 ** attempt)  # Exponential backoff
                    self.logger.warning(
                        "MySQL transient error, retrying",
                        error_code=error_code,
                        error=str(e),
                        attempt=attempt + 1,
                        max_retries=self.max_retries,
                        retry_delay=delay,
                        offset=offset,
                    )
                    time.sleep(delay)
                else:
                    # Non-retryable error or max retries exceeded
                    raise

            finally:
                if conn is not None:
                    try:
                        conn.close()
                    except Exception:
                        pass

        # Should not reach here, but just in case
        if last_error:
            raise last_error
        return []

    def read_chunks(
        self,
        start_row: int = 0,
        max_rows: int | None = None,
    ) -> Iterator[pl.DataFrame]:
        """
        Read data in chunks, yielding Polars DataFrames.

        Supports two modes:
        - "streaming": Single table scan with unbuffered cursor (O(N), fast)
        - "offset": LIMIT/OFFSET pagination (O(N²), slow for large tables)

        Args:
            start_row: Row offset to start from (for resume, offset mode only)
            max_rows: Maximum rows to read (None = all)

        Yields:
            Polars DataFrame for each chunk
        """
        if self.read_mode == "streaming":
            yield from self._read_chunks_streaming(start_row, max_rows)
        else:
            yield from self._read_chunks_offset(start_row, max_rows)

    def _read_chunks_streaming(
        self,
        start_row: int = 0,
        max_rows: int | None = None,
    ) -> Iterator[pl.DataFrame]:
        """
        Read data using unbuffered cursor with fetchmany().

        This is much faster than OFFSET pagination for tables without indexes
        because it only requires a single table scan.

        Note: start_row is handled by skipping rows, not by OFFSET.

        Args:
            start_row: Row offset to start from (rows will be skipped)
            max_rows: Maximum rows to read (None = all)

        Yields:
            Polars DataFrame for each chunk
        """
        total_rows = self.get_total_rows()
        columns = self.get_columns()

        self.logger.info(
            "Starting STREAMING read from MySQL (single table scan)",
            start_row=start_row,
            max_rows=max_rows,
            total_rows=total_rows,
            chunk_size=self.chunk_size,
        )

        conn = None
        cursor = None
        rows_processed = 0
        rows_skipped = 0
        read_start = time.time()

        try:
            # Create connection with read timeout for long streaming
            conn = mysql.connector.connect(
                host=self.host,
                port=self.port,
                database=self.database,
                user=self.user,
                password=self.password,
                ssl_disabled=not self.use_ssl,
                connection_timeout=self.connection_timeout,
                use_pure=True,
            )

            # Use unbuffered cursor - rows are fetched on demand from server
            cursor = conn.cursor(buffered=False)

            # Execute single SELECT query - streams results
            query = f"SELECT * FROM `{self.table}`"
            self.logger.debug("Executing streaming query", query=query)
            cursor.execute(query)

            while True:
                # Check if we've reached max_rows limit
                if max_rows is not None and rows_processed >= max_rows:
                    break

                # Fetch a chunk of rows
                fetch_size = self.chunk_size
                if max_rows is not None:
                    remaining = max_rows - rows_processed
                    fetch_size = min(fetch_size, remaining)

                raw_rows = cursor.fetchmany(fetch_size)

                if not raw_rows:
                    break

                # Handle start_row by skipping initial rows
                if rows_skipped < start_row:
                    rows_to_skip = min(len(raw_rows), start_row - rows_skipped)
                    raw_rows = raw_rows[rows_to_skip:]
                    rows_skipped += rows_to_skip
                    if not raw_rows:
                        continue

                # Convert tuples to dicts with column names
                rows = [dict(zip(columns, row, strict=False)) for row in raw_rows]

                # Convert to Polars DataFrame
                df = pl.DataFrame(rows)

                rows_processed += len(rows)

                # Log progress every 10 chunks
                if (rows_processed // self.chunk_size) % 10 == 0:
                    elapsed = time.time() - read_start
                    rate = rows_processed / elapsed if elapsed > 0 else 0
                    progress_pct = (rows_processed / total_rows) * 100 if total_rows > 0 else 0
                    self.logger.info(
                        "MySQL streaming progress",
                        rows_processed=rows_processed,
                        progress_percent=round(progress_pct, 1),
                        rows_per_second=round(rate, 1),
                        elapsed_seconds=round(elapsed, 1),
                    )

                yield df

                # If we got fewer rows than requested, we've reached the end
                if len(raw_rows) < fetch_size:
                    break

        except mysql.connector.Error as e:
            self.logger.error(
                "MySQL streaming error",
                error=str(e),
                rows_processed=rows_processed,
            )
            raise

        finally:
            if cursor:
                try:
                    cursor.close()
                except Exception:
                    pass
            if conn:
                try:
                    conn.close()
                except Exception:
                    pass

        elapsed = time.time() - read_start
        rate = rows_processed / elapsed if elapsed > 0 else 0
        self.logger.info(
            "MySQL streaming read complete",
            total_processed=rows_processed,
            elapsed_seconds=round(elapsed, 1),
            avg_rows_per_second=round(rate, 1),
        )

    def _read_chunks_offset(
        self,
        start_row: int = 0,
        max_rows: int | None = None,
    ) -> Iterator[pl.DataFrame]:
        """
        Read data using LIMIT/OFFSET pagination (legacy mode).

        WARNING: This is slow for large tables without indexes because
        MySQL must scan all preceding rows for each OFFSET query.
        Use streaming mode instead when possible.

        Args:
            start_row: Row offset to start from (for resume)
            max_rows: Maximum rows to read (None = all)

        Yields:
            Polars DataFrame for each chunk
        """
        total_rows = self.get_total_rows()

        self.logger.info(
            "Starting OFFSET read from MySQL (legacy mode - may be slow)",
            start_row=start_row,
            max_rows=max_rows,
            total_rows=total_rows,
            chunk_size=self.chunk_size,
            max_retries=self.max_retries,
        )

        rows_processed = 0
        current_offset = start_row
        consecutive_failures = 0
        max_consecutive_failures = 5

        while True:
            # Check if we've reached max_rows limit
            if max_rows is not None and rows_processed >= max_rows:
                break

            # Calculate how many rows to fetch
            fetch_size = self.chunk_size
            if max_rows is not None:
                remaining = max_rows - rows_processed
                fetch_size = min(fetch_size, remaining)

            query = f"SELECT * FROM `{self.table}` LIMIT {fetch_size} OFFSET {current_offset}"

            try:
                query_start = time.time()
                rows = self._execute_with_retry(query, current_offset)
                query_duration = time.time() - query_start
                consecutive_failures = 0  # Reset on success

                # Log slow queries (> 30 seconds) as warning
                if query_duration > 30:
                    self.logger.warning(
                        "Slow MySQL query detected",
                        offset=current_offset,
                        duration_seconds=round(query_duration, 1),
                        rows_fetched=len(rows) if rows else 0,
                    )
            except mysql.connector.Error as e:
                consecutive_failures += 1
                self.logger.error(
                    "MySQL query failed after retries",
                    error=str(e),
                    offset=current_offset,
                    consecutive_failures=consecutive_failures,
                )

                if consecutive_failures >= max_consecutive_failures:
                    self.logger.error(
                        "Too many consecutive failures, stopping",
                        consecutive_failures=consecutive_failures,
                    )
                    raise

                # Try to continue with next chunk
                current_offset += fetch_size
                continue

            if not rows:
                break

            # Convert to Polars DataFrame
            df = pl.DataFrame(rows)

            rows_processed += len(rows)
            current_offset += len(rows)

            # Log progress every 10 chunks (with timing info)
            if (rows_processed // self.chunk_size) % 10 == 0:
                progress_pct = (current_offset / total_rows) * 100 if total_rows > 0 else 0
                self.logger.info(
                    "MySQL offset read progress",
                    rows_processed=rows_processed,
                    offset=current_offset,
                    progress_percent=round(progress_pct, 1),
                    last_query_seconds=round(query_duration, 1),
                )
            else:
                self.logger.debug(
                    "Read chunk from MySQL",
                    rows_in_chunk=len(rows),
                    total_processed=rows_processed,
                    offset=current_offset,
                    query_seconds=round(query_duration, 1),
                )

            yield df

            # If we got fewer rows than requested, we've reached the end
            if len(rows) < fetch_size:
                break

        self.logger.info(
            "MySQL offset read complete",
            total_processed=rows_processed,
        )

    def read_sample(self, n_rows: int = 100) -> pl.DataFrame:
        """
        Read a sample of rows for validation.

        Args:
            n_rows: Number of rows to sample

        Returns:
            Polars DataFrame with sample data
        """
        conn = self._get_connection()
        try:
            cursor = conn.cursor(dictionary=True)
            cursor.execute(f"SELECT * FROM `{self.table}` LIMIT {n_rows}")
            rows = cursor.fetchall()
            cursor.close()
        finally:
            conn.close()

        return pl.DataFrame(rows) if rows else pl.DataFrame()

    def read_all(self) -> pl.DataFrame:
        """
        Read entire table into a single DataFrame.

        WARNING: Only use for small tables. For large tables, use read_chunks().

        Returns:
            Polars DataFrame with all data
        """
        self.logger.warning(
            "Reading entire table into memory",
            table=self.table,
            total_rows=self.get_total_rows(),
        )

        conn = self._get_connection()
        try:
            cursor = conn.cursor(dictionary=True)
            cursor.execute(f"SELECT * FROM `{self.table}`")
            rows = cursor.fetchall()
            cursor.close()
        finally:
            conn.close()

        return pl.DataFrame(rows) if rows else pl.DataFrame()

    def test_connection(self) -> bool:
        """
        Test the MySQL connection.

        Returns:
            True if connection is successful, False otherwise
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            cursor.fetchone()
            cursor.close()
            conn.close()
            return True
        except Exception as e:
            self.logger.error("MySQL connection test failed", error=str(e))
            return False

    def close(self) -> None:
        """Close all connections in the pool."""
        # Connection pool handles cleanup automatically when garbage collected
        self._pool = None
        self.logger.info("MySQL reader closed")


__all__ = ["MySQLStreamReader"]
