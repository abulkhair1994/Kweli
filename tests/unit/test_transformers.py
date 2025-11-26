"""Unit tests for data transformers."""

from datetime import date

from models.enums import LearningState, ProfessionalStatus
from transformers.date_converter import DateConverter
from transformers.geo_normalizer import GeoNormalizer
from transformers.json_parser import JSONParser
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
