"""
JSON field parsers for complex CSV columns.

Parses JSON arrays from fields like learning_details, placement_details, etc.
"""

import json
from typing import Any

from pydantic import ValidationError
from structlog.types import FilteringBoundLogger

from kweli.etl.models.parsers import (
    EmploymentDetailsEntry,
    LearningDetailsEntry,
    PlacementDetailsVenture,
    PlacementDetailsWageEmployment,
)
from kweli.etl.utils.logger import get_logger


class JSONParser:
    """Parse JSON fields from CSV data."""

    def __init__(self, logger: FilteringBoundLogger | None = None) -> None:
        """Initialize JSON parser."""
        self.logger = logger or get_logger(__name__)

    def parse_json_field(self, value: str | None) -> list[dict[str, Any]] | None:
        """
        Parse JSON field, handling empty arrays, invalid JSON, and double-encoded JSON.

        Args:
            value: JSON string from CSV

        Returns:
            Parsed list of dictionaries or None

        Examples:
            '[]' -> None (empty array)
            '[{"key": "value"}]' -> [{"key": "value"}]
            '"[]"' -> None (double-encoded empty array)
            '"[{\\"key\\": \\"value\\"}]"' -> [{"key": "value"}] (double-encoded)
            'invalid' -> None (with warning)
        """
        if not value or value == "[]":
            return None

        try:
            parsed = json.loads(value)

            # Handle double-encoded JSON (string containing JSON)
            if isinstance(parsed, str):
                # Check if it's an empty array string
                if parsed == "[]":
                    return None
                # Try parsing again
                try:
                    parsed = json.loads(parsed)
                except json.JSONDecodeError:
                    # If second parse fails, it's not valid JSON
                    self.logger.warning("Failed to parse double-encoded JSON", value=value[:100])
                    return None

            if not parsed or not isinstance(parsed, list):
                return None
            return parsed
        except json.JSONDecodeError as e:
            self.logger.warning("Failed to parse JSON", value=value[:100], error=str(e))
            return None

    def parse_learning_details(self, value: str | None) -> list[LearningDetailsEntry]:
        """
        Parse learning_details JSON array.

        Args:
            value: JSON string

        Returns:
            List of parsed LearningDetailsEntry objects
        """
        parsed = self.parse_json_field(value)
        if not parsed:
            return []

        entries: list[LearningDetailsEntry] = []
        for item in parsed:
            try:
                entry = LearningDetailsEntry(**item)
                entries.append(entry)
            except ValidationError as e:
                self.logger.warning(
                    "Failed to validate learning details entry",
                    item=item,
                    error=str(e),
                )

        return entries

    def parse_placement_details(
        self,
        value: str | None,
        is_venture: bool = False,
    ) -> PlacementDetailsWageEmployment | PlacementDetailsVenture | None:
        """
        Parse placement_details JSON.

        Handles two different schemas:
        - Wage/Freelance: employment_type, job_start_date, organisation_name, etc.
        - Venture: business_name, jobs_created_to_date, capital_secured_todate, etc.

        Args:
            value: JSON string
            is_venture: If True, parse as venture schema

        Returns:
            Parsed placement details or None
        """
        parsed = self.parse_json_field(value)
        if not parsed or len(parsed) == 0:
            return None

        # Take first entry
        item = parsed[0]

        try:
            if is_venture:
                return PlacementDetailsVenture(**item)
            else:
                return PlacementDetailsWageEmployment(**item)
        except ValidationError as e:
            self.logger.warning(
                "Failed to validate placement details",
                item=item,
                is_venture=is_venture,
                error=str(e),
            )
            return None

    def parse_employment_details(self, value: str | None) -> list[EmploymentDetailsEntry]:
        """
        Parse employment_details JSON array.

        Args:
            value: JSON string

        Returns:
            List of parsed EmploymentDetailsEntry objects
        """
        parsed = self.parse_json_field(value)
        if not parsed:
            return []

        entries: list[EmploymentDetailsEntry] = []
        for item in parsed:
            try:
                entry = EmploymentDetailsEntry(**item)
                entries.append(entry)
            except ValidationError as e:
                self.logger.warning(
                    "Failed to validate employment details entry",
                    item=item,
                    error=str(e),
                )

        return entries


__all__ = ["JSONParser"]
