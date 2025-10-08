"""
Data quality checker.

Tracks validation statistics and data quality metrics.
"""

from dataclasses import dataclass, field
from typing import Any

from structlog.types import FilteringBoundLogger

from utils.logger import get_logger


@dataclass
class QualityMetrics:
    """Data quality metrics."""

    total_records: int = 0
    valid_records: int = 0
    invalid_records: int = 0
    errors_by_type: dict[str, int] = field(default_factory=dict)
    errors_by_field: dict[str, int] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)

    @property
    def error_rate(self) -> float:
        """Calculate error rate."""
        if self.total_records == 0:
            return 0.0
        return self.invalid_records / self.total_records

    @property
    def success_rate(self) -> float:
        """Calculate success rate."""
        if self.total_records == 0:
            return 0.0
        return self.valid_records / self.total_records

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "total_records": self.total_records,
            "valid_records": self.valid_records,
            "invalid_records": self.invalid_records,
            "error_rate": round(self.error_rate, 4),
            "success_rate": round(self.success_rate, 4),
            "errors_by_type": self.errors_by_type,
            "errors_by_field": self.errors_by_field,
            "warnings": self.warnings,
        }


class DataQualityChecker:
    """Track and analyze data quality."""

    def __init__(
        self,
        max_error_rate: float = 0.05,
        logger: FilteringBoundLogger | None = None,
    ) -> None:
        """
        Initialize data quality checker.

        Args:
            max_error_rate: Maximum acceptable error rate (0.0-1.0)
            logger: Optional logger instance
        """
        self.logger = logger or get_logger(__name__)
        self.max_error_rate = max_error_rate
        self.metrics = QualityMetrics()

    def record_validation(self, is_valid: bool, errors: list[str] | None = None) -> None:
        """
        Record a validation result.

        Args:
            is_valid: Whether validation passed
            errors: List of error messages if validation failed
        """
        self.metrics.total_records += 1

        if is_valid:
            self.metrics.valid_records += 1
        else:
            self.metrics.invalid_records += 1

            # Track errors by type and field
            if errors:
                for error in errors:
                    # Count by error message
                    self.metrics.errors_by_type[error] = (
                        self.metrics.errors_by_type.get(error, 0) + 1
                    )

                    # Extract field name (assuming format "field: message")
                    if ":" in error:
                        field = error.split(":")[0].strip()
                        self.metrics.errors_by_field[field] = (
                            self.metrics.errors_by_field.get(field, 0) + 1
                        )

    def check_quality_threshold(self) -> bool:
        """
        Check if error rate is below threshold.

        Returns:
            True if quality is acceptable
        """
        if self.metrics.error_rate > self.max_error_rate:
            self.logger.error(
                "Data quality threshold exceeded",
                error_rate=self.metrics.error_rate,
                max_error_rate=self.max_error_rate,
                total_records=self.metrics.total_records,
                invalid_records=self.metrics.invalid_records,
            )
            return False

        return True

    def add_warning(self, warning: str) -> None:
        """Add a warning message."""
        self.metrics.warnings.append(warning)
        self.logger.warning("Data quality warning", warning=warning)

    def get_metrics(self) -> QualityMetrics:
        """Get current quality metrics."""
        return self.metrics

    def get_top_errors(self, limit: int = 10) -> list[tuple[str, int]]:
        """
        Get most common errors.

        Args:
            limit: Maximum number of errors to return

        Returns:
            List of (error_message, count) tuples
        """
        sorted_errors = sorted(
            self.metrics.errors_by_type.items(),
            key=lambda x: x[1],
            reverse=True,
        )
        return sorted_errors[:limit]

    def get_problematic_fields(self, limit: int = 10) -> list[tuple[str, int]]:
        """
        Get fields with most errors.

        Args:
            limit: Maximum number of fields to return

        Returns:
            List of (field_name, error_count) tuples
        """
        sorted_fields = sorted(
            self.metrics.errors_by_field.items(),
            key=lambda x: x[1],
            reverse=True,
        )
        return sorted_fields[:limit]

    def generate_report(self) -> dict[str, Any]:
        """
        Generate comprehensive quality report.

        Returns:
            Quality report dictionary
        """
        return {
            "summary": self.metrics.to_dict(),
            "quality_check": {
                "passed": self.check_quality_threshold(),
                "max_error_rate": self.max_error_rate,
            },
            "top_errors": self.get_top_errors(),
            "problematic_fields": self.get_problematic_fields(),
        }


__all__ = ["DataQualityChecker", "QualityMetrics"]
