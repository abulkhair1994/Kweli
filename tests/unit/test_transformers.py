"""Unit tests for data transformers."""

from datetime import date

from models.enums import LearningState, ProfessionalStatus
from models.parsers import EmploymentDetailsEntry, LearningDetailsEntry
from transformers.date_converter import DateConverter
from transformers.geo_normalizer import GeoNormalizer
from transformers.json_parser import JSONParser
from transformers.learning_state_history_builder import LearningStateHistoryBuilder
from transformers.professional_status_history_builder import ProfessionalStatusHistoryBuilder
from transformers.skills_parser import SkillsParser
from transformers.state_deriver import StateDeriver


class TestJSONParser:
    """Test JSON field parser."""

    def test_parse_empty_array(self) -> None:
        """Test parsing empty array returns None."""
        parser = JSONParser()
        result = parser.parse_json_field("[]")
        assert result is None

    def test_parse_valid_json(self) -> None:
        """Test parsing valid JSON array."""
        parser = JSONParser()
        result = parser.parse_json_field('[{"key": "value"}]')
        assert result == [{"key": "value"}]

    def test_parse_invalid_json(self) -> None:
        """Test parsing invalid JSON returns None."""
        parser = JSONParser()
        result = parser.parse_json_field("invalid json")
        assert result is None

    def test_parse_double_encoded_json(self) -> None:
        """Test parsing double-encoded JSON (bug fix for 72% of data)."""
        parser = JSONParser()
        # Double-encoded JSON: '"[{\\"key\\": \\"value\\"}]"'
        double_encoded = '"[{\\"name\\": \\"test\\"}]"'
        result = parser.parse_json_field(double_encoded)
        assert result == [{"name": "test"}]

    def test_parse_double_encoded_empty_array(self) -> None:
        """Test parsing double-encoded empty array returns None."""
        parser = JSONParser()
        result = parser.parse_json_field('"[]"')
        assert result is None

    def test_parse_learning_details(self) -> None:
        """Test parsing learning_details JSON."""
        parser = JSONParser()
        json_str = """[{
            "index": "1",
            "program_name": "Virtual Assistant",
            "cohort_code": "VA-C4",
            "program_start_date": "2024-07-01",
            "program_end_date": "2024-09-03",
            "enrollment_status": "Graduated",
            "program_graduation_date": "2024-09-03",
            "lms_overall_score": "95.5",
            "no_of_assignments": "15",
            "no_of_submissions": "15",
            "no_of_assignment_passed": "15",
            "assignment_completion_rate": "100",
            "no_of_milestone": "7",
            "no_of_milestone_submitted": "7",
            "no_of_milestone_passed": "7",
            "milestone_completion_rate": "100",
            "no_of_test": "8",
            "no_of_test_submitted": "8",
            "no_of_test_passed": "8",
            "test_completion_rate": "100",
            "completion_rate": "1"
        }]"""

        entries = parser.parse_learning_details(json_str)
        assert len(entries) == 1
        assert entries[0].program_name == "Virtual Assistant"
        assert entries[0].cohort_code == "VA-C4"

    def test_parse_placement_details_wage(self) -> None:
        """Test parsing placement_details for wage employment."""
        parser = JSONParser()
        json_str = """[{
            "employment_type": "Full-time",
            "job_start_date": "2023-01-01",
            "organisation_name": "Vodafone",
            "salary_range": "$1001-$2000",
            "job_title": "Software Engineer"
        }]"""

        result = parser.parse_placement_details(json_str, is_venture=False)
        assert result is not None
        assert result.organisation_name == "Vodafone"
        assert result.job_title == "Software Engineer"

    def test_parse_placement_details_venture(self) -> None:
        """Test parsing placement_details for venture."""
        parser = JSONParser()
        json_str = """[{
            "business_name": "TechStart",
            "job_start_date": "2022-04-01",
            "jobs_created_to_date": 15,
            "capital_secured_todate": 50000.0,
            "female_opp_todate": 8
        }]"""

        result = parser.parse_placement_details(json_str, is_venture=True)
        assert result is not None
        assert result.business_name == "TechStart"
        assert result.jobs_created_to_date == 15


class TestSkillsParser:
    """Test skills parser."""

    def test_parse_simple_skills(self) -> None:
        """Test parsing simple comma-separated skills."""
        parser = SkillsParser()
        skills = parser.parse_skills("Python, Data Analysis, SQL")

        assert len(skills) == 3
        assert skills[0].name == "Python"
        assert skills[0].id == "python"
        assert skills[1].name == "Data Analysis"
        assert skills[1].id == "data_analysis"

    def test_parse_empty_skills(self) -> None:
        """Test parsing empty skills string."""
        parser = SkillsParser()
        skills = parser.parse_skills("")
        assert len(skills) == 0

        skills = parser.parse_skills(None)
        assert len(skills) == 0

    def test_parse_skills_with_na(self) -> None:
        """Test parsing skills with n/a values."""
        parser = SkillsParser()
        skills = parser.parse_skills("Python, n/a, Data Analysis")

        assert len(skills) == 2
        assert skills[0].name == "Python"
        assert skills[1].name == "Data Analysis"

    def test_parse_duplicate_skills(self) -> None:
        """Test parsing removes duplicates."""
        parser = SkillsParser()
        skills = parser.parse_skills("Python, python, PYTHON")

        assert len(skills) == 1
        assert skills[0].id == "python"

    def test_parse_max_skills_limit(self) -> None:
        """Test max skills limit."""
        parser = SkillsParser(max_skills=3)
        skills = parser.parse_skills("Skill1, Skill2, Skill3, Skill4, Skill5")

        assert len(skills) == 3

    def test_categorize_technical_skill(self) -> None:
        """Test technical skill categorization."""
        parser = SkillsParser()
        skills = parser.parse_skills("Python")

        assert skills[0].category == "Technical"

    def test_categorize_soft_skill(self) -> None:
        """Test soft skill categorization."""
        parser = SkillsParser()
        skills = parser.parse_skills("Communication")

        assert skills[0].category == "Soft Skill"


class TestGeoNormalizer:
    """Test geographic normalizer."""

    def test_normalize_country_code(self) -> None:
        """Test country name to code conversion."""
        normalizer = GeoNormalizer()
        assert normalizer.normalize_country_code("Egypt") == "EG"
        assert normalizer.normalize_country_code("Ghana") == "GH"
        assert normalizer.normalize_country_code("Nigeria") == "NG"

    def test_normalize_country_code_case_insensitive(self) -> None:
        """Test case-insensitive country lookup."""
        normalizer = GeoNormalizer()
        assert normalizer.normalize_country_code("EGYPT") == "EG"
        assert normalizer.normalize_country_code("egypt") == "EG"

    def test_normalize_unknown_country(self) -> None:
        """Test unknown country returns first 2 letters."""
        normalizer = GeoNormalizer()
        result = normalizer.normalize_country_code("Unknown Country")
        assert result == "UN"

    def test_create_country_node(self) -> None:
        """Test creating CountryNode."""
        normalizer = GeoNormalizer()
        node = normalizer.create_country_node("Egypt", 26.8206, 30.8025)

        assert node is not None
        assert node.code == "EG"
        assert node.name == "Egypt"
        assert node.latitude == 26.8206

    def test_create_city_node(self) -> None:
        """Test creating CityNode."""
        normalizer = GeoNormalizer()
        node = normalizer.create_city_node("Cairo", "EG", 30.0444, 31.2357)

        assert node is not None
        assert node.id == "EG-CAI"
        assert node.name == "Cairo"
        assert node.country_code == "EG"

    def test_create_city_node_missing_data(self) -> None:
        """Test creating CityNode with missing data returns None."""
        normalizer = GeoNormalizer()
        node = normalizer.create_city_node(None, "EG")
        assert node is None

        node = normalizer.create_city_node("Cairo", None)
        assert node is None


class TestStateDeriver:
    """Test state deriver."""

    def test_derive_learning_state_graduate(self) -> None:
        """Test deriving graduate state."""
        deriver = StateDeriver()
        state = deriver.derive_learning_state(
            is_active=0, is_graduate=1, is_dropped=0
        )
        assert state == LearningState.GRADUATE

    def test_derive_learning_state_active(self) -> None:
        """Test deriving active state."""
        deriver = StateDeriver()
        state = deriver.derive_learning_state(
            is_active=1, is_graduate=0, is_dropped=0
        )
        assert state == LearningState.ACTIVE

    def test_derive_learning_state_dropped_out(self) -> None:
        """Test deriving dropped out state."""
        deriver = StateDeriver()
        state = deriver.derive_learning_state(
            is_active=0, is_graduate=0, is_dropped=1
        )
        assert state == LearningState.DROPPED_OUT

    def test_derive_learning_state_inactive(self) -> None:
        """Test deriving inactive state."""
        deriver = StateDeriver()
        state = deriver.derive_learning_state(
            is_active=0, is_graduate=0, is_dropped=0
        )
        assert state == LearningState.INACTIVE

    def test_derive_professional_status_wage_employed(self) -> None:
        """Test deriving wage employed status."""
        deriver = StateDeriver()
        status = deriver.derive_professional_status(
            is_venture=0, is_freelancer=0, is_wage=1
        )
        assert status == ProfessionalStatus.WAGE_EMPLOYED

    def test_derive_professional_status_entrepreneur(self) -> None:
        """Test deriving entrepreneur status."""
        deriver = StateDeriver()
        status = deriver.derive_professional_status(
            is_venture=1, is_freelancer=0, is_wage=0
        )
        assert status == ProfessionalStatus.ENTREPRENEUR

    def test_derive_professional_status_multiple(self) -> None:
        """Test deriving multiple status from multiple current jobs."""
        deriver = StateDeriver()
        # Multiple status comes from having 2+ current jobs (from employment_details)
        status = deriver.derive_professional_status(
            is_venture=0, is_freelancer=0, is_wage=0,
            current_job_count=2  # Has 2 current jobs
        )
        assert status == ProfessionalStatus.MULTIPLE

    def test_derive_professional_status_unemployed(self) -> None:
        """Test deriving unemployed status."""
        deriver = StateDeriver()
        status = deriver.derive_professional_status(
            is_venture=0, is_freelancer=0, is_wage=0
        )
        assert status == ProfessionalStatus.UNEMPLOYED

    def test_derive_professional_status_from_employment_single_job(self) -> None:
        """Test deriving status from employment_details with single current job."""
        deriver = StateDeriver()
        # Flags say unemployed, but has 1 current job (from employment_details)
        status = deriver.derive_professional_status(
            is_venture=0,
            is_freelancer=0,
            is_wage=0,
            current_job_count=1,  # Has 1 current job
        )
        # Should trust employment_details over flags
        assert status == ProfessionalStatus.WAGE_EMPLOYED

    def test_derive_professional_status_from_employment_multiple_jobs(self) -> None:
        """Test deriving status from employment_details with multiple current jobs."""
        deriver = StateDeriver()
        # Has 2 current jobs (from employment_details)
        status = deriver.derive_professional_status(
            is_venture=0,
            is_freelancer=0,
            is_wage=0,
            current_job_count=2,  # Has 2 current jobs
        )
        assert status == ProfessionalStatus.MULTIPLE

    def test_derive_professional_status_no_current_jobs_fallback_to_flags(self) -> None:
        """Test that when employment_details has no current jobs, fallback to flags."""
        deriver = StateDeriver()
        # Has past employment but no current jobs, flags say entrepreneur
        status = deriver.derive_professional_status(
            is_venture=1,
            is_freelancer=0,
            is_wage=0,
            current_job_count=0,  # No current jobs
        )
        # Should fall back to flags
        assert status == ProfessionalStatus.ENTREPRENEUR

    def test_derive_professional_status_empty_employment_list(self) -> None:
        """Test that empty employment list falls back to flags."""
        deriver = StateDeriver()
        status = deriver.derive_professional_status(
            is_venture=0,
            is_freelancer=0,
            is_wage=1,
            current_job_count=0,  # No employment data
        )
        # Note: is_freelancer is UNUSED in the dataset (always 0)
        # The new logic doesn't check is_freelancer
        assert status == ProfessionalStatus.WAGE_EMPLOYED

    def test_create_learning_state_node(self) -> None:
        """Test creating LearningStateNode."""
        deriver = StateDeriver(default_snapshot_date="2025-10-06")
        node = deriver.create_learning_state_node(LearningState.ACTIVE)

        assert node.state == LearningState.ACTIVE
        assert node.start_date == date(2025, 10, 6)
        assert node.is_current is True

    def test_create_professional_status_node(self) -> None:
        """Test creating ProfessionalStatusNode."""
        deriver = StateDeriver(default_snapshot_date="2025-10-06")
        node = deriver.create_professional_status_node(ProfessionalStatus.WAGE_EMPLOYED)

        assert node.status == ProfessionalStatus.WAGE_EMPLOYED
        assert node.start_date == date(2025, 10, 6)
        assert node.is_current is True


class TestDateConverter:
    """Test date converter."""

    def test_convert_valid_date(self) -> None:
        """Test converting valid date string."""
        converter = DateConverter()
        result = converter.convert_date("2024-01-15")
        assert result == date(2024, 1, 15)

    def test_convert_invalid_marker(self) -> None:
        """Test converting invalid date marker returns None."""
        converter = DateConverter()
        assert converter.convert_date("1970-01-01") is None
        assert converter.convert_date("9999-12-31") is None

    def test_convert_out_of_range_year(self) -> None:
        """Test converting date with year out of range."""
        converter = DateConverter(min_year=2000, max_year=2030)
        assert converter.convert_date("1995-01-01") is None
        assert converter.convert_date("2035-01-01") is None

    def test_convert_invalid_date(self) -> None:
        """Test converting invalid date string."""
        converter = DateConverter()
        assert converter.convert_date("invalid") is None
        assert converter.convert_date("") is None
        assert converter.convert_date(None) is None


class TestUtils:
    """Test utility functions."""

    def test_normalize_string(self) -> None:
        """Test string normalization."""
        from utils.helpers import normalize_string

        assert normalize_string("  Test  ") == "Test"
        assert normalize_string("n/a") is None
        assert normalize_string("") is None

    def test_normalize_skill_name(self) -> None:
        """Test skill name normalization."""
        from utils.helpers import normalize_skill_name

        assert normalize_skill_name("Data Analysis") == "data_analysis"
        assert normalize_skill_name("Python 3.x") == "python_3x"
        assert normalize_skill_name("C++") == "c"

    def test_create_city_id(self) -> None:
        """Test city ID creation."""
        from utils.helpers import create_city_id

        assert create_city_id("Cairo", "EG") == "EG-CAI"
        assert create_city_id("Alexandria", "EG") == "EG-ALE"

    def test_parse_date(self) -> None:
        """Test date parsing."""
        from utils.helpers import parse_date

        assert parse_date("2024-01-15") == date(2024, 1, 15)
        assert parse_date("1970-01-01") is None
        assert parse_date(None) is None

    def test_parse_numeric(self) -> None:
        """Test numeric parsing."""
        from utils.helpers import parse_numeric

        assert parse_numeric("95.5") == 95.5
        assert parse_numeric(-99) is None
        assert parse_numeric("-99") is None

    def test_parse_boolean(self) -> None:
        """Test boolean parsing."""
        from utils.helpers import parse_boolean

        assert parse_boolean("1") is True
        assert parse_boolean("0") is False
        assert parse_boolean(1) is True
        assert parse_boolean("true") is True

    def test_generate_id(self) -> None:
        """Test ID generation."""
        from utils.helpers import generate_id

        id1 = generate_id("test")
        id2 = generate_id("test")
        assert id1 == id2
        assert len(id1) == 16


class TestLearningStateHistoryBuilder:
    """Test learning state history builder."""

    def test_empty_learning_details(self) -> None:
        """Test with no learning details returns empty list."""
        builder = LearningStateHistoryBuilder()
        history = builder.build_state_history([])
        assert history == []

    def test_single_program_active(self) -> None:
        """Test single active program creates Active state."""
        builder = LearningStateHistoryBuilder()
        entries = [
            LearningDetailsEntry(
                index="0",
                program_name="Software Engineering",
                cohort_code="SE-2023-01",
                program_start_date="2023-01-15",
                program_end_date="2023-12-15",
                enrollment_status="Active",
                program_graduation_date="",
                lms_overall_score="85",
                no_of_assignments="10",
                no_of_submissions="9",
                no_of_assignment_passed="8",
                assignment_completion_rate="90",
                no_of_milestone="5",
                no_of_milestone_submitted="5",
                no_of_milestone_passed="4",
                milestone_completion_rate="100",
                no_of_test="3",
                no_of_test_submitted="3",
                no_of_test_passed="2",
                test_completion_rate="100",
                completion_rate="85",
            )
        ]

        history = builder.build_state_history(entries)

        assert len(history) == 1
        assert history[0].state == LearningState.ACTIVE
        assert history[0].start_date == date(2023, 1, 15)
        assert history[0].is_current is True
        assert "SE-2023-01" in history[0].reason

    def test_single_program_graduate(self) -> None:
        """Test single completed program creates Active → Graduate states."""
        builder = LearningStateHistoryBuilder()
        entries = [
            LearningDetailsEntry(
                index="0",
                program_name="Software Engineering",
                cohort_code="SE-2023-01",
                program_start_date="2023-01-15",
                program_end_date="2023-12-15",
                enrollment_status="Graduate",
                program_graduation_date="2023-12-20",
                lms_overall_score="90",
                no_of_assignments="10",
                no_of_submissions="10",
                no_of_assignment_passed="10",
                assignment_completion_rate="100",
                no_of_milestone="5",
                no_of_milestone_submitted="5",
                no_of_milestone_passed="5",
                milestone_completion_rate="100",
                no_of_test="3",
                no_of_test_submitted="3",
                no_of_test_passed="3",
                test_completion_rate="100",
                completion_rate="100",
            )
        ]

        history = builder.build_state_history(entries)

        assert len(history) == 2
        # Active state
        assert history[0].state == LearningState.ACTIVE
        assert history[0].start_date == date(2023, 1, 15)
        assert history[0].end_date == date(2023, 12, 20)  # Graduation date
        assert history[0].is_current is False
        # Graduate state
        assert history[1].state == LearningState.GRADUATE
        assert history[1].start_date == date(2023, 12, 20)
        assert history[1].is_current is True
        assert "Graduated" in history[1].reason

    def test_single_program_dropped_out(self) -> None:
        """Test dropped out program creates Active → Dropped Out states."""
        builder = LearningStateHistoryBuilder()
        entries = [
            LearningDetailsEntry(
                index="0",
                program_name="Data Science",
                cohort_code="DS-2023-02",
                program_start_date="2023-03-01",
                program_end_date="2023-06-15",
                enrollment_status="Dropped Out",
                program_graduation_date="",
                lms_overall_score="45",
                no_of_assignments="10",
                no_of_submissions="4",
                no_of_assignment_passed="3",
                assignment_completion_rate="40",
                no_of_milestone="5",
                no_of_milestone_submitted="2",
                no_of_milestone_passed="1",
                milestone_completion_rate="40",
                no_of_test="3",
                no_of_test_submitted="1",
                no_of_test_passed="0",
                test_completion_rate="33",
                completion_rate="40",
            )
        ]

        history = builder.build_state_history(entries)

        assert len(history) == 2
        # Active state
        assert history[0].state == LearningState.ACTIVE
        assert history[0].start_date == date(2023, 3, 1)
        assert history[0].end_date == date(2023, 6, 15)
        assert history[0].is_current is False
        # Dropped Out state
        assert history[1].state == LearningState.DROPPED_OUT
        assert history[1].start_date == date(2023, 6, 15)
        assert history[1].is_current is True
        assert "Dropped out" in history[1].reason

    def test_multiple_programs_with_gap(self) -> None:
        """Test multiple programs with large gap creates Inactive state."""
        builder = LearningStateHistoryBuilder(inactive_gap_months=6)
        entries = [
            LearningDetailsEntry(
                index="0",
                program_name="Program 1",
                cohort_code="P1-2023",
                program_start_date="2023-01-01",
                program_end_date="2023-06-30",
                enrollment_status="Graduate",
                program_graduation_date="2023-06-30",
                lms_overall_score="90",
                no_of_assignments="10",
                no_of_submissions="10",
                no_of_assignment_passed="10",
                assignment_completion_rate="100",
                no_of_milestone="5",
                no_of_milestone_submitted="5",
                no_of_milestone_passed="5",
                milestone_completion_rate="100",
                no_of_test="3",
                no_of_test_submitted="3",
                no_of_test_passed="3",
                test_completion_rate="100",
                completion_rate="100",
            ),
            LearningDetailsEntry(
                index="1",
                program_name="Program 2",
                cohort_code="P2-2024",
                program_start_date="2024-03-01",  # 8 month gap
                program_end_date="2024-08-31",
                enrollment_status="Active",
                program_graduation_date="",
                lms_overall_score="85",
                no_of_assignments="10",
                no_of_submissions="9",
                no_of_assignment_passed="8",
                assignment_completion_rate="90",
                no_of_milestone="5",
                no_of_milestone_submitted="5",
                no_of_milestone_passed="4",
                milestone_completion_rate="100",
                no_of_test="3",
                no_of_test_submitted="3",
                no_of_test_passed="2",
                test_completion_rate="100",
                completion_rate="85",
            ),
        ]

        history = builder.build_state_history(entries)

        # Should create: Active → Graduate → Inactive → Active
        assert len(history) == 4
        assert history[0].state == LearningState.ACTIVE  # Program 1 Active
        assert history[1].state == LearningState.GRADUATE  # Program 1 Graduate
        assert history[2].state == LearningState.INACTIVE  # Gap
        assert history[3].state == LearningState.ACTIVE  # Program 2 Active

        # Verify Inactive period
        assert history[2].start_date == date(2023, 6, 30)
        assert history[2].end_date == date(2024, 3, 1)
        assert "Gap" in history[2].reason

        # Only last state is current
        assert history[3].is_current is True

    def test_multiple_programs_no_gap(self) -> None:
        """Test multiple programs with small gap (no Inactive state)."""
        builder = LearningStateHistoryBuilder(inactive_gap_months=6)
        entries = [
            LearningDetailsEntry(
                index="0",
                program_name="Program 1",
                cohort_code="P1-2023",
                program_start_date="2023-01-01",
                program_end_date="2023-06-30",
                enrollment_status="Graduate",
                program_graduation_date="2023-06-30",
                lms_overall_score="90",
                no_of_assignments="10",
                no_of_submissions="10",
                no_of_assignment_passed="10",
                assignment_completion_rate="100",
                no_of_milestone="5",
                no_of_milestone_submitted="5",
                no_of_milestone_passed="5",
                milestone_completion_rate="100",
                no_of_test="3",
                no_of_test_submitted="3",
                no_of_test_passed="3",
                test_completion_rate="100",
                completion_rate="100",
            ),
            LearningDetailsEntry(
                index="1",
                program_name="Program 2",
                cohort_code="P2-2023",
                program_start_date="2023-08-01",  # 1 month gap (< 6 months)
                program_end_date="2023-12-31",
                enrollment_status="Active",
                program_graduation_date="",
                lms_overall_score="85",
                no_of_assignments="10",
                no_of_submissions="9",
                no_of_assignment_passed="8",
                assignment_completion_rate="90",
                no_of_milestone="5",
                no_of_milestone_submitted="5",
                no_of_milestone_passed="4",
                milestone_completion_rate="100",
                no_of_test="3",
                no_of_test_submitted="3",
                no_of_test_passed="2",
                test_completion_rate="100",
                completion_rate="85",
            ),
        ]

        history = builder.build_state_history(entries)

        # Should create: Active → Graduate → Active (NO Inactive)
        assert len(history) == 3
        assert history[0].state == LearningState.ACTIVE
        assert history[1].state == LearningState.GRADUATE
        assert history[2].state == LearningState.ACTIVE

        # No Inactive state created
        assert all(state.state != LearningState.INACTIVE for state in history)

    def test_invalid_dates_skipped(self) -> None:
        """Test that programs with invalid dates are skipped."""
        builder = LearningStateHistoryBuilder()
        entries = [
            LearningDetailsEntry(
                index="0",
                program_name="Invalid Program",
                cohort_code="INV-2023",
                program_start_date="invalid-date",  # Invalid
                program_end_date="2023-12-31",
                enrollment_status="Active",
                program_graduation_date="",
                lms_overall_score="85",
                no_of_assignments="10",
                no_of_submissions="9",
                no_of_assignment_passed="8",
                assignment_completion_rate="90",
                no_of_milestone="5",
                no_of_milestone_submitted="5",
                no_of_milestone_passed="4",
                milestone_completion_rate="100",
                no_of_test="3",
                no_of_test_submitted="3",
                no_of_test_passed="2",
                test_completion_rate="100",
                completion_rate="85",
            )
        ]

        history = builder.build_state_history(entries)

        # Invalid program should be skipped
        assert history == []


class TestProfessionalStatusHistoryBuilder:
    """Test professional status history builder."""

    def test_empty_employment_details(self) -> None:
        """Test with no employment details returns initial unemployed."""
        builder = ProfessionalStatusHistoryBuilder(infer_initial_unemployment=True)
        history = builder.build_status_history([])
        assert len(history) == 1
        assert history[0].status == ProfessionalStatus.UNEMPLOYED

    def test_empty_employment_no_inference(self) -> None:
        """Test with no employment and no inference returns empty."""
        builder = ProfessionalStatusHistoryBuilder(infer_initial_unemployment=False)
        history = builder.build_status_history([])
        assert history == []

    def test_single_job_wage_employed(self) -> None:
        """Test single wage employment creates Unemployed → Wage Employed."""
        builder = ProfessionalStatusHistoryBuilder()
        entries = [
            EmploymentDetailsEntry(
                index="0",
                organization_name="Tech Corp",
                start_date="2023-01-15",
                end_date="",  # Current job
                country="Egypt",
                job_title="Software Engineer",
                is_current="1",
                duration_in_years="1.5",
            )
        ]

        history = builder.build_status_history(entries)

        assert len(history) == 2
        # Initial unemployed
        assert history[0].status == ProfessionalStatus.UNEMPLOYED
        assert history[0].end_date == date(2023, 1, 15)
        # Wage employed
        assert history[1].status == ProfessionalStatus.WAGE_EMPLOYED
        assert history[1].start_date == date(2023, 1, 15)
        assert history[1].is_current is True
        assert "Tech Corp" in history[1].details

    def test_single_job_entrepreneur(self) -> None:
        """Test venture/entrepreneur job creates Unemployed → Entrepreneur."""
        builder = ProfessionalStatusHistoryBuilder()
        entries = [
            EmploymentDetailsEntry(
                index="0",
                organization_name="My Startup",
                start_date="2023-06-01",
                end_date="",
                country="Kenya",
                job_title="Founder & CEO",
                is_current="1",
                duration_in_years="0.5",
            )
        ]

        history = builder.build_status_history(entries)

        assert len(history) == 2
        assert history[0].status == ProfessionalStatus.UNEMPLOYED
        assert history[1].status == ProfessionalStatus.ENTREPRENEUR
        assert history[1].is_current is True
        assert "Founder" in history[1].details

    def test_single_job_freelancer(self) -> None:
        """Test freelance job creates Unemployed → Freelancer."""
        builder = ProfessionalStatusHistoryBuilder()
        entries = [
            EmploymentDetailsEntry(
                index="0",
                organization_name="Self-Employed",
                start_date="2023-03-01",
                end_date="",
                country="Nigeria",
                job_title="Freelance Developer",
                is_current="1",
                duration_in_years="1.0",
            )
        ]

        history = builder.build_status_history(entries)

        assert len(history) == 2
        assert history[0].status == ProfessionalStatus.UNEMPLOYED
        assert history[1].status == ProfessionalStatus.FREELANCER
        assert history[1].is_current is True

    def test_job_ended_unemployed(self) -> None:
        """Test ended job creates Unemployed → Wage Employed → Unemployed."""
        builder = ProfessionalStatusHistoryBuilder()
        entries = [
            EmploymentDetailsEntry(
                index="0",
                organization_name="Old Corp",
                start_date="2023-01-01",
                end_date="2023-12-31",
                country="Egypt",
                job_title="Analyst",
                is_current="0",
                duration_in_years="1.0",
            )
        ]

        # No current status flags, so should create final unemployed
        history = builder.build_status_history(entries, current_status_flags=None)

        assert len(history) == 3
        assert history[0].status == ProfessionalStatus.UNEMPLOYED  # Before
        assert history[1].status == ProfessionalStatus.WAGE_EMPLOYED  # During
        assert history[1].end_date == date(2023, 12, 31)
        assert history[2].status == ProfessionalStatus.UNEMPLOYED  # After
        assert history[2].start_date == date(2023, 12, 31)
        assert history[2].is_current is True

    def test_multiple_jobs_no_gap(self) -> None:
        """Test consecutive jobs with small gap (no unemployment)."""
        builder = ProfessionalStatusHistoryBuilder(unemployment_gap_months=1)
        entries = [
            EmploymentDetailsEntry(
                index="0",
                organization_name="Company A",
                start_date="2023-01-01",
                end_date="2023-06-30",
                country="Egypt",
                job_title="Junior Dev",
                is_current="0",
                duration_in_years="0.5",
            ),
            EmploymentDetailsEntry(
                index="1",
                organization_name="Company B",
                start_date="2023-07-15",  # 15 days gap
                end_date="",
                country="Egypt",
                job_title="Senior Dev",
                is_current="1",
                duration_in_years="0.5",
            ),
        ]

        history = builder.build_status_history(entries)

        # Should create: Unemployed → Wage(A) → Wage(B)
        assert len(history) == 3
        assert history[0].status == ProfessionalStatus.UNEMPLOYED
        assert history[1].status == ProfessionalStatus.WAGE_EMPLOYED
        assert "Company A" in history[1].details
        assert history[2].status == ProfessionalStatus.WAGE_EMPLOYED
        assert "Company B" in history[2].details
        assert history[2].is_current is True

        # No unemployment gap created
        assert all(s.status != ProfessionalStatus.UNEMPLOYED or "Before" in s.details for s in history)

    def test_multiple_jobs_with_gap(self) -> None:
        """Test jobs with large gap creates unemployment period."""
        builder = ProfessionalStatusHistoryBuilder(unemployment_gap_months=1)
        entries = [
            EmploymentDetailsEntry(
                index="0",
                organization_name="Company A",
                start_date="2023-01-01",
                end_date="2023-03-31",
                country="Egypt",
                job_title="Dev",
                is_current="0",
                duration_in_years="0.25",
            ),
            EmploymentDetailsEntry(
                index="1",
                organization_name="Company B",
                start_date="2023-08-01",  # 4 month gap
                end_date="",
                country="Egypt",
                job_title="Dev",
                is_current="1",
                duration_in_years="0.5",
            ),
        ]

        history = builder.build_status_history(entries)

        # Should create: Unemployed → Wage(A) → Unemployed(gap) → Wage(B)
        assert len(history) == 4
        assert history[0].status == ProfessionalStatus.UNEMPLOYED  # Initial
        assert history[1].status == ProfessionalStatus.WAGE_EMPLOYED  # Job A
        assert history[2].status == ProfessionalStatus.UNEMPLOYED  # Gap
        assert "Gap" in history[2].details
        assert history[2].start_date == date(2023, 3, 31)
        assert history[2].end_date == date(2023, 8, 1)
        assert history[3].status == ProfessionalStatus.WAGE_EMPLOYED  # Job B
        assert history[3].is_current is True

    def test_current_status_from_flags(self) -> None:
        """Test that current status from flags overrides inferred status."""
        builder = ProfessionalStatusHistoryBuilder()
        entries = [
            EmploymentDetailsEntry(
                index="0",
                organization_name="Old Job",
                start_date="2023-01-01",
                end_date="2023-06-30",  # Ended
                country="Egypt",
                job_title="Dev",
                is_current="0",
                duration_in_years="0.5",
            )
        ]

        # Current flags indicate wage employed (new job not in employment_details)
        current_status_flags = {
            "is_wage": True,
            "is_venture": False,
            "is_freelancer": False,
        }

        history = builder.build_status_history(
            entries,
            current_status_flags=current_status_flags,
        )

        # Should create: Unemployed → Wage(Old) → Wage(Current from flags)
        assert len(history) == 3
        assert history[0].status == ProfessionalStatus.UNEMPLOYED
        assert history[1].status == ProfessionalStatus.WAGE_EMPLOYED
        assert history[1].end_date == date(2023, 6, 30)
        assert history[2].status == ProfessionalStatus.WAGE_EMPLOYED
        assert history[2].is_current is True
        assert "placement/flags" in history[2].details

    def test_placement_venture_classification(self) -> None:
        """Test that placement_is_venture affects classification."""
        builder = ProfessionalStatusHistoryBuilder()
        entries = [
            EmploymentDetailsEntry(
                index="0",
                organization_name="TechCo",
                start_date="2023-01-01",
                end_date="",
                country="Egypt",
                job_title="Product Manager",  # Not a venture keyword
                is_current="1",
                duration_in_years="1.0",
            )
        ]

        history = builder.build_status_history(
            entries,
            placement_is_venture=True,  # Placement indicates it's a venture
        )

        # Should classify as entrepreneur because of placement_is_venture
        assert len(history) == 2
        assert history[1].status == ProfessionalStatus.ENTREPRENEUR

    def test_invalid_dates_skipped(self) -> None:
        """Test that jobs with invalid dates are skipped."""
        builder = ProfessionalStatusHistoryBuilder()
        entries = [
            EmploymentDetailsEntry(
                index="0",
                organization_name="Invalid Corp",
                start_date="invalid-date",  # Invalid
                end_date="2023-12-31",
                country="Egypt",
                job_title="Dev",
                is_current="0",
                duration_in_years="1.0",
            )
        ]

        history = builder.build_status_history(entries)

        # Invalid job should be skipped, only initial unemployed created
        assert len(history) == 1
        assert history[0].status == ProfessionalStatus.UNEMPLOYED
