"""
Data source abstraction for ETL pipeline.

Provides a factory pattern to abstract data source selection,
allowing seamless switching between CSV, MySQL, and Parquet data sources.
"""

from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol

import polars as pl

from kweli.etl.utils.logger import get_logger

if TYPE_CHECKING:
    from collections.abc import Iterator

    from structlog.types import FilteringBoundLogger


class DataSourceType(Enum):
    """Supported data source types."""

    CSV = "csv"
    MYSQL = "mysql"
    PARQUET = "parquet"


class DataSourceReader(Protocol):
    """
    Protocol defining the interface for data source readers.

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
        """
        Create a data source reader based on type.

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
            try:
                source_type = DataSourceType(source_type.lower())
            except ValueError as e:
                raise ValueError(f"Unsupported data source type: {source_type}") from e

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

            required_fields = ["host", "database", "user", "password"]
            missing = [f for f in required_fields if not mysql_config.get(f)]
            if missing:
                raise ValueError(f"Missing required MySQL config: {missing}")

            read_mode = mysql_config.get("read_mode", "streaming")
            logger.info(
                "Creating MySQL reader",
                host=mysql_config["host"],
                database=mysql_config["database"],
                table=mysql_config.get("table", "impact_learners_profile"),
                read_mode=read_mode,
            )

            return MySQLStreamReader(
                host=mysql_config["host"],
                database=mysql_config["database"],
                table=mysql_config.get("table", "impact_learners_profile"),
                user=mysql_config["user"],
                password=mysql_config["password"],
                port=mysql_config.get("port", 3306),
                chunk_size=chunk_size,
                use_ssl=mysql_config.get("use_ssl", True),
                connection_timeout=mysql_config.get("connection_timeout", 120),
                read_timeout=mysql_config.get("read_timeout", 3600),  # 1 hour for streaming
                read_mode=read_mode,
                logger=logger,
            )

        elif source_type == DataSourceType.PARQUET:
            from kweli.etl.transformers.parquet_reader import ParquetReader

            parquet_path = config.get("parquet_path")
            chunk_size = config.get("chunk_size", 10000)

            if not parquet_path:
                raise ValueError("parquet_path is required for Parquet source")

            logger.info("Creating Parquet reader", path=str(parquet_path))
            return ParquetReader(
                file_path=Path(parquet_path),
                chunk_size=chunk_size,
                logger=logger,
            )

        else:
            raise ValueError(f"Unsupported data source type: {source_type}")


__all__ = ["DataSourceType", "DataSourceReader", "DataSourceFactory"]
