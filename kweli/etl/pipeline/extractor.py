"""
ETL Extractor.

Extracts data from CSV, MySQL, or Parquet data sources in chunks.
Supports local CSV/Parquet files and remote MySQL RDS databases.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import TYPE_CHECKING, Any

import polars as pl

from kweli.etl.transformers.data_source import DataSourceFactory, DataSourceType
from kweli.etl.utils.logger import get_logger

if TYPE_CHECKING:
    from structlog.types import FilteringBoundLogger


class Extractor:
    """
    Extract data from CSV, MySQL, or Parquet data sources.

    This class wraps the data source factory to provide a unified interface
    for the ETL pipeline, regardless of the underlying data source.

    Attributes:
        source_type: Type of data source (csv, mysql, or parquet)
        chunk_size: Number of rows per chunk
    """

    def __init__(
        self,
        source_type: str = "csv",
        csv_path: Path | str | None = None,
        mysql_config: dict[str, Any] | None = None,
        parquet_path: Path | str | None = None,
        chunk_size: int = 10000,
        logger: FilteringBoundLogger | None = None,
    ) -> None:
        """
        Initialize the extractor.

        Args:
            source_type: Type of data source ("csv", "mysql", or "parquet")
            csv_path: Path to CSV file (required if source_type is "csv")
            mysql_config: MySQL configuration dict (required if source_type is "mysql")
            parquet_path: Path to Parquet file (required if source_type is "parquet")
            chunk_size: Number of rows per chunk
            logger: Optional structured logger

        Raises:
            ValueError: If required configuration is missing for source type
        """
        self.source_type = source_type
        self.chunk_size = chunk_size
        self.logger = logger or get_logger(__name__)

        # Build configuration for factory
        config: dict[str, Any] = {"chunk_size": chunk_size}

        if source_type == "csv":
            if csv_path is None:
                raise ValueError("csv_path is required for CSV source")
            self.csv_path = Path(csv_path)
            config["csv_path"] = self.csv_path
        elif source_type == "mysql":
            if mysql_config is None:
                raise ValueError("mysql_config is required for MySQL source")
            config["mysql"] = mysql_config
            self.csv_path = None
        elif source_type == "parquet":
            if parquet_path is None:
                raise ValueError("parquet_path is required for Parquet source")
            self.parquet_path = Path(parquet_path)
            config["parquet_path"] = self.parquet_path
            self.csv_path = None
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

    @classmethod
    def from_csv(
        cls,
        csv_path: Path | str,
        chunk_size: int = 10000,
        logger: FilteringBoundLogger | None = None,
    ) -> Extractor:
        """
        Create an extractor for CSV files.

        Args:
            csv_path: Path to CSV file
            chunk_size: Number of rows per chunk
            logger: Optional structured logger

        Returns:
            Extractor instance configured for CSV
        """
        return cls(
            source_type="csv",
            csv_path=csv_path,
            chunk_size=chunk_size,
            logger=logger,
        )

    @classmethod
    def from_mysql(
        cls,
        mysql_config: dict[str, Any],
        chunk_size: int = 10000,
        logger: FilteringBoundLogger | None = None,
    ) -> Extractor:
        """
        Create an extractor for MySQL database.

        Args:
            mysql_config: MySQL configuration dictionary with keys:
                - host: MySQL server hostname
                - database: Database name
                - table: Table name (optional, defaults to impact_learners_profile)
                - user: MySQL username
                - password: MySQL password
                - port: MySQL port (optional, defaults to 3306)
                - use_ssl: Whether to use SSL (optional, defaults to True)
            chunk_size: Number of rows per chunk
            logger: Optional structured logger

        Returns:
            Extractor instance configured for MySQL
        """
        return cls(
            source_type="mysql",
            mysql_config=mysql_config,
            chunk_size=chunk_size,
            logger=logger,
        )

    @classmethod
    def from_parquet(
        cls,
        parquet_path: Path | str,
        chunk_size: int = 10000,
        logger: FilteringBoundLogger | None = None,
    ) -> Extractor:
        """
        Create an extractor for Parquet files.

        Args:
            parquet_path: Path to Parquet file
            chunk_size: Number of rows per chunk
            logger: Optional structured logger

        Returns:
            Extractor instance configured for Parquet
        """
        return cls(
            source_type="parquet",
            parquet_path=parquet_path,
            chunk_size=chunk_size,
            logger=logger,
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
        """
        Extract data in chunks.

        Args:
            start_row: Starting row (for resume)
            max_rows: Maximum rows to extract

        Yields:
            DataFrame chunks
        """
        self.logger.info(
            "Starting data extraction",
            source_type=self.source_type,
            start_row=start_row,
            max_rows=max_rows,
            chunk_size=self.chunk_size,
        )

        yield from self.reader.read_chunks(start_row, max_rows)

    def extract_sample(self, n_rows: int = 100) -> pl.DataFrame:
        """
        Extract sample for testing.

        Args:
            n_rows: Number of rows

        Returns:
            Sample DataFrame
        """
        return self.reader.read_sample(n_rows)


__all__ = ["Extractor"]
