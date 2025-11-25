"""Tests for analytics tools."""


from agent.tools.analytics_tools import (
    get_employment_rate_by_program,
    get_geographic_distribution,
    get_learner_journey,
    get_program_completion_rates,
    get_skills_for_employed_learners,
    get_time_to_employment_stats,
    get_top_countries_by_learners,
    get_top_skills,
)


class TestGetTopCountriesByLearners:
    """Tests for get_top_countries_by_learners tool."""

    def test_default_limit(self):
        """Test with default limit."""
        result = get_top_countries_by_learners.invoke({})
        assert "query" in result
        assert "params" in result
        assert result["params"]["limit"] == 10
        assert "countryOfResidenceCode" in result["query"]

    def test_custom_limit(self):
        """Test with custom limit."""
        result = get_top_countries_by_learners.invoke({"limit": 20})
        assert result["params"]["limit"] == 20

    def test_limit_cap(self):
        """Test that limit is capped at 100."""
        result = get_top_countries_by_learners.invoke({"limit": 500})
        assert result["params"]["limit"] == 100

    def test_uses_hybrid_pattern(self):
        """Test that query uses HYBRID pattern."""
        result = get_top_countries_by_learners.invoke({})
        query = result["query"]
        # Should filter by property, not relationship
        assert "countryOfResidenceCode" in query
        assert "RESIDES_IN" not in query
        # Should join with Country node
        assert "Country" in query


class TestGetProgramCompletionRates:
    """Tests for get_program_completion_rates tool."""

    def test_all_programs(self):
        """Test getting all program completion rates."""
        result = get_program_completion_rates.invoke({})
        assert "query" in result
        assert "ENROLLED_IN" in result["query"]
        assert "completionRate" in result["query"]

    def test_specific_program(self):
        """Test getting completion rate for specific program."""
        result = get_program_completion_rates.invoke({"program_name": "Software Engineering"})
        assert result["params"]["program_name"] == "Software Engineering"
        assert "program_name" in result["query"]

    def test_includes_dropout_rate(self):
        """Test that dropout rate is calculated."""
        result = get_program_completion_rates.invoke({})
        assert "droppedOut" in result["query"]
        assert "dropoutRate" in result["query"]


class TestGetEmploymentRateByProgram:
    """Tests for get_employment_rate_by_program tool."""

    def test_all_programs(self):
        """Test employment rate for all programs."""
        result = get_employment_rate_by_program.invoke({})
        assert "WORKS_FOR" in result["query"]
        assert "employmentRate" in result["query"]

    def test_specific_program(self):
        """Test employment rate for specific program."""
        result = get_employment_rate_by_program.invoke({"program_name": "Data Science"})
        assert result["params"]["program_name"] == "Data Science"

    def test_filters_small_programs(self):
        """Test that small programs are filtered out."""
        result = get_employment_rate_by_program.invoke({})
        # Should only include programs with >100 learners
        assert "totalLearners > 100" in result["query"]


class TestGetTopSkills:
    """Tests for get_top_skills tool."""

    def test_all_categories(self):
        """Test getting top skills across all categories."""
        result = get_top_skills.invoke({})
        assert "HAS_SKILL" in result["query"]
        assert "category" not in result["params"]

    def test_specific_category(self):
        """Test getting skills for specific category."""
        result = get_top_skills.invoke({"category": "Technical"})
        assert result["params"]["category"] == "Technical"
        assert "category" in result["query"]

    def test_custom_limit(self):
        """Test with custom limit."""
        result = get_top_skills.invoke({"limit": 50})
        assert result["params"]["limit"] == 50


class TestGetLearnerJourney:
    """Tests for get_learner_journey tool."""

    def test_requires_email_hash(self):
        """Test that email hash is required."""
        result = get_learner_journey.invoke({"email_hash": "abc123"})
        assert result["params"]["email_hash"] == "abc123"

    def test_includes_all_relationships(self):
        """Test that all relationship types are included."""
        result = get_learner_journey.invoke({"email_hash": "test"})
        query = result["query"]
        assert "HAS_SKILL" in query
        assert "ENROLLED_IN" in query
        assert "WORKS_FOR" in query

    def test_includes_geography(self):
        """Test that geographic info is included."""
        result = get_learner_journey.invoke({"email_hash": "test"})
        query = result["query"]
        assert "Country" in query
        assert "City" in query

    def test_limited_to_one_result(self):
        """Test that result is limited to one learner."""
        result = get_learner_journey.invoke({"email_hash": "test"})
        assert "LIMIT 1" in result["query"]


class TestGetSkillsForEmployedLearners:
    """Tests for get_skills_for_employed_learners tool."""

    def test_all_countries(self):
        """Test skills for employed learners across all countries."""
        result = get_skills_for_employed_learners.invoke({})
        assert "WORKS_FOR" in result["query"]
        assert "HAS_SKILL" in result["query"]

    def test_specific_country(self):
        """Test skills for employed learners in specific country."""
        result = get_skills_for_employed_learners.invoke({"country_code": "EG"})
        assert result["params"]["country_code"] == "EG"
        assert "countryOfResidenceCode" in result["query"]


class TestGetGeographicDistribution:
    """Tests for get_geographic_distribution tool."""

    def test_learners_metric(self):
        """Test geographic distribution of learners."""
        result = get_geographic_distribution.invoke({"metric": "learners"})
        assert "learnerCount" in result["query"]

    def test_programs_metric(self):
        """Test geographic distribution of programs."""
        result = get_geographic_distribution.invoke({"metric": "programs"})
        assert "ENROLLED_IN" in result["query"]
        assert "programCount" in result["query"]

    def test_companies_metric(self):
        """Test geographic distribution of companies."""
        result = get_geographic_distribution.invoke({"metric": "companies"})
        assert "WORKS_FOR" in result["query"]
        assert "companyCount" in result["query"]

    def test_default_metric(self):
        """Test default metric (learners)."""
        result = get_geographic_distribution.invoke({})
        assert "query" in result


class TestGetTimeToEmploymentStats:
    """Tests for get_time_to_employment_stats tool."""

    def test_all_programs(self):
        """Test time to employment across all programs."""
        result = get_time_to_employment_stats.invoke({})
        assert "graduationDate" in result["query"]
        assert "startDate" in result["query"]
        assert "avgDays" in result["query"]
        assert "medianDays" in result["query"]

    def test_specific_program(self):
        """Test time to employment for specific program."""
        result = get_time_to_employment_stats.invoke({"program_name": "Software Engineering"})
        assert result["params"]["program_name"] == "Software Engineering"

    def test_filters_future_employment(self):
        """Test that only employment after graduation is counted."""
        result = get_time_to_employment_stats.invoke({})
        # Should filter for startDate >= graduationDate
        assert "startDate >= e.graduationDate" in result["query"]
