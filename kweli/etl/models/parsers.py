"""
JSON parsing models for complex CSV fields.

This module defines Pydantic models for parsing JSON array fields from the CSV,
such as learning_details, placement_details, employment_details, etc.
"""

from pydantic import BaseModel, Field


class LearningDetailsEntry(BaseModel):
    """
    Single entry from learning_details JSON array.

    Maps directly to the JSON structure in the CSV.
    """

    index: str = Field(..., description="Entry index")
    program_name: str = Field(..., description="Program name")
    cohort_code: str = Field(..., description="Cohort code")
    program_start_date: str = Field(..., description="Start date")
    program_end_date: str = Field(..., description="End date")
    enrollment_status: str = Field(..., description="Enrollment status")
    program_graduation_date: str = Field(..., description="Graduation date")
    lms_overall_score: str = Field(..., description="LMS score")
    no_of_assignments: str = Field(..., description="Total assignments")
    no_of_submissions: str = Field(..., description="Submissions")
    no_of_assignment_passed: str = Field(..., description="Assignments passed")
    assignment_completion_rate: str = Field(..., description="Assignment completion rate")
    no_of_milestone: str = Field(..., description="Total milestones")
    no_of_milestone_submitted: str = Field(..., description="Milestones submitted")
    no_of_milestone_passed: str = Field(..., description="Milestones passed")
    milestone_completion_rate: str = Field(..., description="Milestone completion rate")
    no_of_test: str = Field(..., description="Total tests")
    no_of_test_submitted: str = Field(..., description="Tests submitted")
    no_of_test_passed: str = Field(..., description="Tests passed")
    test_completion_rate: str = Field(..., description="Test completion rate")
    completion_rate: str = Field(..., description="Overall completion rate")


class PlacementDetailsWageEmployment(BaseModel):
    """placement_details JSON for wage/freelance employment.

    Only job_start_date is required. All other fields are optional
    to handle data variations in the source.
    """

    job_start_date: str = Field(..., description="Job start date")
    organisation_name: str | None = Field(None, description="Organization name")
    employment_type: str | None = Field(None, description="Employment type")
    salary_range: str | None = Field(None, description="Salary range")
    job_title: str | None = Field(None, description="Job title")


class PlacementDetailsVenture(BaseModel):
    """placement_details JSON for entrepreneurs/ventures.

    Only job_start_date is required. All other fields are optional
    to handle data variations in the source.
    """

    job_start_date: str = Field(..., description="Venture start date")
    business_name: str | None = Field(None, description="Business/venture name")
    jobs_created_to_date: int | None = Field(None, description="Jobs created")
    capital_secured_todate: float | None = Field(None, description="Capital secured")
    female_opp_todate: int | None = Field(None, description="Female opportunities created")


class EmploymentDetailsEntry(BaseModel):
    """Single entry from employment_details JSON array."""

    index: str = Field(..., description="Entry index")
    organization_name: str = Field(..., description="Institution/company name", alias="organisation_name")
    start_date: str = Field(..., description="Start date")
    end_date: str = Field(..., description="End date")
    country: str = Field(..., description="Country")
    job_title: str = Field(..., description="Job title")
    is_current: str = Field(..., description="Is current employment (1/0)")
    duration_in_years: str = Field(..., description="Duration in years")

    class Config:
        """Pydantic configuration."""

        populate_by_name = True  # Allow both 'organization_name' and 'organisation_name'


class EducationDetailsEntry(BaseModel):
    """Single entry from education_details JSON array."""

    index: str = Field(..., description="Entry index")
    institution_name: str = Field(..., description="Educational institution name")
    start_date: str = Field(..., description="Start date")
    end_date: str = Field(..., description="End date")
    field_of_study: str = Field(..., description="Field of study")
    level_of_study: str = Field(..., description="Education level")
    graduated: str = Field(..., description="Graduated flag (1/0)")


# Export all parser models
__all__ = [
    "LearningDetailsEntry",
    "PlacementDetailsWageEmployment",
    "PlacementDetailsVenture",
    "EmploymentDetailsEntry",
    "EducationDetailsEntry",
]
