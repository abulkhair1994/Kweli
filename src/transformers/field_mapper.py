"""
Field mapper for CSV to Pydantic models.

Maps CSV columns to LearnerNode and related entities.
"""

from typing import Any

from structlog.types import FilteringBoundLogger

from models.enums import Gender
from utils.helpers import normalize_string, parse_boolean
from utils.logger import get_logger


class FieldMapper:
    """Map CSV row to Pydantic models."""

    def __init__(self, logger: FilteringBoundLogger | None = None) -> None:
        """Initialize field mapper."""
        self.logger = logger or get_logger(__name__)

    def map_csv_row_to_dict(self, row: dict[str, Any]) -> dict[str, Any]:
        """
        Map CSV row dictionary to LearnerNode-compatible dictionary.

        Args:
            row: CSV row as dictionary

        Returns:
            Dictionary suitable for LearnerNode(**dict)
        """
        return {
            # Primary identifiers
            "sand_id": normalize_string(row.get("sand_id")),
            "hashed_email": normalize_string(row.get("hashed_email")),
            "full_name": normalize_string(row.get("full_name")),
            # Profile
            "profile_photo_url": normalize_string(row.get("profile_photo_url")),
            "bio": normalize_string(row.get("bio")),
            "gender": self._map_gender(row.get("gender")),
            # Education
            "education_level": normalize_string(row.get("education_level_of_study")),
            "education_field": normalize_string(row.get("education_field_of_study")),
            # Geographic (will be converted to codes by transformers)
            "country_of_residence_code": None,  # Set by geo normalizer
            "country_of_origin_code": None,  # Set by geo normalizer
            "city_of_residence_id": None,  # Set by geo normalizer
            # Status (will be derived by state deriver)
            "current_learning_state": None,  # Set by state deriver
            "current_professional_status": None,  # Set by state deriver
            "is_placed": parse_boolean(row.get("is_placed")) or False,
            "is_featured": parse_boolean(row.get("is_featured")) or False,
            # Socio-economic
            "is_rural": self._map_is_rural(row.get("is_rural")),
            "description_of_living_location": normalize_string(
                row.get("description_of_living_location")
            ),
            "has_disability": parse_boolean(row.get("has_disability")),
            "type_of_disability": normalize_string(row.get("type_of_disability")),
            "is_from_low_income_household": parse_boolean(
                row.get("is_from_low_income_household")
            ),
            # Metadata
            "snapshot_id": row.get("snapshot_id"),
        }

    def _map_gender(self, value: str | None) -> Gender | None:
        """Map gender string to Gender enum."""
        if not value:
            return None

        value_lower = value.lower().strip()

        if value_lower == "male":
            return Gender.MALE
        elif value_lower == "female":
            return Gender.FEMALE
        elif value_lower in ("other/prefer not to say", "prefer not to say", "other"):
            return Gender.OTHER
        else:
            return None

    def _map_is_rural(self, value: Any) -> bool | None:
        """Map is_rural field."""
        if value is None or value == "":
            return None

        # Handle boolean
        if isinstance(value, bool):
            return value

        # Handle int (0/1)
        if isinstance(value, int):
            return value != 0

        # Handle string
        if isinstance(value, str):
            value_lower = value.lower().strip()
            if value_lower in ("1", "true", "yes", "rural"):
                return True
            elif value_lower in ("0", "false", "no", "urban"):
                return False

        return None

    def extract_raw_fields(self, row: dict[str, Any]) -> dict[str, Any]:
        """
        Extract raw fields that need further processing.

        Args:
            row: CSV row dictionary

        Returns:
            Dictionary with raw fields for transformers
        """
        return {
            # Geographic raw data
            "country_of_residence": row.get("country_of_residence"),
            "country_of_origin": row.get("country_of_origin"),
            "city_of_residence": row.get("city_of_residence"),
            "country_of_residence_latitude": row.get("country_of_residence_latitude"),
            "country_of_residence_longitude": row.get("country_of_residence_longitude"),
            "city_of_residence_latitude": row.get("city_of_residence_latitude"),
            "city_of_residence_longitude": row.get("city_of_residence_longitude"),
            # State derivation flags
            "is_active_learner": row.get("is_active_learner"),
            "is_graduate_learner": row.get("is_graduate_learner"),
            "is_a_dropped_out": row.get("is_a_dropped_out"),
            "is_running_a_venture": row.get("is_running_a_venture"),
            "is_a_freelancer": row.get("is_a_freelancer"),
            "is_wage_employed": row.get("is_wage_employed"),
            # JSON fields
            "skills_list": row.get("skills_list"),
            "learning_details": row.get("learning_details"),
            "placement_details": row.get("placement_details"),
            "employment_details": row.get("employment_details"),
            "education_details": row.get("education_details"),
        }


__all__ = ["FieldMapper"]
