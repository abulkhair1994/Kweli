"""
Impact Learners Knowledge Graph Models.

This package contains all Pydantic models for nodes, relationships,
and JSON parsers used in the ETL pipeline.
"""

from kweli.etl.models.enums import (
    EducationLevel,
    EmploymentType,
    EnrollmentStatus,
    Gender,
    LearningState,
    LivingLocation,
    ProfessionalStatus,
    SalaryRange,
)
from kweli.etl.models.nodes import (
    CityNode,
    CompanyNode,
    CountryNode,
    LearnerNode,
    LearningStateNode,
    ProfessionalStatusNode,
    ProgramNode,
    SkillNode,
)
from kweli.etl.models.parsers import (
    EducationDetailsEntry,
    EmploymentDetailsEntry,
    LearningDetailsEntry,
    PlacementDetailsVenture,
    PlacementDetailsWageEmployment,
)
from kweli.etl.models.relationships import (
    EnrolledInRelationship,
    HasProfessionalStatusRelationship,
    HasSkillRelationship,
    InCityRelationship,
    InLearningStateRelationship,
    RunsVentureRelationship,
    WorksForRelationship,
)

__all__ = [
    # Enums
    "Gender",
    "EducationLevel",
    "EnrollmentStatus",
    "LearningState",
    "ProfessionalStatus",
    "EmploymentType",
    "SalaryRange",
    "LivingLocation",
    # Nodes
    "LearnerNode",
    "CountryNode",
    "CityNode",
    "SkillNode",
    "ProgramNode",
    "CompanyNode",
    "LearningStateNode",
    "ProfessionalStatusNode",
    # Relationships
    "HasSkillRelationship",
    "EnrolledInRelationship",
    "WorksForRelationship",
    "RunsVentureRelationship",
    "InLearningStateRelationship",
    "HasProfessionalStatusRelationship",
    "InCityRelationship",
    # Parsers
    "LearningDetailsEntry",
    "PlacementDetailsWageEmployment",
    "PlacementDetailsVenture",
    "EmploymentDetailsEntry",
    "EducationDetailsEntry",
]
