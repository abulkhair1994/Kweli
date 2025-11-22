"""
CSV reader with robust handling of multi-line quoted fields.

IMPROVED SOLUTION using Python's csv module:
- Python's csv.reader() properly handles quoted fields with embedded newlines
- RFC 4180 compliant parsing
- Filters NUL bytes (\x00) that cause parsing errors
- Converts to Polars DataFrame for performance
- No data loss from malformed chunks
"""

import csv
from collections.abc import Iterator
from io import TextIOWrapper
from pathlib import Path

import polars as pl
from structlog.types import FilteringBoundLogger

from utils.logger import get_logger


class NULFilterWrapper:
    """
    File wrapper that filters out NUL bytes (\x00) from text stream.

    Python's csv.reader doesn't accept NUL bytes, even with errors='ignore'.
    This wrapper removes them transparently.
    """

    def __init__(self, file_obj: TextIOWrapper) -> None:
        """Initialize wrapper."""
        self.file_obj = file_obj

    def __iter__(self):
        """Iterate over lines, filtering NUL bytes."""
        return self

    def __next__(self):
        """Get next line with NUL bytes filtered."""
        line = next(self.file_obj)
        return line.replace('\x00', '')

    def seek(self, *args, **kwargs):
        """Pass through seek to underlying file."""
        return self.file_obj.seek(*args, **kwargs)

    def tell(self):
        """Pass through tell to underlying file."""
        return self.file_obj.tell()

    def close(self):
        """Pass through close to underlying file."""
        return self.file_obj.close()

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, *args):
        """Context manager exit."""
        self.file_obj.__exit__(*args)


class CSVReader:
    """
    Robust CSV reader that handles multi-line quoted fields correctly.

    Uses Python's built-in csv module which properly handles:
    - Embedded newlines in quoted fields (e.g., bio fields)
    - Quoted fields with special characters
    - RFC 4180 compliant CSV parsing
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

        # Cache header and validate file
        self._header = self._read_header()
        self._column_count = len(self._header)
        self._total_rows_cache: int | None = None  # Cache for total rows count

    def _read_header(self) -> list[str]:
        """Read the header row using csv.reader."""
        with open(self.file_path, encoding='utf-8-sig', newline='', errors='ignore') as f:
            filtered = NULFilterWrapper(f)
            reader = csv.reader(filtered, quoting=csv.QUOTE_MINIMAL)
            return next(reader)

    def get_total_rows(self) -> int:
        """
        Get total number of rows (excluding header).

        Uses csv.reader to correctly count rows with multi-line fields.
        Cached after first call for performance.
        """
        if self._total_rows_cache is None:
            self.logger.debug("Counting total rows (first time, will cache)")
            with open(self.file_path, encoding='utf-8-sig', newline='', errors='ignore') as f:
                filtered = NULFilterWrapper(f)
                reader = csv.reader(filtered, quoting=csv.QUOTE_MINIMAL)
                next(reader)  # Skip header
                self._total_rows_cache = sum(1 for _ in reader)
            self.logger.debug("Total rows counted", total_rows=self._total_rows_cache)
        return self._total_rows_cache

    def get_columns(self) -> list[str]:
        """Get column names from header."""
        return self._header

    def read_chunks(
        self, start_row: int = 0, max_rows: int | None = None
    ) -> Iterator[pl.DataFrame]:
        """
        Read CSV in chunks using Python's csv.reader.

        This properly handles quoted fields with embedded newlines,
        ensuring 100% data movement without skipping chunks.

        Args:
            start_row: Starting row number (0-indexed, excludes header)
            max_rows: Maximum number of rows to read (None = all)

        Yields:
            Polars DataFrame chunks
        """
        self.logger.info(
            "Starting CSV read with Python csv.reader",
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

        current_row = 0
        chunk_num = 0
        rows_in_chunk = []

        # Open with NUL filter to handle NULL bytes in CSV
        with open(self.file_path, encoding='utf-8-sig', newline='', errors='ignore') as f:
            filtered = NULFilterWrapper(f)
            reader = csv.reader(filtered, quoting=csv.QUOTE_MINIMAL)
            header = next(reader)  # Read header

            # Skip rows before start_row
            for _ in range(start_row):
                next(reader)
                current_row += 1

            # Read data rows
            for row in reader:
                if current_row >= end_row:
                    break

                # Validate row has correct number of columns
                if len(row) != self._column_count:
                    self.logger.warning(
                        "Row has incorrect column count",
                        expected=self._column_count,
                        actual=len(row),
                        row_num=current_row + 1,
                    )
                    # Pad or truncate to match header
                    if len(row) < self._column_count:
                        row.extend([''] * (self._column_count - len(row)))
                    else:
                        row = row[:self._column_count]

                rows_in_chunk.append(row)

                # Yield chunk when full
                if len(rows_in_chunk) >= self.chunk_size:
                    chunk_num += 1
                    df = self._create_dataframe(header, rows_in_chunk)

                    self.logger.debug(
                        "Read chunk",
                        chunk_num=chunk_num,
                        rows=len(df),
                        current_row=current_row + 1,
                    )

                    yield df
                    rows_in_chunk = []

                current_row += 1

            # Yield remaining rows
            if rows_in_chunk:
                chunk_num += 1
                df = self._create_dataframe(header, rows_in_chunk)

                self.logger.debug(
                    "Read final chunk",
                    chunk_num=chunk_num,
                    rows=len(df),
                    current_row=current_row,
                )

                yield df

        self.logger.info(
            "CSV read complete",
            total_chunks=chunk_num,
            total_rows=current_row,
        )

    def _create_dataframe(self, header: list[str], rows: list[list[str]]) -> pl.DataFrame:
        """
        Create Polars DataFrame from header and rows.

        Args:
            header: Column names
            rows: List of row data

        Returns:
            Polars DataFrame with all columns as strings
        """
        # Create dictionary with column names as keys
        data = {col: [row[i] if i < len(row) else '' for row in rows]
                for i, col in enumerate(header)}

        # Create DataFrame with all string columns
        return pl.DataFrame(data, schema=dict.fromkeys(header, pl.Utf8))

    def read_all(self) -> pl.DataFrame:
        """Read entire CSV."""
        with open(self.file_path, encoding='utf-8-sig', newline='', errors='ignore') as f:
            filtered = NULFilterWrapper(f)
            reader = csv.reader(filtered, quoting=csv.QUOTE_MINIMAL)
            header = next(reader)
            rows = list(reader)
            return self._create_dataframe(header, rows)

    def read_sample(self, n_rows: int = 100) -> pl.DataFrame:
        """Read sample of rows."""
        with open(self.file_path, encoding='utf-8-sig', newline='', errors='ignore') as f:
            filtered = NULFilterWrapper(f)
            reader = csv.reader(filtered, quoting=csv.QUOTE_MINIMAL)
            header = next(reader)
            rows = [next(reader) for _ in range(min(n_rows, self.get_total_rows()))]
            return self._create_dataframe(header, rows)


__all__ = ["CSVReader"]
