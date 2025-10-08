"""
Node models for the Impact Learners Knowledge Graph.

This module defines Pydantic models for all node types in the graph database.
Following the HYBRID approach from best practices to avoid supernodes.
"""

from datetime import date, datetime

from pydantic import BaseModel, Field, field_validator

from models.enums import EducationLevel, Gender, LearningState, ProfessionalStatus


class LearnerNode(BaseModel):
    """
    Primary entity representing a learner/student.

    Uses HYBRID approach for Country/City - stores codes as properties
    to avoid supernode problems (millions of learners → same country).
    """

    # Primary Identifiers
    sand_id: str | None = Field(None, description="Primary unique identifier")
    hashed_email: str | None = Field(None, description="Hashed email identifier")

    # Profile
    full_name: str | None = Field(None, description="Full name")
    profile_photo_url: str | None = Field(None, description="Profile photo URL")
    bio: str | None = Field(None, description="Biography")
    gender: Gender | None = Field(None, description="Gender")

    # Education Background
    education_level: EducationLevel | None = Field(None, description="Highest education level")
    education_field: str | None = Field(None, description="Field of study")

    # Geographic References (HYBRID - property references to avoid supernodes)
    country_of_residence_code: str | None = Field(
        None, description="ISO country code for residence"
    )
    country_of_origin_code: str | None = Field(None, description="ISO country code for origin")
    city_of_residence_id: str | None = Field(None, description="City identifier")

    # Current Status (snapshot in time)
    current_learning_state: LearningState | None = Field(
        None, description="Current learning state"
    )
    current_professional_status: ProfessionalStatus | None = Field(
        None, description="Current professional status"
    )
    is_placed: bool = Field(False, description="Has any employment/placement")
    is_featured: bool = Field(False, description="Featured learner")

    # Socio-Economic Data
    is_rural: bool | None = Field(None, description="Lives in rural area")
    description_of_living_location: str | None = Field(
        None, description="Living location description"
    )
    has_disability: bool | None = Field(None, description="Has disability")
    type_of_disability: str | None = Field(None, description="Type of disability")
    is_from_low_income_household: bool | None = Field(
        None, description="From low-income household"
    )

    # Metadata
    snapshot_id: int | None = Field(None, description="Data snapshot identifier")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    @field_validator('education_level', mode='before')
    @classmethod
    def normalize_education_level(cls, v):
        """Normalize education level to handle case variations."""
        if v is None or v == "n/a":
            return None

        # Try to match case-insensitively
        v_lower = str(v).lower()
        for level in EducationLevel:
            if level.value.lower() == v_lower:
                return level.value

        # Return None if no match (lenient mode)
        return None

    class Config:
        """Pydantic configuration."""

        use_enum_values = True


class CountryNode(BaseModel):
    """
    Reference entity for countries.

    Created as nodes but referenced by properties on Learner (HYBRID approach).
    """

    code: str = Field(..., description="ISO 3166-1 alpha-2 code (e.g., 'EG', 'US')")
    name: str = Field(..., description="Country name")
    latitude: float | None = Field(None, description="Country centroid latitude")
    longitude: float | None = Field(None, description="Country centroid longitude")


class CityNode(BaseModel):
    """Reference entity for cities."""

    id: str = Field(..., description="Unique city identifier (e.g., 'EG-CAI')")
    name: str = Field(..., description="City name")
    country_code: str = Field(..., description="ISO country code")
    latitude: float | None = Field(None, description="City latitude")
    longitude: float | None = Field(None, description="City longitude")


class SkillNode(BaseModel):
    """Individual skill entity."""

    id: str = Field(..., description="Normalized skill ID (e.g., 'python', 'data_analysis')")
    name: str = Field(..., description="Display name (e.g., 'Python', 'Data Analysis')")
    category: str | None = Field(
        None, description="Skill category (e.g., 'Technical', 'Business')"
    )


class ProgramNode(BaseModel):
    """Learning program/course entity."""

    id: str = Field(..., description="Unique program identifier (typically cohort_code)")
    name: str = Field(..., description="Program name")
    cohort_code: str = Field(..., description="Cohort code")
    provider: str | None = Field(None, description="Program provider")


class CompanyNode(BaseModel):
    """Company/organization entity for employment."""

    id: str = Field(..., description="Unique company identifier")
    name: str = Field(..., description="Company/organization name")
    industry: str | None = Field(None, description="Industry sector")
    country_code: str | None = Field(None, description="Country where company is based")


class LearningStateNode(BaseModel):
    """
    Temporal learning state tracking (SCD Type 2).

    Tracks when a learner transitions between states:
    - Active → Dropped Out
    - Active → Graduate
    - Inactive → Active
    """

    state: LearningState = Field(..., description="Learning state")
    start_date: date = Field(..., description="When this state began")
    end_date: date | None = Field(None, description="When this state ended (NULL = current)")
    is_current: bool = Field(True, description="Is this the current state?")
    reason: str | None = Field(None, description="Reason for state change")


class ProfessionalStatusNode(BaseModel):
    """
    Temporal professional status tracking (SCD Type 2).

    Tracks employment status changes over time:
    - Unemployed → Wage Employed
    - Wage Employed → Entrepreneur
    - Freelancer → Multiple (freelance + venture)
    """

    status: ProfessionalStatus = Field(..., description="Professional status")
    start_date: date = Field(..., description="When this status began")
    end_date: date | None = Field(None, description="When this status ended (NULL = current)")
    is_current: bool = Field(True, description="Is this the current status?")
    details: str | None = Field(None, description="Additional details about this status")


# Export all node models
__all__ = [
    "LearnerNode",
    "CountryNode",
    "CityNode",
    "SkillNode",
    "ProgramNode",
    "CompanyNode",
    "LearningStateNode",
    "ProfessionalStatusNode",
]
