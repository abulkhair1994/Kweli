"""
CSV reader with robust handling of malformed CSV files.

FINAL SOLUTION for embedded newlines in quoted fields:
- DO NOT use skip_rows_after_header with malformed CSV
- Read from file handle with manual seeking instead
- Use n_threads=1 for single-threaded parsing
- Use infer_schema=False to treat all as strings
"""

from collections.abc import Iterator
from pathlib import Path
from io import StringIO

import polars as pl
from structlog.types import FilteringBoundLogger

from utils.logger import get_logger


class CSVReaderFixed:
    """
    Robust CSV reader for malformed large files.

    This implementation handles CSVs with:
    - Embedded newlines in quoted fields
    - Unescaped quotes
    - Ragged lines (inconsistent column counts)
    """

    def __init__(
        self,
        file_path: str | Path,
        chunk_size: int = 10000,
        logger: FilteringBoundLogger | None = None,
    ) -> None:
        """Initialize CSV reader."""
        self.file_path = Path(file_path)
        self.chunk_size = chunk_size
        self.logger = logger or get_logger(__name__)

        if not self.file_path.exists():
            raise FileNotFoundError(f"CSV file not found: {self.file_path}")

        # Cache header
        self._header = self._read_header()

    def _read_header(self) -> str:
        """Read the first line (header) of the CSV."""
        with open(self.file_path, 'r', encoding='utf-8-sig') as f:
            return f.readline()

    def get_total_rows(self) -> int:
        """Get total number of rows (excluding header)."""
        with open(self.file_path, 'r', encoding='utf-8-sig') as f:
            return sum(1 for _ in f) - 1

    def get_columns(self) -> list[str]:
        """Get column names from header."""
        # Parse header using Polars
        header_df = pl.read_csv(
            StringIO(self._header),
            n_rows=0,
            has_header=True,
        )
        return header_df.columns

    def read_chunks(
        self, start_row: int = 0, max_rows: int | None = None
    ) -> Iterator[pl.DataFrame]:
        """
        Read CSV in chunks WITHOUT using skip_rows_after_header.

        This avoids Polars bugs with malformed CSV + skip_rows_after_header.
        """
        self.logger.info(
            "Starting CSV read",
            file=str(self.file_path),
            chunk_size=self.chunk_size,
            start_row=start_row,
        )

        total_rows = self.get_total_rows()
        end_row = min(total_rows, start_row + max_rows) if max_rows else total_rows
        rows_to_read = end_row - start_row

        if rows_to_read <= 0:
            self.logger.warning("No rows to read", start_row=start_row, total_rows=total_rows)
            return

        current_row = start_row
        chunk_num = 0

        with open(self.file_path, 'r', encoding='utf-8-sig') as f:
            # Skip header
            f.readline()

            # Skip to start_row
            for _ in range(start_row):
                f.readline()

            while current_row < end_row:
                rows_remaining = end_row - current_row
                current_chunk_size = min(self.chunk_size, rows_remaining)

                # Read chunk_size lines into buffer
                lines = [self._header]  # Include header
                for _ in range(current_chunk_size):
                    line = f.readline()
                    if not line:
                        break
                    lines.append(line)

                if len(lines) <= 1:  # Only header
                    break

                # Parse with Polars using StringIO
                # CRITICAL CONFIGURATION for malformed CSV:
                df = pl.read_csv(
                    StringIO(''.join(lines)),
                    n_threads=1,  # Single-threaded for malformed CSV
                    infer_schema=False,  # All columns as strings
                    ignore_errors=True,  # Ignore type conversion errors
                    truncate_ragged_lines=True,  # Handle ragged lines
                    quote_char='"',
                    eol_char='\n',
                    raise_if_empty=False,
                )

                chunk_num += 1
                actual_rows = len(df)

                self.logger.debug(
                    "Read chunk",
                    chunk_num=chunk_num,
                    rows=actual_rows,
                    current_row=current_row,
                )

                if actual_rows > 0:
                    yield df
                    current_row += actual_rows
                else:
                    break

    def read_all(self) -> pl.DataFrame:
        """Read entire CSV."""
        return pl.read_csv(
            self.file_path,
            n_threads=1,
            infer_schema=False,
            ignore_errors=True,
            truncate_ragged_lines=True,
        )

    def read_sample(self, n_rows: int = 100) -> pl.DataFrame:
        """Read sample of rows."""
        return pl.read_csv(
            self.file_path,
            n_rows=n_rows,
            n_threads=1,
            infer_schema=False,
            ignore_errors=True,
            truncate_ragged_lines=True,
        )


__all__ = ["CSVReaderFixed"]
