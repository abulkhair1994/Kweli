"""
Parquet file reader for ETL pipeline.

Reads Parquet files in chunks using Polars for efficient memory usage.
This is the recommended data source for production ETL runs as it
eliminates MySQL connection timeout issues.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import TYPE_CHECKING

import polars as pl

from kweli.etl.utils.logger import get_logger

if TYPE_CHECKING:
    from structlog.types import FilteringBoundLogger


class ParquetReader:
    """
    Read Parquet files in chunks for ETL processing.

    Implements the DataSourceReader protocol for seamless integration
    with the existing ETL pipeline.
    """

    def __init__(
        self,
        file_path: Path | str,
        chunk_size: int = 10000,
        logger: FilteringBoundLogger | None = None,
    ) -> None:
        """
        Initialize the Parquet reader.

        Args:
            file_path: Path to Parquet file
            chunk_size: Number of rows per chunk
            logger: Optional structured logger
        """
        self.file_path = Path(file_path)
        self.chunk_size = chunk_size
        self.logger = logger or get_logger(__name__)

        if not self.file_path.exists():
            raise FileNotFoundError(f"Parquet file not found: {self.file_path}")

        # Read schema to get columns
        self._schema = pl.read_parquet_schema(self.file_path)
        self._columns = list(self._schema.keys())

        # Get total rows (lazy scan for efficiency)
        self._total_rows = pl.scan_parquet(self.file_path).select(pl.len()).collect().item()

        self.logger.info(
            "Parquet reader initialized",
            file=str(self.file_path),
            total_rows=self._total_rows,
            columns=len(self._columns),
            chunk_size=chunk_size,
        )

    def get_columns(self) -> list[str]:
        """Get column names from the Parquet file."""
        return self._columns

    def get_total_rows(self) -> int:
        """Get total number of rows in the Parquet file."""
        return self._total_rows

    def read_chunks(
        self,
        start_row: int = 0,
        max_rows: int | None = None,
    ) -> Iterator[pl.DataFrame]:
        """
        Read Parquet file in chunks.

        Args:
            start_row: Starting row offset (for resume)
            max_rows: Maximum rows to read (None for all)

        Yields:
            DataFrame chunks
        """
        self.logger.info(
            "Starting Parquet read",
            file=str(self.file_path),
            start_row=start_row,
            max_rows=max_rows,
            chunk_size=self.chunk_size,
        )

        # Calculate actual rows to read
        rows_to_read = self._total_rows - start_row
        if max_rows is not None:
            rows_to_read = min(rows_to_read, max_rows)

        rows_yielded = 0
        current_offset = start_row

        while rows_yielded < rows_to_read:
            # Calculate chunk size for this iteration
            remaining = rows_to_read - rows_yielded
            current_chunk_size = min(self.chunk_size, remaining)

            # Read chunk using lazy scan with slice
            chunk = (
                pl.scan_parquet(self.file_path)
                .slice(current_offset, current_chunk_size)
                .collect()
            )

            if chunk.is_empty():
                break

            rows_yielded += len(chunk)
            current_offset += len(chunk)

            yield chunk

        self.logger.info(
            "Parquet read complete",
            rows_read=rows_yielded,
            chunks_yielded=rows_yielded // self.chunk_size + (1 if rows_yielded % self.chunk_size else 0),
        )

    def read_sample(self, n_rows: int = 100) -> pl.DataFrame:
        """
        Read a sample of rows for validation.

        Args:
            n_rows: Number of rows to read

        Returns:
            Sample DataFrame
        """
        return pl.scan_parquet(self.file_path).head(n_rows).collect()

    def close(self) -> None:
        """Close the reader (no-op for Parquet, included for protocol compatibility)."""
        self.logger.debug("Parquet reader closed (no-op)")


__all__ = ["ParquetReader"]
