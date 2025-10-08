"""Unit tests for Pydantic models."""

from datetime import date, datetime

import pytest
from pydantic import ValidationError

from models.enums import (
    EducationLevel,
    EmploymentType,
    EnrollmentStatus,
    Gender,
    LearningState,
    ProfessionalStatus,
    SalaryRange,
)
from models.nodes import (
    CityNode,
    CompanyNode,
    CountryNode,
    LearnerNode,
    LearningStateNode,
    ProfessionalStatusNode,
    ProgramNode,
    SkillNode,
)
from models.parsers import (
    EducationDetailsEntry,
    EmploymentDetailsEntry,
    LearningDetailsEntry,
    PlacementDetailsVenture,
    PlacementDetailsWageEmployment,
)
from models.relationships import (
    EnrolledInRelationship,
    HasProfessionalStatusRelationship,
    HasSkillRelationship,
    InLearningStateRelationship,
    RunsVentureRelationship,
    WorksForRelationship,
)


class TestEnums:
    """Test all enum types."""

    def test_gender_enum(self) -> None:
        """Test Gender enum values."""
        assert Gender.MALE.value == "male"
        assert Gender.FEMALE.value == "female"
        assert Gender.OTHER.value == "other/prefer not to say"

    def test_learning_state_enum(self) -> None:
        """Test LearningState enum values."""
        assert LearningState.ACTIVE.value == "Active"
        assert LearningState.GRADUATE.value == "Graduate"
        assert LearningState.DROPPED_OUT.value == "Dropped Out"

    def test_professional_status_enum(self) -> None:
        """Test ProfessionalStatus enum values."""
        assert ProfessionalStatus.UNEMPLOYED.value == "Unemployed"
        assert ProfessionalStatus.WAGE_EMPLOYED.value == "Wage Employed"
        assert ProfessionalStatus.ENTREPRENEUR.value == "Entrepreneur"


class TestNodeModels:
    """Test all node models."""

    def test_learner_node_minimal(self) -> None:
        """Test LearnerNode with minimal required fields."""
        learner = LearnerNode(
            sand_id="SAND123",
            hashed_email="hash123",
            full_name="Test User",
        )
        assert learner.sand_id == "SAND123"
        assert learner.hashed_email == "hash123"
        assert learner.full_name == "Test User"
        assert learner.is_placed is False
        assert learner.is_featured is False

    def test_learner_node_full(self) -> None:
        """Test LearnerNode with all fields."""
        learner = LearnerNode(
            sand_id="SAND123",
            hashed_email="hash123",
            full_name="Ahmed Hassan",
            gender=Gender.MALE,
            education_level=EducationLevel.BACHELOR_DEGREE,
            education_field="Computer Science",
            country_of_residence_code="EG",
            city_of_residence_id="EG-CAI",
            current_learning_state=LearningState.ACTIVE,
            current_professional_status=ProfessionalStatus.WAGE_EMPLOYED,
            is_placed=True,
            is_rural=False,
            has_disability=False,
        )
        assert learner.gender == Gender.MALE
        assert learner.country_of_residence_code == "EG"
        assert learner.current_learning_state == LearningState.ACTIVE

    def test_country_node(self) -> None:
        """Test CountryNode creation."""
        country = CountryNode(
            code="EG",
            name="Egypt",
            latitude=26.8206,
            longitude=30.8025,
        )
        assert country.code == "EG"
        assert country.name == "Egypt"
        assert country.latitude == 26.8206

    def test_city_node(self) -> None:
        """Test CityNode creation."""
        city = CityNode(
            id="EG-CAI",
            name="Cairo",
            country_code="EG",
            latitude=30.0444,
            longitude=31.2357,
        )
        assert city.id == "EG-CAI"
        assert city.country_code == "EG"

    def test_skill_node(self) -> None:
        """Test SkillNode creation."""
        skill = SkillNode(
            id="python",
            name="Python",
            category="Technical",
        )
        assert skill.id == "python"
        assert skill.name == "Python"

    def test_program_node(self) -> None:
        """Test ProgramNode creation."""
        program = ProgramNode(
            id="VA-C4",
            name="Virtual Assistant",
            cohort_code="VA-C4",
            provider="ALX",
        )
        assert program.cohort_code == "VA-C4"

    def test_company_node(self) -> None:
        """Test CompanyNode creation."""
        company = CompanyNode(
            id="vodafone_eg",
            name="Vodafone Egypt",
            industry="Telecommunications",
            country_code="EG",
        )
        assert company.name == "Vodafone Egypt"

    def test_learning_state_node(self) -> None:
        """Test LearningStateNode creation."""
        state = LearningStateNode(
            state=LearningState.GRADUATE,
            start_date=date(2024, 6, 15),
            end_date=None,
            is_current=True,
        )
        assert state.state == LearningState.GRADUATE
        assert state.is_current is True

    def test_professional_status_node(self) -> None:
        """Test ProfessionalStatusNode creation."""
        status = ProfessionalStatusNode(
            status=ProfessionalStatus.WAGE_EMPLOYED,
            start_date=date(2023, 8, 1),
            is_current=True,
        )
        assert status.status == ProfessionalStatus.WAGE_EMPLOYED


class TestRelationshipModels:
    """Test all relationship models."""

    def test_has_skill_relationship(self) -> None:
        """Test HasSkillRelationship."""
        rel = HasSkillRelationship(
            proficiency_level="Intermediate",
            source="Profile",
        )
        assert rel.proficiency_level == "Intermediate"
        assert rel.source == "Profile"

    def test_enrolled_in_relationship(self) -> None:
        """Test EnrolledInRelationship with validation."""
        rel = EnrolledInRelationship(
            index=1,
            cohort_code="VA-C4",
            enrollment_status=EnrollmentStatus.COMPLETED,
            start_date=date(2024, 7, 1),
            end_date=date(2024, 9, 3),
            lms_overall_score=95.5,
            completion_rate=100.0,
        )
        assert rel.is_completed is True
        assert rel.is_dropped is False
        assert rel.duration == 64  # days

    def test_enrolled_in_handles_missing_values(self) -> None:
        """Test EnrolledInRelationship handles -99 as None."""
        rel = EnrolledInRelationship(
            index=1,
            cohort_code="VA-C4",
            enrollment_status=EnrollmentStatus.DROPPED_OUT,
            start_date=date(2024, 7, 1),
            lms_overall_score="-99",  # Should convert to None
            completion_rate=-99,  # Should convert to None
        )
        assert rel.lms_overall_score is None
        assert rel.completion_rate is None
        assert rel.is_dropped is True

    def test_enrolled_in_handles_invalid_graduation_date(self) -> None:
        """Test EnrolledInRelationship handles 1970-01-01 as None."""
        rel = EnrolledInRelationship(
            index=1,
            cohort_code="VA-C4",
            enrollment_status=EnrollmentStatus.ACTIVE,
            start_date=date(2024, 7, 1),
            graduation_date="1970-01-01",  # Should convert to None
        )
        assert rel.graduation_date is None

    def test_works_for_relationship(self) -> None:
        """Test WorksForRelationship with duration calculation."""
        rel = WorksForRelationship(
            position="Software Engineer",
            employment_type=EmploymentType.FULL_TIME,
            start_date=date(2023, 1, 1),
            end_date=date(2023, 7, 1),
            salary_range=SalaryRange.RANGE_1001_2000,
            source="placement_details",
        )
        assert rel.is_current is False
        assert rel.duration == 6  # months

    def test_works_for_current_employment(self) -> None:
        """Test WorksForRelationship with current employment."""
        rel = WorksForRelationship(
            position="Data Analyst",
            start_date=date(2023, 1, 1),
            end_date=None,
            source="employment_details",
        )
        assert rel.is_current is True
        assert rel.duration is None

    def test_runs_venture_relationship(self) -> None:
        """Test RunsVentureRelationship."""
        rel = RunsVentureRelationship(
            role="Founder",
            start_date=date(2022, 4, 1),
            jobs_created=15,
            capital_secured=50000.0,
            female_opportunities=8,
        )
        assert rel.jobs_created == 15
        assert rel.capital_secured == 50000.0

    def test_in_learning_state_relationship(self) -> None:
        """Test InLearningStateRelationship."""
        rel = InLearningStateRelationship(
            transition_date=datetime(2024, 6, 15, 10, 30),
            notes="Graduated successfully",
        )
        assert rel.notes == "Graduated successfully"

    def test_has_professional_status_relationship(self) -> None:
        """Test HasProfessionalStatusRelationship."""
        rel = HasProfessionalStatusRelationship(
            transition_date=datetime(2023, 8, 1),
            notes="Started first job",
        )
        assert rel.notes == "Started first job"


class TestParserModels:
    """Test JSON parser models."""

    def test_learning_details_entry(self) -> None:
        """Test LearningDetailsEntry parsing."""
        entry = LearningDetailsEntry(
            index="1",
            program_name="Virtual Assistant",
            cohort_code="VA-C4",
            program_start_date="2024-07-01",
            program_end_date="2024-09-03",
            enrollment_status="Graduated",
            program_graduation_date="2024-09-03",
            lms_overall_score="95.5",
            no_of_assignments="15",
            no_of_submissions="15",
            no_of_assignment_passed="15",
            assignment_completion_rate="100",
            no_of_milestone="7",
            no_of_milestone_submitted="7",
            no_of_milestone_passed="7",
            milestone_completion_rate="100",
            no_of_test="8",
            no_of_test_submitted="8",
            no_of_test_passed="8",
            test_completion_rate="100",
            completion_rate="1",
        )
        assert entry.program_name == "Virtual Assistant"
        assert entry.cohort_code == "VA-C4"

    def test_placement_details_wage_employment(self) -> None:
        """Test PlacementDetailsWageEmployment parsing."""
        entry = PlacementDetailsWageEmployment(
            employment_type="Full-time",
            job_start_date="2023-01-01",
            organisation_name="Vodafone",
            salary_range="$1001-$2000",
            job_title="Backend Developer",
        )
        assert entry.organisation_name == "Vodafone"
        assert entry.job_title == "Backend Developer"

    def test_placement_details_venture(self) -> None:
        """Test PlacementDetailsVenture parsing."""
        entry = PlacementDetailsVenture(
            business_name="TechStart Solutions",
            job_start_date="2022-04-01",
            jobs_created_to_date=15,
            capital_secured_todate=50000.0,
            female_opp_todate=8,
        )
        assert entry.business_name == "TechStart Solutions"
        assert entry.jobs_created_to_date == 15

    def test_employment_details_entry(self) -> None:
        """Test EmploymentDetailsEntry parsing with alias."""
        entry = EmploymentDetailsEntry(
            index="1",
            organisation_name="Vodafone Egypt",  # Using alias
            start_date="2023-01-01",
            end_date="9999-12-31",
            country="Egypt",
            job_title="Software Engineer",
            is_current="1",
            duration_in_years="2.5",
        )
        assert entry.organization_name == "Vodafone Egypt"
        assert entry.job_title == "Software Engineer"

    def test_education_details_entry(self) -> None:
        """Test EducationDetailsEntry parsing."""
        entry = EducationDetailsEntry(
            index="1",
            institution_name="Cairo University",
            start_date="2018-09-01",
            end_date="2022-06-01",
            field_of_study="Computer Science",
            level_of_study="Bachelor's degree",
            graduated="1",
        )
        assert entry.institution_name == "Cairo University"
        assert entry.field_of_study == "Computer Science"


class TestValidationErrors:
    """Test validation errors for required fields."""

    def test_learner_node_missing_required_fields(self) -> None:
        """Test LearnerNode raises error when required fields missing."""
        with pytest.raises(ValidationError) as exc_info:
            LearnerNode()  # Missing all required fields

        errors = exc_info.value.errors()
        required_fields = {"sand_id", "hashed_email", "full_name"}
        error_fields = {err["loc"][0] for err in errors}
        assert required_fields.issubset(error_fields)

    def test_country_node_missing_code(self) -> None:
        """Test CountryNode requires code."""
        with pytest.raises(ValidationError) as exc_info:
            CountryNode(name="Egypt")

        errors = exc_info.value.errors()
        assert any(err["loc"][0] == "code" for err in errors)

    def test_enrolled_in_invalid_date_order(self) -> None:
        """Test EnrolledInRelationship with end_date before start_date."""
        # Note: We don't validate date order in the model, but we calculate duration
        rel = EnrolledInRelationship(
            index=1,
            cohort_code="VA-C4",
            enrollment_status=EnrollmentStatus.ACTIVE,
            start_date=date(2024, 9, 1),
            end_date=date(2024, 7, 1),  # Earlier than start_date
        )
        # Duration will be negative
        assert rel.duration == -62
