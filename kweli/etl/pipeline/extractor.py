"""
ETL Extractor.

Extracts data from CSV file in chunks.
"""

from collections.abc import Iterator
from pathlib import Path

import polars as pl
from structlog.types import FilteringBoundLogger

from kweli.etl.transformers.polars_csv_reader import StreamingCSVReader
from kweli.etl.utils.logger import get_logger


class Extractor:
    """Extract data from CSV file."""

    def __init__(
        self,
        csv_path: Path | str,
        chunk_size: int = 10000,
        logger: FilteringBoundLogger | None = None,
    ) -> None:
        """
        Initialize extractor.

        Args:
            csv_path: Path to CSV file
            chunk_size: Rows per chunk
            logger: Optional logger instance
        """
        self.csv_path = Path(csv_path)
        self.chunk_size = chunk_size
        self.logger = logger or get_logger(__name__)
        self.reader = StreamingCSVReader(
            csv_path,
            chunk_size,
            use_streaming=True,  # Try Polars first, fallback to csv.reader
            logger=logger,
        )

    def get_total_rows(self) -> int:
        """Get total number of rows."""
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
            csv_path=str(self.csv_path),
            start_row=start_row,
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
