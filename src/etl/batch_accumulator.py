"""
Batch Accumulator for ETL Pipeline.

Accumulates entities from multiple rows and prepares them for batch loading.
De-duplicates shared nodes (countries, cities, skills, programs, companies).
"""

from typing import Any

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
from models.parsers import EmploymentDetailsEntry, LearningDetailsEntry


class BatchData:
    """Container for batched entities ready for loading."""

    def __init__(self) -> None:
        """Initialize batch data container."""
        # Unique entities (de-duplicated)
        self.countries: dict[str, CountryNode] = {}  # key: code
        self.cities: dict[str, CityNode] = {}  # key: id
        self.skills: dict[str, SkillNode] = {}  # key: id
        self.programs: dict[str, ProgramNode] = {}  # key: id
        self.companies: dict[str, CompanyNode] = {}  # key: id

        # Non-unique entities (all kept)
        self.learners: list[LearnerNode] = []
        self.learning_states: list[LearningStateNode] = []
        self.professional_statuses: list[ProfessionalStatusNode] = []

        # Relationship data (stored for batch creation)
        self.learning_entries: list[tuple[str, LearningDetailsEntry]] = []  # (hashed_email, entry)
        self.employment_entries: list[tuple[str, EmploymentDetailsEntry]] = []  # (hashed_email, entry)
        self.skill_associations: list[tuple[str, str]] = []  # (hashed_email, skill_id)

    def count_entities(self) -> int:
        """Count total entities in this batch."""
        return (
            len(self.learners)
            + len(self.countries)
            + len(self.cities)
            + len(self.skills)
            + len(self.programs)
            + len(self.companies)
            + len(self.learning_states)
            + len(self.professional_statuses)
        )


class BatchAccumulator:
    """
    Accumulate entities from multiple rows for batch processing.

    De-duplicates shared nodes to avoid creating duplicates in Neo4j.
    """

    def __init__(self, batch_size: int = 1000) -> None:
        """
        Initialize batch accumulator.

        Args:
            batch_size: Number of learners per batch (default: 1000)
        """
        self.batch_size = batch_size
        self.batch_data = BatchData()
        self._learner_count = 0

    def add(
        self,
        learner: LearnerNode,
        countries: list[CountryNode],
        cities: list[CityNode],
        skills: list[SkillNode],
        programs: list[ProgramNode],
        companies: list[CompanyNode],
        learning_states: list[LearningStateNode],
        professional_statuses: list[ProfessionalStatusNode],
        learning_entries: list[Any],
        employment_entries: list[Any],
    ) -> None:
        """
        Add entities from one row to the batch.

        Args:
            learner: Learner node
            countries: Country nodes
            cities: City nodes
            skills: Skill nodes
            programs: Program nodes
            companies: Company nodes
            learning_states: Learning state nodes
            professional_statuses: Professional status nodes
            learning_entries: Learning detail entries (for relationships)
            employment_entries: Employment detail entries (for relationships)
        """
        # Always add learner (unique per row)
        self.batch_data.learners.append(learner)
        self._learner_count += 1

        # De-duplicate countries
        for country in countries:
            if country.code not in self.batch_data.countries:
                self.batch_data.countries[country.code] = country

        # De-duplicate cities
        for city in cities:
            if city.id not in self.batch_data.cities:
                self.batch_data.cities[city.id] = city

        # De-duplicate skills
        for skill in skills:
            if skill.id not in self.batch_data.skills:
                self.batch_data.skills[skill.id] = skill

        # De-duplicate programs
        for program in programs:
            if program.id not in self.batch_data.programs:
                self.batch_data.programs[program.id] = program

        # De-duplicate companies
        for company in companies:
            if company.id not in self.batch_data.companies:
                self.batch_data.companies[company.id] = company

        # Add all learning states (temporal, non-unique)
        self.batch_data.learning_states.extend(learning_states)

        # Add all professional statuses (temporal, non-unique)
        self.batch_data.professional_statuses.extend(professional_statuses)

        # Store relationship entries with learner hashed_email
        hashed_email = learner.hashed_email
        if hashed_email:
            for entry in learning_entries:
                self.batch_data.learning_entries.append((hashed_email, entry))
            for entry in employment_entries:
                self.batch_data.employment_entries.append((hashed_email, entry))
            # Store learner-skill associations
            for skill in skills:
                self.batch_data.skill_associations.append((hashed_email, skill.id))

    def is_full(self) -> bool:
        """Check if batch has reached target size."""
        return self._learner_count >= self.batch_size

    def is_empty(self) -> bool:
        """Check if batch is empty."""
        return self._learner_count == 0

    def get_batch(self) -> BatchData:
        """Get current batch data."""
        return self.batch_data

    def clear(self) -> None:
        """Clear batch and reset counters."""
        self.batch_data = BatchData()
        self._learner_count = 0

    def get_stats(self) -> dict[str, int]:
        """Get statistics about current batch."""
        return {
            "learners": len(self.batch_data.learners),
            "countries": len(self.batch_data.countries),
            "cities": len(self.batch_data.cities),
            "skills": len(self.batch_data.skills),
            "programs": len(self.batch_data.programs),
            "companies": len(self.batch_data.companies),
            "learning_states": len(self.batch_data.learning_states),
            "professional_statuses": len(self.batch_data.professional_statuses),
            "learning_relationships": len(self.batch_data.learning_entries),
            "employment_relationships": len(self.batch_data.employment_entries),
            "skill_relationships": len(self.batch_data.skill_associations),
        }


__all__ = ["BatchAccumulator", "BatchData"]
