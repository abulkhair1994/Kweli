"""
Date converter for parsing and validating dates.

Handles edge cases like -99, 1970-01-01, 9999-12-31.
"""

from datetime import date, datetime

from structlog.types import FilteringBoundLogger

from utils.helpers import parse_date
from utils.logger import get_logger


class DateConverter:
    """Convert and validate date values."""

    def __init__(
        self,
        invalid_markers: list[str] | None = None,
        min_year: int = 1970,
        max_year: int = 2030,
        logger: FilteringBoundLogger | None = None,
    ) -> None:
        """
        Initialize date converter.

        Args:
            invalid_markers: Date strings to treat as None
            min_year: Minimum valid year
            max_year: Maximum valid year
            logger: Optional logger instance
        """
        self.logger = logger or get_logger(__name__)
        self.invalid_markers = invalid_markers or ["1970-01-01", "9999-12-31"]
        self.min_year = min_year
        self.max_year = max_year

    def convert_date(self, date_str: str | None) -> date | None:
        """
        Convert date string to date object.

        Args:
            date_str: Date string to parse

        Returns:
            Parsed date or None

        Examples:
            "2024-01-15" -> date(2024, 1, 15)
            "1970-01-01" -> None (invalid marker)
            "invalid" -> None (with warning)
        """
        if not date_str:
            return None

        # Check invalid markers
        if date_str in self.invalid_markers:
            return None

        # Parse date
        parsed = parse_date(date_str, self.invalid_markers)
        if not parsed:
            return None

        # Validate year range
        if not (self.min_year <= parsed.year <= self.max_year):
            self.logger.warning(
                "Date outside valid range",
                date=date_str,
                year=parsed.year,
                min_year=self.min_year,
                max_year=self.max_year,
            )
            return None

        return parsed

    def convert_datetime(self, datetime_str: str | None) -> datetime | None:
        """
        Convert datetime string to datetime object.

        Args:
            datetime_str: Datetime string to parse

        Returns:
            Parsed datetime or None
        """
        if not datetime_str:
            return None

        try:
            return datetime.fromisoformat(datetime_str)
        except (ValueError, TypeError) as e:
            self.logger.warning("Failed to parse datetime", value=datetime_str, error=str(e))
            return None


__all__ = ["DateConverter"]
