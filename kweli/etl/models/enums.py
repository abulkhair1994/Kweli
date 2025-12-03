"""
Enumeration types for the Impact Learners Knowledge Graph.

This module defines all enum types used across the data model, ensuring
consistent vocabulary and type safety throughout the ETL pipeline.
"""

from enum import Enum


class Gender(str, Enum):
    """Gender categories for learners."""

    MALE = "male"
    FEMALE = "female"
    OTHER = "other/prefer not to say"
    PREFER_NOT_TO_SAY = "prefer not to say"


class EducationLevel(str, Enum):
    """Highest education level attained by learners."""

    COMPLETED_SECONDARY = (
        "Completed secondary school or equivalent and earned a secondary or final "
        "national examination certificate."
    )
    CURRENTLY_ENROLLED_UNIVERSITY = "Currently Enrolled At University/College"
    HIGH_SCHOOL = "High School"
    ASSOCIATE_DEGREE = "Associate Degree"
    UNIVERSITY_DIPLOMA = "University Diploma or equivalent"
    BACHELOR_DEGREE = "Bachelor's degree or equivalent"
    BACHELOR_DEGREE_ALT = "Bachelor'S Degree"
    MASTER_DEGREE = "Master's degree"
    PHD = "PhD"
    PROFESSIONAL_CERTIFICATE = "Professional Certificate"


class EnrollmentStatus(str, Enum):
    """Current status of a learner's enrollment in a program."""

    ENROLLED = "Enrolled"
    ACTIVE = "Active"
    COMPLETED = "Completed"
    GRADUATED = "Graduated"
    DROPPED_OUT = "Dropped Out"
    SUSPENDED = "Suspended"


class LearningState(str, Enum):
    """
    Temporal learning state derived from flags.

    Derived from:
    - is_active_learner
    - is_graduate_learner
    - is_a_dropped_out
    """

    ACTIVE = "Active"
    GRADUATE = "Graduate"
    DROPPED_OUT = "Dropped Out"
    INACTIVE = "Inactive"


class ProfessionalStatus(str, Enum):
    """
    Temporal professional/employment status derived from flags.

    Derived from:
    - is_running_a_venture
    - is_a_freelancer
    - is_wage_employed
    """

    UNEMPLOYED = "Unemployed"
    WAGE_EMPLOYED = "Wage Employed"
    FREELANCER = "Freelancer"
    ENTREPRENEUR = "Entrepreneur"
    MULTIPLE = "Multiple"  # e.g., freelance + venture


class EmploymentType(str, Enum):
    """Type of employment arrangement."""

    FULL_TIME = "Full-time"
    PART_TIME = "Part-time"
    CONTRACT = "Contract"
    INTERNSHIP = "Internship"
    UNCATEGORIZED = "Uncategorized"


class SalaryRange(str, Enum):
    """Salary range categories."""

    RANGE_0_500 = "$0-$500"
    RANGE_501_1000 = "$501-$1000"
    RANGE_1001_2000 = "$1001-$2000"
    RANGE_2001_PLUS = "$2001+"
    NOT_APPLICABLE = "n/a"


class LivingLocation(str, Enum):
    """Type of living location (urban/rural)."""

    URBAN = "Urban"
    RURAL = "Rural"
    PREFER_NOT_TO_SAY = "Prefer not to say"


# Export all enums
__all__ = [
    "Gender",
    "EducationLevel",
    "EnrollmentStatus",
    "LearningState",
    "ProfessionalStatus",
    "EmploymentType",
    "SalaryRange",
    "LivingLocation",
]
