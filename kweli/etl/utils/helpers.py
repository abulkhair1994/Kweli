"""Helper functions for the ETL pipeline."""

import hashlib
import re
from datetime import date, datetime


def normalize_string(text: str | None) -> str | None:
    """
    Normalize a string by stripping whitespace and converting to lowercase.

    Args:
        text: Input string

    Returns:
        Normalized string or None if input is None/empty
    """
    if not text or text.strip().lower() in ("n/a", "none", "null", ""):
        return None

    return text.strip()


def normalize_skill_name(skill: str) -> str:
    """
    Normalize skill name for consistent identification.

    Args:
        skill: Raw skill name

    Returns:
        Normalized skill name (lowercase, underscores)

    Examples:
        "Data Analysis" -> "data_analysis"
        "Python 3.x" -> "python_3x"
    """
    # Remove special characters and convert to lowercase
    normalized = re.sub(r"[^\w\s-]", "", skill.lower())
    # Replace spaces and hyphens with underscores
    normalized = re.sub(r"[\s-]+", "_", normalized)
    # Remove multiple underscores
    normalized = re.sub(r"_+", "_", normalized)
    return normalized.strip("_")


def create_city_id(city_name: str, country_code: str) -> str:
    """
    Create unique city identifier.

    Args:
        city_name: City name
        country_code: ISO country code

    Returns:
        Unique city ID (e.g., "EG-CAI")

    Examples:
        "Cairo", "EG" -> "EG-CAI"
        "Alexandria", "EG" -> "EG-ALE"
    """
    if not city_name or not country_code:
        return ""

    # Take first 3 letters of city name (uppercase)
    city_abbr = normalize_string(city_name)
    if not city_abbr:
        return ""

    city_abbr = city_abbr[:3].upper()
    return f"{country_code.upper()}-{city_abbr}"


def parse_date(date_str: str | None, invalid_markers: list[str] | None = None) -> date | None:
    """
    Parse date string, handling invalid markers.

    Args:
        date_str: Date string to parse
        invalid_markers: List of invalid date strings to treat as None

    Returns:
        Parsed date or None

    Examples:
        "2024-01-15" -> date(2024, 1, 15)
        "1970-01-01" -> None (invalid marker)
        "9999-12-31" -> None (invalid marker)
    """
    if not date_str:
        return None

    # Check invalid markers
    invalid_markers = invalid_markers or ["1970-01-01", "9999-12-31"]
    if date_str in invalid_markers:
        return None

    # Try parsing
    try:
        # Try ISO format first
        return datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        try:
            # Try datetime format
            return datetime.fromisoformat(date_str).date()
        except ValueError:
            return None


def parse_numeric(
    value: str | int | float | None, missing_markers: list[str | int] | None = None
) -> float | None:
    """
    Parse numeric value, handling missing value markers.

    Args:
        value: Value to parse
        missing_markers: List of values to treat as None (e.g., -99, "-99")

    Returns:
        Parsed float or None

    Examples:
        "95.5" -> 95.5
        -99 -> None (missing marker)
        "-99" -> None (missing marker)
    """
    if value is None:
        return None

    # Check missing markers
    missing_markers = missing_markers or [-99, "-99"]
    if value in missing_markers:
        return None

    # Try parsing
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


def parse_boolean(value: str | int | bool | None) -> bool | None:
    """
    Parse boolean value from various formats.

    Args:
        value: Value to parse

    Returns:
        Parsed boolean or None

    Examples:
        "1" -> True
        "0" -> False
        1 -> True
        "true" -> True
    """
    if value is None:
        return None

    if isinstance(value, bool):
        return value

    if isinstance(value, int):
        return value != 0

    if isinstance(value, str):
        value_lower = value.lower().strip()
        if value_lower in ("1", "true", "yes", "y"):
            return True
        if value_lower in ("0", "false", "no", "n"):
            return False

    return None


def generate_id(text: str) -> str:
    """
    Generate a unique ID from text using SHA-256.

    Args:
        text: Input text

    Returns:
        Hexadecimal hash (first 16 characters)

    Examples:
        "Vodafone Egypt" -> "3a7c8b9d1e2f4a5b"
    """
    return hashlib.sha256(text.encode()).hexdigest()[:16]


__all__ = [
    "normalize_string",
    "normalize_skill_name",
    "create_city_id",
    "parse_date",
    "parse_numeric",
    "parse_boolean",
    "generate_id",
]
