# Production Pipeline Migration Plan

## MySQL RDS to Neo4j Aura

**Created**: December 3, 2025
**Status**: Ready for Implementation

---

## Executive Summary

This document details the migration from a CSV-based ETL pipeline to a production setup that:
1. **Reads** from MySQL RDS (`prod-impact-tracking-mysql.cylzdy8g0gui.eu-west-1.rds.amazonaws.com`)
2. **Writes** to Neo4j Aura (`neo4j+s://66c01309.databases.neo4j.io`)

The design follows existing architecture patterns to ensure minimal code changes and backward compatibility with CSV mode.

### Migration Strategy

**Phase A (Now)**: Keep both CSV and MySQL sources available
- Implement MySQL reader alongside existing CSV reader
- Use `--source` flag to switch between them
- Validate MySQL → Neo4j Aura pipeline works correctly

**Phase B (Later)**: Remove CSV code once MySQL is stable
- Delete `csv_reader.py`, `polars_csv_reader.py`
- Remove `DataSourceFactory` abstraction
- Simplify CLI (remove `--source` option)
- Update extractor to use MySQL directly

---

## Connection Verification (December 3, 2025)

### MySQL RDS

| Property | Value |
|----------|-------|
| Host | `prod-impact-tracking-mysql.cylzdy8g0gui.eu-west-1.rds.amazonaws.com` |
| Port | 3306 |
| Database | `prod_impact_tracking` |
| User | `kweli_RO` (read-only) |
| Status | **Connected** |

**Tables in Database**:
| Table | Row Count |
|-------|-----------|
| `impact_learners_profile` | **1,617,360** |
| `fact_impact_members_all` | 1,447,849 |
| `impact_jobs_feed_v2` | 68,932 |
| `impact_jobs_feed` | 68,932 |
| `fact_impact_jobs_feed` | 59,956 |
| `impact_map_overview` | 3,681 |
| `impact_metrics` | 1,287 |
| `fact_static_impact_metrics` | 651 |
| `impact_placement_overview_by_country` | 236 |
| `fact_overview_summary` | 224 |
| `impact_outreach_feed` | 113 |
| `fact_impact_outreach_feed` | 19 |

**Target Table Schema** (`impact_learners_profile` - 58 columns):

```
 1. hashed_email                             | text
 2. sand_id                                  | text
 3. email                                    | text
 4. full_name                                | text
 5. profile_photo_url                        | text
 6. bio                                      | text
 7. skills_list                              | text
 8. gender                                   | text
 9. country_of_residence                     | text
10. country_of_origin                        | text
11. city_of_residence                        | text
12. region_name                              | text
13. education_level_of_study                 | text
14. education_field_of_study                 | text
15. country_of_residence_latitude            | decimal(38,6)
16. country_of_residence_longitude           | decimal(38,6)
17. city_of_residence_latitude               | decimal(38,6)
18. city_of_residence_longitude              | decimal(38,6)
19. designation                              | text
20. testimonial                              | text
21. is_learning_data                         | bigint
22. is_featured                              | bigint
23. youtube_id                               | text
24. is_featured_video                        | bigint
25. is_graduate_learner                      | bigint
26. is_active_learner                        | bigint
27. is_a_dropped_out                         | bigint
28. learning_details                         | text (JSON array)
29. is_running_a_venture                     | bigint
30. is_a_freelancer                          | bigint
31. is_wage_employed                         | bigint
32. placement_details                        | text (JSON array)
33. is_placed                                | bigint
34. employment_details                       | text (JSON array)
35. has_employment_details                   | bigint
36. education_details                        | text (JSON array)
37. has_education_details                    | bigint
38. has_data                                 | bigint
39. is_rural                                 | bigint
40. description_of_living_location           | text
41. has_disability                           | bigint
42. type_of_disability                       | text
43. is_from_low_income_household             | bigint
44. demographic_details                      | text
45. legacy_points_transaction_history        | text
46. has_legacy_points_transactions           | bigint
47. meta_rn                                  | bigint
48. meta_ui_lat                              | double
49. meta_ui_lng                              | double
50. student_record_ranking                   | bigint
51. rnk                                      | bigint
52. zoom_attendance_details                  | text
53. circle_events                            | text
54. ehub_check_ins                           | text
55. has_placement_details                    | bigint
56. has_profile_profile_photo                | bigint
57. has_social_economic_data                 | bigint
58. snapshot_id                              | bigint
```

### Neo4j Aura

| Property | Value |
|----------|-------|
| URI | `neo4j+s://66c01309.databases.neo4j.io` |
| User | `neo4j` |
| Encryption | TLS (neo4j+s://) |
| Status | **Connected** |
| Current Nodes | 0 (empty) |
| Current Labels | None |

---

## Architecture Overview

### Current Architecture (CSV-based)

```
CSV File --> StreamingCSVReader --> Extractor --> Transformer --> Loader --> Neo4j (local)
                                                                               |
                                                                    BatchOperations
```

### Proposed Architecture (MySQL + CSV)

```
                    +--> StreamingCSVReader --|
DataSourceFactory --|                         |--> Extractor --> Transformer --> Loader --> Neo4j Aura
                    +--> MySQLStreamReader  --|
```

The key insight is that `Transformer`, `Loader`, and all downstream components work with **Polars DataFrames** containing dictionaries. By creating a MySQL reader that yields identical Polars DataFrames, the existing transformation and loading code remains untouched.

---

## Phase 1: New Files to Create

### 1.1 MySQL Reader Class

**File**: `kweli/etl/transformers/mysql_reader.py`
**Estimated Lines**: ~200-250 lines

This class mirrors the `StreamingCSVReader` interface but reads from MySQL.

**Key Design Decisions**:
- Use `mysql-connector-python` (already in dependencies)
- Server-side cursors for memory efficiency
- Yield Polars DataFrames matching CSV reader output
- Column names from MySQL match CSV exactly (same schema)

**Interface**:

```python
"""MySQL streaming reader for ETL pipeline."""

from __future__ import annotations

import mysql.connector
from mysql.connector import pooling
from mysql.connector.cursor import MySQLCursorDict
import polars as pl
from typing import Iterator
from pathlib import Path
from structlog.typing import FilteringBoundLogger

from kweli.etl.utils.logger import get_logger


class MySQLStreamReader:
    """Stream data from MySQL database in chunks, yielding Polars DataFrames.

    This class provides the same interface as StreamingCSVReader to allow
    seamless switching between CSV and MySQL data sources.

    Attributes:
        host: MySQL server hostname
        database: Database name
        table: Table name to read from
        user: MySQL username
        password: MySQL password
        port: MySQL port (default 3306)
        chunk_size: Number of rows per chunk (default 10000)
        use_ssl: Whether to use SSL connection (default True for RDS)
    """

    def __init__(
        self,
        host: str,
        database: str,
        table: str,
        user: str,
        password: str,
        port: int = 3306,
        chunk_size: int = 10000,
        use_ssl: bool = True,
        connection_timeout: int = 30,
        read_timeout: int = 120,
        pool_size: int = 3,
        logger: FilteringBoundLogger | None = None,
    ) -> None:
        """Initialize MySQL stream reader.

        Args:
            host: MySQL server hostname
            database: Database name
            table: Table name to read from
            user: MySQL username
            password: MySQL password
            port: MySQL port
            chunk_size: Number of rows per chunk
            use_ssl: Whether to use SSL connection
            connection_timeout: Connection timeout in seconds
            read_timeout: Read timeout for large queries
            pool_size: Connection pool size
            logger: Optional structured logger
        """
        self.host = host
        self.database = database
        self.table = table
        self.user = user
        self.password = password
        self.port = port
        self.chunk_size = chunk_size
        self.use_ssl = use_ssl
        self.connection_timeout = connection_timeout
        self.read_timeout = read_timeout
        self.logger = logger or get_logger(__name__)

        # Connection pool for efficient resource management
        self._pool = pooling.MySQLConnectionPool(
            pool_name="etl_pool",
            pool_size=pool_size,
            host=host,
            port=port,
            database=database,
            user=user,
            password=password,
            ssl_disabled=not use_ssl,
            connection_timeout=connection_timeout,
            use_pure=True,  # Pure Python implementation for better compatibility
        )

        # Cache for metadata
        self._columns: list[str] | None = None
        self._total_rows: int | None = None

        self.logger.info(
            "Initialized MySQL reader",
            host=host,
            database=database,
            table=table,
            chunk_size=chunk_size,
        )

    def _get_connection(self) -> mysql.connector.MySQLConnection:
        """Get a connection from the pool."""
        return self._pool.get_connection()

    def get_columns(self) -> list[str]:
        """Get column names from the table.

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
        """Get total number of rows in the table.

        Returns:
            Total row count
        """
        if self._total_rows is not None:
            return self._total_rows

        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(f"SELECT COUNT(*) FROM `{self.table}`")
            self._total_rows = cursor.fetchone()[0]
            cursor.close()
        finally:
            conn.close()

        self.logger.info("Total rows in table", count=self._total_rows)
        return self._total_rows

    def read_chunks(
        self,
        start_row: int = 0,
        max_rows: int | None = None,
    ) -> Iterator[pl.DataFrame]:
        """Read data in chunks, yielding Polars DataFrames.

        Uses LIMIT/OFFSET with ORDER BY for deterministic chunking.

        Args:
            start_row: Row offset to start from (for resume)
            max_rows: Maximum rows to read (None = all)

        Yields:
            Polars DataFrame for each chunk
        """
        columns = self.get_columns()
        total_rows = self.get_total_rows()

        # Calculate rows to process
        remaining_rows = total_rows - start_row
        if max_rows is not None:
            remaining_rows = min(remaining_rows, max_rows)

        rows_processed = 0
        current_offset = start_row

        self.logger.info(
            "Starting chunked read",
            start_row=start_row,
            max_rows=max_rows,
            total_rows=total_rows,
        )

        while rows_processed < remaining_rows:
            chunk_size = min(self.chunk_size, remaining_rows - rows_processed)

            conn = self._get_connection()
            try:
                cursor = conn.cursor(dictionary=True)

                # Use ORDER BY for deterministic results
                # sand_id is a good candidate for ordering
                query = f"""
                    SELECT * FROM `{self.table}`
                    ORDER BY sand_id
                    LIMIT {chunk_size} OFFSET {current_offset}
                """

                cursor.execute(query)
                rows = cursor.fetchall()
                cursor.close()

            finally:
                conn.close()

            if not rows:
                break

            # Convert to Polars DataFrame
            df = pl.DataFrame(rows)

            rows_processed += len(rows)
            current_offset += len(rows)

            self.logger.debug(
                "Read chunk",
                rows_in_chunk=len(rows),
                total_processed=rows_processed,
                offset=current_offset,
            )

            yield df

    def read_sample(self, n_rows: int = 100) -> pl.DataFrame:
        """Read a sample of rows for validation.

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

        return pl.DataFrame(rows)

    def close(self) -> None:
        """Close all connections in the pool."""
        # Connection pool handles cleanup automatically
        self.logger.info("MySQL reader closed")
```

### 1.2 Data Source Factory

**File**: `kweli/etl/transformers/data_source.py`
**Estimated Lines**: ~80-100 lines

Factory pattern to abstract data source selection.

```python
"""Data source abstraction for ETL pipeline."""

from __future__ import annotations

from enum import Enum
from typing import Protocol, Iterator, Any
from pathlib import Path

import polars as pl
from structlog.typing import FilteringBoundLogger

from kweli.etl.utils.logger import get_logger


class DataSourceType(Enum):
    """Supported data source types."""
    CSV = "csv"
    MYSQL = "mysql"


class DataSourceReader(Protocol):
    """Protocol defining the interface for data source readers.

    Both CSV and MySQL readers must implement this interface.
    """

    def get_columns(self) -> list[str]:
        """Get column names from the data source."""
        ...

    def get_total_rows(self) -> int:
        """Get total number of rows in the data source."""
        ...

    def read_chunks(
        self,
        start_row: int = 0,
        max_rows: int | None = None,
    ) -> Iterator[pl.DataFrame]:
        """Read data in chunks, yielding Polars DataFrames."""
        ...

    def read_sample(self, n_rows: int = 100) -> pl.DataFrame:
        """Read a sample of rows for validation."""
        ...


class DataSourceFactory:
    """Factory for creating data source readers."""

    @staticmethod
    def create(
        source_type: DataSourceType | str,
        config: dict[str, Any],
        logger: FilteringBoundLogger | None = None,
    ) -> DataSourceReader:
        """Create a data source reader based on type.

        Args:
            source_type: Type of data source (csv or mysql)
            config: Configuration dictionary with source-specific settings
            logger: Optional structured logger

        Returns:
            DataSourceReader implementation

        Raises:
            ValueError: If source type is not supported
        """
        logger = logger or get_logger(__name__)

        # Normalize source type
        if isinstance(source_type, str):
            source_type = DataSourceType(source_type.lower())

        if source_type == DataSourceType.CSV:
            from kweli.etl.transformers.polars_csv_reader import StreamingCSVReader

            csv_path = config.get("csv_path")
            chunk_size = config.get("chunk_size", 10000)

            if not csv_path:
                raise ValueError("csv_path is required for CSV source")

            logger.info("Creating CSV reader", path=str(csv_path))
            return StreamingCSVReader(
                file_path=Path(csv_path),
                chunk_size=chunk_size,
                logger=logger,
            )

        elif source_type == DataSourceType.MYSQL:
            from kweli.etl.transformers.mysql_reader import MySQLStreamReader

            mysql_config = config.get("mysql", {})
            chunk_size = config.get("chunk_size", 10000)

            required_fields = ["host", "database", "table", "user", "password"]
            missing = [f for f in required_fields if not mysql_config.get(f)]
            if missing:
                raise ValueError(f"Missing required MySQL config: {missing}")

            logger.info(
                "Creating MySQL reader",
                host=mysql_config["host"],
                database=mysql_config["database"],
                table=mysql_config["table"],
            )

            return MySQLStreamReader(
                host=mysql_config["host"],
                database=mysql_config["database"],
                table=mysql_config["table"],
                user=mysql_config["user"],
                password=mysql_config["password"],
                port=mysql_config.get("port", 3306),
                chunk_size=chunk_size,
                use_ssl=mysql_config.get("use_ssl", True),
                connection_timeout=mysql_config.get("connection_timeout", 30),
                read_timeout=mysql_config.get("read_timeout", 120),
                logger=logger,
            )

        else:
            raise ValueError(f"Unsupported data source type: {source_type}")
```

### 1.3 MySQL Configuration Model

**File**: `kweli/etl/utils/config.py` (add to existing)
**Lines to Add**: ~40 lines

```python
class MySQLConfig(BaseModel):
    """MySQL connection configuration."""

    host: str = Field(..., description="MySQL server hostname")
    port: int = Field(3306, description="MySQL port")
    database: str = Field(..., description="Database name")
    table: str = Field("impact_learners_profile", description="Table to read from")
    user: str = Field(..., description="MySQL username")
    password: str = Field(..., description="MySQL password (from environment)")
    use_ssl: bool = Field(True, description="Use SSL for connection")
    connection_timeout: int = Field(30, description="Connection timeout in seconds")
    read_timeout: int = Field(120, description="Read timeout for large queries")
    pool_size: int = Field(3, description="Connection pool size")

    @classmethod
    def from_env(cls) -> "MySQLConfig":
        """Load MySQL configuration from environment variables.

        Environment variables:
            MYSQL_HOST: MySQL server hostname
            MYSQL_PORT: MySQL port (default 3306)
            MYSQL_DATABASE: Database name
            MYSQL_TABLE: Table name (default impact_learners_profile)
            MYSQL_USER: MySQL username
            MYSQL_PASSWORD: MySQL password
        """
        return cls(
            host=os.getenv("MYSQL_HOST", ""),
            port=int(os.getenv("MYSQL_PORT", "3306")),
            database=os.getenv("MYSQL_DATABASE", ""),
            table=os.getenv("MYSQL_TABLE", "impact_learners_profile"),
            user=os.getenv("MYSQL_USER", ""),
            password=os.getenv("MYSQL_PASSWORD", ""),
            use_ssl=os.getenv("MYSQL_USE_SSL", "true").lower() == "true",
        )


class DataSourceConfig(BaseModel):
    """Data source configuration supporting multiple source types."""

    type: str = Field("csv", description="Data source type: csv or mysql")

    # CSV configuration
    csv_path: str | None = Field(None, description="Path to CSV file")

    # MySQL configuration (loaded from environment for security)
    mysql: MySQLConfig | None = Field(None, description="MySQL configuration")

    # Common settings
    chunk_size: int = Field(10000, description="Rows per chunk")
```

### 1.4 Unit Tests for MySQL Reader

**File**: `tests/unit/test_mysql_reader.py`
**Estimated Lines**: ~200 lines

```python
"""Unit tests for MySQL stream reader."""

import pytest
from unittest.mock import Mock, MagicMock, patch
import polars as pl

from kweli.etl.transformers.mysql_reader import MySQLStreamReader
from kweli.etl.transformers.data_source import DataSourceFactory, DataSourceType


class TestMySQLStreamReader:
    """Tests for MySQL stream reader."""

    @pytest.fixture
    def mock_pool(self):
        """Create mock connection pool."""
        with patch("mysql.connector.pooling.MySQLConnectionPool") as mock:
            yield mock

    @pytest.fixture
    def mock_connection(self):
        """Create mock database connection."""
        conn = MagicMock()
        cursor = MagicMock()
        conn.cursor.return_value = cursor
        return conn, cursor

    def test_init_creates_connection_pool(self, mock_pool):
        """Test that initialization creates a connection pool."""
        reader = MySQLStreamReader(
            host="localhost",
            database="test_db",
            table="test_table",
            user="test_user",
            password="test_pass",
        )

        mock_pool.assert_called_once()
        assert reader.host == "localhost"
        assert reader.database == "test_db"
        assert reader.table == "test_table"
        assert reader.chunk_size == 10000

    def test_get_columns_returns_column_names(self, mock_pool, mock_connection):
        """Test that get_columns returns column names from DESCRIBE."""
        conn, cursor = mock_connection
        mock_pool.return_value.get_connection.return_value = conn
        cursor.fetchall.return_value = [
            ("id", "int", "NO", "PRI", None, "auto_increment"),
            ("name", "varchar(255)", "YES", "", None, ""),
            ("email", "text", "YES", "", None, ""),
        ]

        reader = MySQLStreamReader(
            host="localhost",
            database="test_db",
            table="test_table",
            user="test_user",
            password="test_pass",
        )

        columns = reader.get_columns()

        assert columns == ["id", "name", "email"]
        cursor.execute.assert_called_with("DESCRIBE `test_table`")

    def test_get_columns_caches_result(self, mock_pool, mock_connection):
        """Test that columns are cached after first call."""
        conn, cursor = mock_connection
        mock_pool.return_value.get_connection.return_value = conn
        cursor.fetchall.return_value = [("col1", "text", "", "", None, "")]

        reader = MySQLStreamReader(
            host="localhost",
            database="test_db",
            table="test_table",
            user="test_user",
            password="test_pass",
        )

        # Call twice
        reader.get_columns()
        reader.get_columns()

        # Should only query once
        assert cursor.execute.call_count == 1

    def test_get_total_rows_returns_count(self, mock_pool, mock_connection):
        """Test that get_total_rows returns correct count."""
        conn, cursor = mock_connection
        mock_pool.return_value.get_connection.return_value = conn
        cursor.fetchone.return_value = (1617360,)

        reader = MySQLStreamReader(
            host="localhost",
            database="test_db",
            table="test_table",
            user="test_user",
            password="test_pass",
        )

        total = reader.get_total_rows()

        assert total == 1617360

    def test_read_chunks_yields_dataframes(self, mock_pool, mock_connection):
        """Test that read_chunks yields Polars DataFrames."""
        conn, cursor = mock_connection
        mock_pool.return_value.get_connection.return_value = conn

        # Mock DESCRIBE
        cursor.fetchall.side_effect = [
            [("id", "int", "", "", None, ""), ("name", "text", "", "", None, "")],
            [{"id": 1, "name": "Test1"}, {"id": 2, "name": "Test2"}],
        ]
        cursor.fetchone.return_value = (2,)  # Total rows

        reader = MySQLStreamReader(
            host="localhost",
            database="test_db",
            table="test_table",
            user="test_user",
            password="test_pass",
            chunk_size=10,
        )

        chunks = list(reader.read_chunks())

        assert len(chunks) == 1
        assert isinstance(chunks[0], pl.DataFrame)

    def test_read_chunks_respects_start_row(self, mock_pool, mock_connection):
        """Test that read_chunks starts from specified offset."""
        conn, cursor = mock_connection
        mock_pool.return_value.get_connection.return_value = conn
        cursor.fetchall.side_effect = [
            [("id", "int", "", "", None, "")],
            [{"id": 101}],
        ]
        cursor.fetchone.return_value = (200,)

        reader = MySQLStreamReader(
            host="localhost",
            database="test_db",
            table="test_table",
            user="test_user",
            password="test_pass",
            chunk_size=100,
        )

        list(reader.read_chunks(start_row=100))

        # Check that OFFSET 100 was used
        call_args = cursor.execute.call_args_list[-1][0][0]
        assert "OFFSET 100" in call_args

    def test_read_chunks_respects_max_rows(self, mock_pool, mock_connection):
        """Test that read_chunks stops after max_rows."""
        conn, cursor = mock_connection
        mock_pool.return_value.get_connection.return_value = conn
        cursor.fetchall.side_effect = [
            [("id", "int", "", "", None, "")],
            [{"id": i} for i in range(50)],
        ]
        cursor.fetchone.return_value = (1000,)

        reader = MySQLStreamReader(
            host="localhost",
            database="test_db",
            table="test_table",
            user="test_user",
            password="test_pass",
            chunk_size=100,
        )

        chunks = list(reader.read_chunks(max_rows=50))

        assert len(chunks) == 1
        assert len(chunks[0]) == 50


class TestDataSourceFactory:
    """Tests for data source factory."""

    def test_create_csv_reader(self, tmp_path):
        """Test creating CSV reader through factory."""
        # Create a test CSV file
        csv_file = tmp_path / "test.csv"
        csv_file.write_text("id,name\n1,Test\n")

        reader = DataSourceFactory.create(
            source_type=DataSourceType.CSV,
            config={"csv_path": csv_file, "chunk_size": 100},
        )

        assert reader is not None
        assert hasattr(reader, "read_chunks")

    def test_create_mysql_reader(self):
        """Test creating MySQL reader through factory."""
        with patch("kweli.etl.transformers.mysql_reader.MySQLStreamReader") as mock:
            mock.return_value = MagicMock()

            reader = DataSourceFactory.create(
                source_type="mysql",
                config={
                    "mysql": {
                        "host": "localhost",
                        "database": "test",
                        "table": "test",
                        "user": "user",
                        "password": "pass",
                    }
                },
            )

            mock.assert_called_once()

    def test_create_raises_for_missing_config(self):
        """Test that factory raises error for missing config."""
        with pytest.raises(ValueError, match="csv_path is required"):
            DataSourceFactory.create(
                source_type=DataSourceType.CSV,
                config={},
            )

    def test_create_raises_for_unsupported_type(self):
        """Test that factory raises error for unsupported type."""
        with pytest.raises(ValueError):
            DataSourceFactory.create(
                source_type="unsupported",
                config={},
            )
```

---

## Phase 2: Files to Modify

### 2.1 Configuration Files

**File**: `config/settings.yaml`
**Lines to Add**: ~20 lines

```yaml
# =============================================================================
# Data Source Configuration
# =============================================================================
data_source:
  # Source type: "csv" or "mysql"
  type: "mysql"

  # CSV source configuration
  csv:
    path: "data/raw/impact_learners_profile-1759316791571.csv"

  # MySQL source configuration
  # Note: Credentials should be in environment variables, not here
  mysql:
    host: "prod-impact-tracking-mysql.cylzdy8g0gui.eu-west-1.rds.amazonaws.com"
    port: 3306
    database: "prod_impact_tracking"
    table: "impact_learners_profile"
    use_ssl: true
    connection_timeout: 30
    read_timeout: 120
    pool_size: 3

# =============================================================================
# Neo4j Configuration (Updated for Aura)
# =============================================================================
neo4j:
  # For Aura, use neo4j+s:// scheme (encrypted)
  uri: "neo4j+s://66c01309.databases.neo4j.io"
  user: "neo4j"
  # password from NEO4J_PASSWORD environment variable

  # Optimized for cloud (reduced from local settings)
  max_connection_pool_size: 30
  connection_timeout: 30
  max_transaction_retry_time: 60

  # Batch settings for cloud (smaller batches, more retries)
  batch_size: 1000  # Reduced from 5000 for cloud latency
  max_retries: 3
  retry_delay: 1.0

# =============================================================================
# ETL Pipeline Configuration
# =============================================================================
etl:
  # Reduced chunk size for cloud environment
  chunk_size: 10000  # Reduced from 50000

  # Reduced parallelism for cloud
  max_workers: 4  # Reduced from 8

  # Checkpoint settings
  checkpoint:
    enabled: true
    interval: 5000  # Save checkpoint every 5000 rows
    path: "data/checkpoints"
```

**File**: `.env.example`
**Lines to Add**: ~15 lines

```bash
# =============================================================================
# MySQL RDS Configuration
# =============================================================================
MYSQL_HOST=prod-impact-tracking-mysql.cylzdy8g0gui.eu-west-1.rds.amazonaws.com
MYSQL_PORT=3306
MYSQL_DATABASE=prod_impact_tracking
MYSQL_TABLE=impact_learners_profile
MYSQL_USER=kweli_RO
MYSQL_PASSWORD=your-mysql-password-here

# =============================================================================
# Neo4j Aura Configuration
# =============================================================================
NEO4J_URI=neo4j+s://66c01309.databases.neo4j.io
NEO4J_USER=neo4j
NEO4J_PASSWORD=your-neo4j-aura-password-here
```

### 2.2 Extractor Modification

**File**: `kweli/etl/pipeline/extractor.py`
**Lines to Modify**: ~40 lines

Update to support both CSV and MySQL sources:

```python
"""Data extraction from CSV or MySQL sources."""

from __future__ import annotations

from pathlib import Path
from typing import Iterator, Any
import polars as pl
from structlog.typing import FilteringBoundLogger

from kweli.etl.utils.logger import get_logger
from kweli.etl.transformers.data_source import DataSourceFactory, DataSourceType


class Extractor:
    """Extract data from CSV or MySQL data sources.

    This class wraps the data source factory to provide a unified interface
    for the ETL pipeline, regardless of the underlying data source.

    Attributes:
        source_type: Type of data source (csv or mysql)
        chunk_size: Number of rows per chunk
    """

    def __init__(
        self,
        source_type: str = "csv",
        csv_path: Path | str | None = None,
        mysql_config: dict[str, Any] | None = None,
        chunk_size: int = 10000,
        logger: FilteringBoundLogger | None = None,
    ) -> None:
        """Initialize the extractor.

        Args:
            source_type: Type of data source ("csv" or "mysql")
            csv_path: Path to CSV file (required if source_type is "csv")
            mysql_config: MySQL configuration dict (required if source_type is "mysql")
            chunk_size: Number of rows per chunk
            logger: Optional structured logger
        """
        self.source_type = source_type
        self.chunk_size = chunk_size
        self.logger = logger or get_logger(__name__)

        # Build configuration for factory
        config = {"chunk_size": chunk_size}

        if source_type == "csv":
            if csv_path is None:
                raise ValueError("csv_path is required for CSV source")
            config["csv_path"] = Path(csv_path)
        elif source_type == "mysql":
            if mysql_config is None:
                raise ValueError("mysql_config is required for MySQL source")
            config["mysql"] = mysql_config
        else:
            raise ValueError(f"Unsupported source type: {source_type}")

        # Create appropriate reader via factory
        self.reader = DataSourceFactory.create(
            source_type=DataSourceType(source_type),
            config=config,
            logger=self.logger,
        )

        self.logger.info(
            "Extractor initialized",
            source_type=source_type,
            chunk_size=chunk_size,
        )

    def get_columns(self) -> list[str]:
        """Get column names from the data source."""
        return self.reader.get_columns()

    def get_total_rows(self) -> int:
        """Get total number of rows in the data source."""
        return self.reader.get_total_rows()

    def extract_chunks(
        self,
        start_row: int = 0,
        max_rows: int | None = None,
    ) -> Iterator[pl.DataFrame]:
        """Extract data in chunks.

        Args:
            start_row: Row offset to start from (for resume)
            max_rows: Maximum rows to extract (None = all)

        Yields:
            Polars DataFrame for each chunk
        """
        self.logger.info(
            "Starting extraction",
            start_row=start_row,
            max_rows=max_rows,
        )

        yield from self.reader.read_chunks(
            start_row=start_row,
            max_rows=max_rows,
        )

    def read_sample(self, n_rows: int = 100) -> pl.DataFrame:
        """Read a sample of rows for validation.

        Args:
            n_rows: Number of rows to sample

        Returns:
            Polars DataFrame with sample data
        """
        return self.reader.read_sample(n_rows)
```

### 2.3 Neo4j Connection Enhancement for Aura

**File**: `kweli/etl/neo4j_ops/connection.py`
**Lines to Modify**: ~50 lines

Enhance for Neo4j Aura compatibility with retry logic:

```python
# Add these imports at the top
from neo4j.exceptions import ServiceUnavailable, SessionExpired, TransientError
import time

class Neo4jConnection:
    """Neo4j connection manager with Aura support."""

    def __init__(
        self,
        uri: str | None = None,
        user: str | None = None,
        password: str | None = None,
        database: str = "neo4j",
        max_connection_pool_size: int = 50,
        connection_timeout: int = 30,
        max_transaction_retry_time: int = 60,  # Increased for cloud
        max_retries: int = 3,
        retry_delay: float = 1.0,
        logger: FilteringBoundLogger | None = None,
    ) -> None:
        """Initialize Neo4j connection.

        Args:
            uri: Neo4j URI (supports bolt://, neo4j://, neo4j+s://)
            user: Neo4j username
            password: Neo4j password
            database: Database name
            max_connection_pool_size: Maximum connections in pool
            connection_timeout: Connection timeout in seconds
            max_transaction_retry_time: Max retry time for transactions
            max_retries: Number of retries for transient errors
            retry_delay: Initial delay between retries
            logger: Optional structured logger
        """
        self.uri = uri or os.getenv("NEO4J_URI", "bolt://localhost:7687")
        self.user = user or os.getenv("NEO4J_USER", "neo4j")
        self.password = password or os.getenv("NEO4J_PASSWORD", "password123")
        self.database = database
        self.max_connection_pool_size = max_connection_pool_size
        self.connection_timeout = connection_timeout
        self.max_transaction_retry_time = max_transaction_retry_time
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.logger = logger or get_logger(__name__)

        # Auto-detect encryption from URI scheme
        # neo4j+s:// and bolt+s:// require encryption
        self.encrypted = (
            self.uri.startswith("neo4j+s://") or
            self.uri.startswith("bolt+s://")
        )

        self._driver: Driver | None = None

        self.logger.info(
            "Neo4j connection configured",
            uri=self.uri,
            database=self.database,
            encrypted=self.encrypted,
            is_aura="databases.neo4j.io" in self.uri,
        )

    def connect(self) -> None:
        """Establish connection to Neo4j."""
        try:
            self._driver = GraphDatabase.driver(
                self.uri,
                auth=(self.user, self.password),
                max_connection_pool_size=self.max_connection_pool_size,
                connection_timeout=self.connection_timeout,
                max_transaction_retry_time=self.max_transaction_retry_time,
            )

            # Verify connection
            self._driver.verify_connectivity()

            self.logger.info(
                "Connected to Neo4j",
                uri=self.uri,
                encrypted=self.encrypted,
            )

        except Exception as e:
            self.logger.error("Failed to connect to Neo4j", error=str(e))
            raise

    def execute_with_retry(
        self,
        query: str,
        parameters: dict | None = None,
    ) -> list[dict]:
        """Execute a query with retry logic for transient errors.

        Args:
            query: Cypher query string
            parameters: Query parameters

        Returns:
            List of result records as dictionaries

        Raises:
            Exception: If all retries are exhausted
        """
        last_exception = None

        for attempt in range(self.max_retries):
            try:
                return self.execute_query(query, parameters)

            except (ServiceUnavailable, SessionExpired, TransientError) as e:
                last_exception = e

                if attempt < self.max_retries - 1:
                    # Exponential backoff
                    sleep_time = self.retry_delay * (2 ** attempt)

                    self.logger.warning(
                        "Retrying query after transient error",
                        attempt=attempt + 1,
                        max_retries=self.max_retries,
                        sleep_time=sleep_time,
                        error=str(e),
                    )

                    time.sleep(sleep_time)

        self.logger.error(
            "All retries exhausted",
            max_retries=self.max_retries,
            error=str(last_exception),
        )
        raise last_exception
```

### 2.4 CLI Enhancement

**File**: `kweli/etl/cli.py`
**Lines to Modify**: ~80 lines

Add source type selection and dry-run mode:

```python
import os
import yaml
from pathlib import Path
import click

from kweli.etl.utils.config import MySQLConfig
from kweli.etl.neo4j_ops.connection import Neo4jConnection


@cli.command()
@click.option(
    "--source",
    type=click.Choice(["csv", "mysql"], case_sensitive=False),
    default=None,
    help="Data source type (overrides config file)",
)
@click.option(
    "--csv-path",
    type=click.Path(exists=True, path_type=Path),
    default=None,
    help="Path to CSV file (required if source=csv)",
)
@click.option(
    "--dry-run/--no-dry-run",
    default=False,
    help="Validate connections without running ETL",
)
@click.option(
    "--config",
    type=click.Path(exists=True, path_type=Path),
    default=Path("config/settings.yaml"),
    help="Path to configuration file",
)
@click.option(
    "--mode",
    type=click.Choice(["sequential", "parallel"], case_sensitive=False),
    default="parallel",
    help="Pipeline execution mode",
)
@click.option(
    "--resume/--no-resume",
    default=False,
    help="Resume from last checkpoint",
)
@click.option(
    "--max-rows",
    type=int,
    default=None,
    help="Maximum rows to process (for testing)",
)
@click.option(
    "--progress/--no-progress",
    default=True,
    help="Show progress bar",
)
def run(
    source: str | None,
    csv_path: Path | None,
    dry_run: bool,
    config: Path,
    mode: str,
    resume: bool,
    max_rows: int | None,
    progress: bool,
):
    """Run the ETL pipeline.

    Examples:

        # Run with MySQL source (production)
        uv run python -m kweli.etl.cli run --source mysql

        # Dry run to validate connections
        uv run python -m kweli.etl.cli run --source mysql --dry-run

        # Run with CSV source
        uv run python -m kweli.etl.cli run --source csv --csv-path data/raw/file.csv

        # Resume interrupted run
        uv run python -m kweli.etl.cli run --source mysql --resume

        # Test with limited rows
        uv run python -m kweli.etl.cli run --source mysql --max-rows 1000
    """
    # Load configuration
    with open(config) as f:
        cfg = yaml.safe_load(f)

    # Determine source type
    source_type = source or cfg.get("data_source", {}).get("type", "csv")

    # Build source configuration
    if source_type == "mysql":
        # Load MySQL config from settings + environment
        mysql_cfg = cfg.get("data_source", {}).get("mysql", {})

        # Override with environment variables (for secrets)
        mysql_cfg["user"] = os.getenv("MYSQL_USER", mysql_cfg.get("user", ""))
        mysql_cfg["password"] = os.getenv("MYSQL_PASSWORD", "")

        if not mysql_cfg["password"]:
            raise click.ClickException(
                "MYSQL_PASSWORD environment variable is required for MySQL source"
            )

        source_config = {"mysql": mysql_cfg}
        click.echo(f"Source: MySQL ({mysql_cfg['host']}/{mysql_cfg['database']})")

    else:
        # CSV source
        csv_path = csv_path or Path(
            cfg.get("data_source", {}).get("csv", {}).get("path", "")
        )
        if not csv_path or not csv_path.exists():
            raise click.ClickException(f"CSV file not found: {csv_path}")

        source_config = {"csv_path": csv_path}
        click.echo(f"Source: CSV ({csv_path})")

    # Build Neo4j configuration
    neo4j_cfg = cfg.get("neo4j", {})
    neo4j_cfg["uri"] = os.getenv("NEO4J_URI", neo4j_cfg.get("uri", ""))
    neo4j_cfg["user"] = os.getenv("NEO4J_USER", neo4j_cfg.get("user", "neo4j"))
    neo4j_cfg["password"] = os.getenv("NEO4J_PASSWORD", "")

    if not neo4j_cfg["password"]:
        raise click.ClickException(
            "NEO4J_PASSWORD environment variable is required"
        )

    click.echo(f"Target: Neo4j ({neo4j_cfg['uri']})")

    # Dry run mode - just validate connections
    if dry_run:
        click.echo("\n--- Dry Run Mode ---")

        # Test MySQL connection
        if source_type == "mysql":
            click.echo("\nTesting MySQL connection...")
            try:
                from kweli.etl.transformers.mysql_reader import MySQLStreamReader
                reader = MySQLStreamReader(**mysql_cfg)
                total_rows = reader.get_total_rows()
                columns = reader.get_columns()
                sample = reader.read_sample(5)
                click.echo(f"  Connected to {mysql_cfg['host']}")
                click.echo(f"  Table: {mysql_cfg['table']}")
                click.echo(f"  Total rows: {total_rows:,}")
                click.echo(f"  Columns: {len(columns)}")
                click.echo(f"  Sample rows retrieved: {len(sample)}")
            except Exception as e:
                raise click.ClickException(f"MySQL connection failed: {e}")

        # Test Neo4j connection
        click.echo("\nTesting Neo4j connection...")
        try:
            conn = Neo4jConnection(
                uri=neo4j_cfg["uri"],
                user=neo4j_cfg["user"],
                password=neo4j_cfg["password"],
            )
            conn.connect()
            result = conn.execute_query("RETURN 1 as test")
            node_count = conn.execute_query("MATCH (n) RETURN count(n) as count")[0]["count"]
            click.echo(f"  Connected to {neo4j_cfg['uri']}")
            click.echo(f"  Current nodes: {node_count:,}")
            conn.close()
        except Exception as e:
            raise click.ClickException(f"Neo4j connection failed: {e}")

        click.echo("\n All connections validated successfully!")
        return

    # Run actual ETL pipeline
    # ... rest of existing run logic with source_type and source_config ...
```

### 2.5 Batch Operations Optimization

**File**: `kweli/etl/neo4j_ops/batch_ops.py`
**Lines to Modify**: ~40 lines

Add retry logic for cloud operations:

```python
from neo4j.exceptions import ServiceUnavailable, SessionExpired, TransientError
import time


class BatchOperations:
    """Batch operations for Neo4j with retry logic."""

    def __init__(
        self,
        connection: Neo4jConnection,
        batch_size: int = 1000,  # Reduced default for cloud
        max_retries: int = 3,
        retry_delay: float = 1.0,
        logger: FilteringBoundLogger | None = None,
    ) -> None:
        """Initialize batch operations.

        Args:
            connection: Neo4j connection instance
            batch_size: Number of records per batch
            max_retries: Number of retries for transient errors
            retry_delay: Initial delay between retries (exponential backoff)
            logger: Optional structured logger
        """
        self.connection = connection
        self.batch_size = batch_size
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.logger = logger or get_logger(__name__)

    def execute_batch_with_retry(
        self,
        query: str,
        records: list[dict],
    ) -> int:
        """Execute a batch query with retry logic.

        Args:
            query: Cypher query with $batch parameter
            records: List of records to process

        Returns:
            Number of records processed

        Raises:
            Exception: If all retries exhausted
        """
        last_exception = None

        for attempt in range(self.max_retries):
            try:
                result = self.connection.execute_query(
                    query,
                    {"batch": records},
                )
                return len(records)

            except (ServiceUnavailable, SessionExpired, TransientError) as e:
                last_exception = e

                if attempt < self.max_retries - 1:
                    sleep_time = self.retry_delay * (2 ** attempt)

                    self.logger.warning(
                        "Retrying batch after transient error",
                        attempt=attempt + 1,
                        max_retries=self.max_retries,
                        sleep_time=sleep_time,
                        batch_size=len(records),
                        error=str(e),
                    )

                    time.sleep(sleep_time)

        self.logger.error(
            "Batch operation failed after all retries",
            max_retries=self.max_retries,
            error=str(last_exception),
        )
        raise last_exception
```

---

## Phase 3: Testing Strategy

### 3.1 Unit Tests (Mock-based)

**Coverage Goals**:
- MySQL Reader: 90%+ coverage
- Data Source Factory: 95%+ coverage
- Connection retry logic: 100% coverage

**Test Categories**:
1. **MySQL Reader Tests**
   - Connection pool initialization
   - Column retrieval and caching
   - Row count caching
   - Chunk reading with LIMIT/OFFSET
   - Sample reading
   - Error handling (connection failures)

2. **Factory Tests**
   - CSV reader creation
   - MySQL reader creation
   - Missing config validation
   - Unsupported type handling

3. **Connection Tests**
   - Aura URI detection
   - Encryption auto-detection
   - Retry logic with exponential backoff

### 3.2 Integration Tests

**File**: `tests/integration/test_production.py`

```python
"""Integration tests for production environment.

These tests require live database connections.
Run with: pytest tests/integration -m integration
"""

import os
import pytest
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


@pytest.fixture
def mysql_config():
    """MySQL configuration from environment."""
    return {
        "host": os.getenv("MYSQL_HOST"),
        "port": int(os.getenv("MYSQL_PORT", "3306")),
        "database": os.getenv("MYSQL_DATABASE"),
        "table": os.getenv("MYSQL_TABLE", "impact_learners_profile"),
        "user": os.getenv("MYSQL_USER"),
        "password": os.getenv("MYSQL_PASSWORD"),
    }


@pytest.fixture
def neo4j_config():
    """Neo4j configuration from environment."""
    return {
        "uri": os.getenv("NEO4J_URI"),
        "user": os.getenv("NEO4J_USER"),
        "password": os.getenv("NEO4J_PASSWORD"),
    }


@pytest.mark.integration
class TestMySQLIntegration:
    """Integration tests for MySQL RDS connection."""

    def test_connect_to_rds(self, mysql_config):
        """Test connection to MySQL RDS."""
        from kweli.etl.transformers.mysql_reader import MySQLStreamReader

        reader = MySQLStreamReader(**mysql_config)
        total_rows = reader.get_total_rows()

        assert total_rows > 1_000_000  # Should have 1.6M+ rows

    def test_schema_matches_expected(self, mysql_config):
        """Test that MySQL schema matches expected columns."""
        from kweli.etl.transformers.mysql_reader import MySQLStreamReader

        reader = MySQLStreamReader(**mysql_config)
        columns = reader.get_columns()

        # Check for essential columns
        essential = [
            "hashed_email",
            "sand_id",
            "full_name",
            "learning_details",
            "employment_details",
            "placement_details",
        ]

        for col in essential:
            assert col in columns, f"Missing column: {col}"

    def test_read_sample_data(self, mysql_config):
        """Test reading sample data from MySQL."""
        from kweli.etl.transformers.mysql_reader import MySQLStreamReader

        reader = MySQLStreamReader(**mysql_config)
        sample = reader.read_sample(100)

        assert len(sample) == 100
        assert "hashed_email" in sample.columns
        assert "learning_details" in sample.columns


@pytest.mark.integration
class TestNeo4jAuraIntegration:
    """Integration tests for Neo4j Aura connection."""

    def test_connect_to_aura(self, neo4j_config):
        """Test connection to Neo4j Aura."""
        from kweli.etl.neo4j_ops.connection import Neo4jConnection

        conn = Neo4jConnection(**neo4j_config)
        conn.connect()

        result = conn.execute_query("RETURN 1 as test")
        assert result[0]["test"] == 1

        conn.close()

    def test_aura_encryption(self, neo4j_config):
        """Test that Aura connection uses encryption."""
        from kweli.etl.neo4j_ops.connection import Neo4jConnection

        conn = Neo4jConnection(**neo4j_config)

        # neo4j+s:// should enable encryption
        assert conn.encrypted is True

    def test_create_and_delete_test_node(self, neo4j_config):
        """Test creating and deleting a test node."""
        from kweli.etl.neo4j_ops.connection import Neo4jConnection

        conn = Neo4jConnection(**neo4j_config)
        conn.connect()

        # Create test node
        conn.execute_query(
            "CREATE (n:TestNode {id: $id, name: $name})",
            {"id": "test-123", "name": "Integration Test"},
        )

        # Verify creation
        result = conn.execute_query(
            "MATCH (n:TestNode {id: $id}) RETURN n",
            {"id": "test-123"},
        )
        assert len(result) == 1

        # Delete test node
        conn.execute_query(
            "MATCH (n:TestNode {id: $id}) DELETE n",
            {"id": "test-123"},
        )

        conn.close()
```

### 3.3 Dry-Run Validation

The CLI includes a `--dry-run` option that:
1. Connects to MySQL and reads sample data
2. Connects to Neo4j Aura and runs health check
3. Validates schema compatibility
4. Reports estimated processing time

```bash
# Validate all connections
uv run python -m kweli.etl.cli run --source mysql --dry-run
```

---

## Phase 4: Execution Strategy

### 4.1 Handling 1.6M Rows Efficiently

**MySQL Reading**:
- Use `LIMIT/OFFSET` with `ORDER BY sand_id` for deterministic ordering
- Chunk size: 10,000 rows (balance memory vs network overhead)
- Connection pooling with 3 connections

**Neo4j Aura Writing**:
- Batch size: 1,000 records (reduced for cloud latency)
- Connection pool: 30 connections max
- Retry logic with exponential backoff
- Workers: 4 (reduced from 8 for cloud)

### 4.2 Performance Configuration

| Setting | Local Neo4j | Neo4j Aura |
|---------|-------------|------------|
| `etl.chunk_size` | 50,000 | 10,000 |
| `neo4j.batch_size` | 5,000 | 1,000 |
| `neo4j.max_connection_pool_size` | 100 | 30 |
| `etl.max_workers` | 8 | 4 |
| `neo4j.max_transaction_retry_time` | 30 | 60 |

### 4.3 Estimated Processing Time

Based on current performance metrics:

| Metric | Local Neo4j | Neo4j Aura (estimated) |
|--------|-------------|------------------------|
| Processing rate | ~2,000 rows/sec | ~500-1,000 rows/sec |
| Total time (1.6M rows) | ~15 minutes | ~30-60 minutes |
| Checkpoint interval | 5,000 rows | 5,000 rows |
| Resume granularity | ~2.5 seconds | ~5-10 seconds |

### 4.4 Checkpoint and Resume

The existing checkpoint system works with row offsets:

```python
# Checkpoint saved every 5,000 rows
checkpoint = {
    "last_processed_row": 150000,
    "timestamp": "2024-12-03T10:30:00Z",
    "source_type": "mysql",
    "source_table": "impact_learners_profile",
}
```

Resume query for MySQL:
```sql
SELECT * FROM impact_learners_profile
ORDER BY sand_id
LIMIT 10000 OFFSET 150000
```

---

## Phase 5: Production Deployment

### 5.1 Pre-Deployment Checklist

1. [ ] Create `.env` file with production credentials
2. [ ] Run dry-run validation
3. [ ] Test with 1,000 rows
4. [ ] Monitor Neo4j Aura capacity
5. [ ] Clear existing data if needed

### 5.2 Deployment Steps

```bash
# 1. Create .env file
cat > .env << 'EOF'
MYSQL_HOST=prod-impact-tracking-mysql.cylzdy8g0gui.eu-west-1.rds.amazonaws.com
MYSQL_PORT=3306
MYSQL_DATABASE=prod_impact_tracking
MYSQL_TABLE=impact_learners_profile
MYSQL_USER=kweli_RO
MYSQL_PASSWORD=haO5O2IkhH7VEkkKAJwvbA-Mpdk_eL

NEO4J_URI=neo4j+s://66c01309.databases.neo4j.io
NEO4J_USER=neo4j
NEO4J_PASSWORD=RDDhBOR0EBHXXIjtLY0gcPs82wahv1xiXLqWmrZdiwE
EOF

# 2. Validate connections
uv run python -m kweli.etl.cli run --source mysql --dry-run

# 3. Test with limited rows
uv run python -m kweli.etl.cli run --source mysql --max-rows 1000 --progress

# 4. Run full production ETL
uv run python -m kweli.etl.cli run --source mysql --progress

# 5. Resume if interrupted
uv run python -m kweli.etl.cli run --source mysql --resume --progress
```

### 5.3 Monitoring

Watch for:
- Processing rate (rows/second)
- Memory usage
- Network errors and retries
- Neo4j Aura metrics (queries, memory, storage)

### 5.4 Rollback Plan

If issues occur:
1. Stop ETL process (Ctrl+C saves checkpoint)
2. Clear Neo4j data: `MATCH (n) DETACH DELETE n`
3. Fix issue
4. Resume from checkpoint or restart

---

## Summary

### New Files (3)

| File | Lines | Purpose |
|------|-------|---------|
| `kweli/etl/transformers/mysql_reader.py` | ~220 | MySQL streaming reader |
| `kweli/etl/transformers/data_source.py` | ~100 | Factory pattern |
| `tests/unit/test_mysql_reader.py` | ~200 | Unit tests |

### Modified Files (7)

| File | Lines Changed | Purpose |
|------|---------------|---------|
| `config/settings.yaml` | +25 | MySQL + Aura config |
| `.env.example` | +15 | Environment variables |
| `kweli/etl/utils/config.py` | +40 | MySQLConfig model |
| `kweli/etl/pipeline/extractor.py` | ~80 (rewrite) | Source type selection |
| `kweli/etl/neo4j_ops/connection.py` | +50 | Aura + retry support |
| `kweli/etl/neo4j_ops/batch_ops.py` | +40 | Retry logic |
| `kweli/etl/cli.py` | +80 | CLI options |

### Total Changes

- **New code**: ~520 lines
- **Modified code**: ~330 lines
- **Test code**: ~200 lines
- **Config/docs**: ~40 lines
- **Total**: ~1,090 lines

---

## Security Notes

1. **Credentials**: Store in `.env` file (not committed to git)
2. **MySQL user**: Read-only access (`kweli_RO`)
3. **SSL/TLS**: Required for both MySQL RDS and Neo4j Aura
4. **Neo4j Aura**: Uses `neo4j+s://` scheme (encrypted)
5. **Password rotation**: Update `.env` file when credentials change

---

*Document generated: December 3, 2025*
