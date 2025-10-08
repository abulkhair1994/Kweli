"""Unit tests for validators."""

from datetime import date

from models.enums import EmploymentType, EnrollmentStatus
from models.nodes import LearnerNode
from models.relationships import EnrolledInRelationship, WorksForRelationship
from validators.data_quality import DataQualityChecker, QualityMetrics
from validators.learner_validator import LearnerValidator, ValidationResult
from validators.relationship_validator import RelationshipValidator


class TestValidationResult:
    """Test ValidationResult class."""

    def test_create_valid_result(self) -> None:
        """Test creating valid result."""
        result = ValidationResult(is_valid=True)
        assert result.is_valid is True
        assert len(result.errors) == 0
        assert bool(result) is True

    def test_create_invalid_result(self) -> None:
        """Test creating invalid result."""
        result = ValidationResult(is_valid=False, errors=["Error 1", "Error 2"])
        assert result.is_valid is False
        assert len(result.errors) == 2
        assert bool(result) is False

    def test_add_error(self) -> None:
        """Test adding error to result."""
        result = ValidationResult()
        assert result.is_valid is True

        result.add_error("New error")
        assert result.is_valid is False
        assert "New error" in result.errors


class TestLearnerValidator:
    """Test LearnerValidator."""

    def test_validate_valid_learner_data(self) -> None:
        """Test validating valid learner data."""
        validator = LearnerValidator()
        data = {
            "sand_id": "SAND123",
            "hashed_email": "hash123",
            "full_name": "Test User",
        }

        result = validator.validate_learner_data(data)
        assert result.is_valid is True

    def test_validate_missing_required_field(self) -> None:
        """Test validation fails with missing required field."""
        validator = LearnerValidator()
        data = {
            "sand_id": "SAND123",
            # Missing hashed_email
            "full_name": "Test User",
        }

        result = validator.validate_learner_data(data)
        assert result.is_valid is False
        assert any("hashed_email" in error for error in result.errors)

    def test_validate_invalid_country_code(self) -> None:
        """Test validation fails with invalid country code."""
        validator = LearnerValidator()
        data = {
            "sand_id": "SAND123",
            "hashed_email": "hash123",
            "full_name": "Test User",
            "country_of_residence_code": "INVALID",  # Should be 2 letters
        }

        result = validator.validate_learner_data(data)
        assert result.is_valid is False
        assert any("country code" in error.lower() for error in result.errors)

    def test_validate_learner_node(self) -> None:
        """Test validating LearnerNode."""
        validator = LearnerValidator()
        learner = LearnerNode(
            sand_id="SAND123",
            hashed_email="hash123",
            full_name="Test User",
            country_of_residence_code="EG",
        )

        result = validator.validate_learner_node(learner)
        assert result.is_valid is True

    def test_validate_learner_node_invalid_country(self) -> None:
        """Test validating LearnerNode with invalid country code."""
        validator = LearnerValidator()
        learner = LearnerNode(
            sand_id="SAND123",
            hashed_email="hash123",
            full_name="Test User",
            country_of_residence_code="INVALID",
        )

        result = validator.validate_learner_node(learner)
        assert result.is_valid is False

    def test_try_create_learner_node_success(self) -> None:
        """Test successfully creating LearnerNode."""
        validator = LearnerValidator()
        data = {
            "sand_id": "SAND123",
            "hashed_email": "hash123",
            "full_name": "Test User",
        }

        learner, errors = validator.try_create_learner_node(data)
        assert learner is not None
        assert len(errors) == 0
        assert learner.sand_id == "SAND123"

    def test_try_create_learner_node_failure(self) -> None:
        """Test failing to create LearnerNode."""
        validator = LearnerValidator()
        data = {
            "sand_id": "SAND123",
            # Missing required fields
        }

        learner, errors = validator.try_create_learner_node(data)
        assert learner is None
        assert len(errors) > 0


class TestRelationshipValidator:
    """Test RelationshipValidator."""

    def test_validate_valid_enrollment(self) -> None:
        """Test validating valid enrollment."""
        validator = RelationshipValidator()
        enrollment = EnrolledInRelationship(
            index=1,
            cohort_code="VA-C4",
            enrollment_status=EnrollmentStatus.ACTIVE,
            start_date=date(2024, 7, 1),
            end_date=date(2024, 9, 3),
            lms_overall_score=95.5,
            completion_rate=100.0,
        )

        result = validator.validate_enrollment(enrollment)
        assert result.is_valid is True

    def test_validate_enrollment_invalid_dates(self) -> None:
        """Test enrollment with end_date before start_date."""
        validator = RelationshipValidator()
        enrollment = EnrolledInRelationship(
            index=1,
            cohort_code="VA-C4",
            enrollment_status=EnrollmentStatus.ACTIVE,
            start_date=date(2024, 9, 1),
            end_date=date(2024, 7, 1),  # Before start_date
        )

        result = validator.validate_enrollment(enrollment)
        assert result.is_valid is False
        assert any("end_date" in error and "before" in error for error in result.errors)

    def test_validate_enrollment_invalid_score(self) -> None:
        """Test enrollment with invalid LMS score."""
        validator = RelationshipValidator()
        enrollment = EnrolledInRelationship(
            index=1,
            cohort_code="VA-C4",
            enrollment_status=EnrollmentStatus.ACTIVE,
            start_date=date(2024, 7, 1),
            lms_overall_score=150.0,  # Out of range
        )

        result = validator.validate_enrollment(enrollment)
        assert result.is_valid is False
        assert any("lms_overall_score" in error for error in result.errors)

    def test_validate_enrollment_invalid_completion_rate(self) -> None:
        """Test enrollment with invalid completion rate."""
        validator = RelationshipValidator()
        enrollment = EnrolledInRelationship(
            index=1,
            cohort_code="VA-C4",
            enrollment_status=EnrollmentStatus.ACTIVE,
            start_date=date(2024, 7, 1),
            completion_rate=150.0,  # Out of range
        )

        result = validator.validate_enrollment(enrollment)
        assert result.is_valid is False
        assert any("completion_rate" in error for error in result.errors)

    def test_validate_valid_employment(self) -> None:
        """Test validating valid employment."""
        validator = RelationshipValidator()
        employment = WorksForRelationship(
            position="Software Engineer",
            employment_type=EmploymentType.FULL_TIME,
            start_date=date(2023, 1, 1),
            end_date=date(2024, 1, 1),
            source="employment_details",
            is_current=False,
        )

        result = validator.validate_employment(employment)
        assert result.is_valid is True

    def test_validate_employment_invalid_dates(self) -> None:
        """Test employment with end_date before start_date."""
        validator = RelationshipValidator()
        employment = WorksForRelationship(
            position="Software Engineer",
            start_date=date(2024, 1, 1),
            end_date=date(2023, 1, 1),  # Before start_date
            source="employment_details",
        )

        result = validator.validate_employment(employment)
        assert result.is_valid is False

    def test_validate_employment_auto_corrects_current_flag(self) -> None:
        """Test employment model auto-corrects is_current when end_date is set."""
        validator = RelationshipValidator()
        employment = WorksForRelationship(
            position="Software Engineer",
            start_date=date(2023, 1, 1),
            end_date=date(2024, 1, 1),
            is_current=True,  # Model auto-corrects this to False
            source="employment_details",
        )

        # Model's @model_validator automatically sets is_current=False when end_date exists
        assert employment.is_current is False
        # So validation should pass
        result = validator.validate_employment(employment)
        assert result.is_valid is True

    def test_validate_date_range(self) -> None:
        """Test date range validation."""
        validator = RelationshipValidator()

        # Valid range
        result = validator.validate_date_range(
            date(2023, 1, 1), date(2024, 1, 1), "test"
        )
        assert result.is_valid is True

        # Invalid range
        result = validator.validate_date_range(
            date(2024, 1, 1), date(2023, 1, 1), "test"
        )
        assert result.is_valid is False


class TestDataQualityChecker:
    """Test DataQualityChecker."""

    def test_initial_metrics(self) -> None:
        """Test initial metrics are zero."""
        checker = DataQualityChecker()
        metrics = checker.get_metrics()

        assert metrics.total_records == 0
        assert metrics.valid_records == 0
        assert metrics.invalid_records == 0
        assert metrics.error_rate == 0.0
        assert metrics.success_rate == 0.0

    def test_record_valid_validation(self) -> None:
        """Test recording valid validation."""
        checker = DataQualityChecker()
        checker.record_validation(is_valid=True)

        metrics = checker.get_metrics()
        assert metrics.total_records == 1
        assert metrics.valid_records == 1
        assert metrics.invalid_records == 0
        assert metrics.success_rate == 1.0

    def test_record_invalid_validation(self) -> None:
        """Test recording invalid validation."""
        checker = DataQualityChecker()
        checker.record_validation(is_valid=False, errors=["Error 1", "Error 2"])

        metrics = checker.get_metrics()
        assert metrics.total_records == 1
        assert metrics.valid_records == 0
        assert metrics.invalid_records == 1
        assert metrics.error_rate == 1.0

    def test_track_errors_by_type(self) -> None:
        """Test tracking errors by type."""
        checker = DataQualityChecker()
        checker.record_validation(is_valid=False, errors=["Missing field: name"])
        checker.record_validation(is_valid=False, errors=["Missing field: name"])
        checker.record_validation(is_valid=False, errors=["Invalid date"])

        metrics = checker.get_metrics()
        assert metrics.errors_by_type["Missing field: name"] == 2
        assert metrics.errors_by_type["Invalid date"] == 1

    def test_track_errors_by_field(self) -> None:
        """Test tracking errors by field."""
        checker = DataQualityChecker()
        checker.record_validation(is_valid=False, errors=["name: required field"])
        checker.record_validation(is_valid=False, errors=["name: invalid format"])
        checker.record_validation(is_valid=False, errors=["email: invalid format"])

        metrics = checker.get_metrics()
        assert metrics.errors_by_field["name"] == 2
        assert metrics.errors_by_field["email"] == 1

    def test_check_quality_threshold_pass(self) -> None:
        """Test quality threshold check passes."""
        checker = DataQualityChecker(max_error_rate=0.1)  # 10%

        # Add 95 valid, 5 invalid = 5% error rate
        for _ in range(95):
            checker.record_validation(is_valid=True)
        for _ in range(5):
            checker.record_validation(is_valid=False)

        assert checker.check_quality_threshold() is True

    def test_check_quality_threshold_fail(self) -> None:
        """Test quality threshold check fails."""
        checker = DataQualityChecker(max_error_rate=0.05)  # 5%

        # Add 80 valid, 20 invalid = 20% error rate
        for _ in range(80):
            checker.record_validation(is_valid=True)
        for _ in range(20):
            checker.record_validation(is_valid=False)

        assert checker.check_quality_threshold() is False

    def test_add_warning(self) -> None:
        """Test adding warnings."""
        checker = DataQualityChecker()
        checker.add_warning("Data looks suspicious")

        metrics = checker.get_metrics()
        assert "Data looks suspicious" in metrics.warnings

    def test_get_top_errors(self) -> None:
        """Test getting top errors."""
        checker = DataQualityChecker()
        checker.record_validation(is_valid=False, errors=["Error A"])
        checker.record_validation(is_valid=False, errors=["Error A"])
        checker.record_validation(is_valid=False, errors=["Error A"])
        checker.record_validation(is_valid=False, errors=["Error B"])
        checker.record_validation(is_valid=False, errors=["Error B"])
        checker.record_validation(is_valid=False, errors=["Error C"])

        top_errors = checker.get_top_errors(limit=2)
        assert len(top_errors) == 2
        assert top_errors[0] == ("Error A", 3)
        assert top_errors[1] == ("Error B", 2)

    def test_get_problematic_fields(self) -> None:
        """Test getting problematic fields."""
        checker = DataQualityChecker()
        checker.record_validation(is_valid=False, errors=["field1: error"])
        checker.record_validation(is_valid=False, errors=["field1: error"])
        checker.record_validation(is_valid=False, errors=["field2: error"])

        fields = checker.get_problematic_fields(limit=2)
        assert len(fields) == 2
        assert fields[0] == ("field1", 2)
        assert fields[1] == ("field2", 1)

    def test_generate_report(self) -> None:
        """Test generating quality report."""
        checker = DataQualityChecker(max_error_rate=0.1)

        for _ in range(90):
            checker.record_validation(is_valid=True)
        for _ in range(10):
            checker.record_validation(is_valid=False, errors=["Test error"])

        report = checker.generate_report()

        assert "summary" in report
        assert "quality_check" in report
        assert "top_errors" in report
        assert "problematic_fields" in report
        assert report["summary"]["total_records"] == 100
        assert report["quality_check"]["passed"] is True


class TestQualityMetrics:
    """Test QualityMetrics."""

    def test_metrics_to_dict(self) -> None:
        """Test converting metrics to dictionary."""
        metrics = QualityMetrics(
            total_records=100,
            valid_records=95,
            invalid_records=5,
        )

        data = metrics.to_dict()
        assert data["total_records"] == 100
        assert data["valid_records"] == 95
        assert data["invalid_records"] == 5
        assert data["error_rate"] == 0.05
        assert data["success_rate"] == 0.95
