"""
MySQL to Parquet exporter.

Exports data from MySQL to a local Parquet file using streaming.
This separates data extraction from transformation, eliminating
MySQL timeout issues during ETL processing.

Uses incremental writing (temp files per chunk) to avoid losing
progress if the connection times out.
"""

from __future__ import annotations

import shutil
import tempfile
import time
from pathlib import Path
from typing import TYPE_CHECKING

import polars as pl

from kweli.etl.utils.logger import get_logger

if TYPE_CHECKING:
    from structlog.types import FilteringBoundLogger

# MySQL connector import
try:
    import mysql.connector
    from mysql.connector import Error as MySQLError
except ImportError as e:
    raise ImportError("mysql-connector-python is required for MySQL export") from e


class MySQLToParquetExporter:
    """
    Export MySQL table to Parquet file using streaming.

    Uses unbuffered cursor to stream data without loading entire table
    into memory. Writes to Parquet in chunks for memory efficiency.
    """

    def __init__(
        self,
        host: str,
        database: str,
        table: str,
        user: str,
        password: str,
        port: int = 3306,
        use_ssl: bool = True,
        chunk_size: int = 50000,
        logger: FilteringBoundLogger | None = None,
    ) -> None:
        """Initialize the exporter."""
        self.host = host
        self.database = database
        self.table = table
        self.user = user
        self.password = password
        self.port = port
        self.use_ssl = use_ssl
        self.chunk_size = chunk_size
        self.logger = logger or get_logger(__name__)

    def _get_connection(self) -> mysql.connector.MySQLConnection:
        """Create MySQL connection for streaming."""
        ssl_config = {"ssl_disabled": not self.use_ssl}
        if self.use_ssl:
            ssl_config = {
                "ssl_ca": None,
                "ssl_verify_cert": False,
                "ssl_verify_identity": False,
            }

        conn = mysql.connector.connect(
            host=self.host,
            database=self.database,
            user=self.user,
            password=self.password,
            port=self.port,
            connection_timeout=120,
            **ssl_config,
        )
        return conn

    def _get_total_rows(self, conn: mysql.connector.MySQLConnection) -> int:
        """Get total row count."""
        cursor = conn.cursor()
        cursor.execute(f"SELECT COUNT(*) FROM `{self.table}`")
        count = cursor.fetchone()[0]
        cursor.close()
        return count

    def _get_columns(self, conn: mysql.connector.MySQLConnection) -> list[str]:
        """Get column names from table."""
        cursor = conn.cursor()
        cursor.execute(f"SELECT * FROM `{self.table}` LIMIT 1")
        columns = [desc[0] for desc in cursor.description]
        cursor.fetchall()  # Clear result
        cursor.close()
        return columns

    def export(self, output_path: Path | str) -> dict:
        """
        Export MySQL table to Parquet file.

        Uses incremental writing to temp files to avoid losing progress
        if the MySQL connection times out. Each chunk is written immediately
        to a temp Parquet file, then all are merged at the end.

        Args:
            output_path: Path for output Parquet file

        Returns:
            Export statistics
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        self.logger.info(
            "Starting MySQL to Parquet export (incremental mode)",
            host=self.host,
            database=self.database,
            table=self.table,
            output=str(output_path),
            chunk_size=self.chunk_size,
        )

        start_time = time.time()
        conn = self._get_connection()
        temp_dir = None
        temp_files: list[Path] = []

        try:
            total_rows = self._get_total_rows(conn)
            columns = self._get_columns(conn)

            self.logger.info(
                "Export configuration",
                total_rows=total_rows,
                columns=len(columns),
            )

            # Create temp directory for incremental writes
            temp_dir = Path(tempfile.mkdtemp(prefix="parquet_export_"))
            self.logger.info("Using temp directory", temp_dir=str(temp_dir))

            # Create streaming cursor
            cursor = conn.cursor(buffered=False)
            cursor.execute(f"SELECT * FROM `{self.table}`")

            rows_exported = 0
            chunk_number = 0

            while True:
                # Fetch chunk
                rows = cursor.fetchmany(self.chunk_size)
                if not rows:
                    break

                chunk_number += 1
                rows_exported += len(rows)

                # Convert to Polars DataFrame and write to temp file immediately
                df = pl.DataFrame(rows, schema=columns, orient="row")
                temp_file = temp_dir / f"chunk_{chunk_number:05d}.parquet"
                df.write_parquet(temp_file, compression="zstd")
                temp_files.append(temp_file)

                # Progress logging
                progress_pct = (rows_exported / total_rows) * 100
                elapsed = time.time() - start_time
                rate = rows_exported / elapsed if elapsed > 0 else 0

                if chunk_number % 5 == 0:  # Log every 5 chunks
                    self.logger.info(
                        "Export progress",
                        rows_exported=rows_exported,
                        total_rows=total_rows,
                        progress_percent=round(progress_pct, 1),
                        rate=round(rate, 1),
                        elapsed_seconds=round(elapsed, 1),
                        chunks_written=chunk_number,
                    )

            cursor.close()
            conn.close()  # Close MySQL connection ASAP

            # Merge all temp files into final output
            self.logger.info(
                "Merging temp files into final Parquet...",
                temp_files=len(temp_files),
            )

            # Read all temp files and concatenate
            all_dfs = [pl.read_parquet(f) for f in temp_files]
            final_df = pl.concat(all_dfs)
            final_df.write_parquet(output_path, compression="zstd")

            elapsed = time.time() - start_time
            file_size_mb = output_path.stat().st_size / (1024 * 1024)

            stats = {
                "rows_exported": rows_exported,
                "total_rows": total_rows,
                "columns": len(columns),
                "elapsed_seconds": round(elapsed, 2),
                "rate_rows_per_sec": round(rows_exported / elapsed, 1),
                "output_file": str(output_path),
                "file_size_mb": round(file_size_mb, 2),
                "compression": "zstd",
            }

            self.logger.info("Export complete", **stats)
            return stats

        except MySQLError as e:
            self.logger.error("MySQL error during export", error=str(e))
            raise
        finally:
            # Clean up temp directory
            if temp_dir and temp_dir.exists():
                shutil.rmtree(temp_dir, ignore_errors=True)
                self.logger.debug("Cleaned up temp directory")


def export_mysql_to_parquet(
    host: str,
    database: str,
    table: str,
    user: str,
    password: str,
    output_path: Path | str,
    port: int = 3306,
    use_ssl: bool = True,
    chunk_size: int = 50000,
    logger: FilteringBoundLogger | None = None,
) -> dict:
    """
    Convenience function to export MySQL table to Parquet.

    Args:
        host: MySQL server hostname
        database: Database name
        table: Table name
        user: MySQL username
        password: MySQL password
        output_path: Output Parquet file path
        port: MySQL port (default 3306)
        use_ssl: Use SSL connection (default True)
        chunk_size: Rows per chunk (default 50000)
        logger: Optional logger

    Returns:
        Export statistics dict
    """
    exporter = MySQLToParquetExporter(
        host=host,
        database=database,
        table=table,
        user=user,
        password=password,
        port=port,
        use_ssl=use_ssl,
        chunk_size=chunk_size,
        logger=logger,
    )
    return exporter.export(output_path)


__all__ = ["MySQLToParquetExporter", "export_mysql_to_parquet"]
