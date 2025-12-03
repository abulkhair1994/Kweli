"""
Relationship models for the Impact Learners Knowledge Graph.

This module defines Pydantic models for all relationship types in the graph database.
Relationships include rich properties for metadata about connections.
"""

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from kweli.etl.models.enums import EmploymentType, EnrollmentStatus, SalaryRange


class HasSkillRelationship(BaseModel):
    """Learner → Skill relationship."""

    proficiency_level: str | None = Field(
        None, description="Skill proficiency (e.g., 'Beginner', 'Intermediate', 'Expert')"
    )
    source: str = Field("Profile", description="Where skill was reported from")
    acquired_date: date | None = Field(None, description="When skill was acquired")
    last_updated: datetime = Field(default_factory=datetime.utcnow)


class EnrolledInRelationship(BaseModel):
    """Learner → Program enrollment relationship with rich performance metrics."""

    index: int = Field(..., description="Enrollment index")
    cohort_code: str = Field(..., description="Cohort code")
    enrollment_status: EnrollmentStatus = Field(..., description="Current enrollment status")

    # Dates
    start_date: date = Field(..., description="Program start date")
    end_date: date | None = Field(None, description="Program end date")
    graduation_date: date | None = Field(None, description="Graduation date")

    # Performance Metrics
    lms_overall_score: float | None = Field(None, description="Overall LMS score")
    completion_rate: float | None = Field(None, description="Overall completion rate")

    # Assignment Metrics
    number_of_assignments: int | None = Field(None, description="Total assignments")
    number_of_submissions: int | None = Field(None, description="Assignments submitted")
    number_of_assignments_passed: int | None = Field(None, description="Assignments passed")
    assignment_completion_rate: float | None = Field(None, description="Assignment completion %")

    # Milestone Metrics
    number_of_milestones: int | None = Field(None, description="Total milestones")
    number_of_milestones_submitted: int | None = Field(None, description="Milestones submitted")
    number_of_milestones_passed: int | None = Field(None, description="Milestones passed")
    milestone_completion_rate: float | None = Field(None, description="Milestone completion %")

    # Test Metrics
    number_of_tests: int | None = Field(None, description="Total tests")
    number_of_tests_submitted: int | None = Field(None, description="Tests submitted")
    number_of_tests_passed: int | None = Field(None, description="Tests passed")
    test_completion_rate: float | None = Field(None, description="Test completion %")

    # Derived
    is_completed: bool = Field(False, description="Derived from enrollment_status")
    is_dropped: bool = Field(False, description="Derived from enrollment_status")
    duration: int | None = Field(None, description="Duration in days")

    @field_validator(
        "lms_overall_score",
        "completion_rate",
        "assignment_completion_rate",
        "milestone_completion_rate",
        "test_completion_rate",
        mode="before",
    )
    @classmethod
    def handle_missing_values(cls, v: float | str | None) -> float | None:
        """Convert -99 to None."""
        if v in (-99, "-99", -99.0):
            return None
        if isinstance(v, str):
            try:
                return float(v)
            except ValueError:
                return None
        return v

    @field_validator("graduation_date", mode="before")
    @classmethod
    def handle_invalid_graduation_date(cls, v: date | str | None) -> date | None:
        """Convert 1970-01-01 to None."""
        if v and str(v).startswith("1970-01-01"):
            return None
        return v

    @model_validator(mode="after")
    def derive_flags(self) -> "EnrolledInRelationship":
        """Derive completion flags and duration."""
        self.is_completed = self.enrollment_status in (
            EnrollmentStatus.COMPLETED,
            EnrollmentStatus.GRADUATED,
        )
        self.is_dropped = self.enrollment_status == EnrollmentStatus.DROPPED_OUT

        # Calculate duration
        if self.start_date and self.end_date:
            self.duration = (self.end_date - self.start_date).days

        return self

    class Config:
        """Pydantic configuration."""

        use_enum_values = True


class WorksForRelationship(BaseModel):
    """Learner → Company employment relationship."""

    position: str | None = Field(None, description="Job title/position")
    department: str | None = Field(None, description="Department/field")
    employment_type: EmploymentType | None = Field(None, description="Employment type")

    # Dates
    start_date: date | None = Field(None, description="Employment start date")
    end_date: date | None = Field(None, description="Employment end date")
    is_current: bool = Field(True, description="Is this current employment?")

    # Compensation
    salary_range: SalaryRange | None = Field(None, description="Salary range")

    # Metadata
    source: Literal["placement_details", "employment_details"] = Field(
        ..., description="Data source"
    )
    duration: int | None = Field(None, description="Duration in months")

    @model_validator(mode="after")
    def derive_current_and_duration(self) -> "WorksForRelationship":
        """Derive is_current and duration."""
        self.is_current = self.end_date is None

        if self.start_date and self.end_date:
            days = (self.end_date - self.start_date).days
            self.duration = max(1, days // 30)  # Convert to months

        return self

    class Config:
        """Pydantic configuration."""

        use_enum_values = True


class RunsVentureRelationship(BaseModel):
    """Learner → Company relationship for entrepreneurs."""

    role: str = Field("Founder", description="Role in venture")
    start_date: date | None = Field(None, description="Venture start date")
    end_date: date | None = Field(None, description="Venture end date")
    is_current: bool = Field(True, description="Is venture currently active?")

    # Impact Metrics (specific to ventures)
    jobs_created: int | None = Field(None, description="Jobs created to date")
    capital_secured: float | None = Field(None, description="Capital secured to date in USD")
    female_opportunities: int | None = Field(
        None, description="Female employment opportunities created"
    )


class InLearningStateRelationship(BaseModel):
    """Learner → LearningState temporal relationship."""

    transition_date: datetime = Field(..., description="When this state transition occurred")
    notes: str | None = Field(None, description="Notes about the transition")


class HasProfessionalStatusRelationship(BaseModel):
    """Learner → ProfessionalStatus temporal relationship."""

    transition_date: datetime = Field(..., description="When this status transition occurred")
    notes: str | None = Field(None, description="Notes about the transition")


class InCityRelationship(BaseModel):
    """City → Country relationship (for geographic hierarchy)."""

    since: date | None = Field(None, description="When city became part of this country")


# Export all relationship models
__all__ = [
    "HasSkillRelationship",
    "EnrolledInRelationship",
    "WorksForRelationship",
    "RunsVentureRelationship",
    "InLearningStateRelationship",
    "HasProfessionalStatusRelationship",
    "InCityRelationship",
]
