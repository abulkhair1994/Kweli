"""
Learner data validator.

Validates learner records before loading into Neo4j.
"""

from typing import Any

from pydantic import ValidationError
from structlog.types import FilteringBoundLogger

from kweli.etl.models.enums import ProfessionalStatus
from kweli.etl.models.nodes import LearnerNode
from kweli.etl.models.parsers import EmploymentDetailsEntry
from kweli.etl.utils.logger import get_logger


class ValidationResult:
    """Result of validation check."""

    def __init__(self, is_valid: bool = True, errors: list[str] | None = None) -> None:
        """Initialize validation result."""
        self.is_valid = is_valid
        self.errors = errors or []

    def add_error(self, error: str) -> None:
        """Add an error to the result."""
        self.errors.append(error)
        self.is_valid = False

    def __bool__(self) -> bool:
        """Return validation status."""
        return self.is_valid


class LearnerValidator:
    """Validate learner data."""

    def __init__(
        self,
        required_fields: list[str] | None = None,
        logger: FilteringBoundLogger | None = None,
    ) -> None:
        """
        Initialize learner validator.

        Args:
            required_fields: List of required field names
            logger: Optional logger instance
        """
        self.logger = logger or get_logger(__name__)
        self.required_fields = required_fields or ["hashed_email", "full_name"]

    def validate_learner_data(self, data: dict[str, Any]) -> ValidationResult:
        """
        Validate raw learner data dictionary.

        Args:
            data: Raw learner data from CSV

        Returns:
            ValidationResult with errors if any
        """
        result = ValidationResult()

        # Check required fields
        for field in self.required_fields:
            if field not in data or not data[field]:
                result.add_error(f"Missing required field: {field}")

        # Check data types for critical fields
        if "sand_id" in data and data["sand_id"]:
            if not isinstance(data["sand_id"], str):
                result.add_error(f"sand_id must be string, got {type(data['sand_id'])}")

        if "hashed_email" in data and data["hashed_email"]:
            if not isinstance(data["hashed_email"], str):
                result.add_error(
                    f"hashed_email must be string, got {type(data['hashed_email'])}"
                )

        # Validate country codes (should be 2 letters)
        if "country_of_residence_code" in data and data["country_of_residence_code"]:
            code = data["country_of_residence_code"]
            if not isinstance(code, str) or len(code) != 2:
                result.add_error(f"Invalid country code: {code}")

        return result

    def validate_learner_node(self, learner: LearnerNode) -> ValidationResult:
        """
        Validate LearnerNode object.

        Args:
            learner: LearnerNode instance

        Returns:
            ValidationResult
        """
        result = ValidationResult()

        # Validate required fields
        if not learner.hashed_email:
            result.add_error("hashed_email is required")

        if not learner.full_name:
            result.add_error("full_name is required")

        # Validate country codes
        if learner.country_of_residence_code:
            if len(learner.country_of_residence_code) != 2:
                result.add_error(
                    f"Invalid country_of_residence_code: {learner.country_of_residence_code}"
                )

        if learner.country_of_origin_code:
            if len(learner.country_of_origin_code) != 2:
                result.add_error(
                    f"Invalid country_of_origin_code: {learner.country_of_origin_code}"
                )

        return result

    def validate_employment_consistency(
        self,
        learner: LearnerNode,
        employment_entries: list[EmploymentDetailsEntry] | None = None,
    ) -> list[str]:
        """
        Validate consistency between professional status and employment relationships.

        This check helps identify data quality issues where the professional status
        contradicts the actual employment records.

        Args:
            learner: LearnerNode instance
            employment_entries: List of employment detail entries (if available)

        Returns:
            List of warning messages (empty if no issues found)
        """
        warnings: list[str] = []

        # If no employment entries provided, can't validate
        if employment_entries is None:
            return warnings

        # Count current jobs
        current_jobs = [entry for entry in employment_entries if entry.is_current == "1"]
        current_job_count = len(current_jobs)

        # Check 1: Unemployed but has current jobs
        if learner.current_professional_status == ProfessionalStatus.UNEMPLOYED and current_job_count > 0:
            org_names = [job.organization_name for job in current_jobs]
            warnings.append(
                f"Professional status is 'Unemployed' but learner has {current_job_count} current job(s): {', '.join(org_names)}"
            )

        # Check 2: Employed but no current jobs
        employed_statuses = {
            ProfessionalStatus.WAGE_EMPLOYED,
            ProfessionalStatus.FREELANCER,
            ProfessionalStatus.MULTIPLE,
            ProfessionalStatus.ENTREPRENEUR,
        }
        if learner.current_professional_status in employed_statuses and current_job_count == 0:
            # Get status value (handle both enum and string)
            status_str = (
                learner.current_professional_status.value
                if isinstance(learner.current_professional_status, ProfessionalStatus)
                else str(learner.current_professional_status)
            )
            # Check if they have any past employment
            if len(employment_entries) > 0:
                warnings.append(
                    f"Professional status is '{status_str}' but has no current jobs (has {len(employment_entries)} past job(s))"
                )
            else:
                warnings.append(
                    f"Professional status is '{status_str}' but has no employment records"
                )

        # Check 3: Multiple current jobs on same date (info, not warning)
        if current_job_count > 1:
            start_dates = [job.start_date for job in current_jobs]
            # Check if all start dates are the same
            if len(set(start_dates)) == 1:
                warnings.append(
                    f"INFO: {current_job_count} current jobs all started on same date ({start_dates[0]}) - may be legitimate consulting/part-time work"
                )

        return warnings

    def try_create_learner_node(self, data: dict[str, Any]) -> tuple[LearnerNode | None, list[str]]:
        """
        Attempt to create LearnerNode from data.

        Args:
            data: Raw learner data

        Returns:
            Tuple of (LearnerNode or None, list of errors)
        """
        errors: list[str] = []

        # First validate raw data
        validation = self.validate_learner_data(data)
        if not validation.is_valid:
            return None, validation.errors

        # Try to create Pydantic model
        try:
            learner = LearnerNode(**data)
            # Validate the node
            node_validation = self.validate_learner_node(learner)
            if not node_validation.is_valid:
                return None, node_validation.errors
            return learner, []
        except ValidationError as e:
            for error in e.errors():
                field = ".".join(str(x) for x in error["loc"])
                errors.append(f"{field}: {error['msg']}")
            return None, errors
        except Exception as e:
            errors.append(f"Unexpected error: {str(e)}")
            return None, errors


__all__ = ["LearnerValidator", "ValidationResult"]
