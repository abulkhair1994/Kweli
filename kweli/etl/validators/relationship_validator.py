"""
Relationship validator.

Validates relationships before creating in Neo4j.
"""

from datetime import date

from structlog.types import FilteringBoundLogger

from kweli.etl.models.relationships import EnrolledInRelationship, WorksForRelationship
from kweli.etl.utils.logger import get_logger
from kweli.etl.validators.learner_validator import ValidationResult


class RelationshipValidator:
    """Validate relationship data."""

    def __init__(self, logger: FilteringBoundLogger | None = None) -> None:
        """
        Initialize relationship validator.

        Args:
            logger: Optional logger instance
        """
        self.logger = logger or get_logger(__name__)

    def validate_enrollment(self, enrollment: EnrolledInRelationship) -> ValidationResult:
        """
        Validate enrollment relationship.

        Args:
            enrollment: EnrolledInRelationship instance

        Returns:
            ValidationResult
        """
        result = ValidationResult()

        # Validate required fields
        if not enrollment.cohort_code:
            result.add_error("cohort_code is required")

        # Validate date logic
        if enrollment.start_date and enrollment.end_date:
            if enrollment.end_date < enrollment.start_date:
                result.add_error(
                    f"end_date ({enrollment.end_date}) before start_date ({enrollment.start_date})"
                )

        if enrollment.start_date and enrollment.graduation_date:
            if enrollment.graduation_date < enrollment.start_date:
                result.add_error(
                    f"graduation_date ({enrollment.graduation_date}) before start_date "
                    f"({enrollment.start_date})"
                )

        # Validate completion rates (0-100 or 0-1)
        rates = [
            ("completion_rate", enrollment.completion_rate),
            ("assignment_completion_rate", enrollment.assignment_completion_rate),
            ("milestone_completion_rate", enrollment.milestone_completion_rate),
            ("test_completion_rate", enrollment.test_completion_rate),
        ]

        for name, rate in rates:
            if rate is not None:
                if rate < 0 or rate > 100:
                    result.add_error(f"{name} must be between 0 and 100, got {rate}")

        # Validate LMS score (0-100)
        if enrollment.lms_overall_score is not None:
            if enrollment.lms_overall_score < 0 or enrollment.lms_overall_score > 100:
                result.add_error(
                    f"lms_overall_score must be between 0 and 100, "
                    f"got {enrollment.lms_overall_score}"
                )

        return result

    def validate_employment(self, employment: WorksForRelationship) -> ValidationResult:
        """
        Validate employment relationship.

        Args:
            employment: WorksForRelationship instance

        Returns:
            ValidationResult
        """
        result = ValidationResult()

        # Validate date logic
        if employment.start_date and employment.end_date:
            if employment.end_date < employment.start_date:
                result.add_error(
                    f"end_date ({employment.end_date}) before start_date ({employment.start_date})"
                )

        # Validate current employment flag
        if employment.end_date is not None and employment.is_current:
            result.add_error("is_current=True but end_date is set")

        return result

    def validate_date_range(
        self, start_date: date | None, end_date: date | None, context: str = "relationship"
    ) -> ValidationResult:
        """
        Validate a date range.

        Args:
            start_date: Start date
            end_date: End date
            context: Context for error messages

        Returns:
            ValidationResult
        """
        result = ValidationResult()

        if start_date and end_date:
            if end_date < start_date:
                result.add_error(
                    f"{context}: end_date ({end_date}) before start_date ({start_date})"
                )

        return result


__all__ = ["RelationshipValidator"]
