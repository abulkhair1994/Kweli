"""
CSV reader with chunked processing for large files.

Uses Polars for efficient memory usage when processing 2.5GB+ CSV files.
"""

from collections.abc import Iterator
from pathlib import Path

import polars as pl
from structlog.types import FilteringBoundLogger

from utils.logger import get_logger


class CSVReader:
    """
    Chunked CSV reader for large files.

    Uses Polars for memory-efficient processing.
    """

    def __init__(
        self,
        file_path: str | Path,
        chunk_size: int = 10000,
        logger: FilteringBoundLogger | None = None,
    ) -> None:
        """
        Initialize CSV reader.

        Args:
            file_path: Path to CSV file
            chunk_size: Number of rows per chunk
            logger: Optional logger instance
        """
        self.file_path = Path(file_path)
        self.chunk_size = chunk_size
        self.logger = logger or get_logger(__name__)

        if not self.file_path.exists():
            raise FileNotFoundError(f"CSV file not found: {self.file_path}")

    def get_total_rows(self) -> int:
        """
        Get total number of rows in CSV (excluding header).

        Returns:
            Total row count
        """
        # Count lines (fast for line counting)
        with open(self.file_path) as f:
            # Count all lines and subtract 1 for header
            return sum(1 for _ in f) - 1

    def get_columns(self) -> list[str]:
        """
        Get column names from CSV.

        Returns:
            List of column names
        """
        # Read just the first row to get columns
        df = pl.read_csv(
            self.file_path,
            n_rows=1,
            n_threads=1,  # Use single-threaded for malformed CSV
            ignore_errors=True,
            truncate_ragged_lines=True,
        )
        return df.columns

    def read_chunks(
        self, start_row: int = 0, max_rows: int | None = None
    ) -> Iterator[pl.DataFrame]:
        """
        Read CSV in chunks.

        Args:
            start_row: Row number to start from (0-indexed, excluding header)
            max_rows: Maximum number of rows to read (None = all)

        Yields:
            DataFrame chunks
        """
        self.logger.info(
            "Starting CSV read",
            file=str(self.file_path),
            chunk_size=self.chunk_size,
            start_row=start_row,
        )

        # Calculate rows to read
        total_rows = self.get_total_rows()
        end_row = min(total_rows, start_row + max_rows) if max_rows else total_rows
        rows_to_read = end_row - start_row

        if rows_to_read <= 0:
            self.logger.warning("No rows to read", start_row=start_row, total_rows=total_rows)
            return

        # Read in chunks
        current_row = start_row
        chunk_num = 0

        while current_row < end_row:
            # Calculate chunk boundaries
            rows_remaining = end_row - current_row
            current_chunk_size = min(self.chunk_size, rows_remaining)

            # Read chunk with Polars
            # CRITICAL: Use n_threads=1 + infer_schema=False for malformed CSVs
            # - Polars parallel parser fails on unescaped newlines in quoted fields
            # - Single-threaded parser is more tolerant of RFC 4180 violations
            # - Setting infer_schema=False treats ALL columns as strings (no parsing)
            # - This bypasses the "could not parse as dtype str" error
            # - ignore_errors only handles TYPE conversion errors, not parsing errors
            # - truncate_ragged_lines handles rows with inconsistent column counts
            df = pl.read_csv(
                self.file_path,
                skip_rows_after_header=current_row,
                n_rows=current_chunk_size,
                n_threads=1,  # REQUIRED for malformed CSV with embedded newlines
                infer_schema=False,  # CRITICAL: Treat all columns as strings
                ignore_errors=True,  # Ignore type conversion errors
                truncate_ragged_lines=True,  # Handle ragged lines
                quote_char='"',  # Standard CSV quote character
                eol_char='\n',  # Line terminator (handles \r\n automatically)
                raise_if_empty=False,
                low_memory=False,  # Better performance for large chunks
            )

            chunk_num += 1
            self.logger.debug(
                "Read chunk",
                chunk_num=chunk_num,
                rows=len(df),
                current_row=current_row,
            )

            yield df
            current_row += len(df)

    def read_all(self) -> pl.DataFrame:
        """
        Read entire CSV into memory.

        Returns:
            Complete DataFrame
        """
        return pl.read_csv(
            self.file_path,
            n_threads=1,  # Use single-threaded for malformed CSV
            ignore_errors=True,
            truncate_ragged_lines=True,
            infer_schema_length=10000,
        )

    def read_sample(self, n_rows: int = 100) -> pl.DataFrame:
        """
        Read a sample of rows from the CSV.

        Args:
            n_rows: Number of rows to read

        Returns:
            Sample DataFrame
        """
        return pl.read_csv(
            self.file_path,
            n_rows=n_rows,
            n_threads=1,  # Use single-threaded for malformed CSV
            ignore_errors=True,
            truncate_ragged_lines=True,
        )


__all__ = ["CSVReader"]
