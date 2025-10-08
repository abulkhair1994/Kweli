"""
Learner data validator.

Validates learner records before loading into Neo4j.
"""

from typing import Any

from pydantic import ValidationError
from structlog.types import FilteringBoundLogger

from models.nodes import LearnerNode
from utils.logger import get_logger


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
        self.required_fields = required_fields or ["sand_id", "hashed_email", "full_name"]

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
        if not learner.sand_id:
            result.add_error("sand_id is required")

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
