"""
ETL Loader.

Loads graph entities into Neo4j database.
"""

from collections.abc import Callable
from typing import Any

from structlog.types import FilteringBoundLogger

from etl.batch_accumulator import BatchData
from etl.transformer import GraphEntities
from models.relationships import EnrolledInRelationship, HasSkillRelationship, WorksForRelationship
from neo4j_ops.batch_ops import BatchOperations
from neo4j_ops.connection import Neo4jConnection
from neo4j_ops.node_creator import NodeCreator
from neo4j_ops.relationship_creator import RelationshipCreator
from utils.logger import get_logger


class Loader:
    """Load graph entities to Neo4j."""

    def __init__(
        self,
        connection: Neo4jConnection,
        logger: FilteringBoundLogger | None = None,
    ) -> None:
        """
        Initialize loader.

        Args:
            connection: Neo4j connection
            logger: Optional logger instance
        """
        self.connection = connection
        self.logger = logger or get_logger(__name__)
        self.node_creator = NodeCreator(connection, logger)
        self.relationship_creator = RelationshipCreator(connection, logger)
        self.batch_ops = BatchOperations(connection, batch_size=1000, logger=logger)

    # ====================
    # Helper Methods
    # ====================

    @staticmethod
    def _parse_float(value: str) -> float | None:
        """Parse float value, treating -99.0 as NULL."""
        try:
            f = float(value)
            return None if f == -99.0 else f
        except (ValueError, TypeError):
            return None

    @staticmethod
    def _parse_int(value: str) -> int | None:
        """Parse integer value."""
        try:
            return int(float(value))
        except (ValueError, TypeError):
            return None

    def _load_nodes(
        self,
        items: list,
        creator_method: Callable,
        entity_name: str,
        id_extractor: Callable | None = None,
    ) -> None:
        """
        Generic method to load nodes one by one.

        Args:
            items: List of items to load
            creator_method: Method to create each node
            entity_name: Name of entity for logging
            id_extractor: Optional function to extract ID for logging
        """
        for item in items:
            try:
                creator_method(item)
            except Exception as e:
                log_data = {"error": str(e)}
                if id_extractor:
                    log_data[f"{entity_name}_id"] = id_extractor(item)
                self.logger.warning(f"Failed to create {entity_name}", **log_data)

    # ====================
    # Single Entity Loading
    # ====================

    def load_entities(self, entities: GraphEntities) -> None:
        """
        Load all entities from GraphEntities to Neo4j.

        Args:
            entities: GraphEntities container
        """
        try:
            # Load reference nodes first (to satisfy foreign key constraints)
            self._load_nodes(entities.countries, self.node_creator.create_country,
                           "country", lambda c: c.code)
            self._load_nodes(entities.cities, self.node_creator.create_city,
                           "city", lambda c: c.id)
            self._load_nodes(entities.skills, self.node_creator.create_skill,
                           "skill", lambda s: s.id)
            self._load_nodes(entities.programs, self.node_creator.create_program,
                           "program", lambda p: p.id)
            self._load_nodes(entities.companies, self.node_creator.create_company,
                           "company", lambda c: c.id)

            # Load learner node
            if entities.learner:
                self.node_creator.create_learner(entities.learner)

            # Load temporal state nodes
            self._load_nodes(entities.learning_states,
                           self.node_creator.create_learning_state, "learning state")
            self._load_nodes(entities.professional_statuses,
                           self.node_creator.create_professional_status, "professional status")

            # Create relationships (after all nodes exist)
            self._create_relationships(entities)

        except Exception as e:
            self.logger.error(
                "Failed to load entities",
                hashed_email=entities.learner.hashed_email if entities.learner else None,
                error=str(e),
            )
            raise

    def _create_relationships(self, entities: GraphEntities) -> None:
        """Create all relationships for the learner."""
        if not entities.learner:
            return

        learner_id = entities.learner.hashed_email or entities.learner.sand_id
        if not learner_id:
            return

        self.logger.info(
            "Creating relationships",
            learner_id=learner_id,
            skills_count=len(entities.skills),
            programs_count=len(entities.programs),
            companies_count=len(entities.companies),
        )

        # Skills relationships
        self._create_skill_relationships(learner_id, entities.skills)

        # Program enrollment relationships
        self._create_enrollment_relationships(learner_id, entities.learning_details_entries)

        # Employment relationships
        self._create_employment_relationships(learner_id, entities.employment_details_entries)

        # Temporal state relationships
        self._create_state_relationships(learner_id, entities.learning_states,
                                        entities.professional_statuses)

    def _create_skill_relationships(self, learner_id: str, skills: list) -> None:
        """Create HAS_SKILL relationships."""
        for skill in skills:
            try:
                rel = HasSkillRelationship(proficiency_level=None, years_of_experience=None)
                self.relationship_creator.create_has_skill(learner_id, skill.id, rel)
            except Exception as e:
                self.logger.warning("Failed to create skill relationship", error=str(e))

    def _create_enrollment_relationships(self, learner_id: str, entries: list) -> None:
        """Create ENROLLED_IN relationships."""
        from transformers.date_converter import DateConverter
        date_converter = DateConverter(logger=self.logger)

        for entry in entries:
            try:
                self.logger.debug(
                    "Creating program relationship",
                    learner_id=learner_id,
                    program_id=entry.cohort_code,
                    cohort_code=entry.cohort_code,
                )

                rel = EnrolledInRelationship(
                    index=int(entry.index),
                    cohort_code=entry.cohort_code,
                    enrollment_status=entry.enrollment_status,
                    start_date=date_converter.convert_date(entry.program_start_date),
                    end_date=date_converter.convert_date(entry.program_end_date),
                    graduation_date=date_converter.convert_date(entry.program_graduation_date),
                    lms_overall_score=self._parse_float(entry.lms_overall_score),
                    completion_rate=self._parse_float(entry.completion_rate),
                    number_of_assignments=self._parse_int(entry.no_of_assignments),
                    number_of_submissions=self._parse_int(entry.no_of_submissions),
                    number_of_assignments_passed=self._parse_int(entry.no_of_assignment_passed),
                    assignment_completion_rate=self._parse_float(entry.assignment_completion_rate),
                    number_of_milestones=self._parse_int(entry.no_of_milestone),
                    number_of_milestones_submitted=self._parse_int(entry.no_of_milestone_submitted),
                    number_of_milestones_passed=self._parse_int(entry.no_of_milestone_passed),
                    milestone_completion_rate=self._parse_float(entry.milestone_completion_rate),
                    number_of_tests=self._parse_int(entry.no_of_test),
                    number_of_tests_submitted=self._parse_int(entry.no_of_test_submitted),
                    number_of_tests_passed=self._parse_int(entry.no_of_test_passed),
                    test_completion_rate=self._parse_float(entry.test_completion_rate),
                )
                self.relationship_creator.create_enrolled_in(learner_id, entry.cohort_code, rel)
                self.logger.debug("Program relationship created successfully")
            except Exception as e:
                self.logger.warning(
                    "Failed to create program relationship",
                    learner_id=learner_id,
                    error=str(e)
                )

    def _create_employment_relationships(self, learner_id: str, entries: list) -> None:
        """Create WORKS_FOR relationships."""
        from transformers.date_converter import DateConverter
        from utils.helpers import generate_id

        date_converter = DateConverter(logger=self.logger)

        for entry in entries:
            try:
                company_id = generate_id(entry.organization_name)

                self.logger.debug(
                    "Creating employment relationship",
                    learner_id=learner_id,
                    company_id=company_id,
                )

                rel = WorksForRelationship(
                    position=entry.job_title,
                    department=None,
                    employment_type=None,
                    start_date=date_converter.convert_date(entry.start_date),
                    end_date=date_converter.convert_date(entry.end_date),
                    is_current=entry.is_current == "1",
                    salary_range=None,
                    source="employment_details",
                )
                self.relationship_creator.create_works_for(learner_id, company_id, rel)
                self.logger.debug("Employment relationship created successfully")
            except Exception as e:
                self.logger.warning(
                    "Failed to create employment relationship",
                    learner_id=learner_id,
                    error=str(e)
                )

    def _create_state_relationships(
        self, learner_id: str, learning_states: list, professional_statuses: list
    ) -> None:
        """Create temporal state relationships."""
        for state in learning_states:
            self._execute_state_relationship(
                learner_id, "LearningState", "HAS_LEARNING_STATE",
                {"state": state.state, "start_date": state.start_date,
                 "end_date": state.end_date, "is_current": state.is_current},
                "state"
            )
        for status in professional_statuses:
            self._execute_state_relationship(
                learner_id, "ProfessionalStatus", "HAS_PROFESSIONAL_STATUS",
                {"status": status.status, "start_date": status.start_date,
                 "end_date": status.end_date, "is_current": status.is_current},
                "status"
            )

    def _execute_state_relationship(
        self, learner_id: str, node_label: str, rel_type: str, params: dict, key: str
    ) -> None:
        """Execute a temporal state relationship query."""
        try:
            with self.connection.get_session() as session:
                session.run(f"""
                    MATCH (l:Learner {{hashedEmail: $learner_id}})
                    MATCH (n:{node_label} {{{key}: ${key}, startDate: $start_date}})
                    MERGE (l)-[r:{rel_type}]->(n)
                    SET r.validFrom = $start_date, r.validTo = $end_date, r.isCurrent = $is_current
                """, {"learner_id": learner_id, **params})
        except Exception as e:
            self.logger.warning(f"Failed to create {rel_type} relationship", error=str(e))

    # ====================
    # Batch Loading
    # ====================

    def load_batch(self, batch: BatchData) -> None:
        """
        Load a batch of entities using batch operations.

        Args:
            batch: BatchData containing de-duplicated entities
        """
        try:
            # Load reference nodes first (order matters for relationships)
            self._batch_load_countries(batch)
            self._batch_load_cities(batch)
            self._batch_load_skills(batch)
            self._batch_load_programs(batch)
            self._batch_load_companies(batch)

            # Load learner nodes
            self._batch_load_learners(batch)

            # Load temporal state nodes
            self._batch_load_learning_states(batch)
            self._batch_load_professional_statuses(batch)

            # Create relationships (after all nodes exist)
            self._batch_create_skill_relationships(batch)
            self._batch_create_enrollment_relationships(batch)
            self._batch_create_employment_relationships(batch)
            self._batch_create_learning_state_relationships(batch)
            self._batch_create_professional_status_relationships(batch)

        except Exception as e:
            self.logger.error("Failed to load batch", error=str(e))
            raise

    def _batch_load_simple_nodes(
        self, items: dict, node_label: str, mapper: Callable, key_field: str
    ) -> None:
        """Generic batch loader for simple nodes."""
        if not items:
            return
        records = [mapper(item) for item in items.values()]
        self.batch_ops.batch_create_nodes(node_label, records, key_field)

    def _batch_load_countries(self, batch: BatchData) -> None:
        """Load country nodes in batch."""
        self._batch_load_simple_nodes(
            batch.countries, "Country",
            lambda c: {"code": c.code, "name": c.name, "latitude": c.latitude, "longitude": c.longitude},
            "code"
        )

    def _batch_load_cities(self, batch: BatchData) -> None:
        """Load city nodes in batch."""
        self._batch_load_simple_nodes(
            batch.cities, "City",
            lambda c: {"id": c.id, "name": c.name, "countryCode": c.country_code,
                      "latitude": c.latitude, "longitude": c.longitude},
            "id"
        )

    def _batch_load_skills(self, batch: BatchData) -> None:
        """Load skill nodes in batch."""
        self._batch_load_simple_nodes(
            batch.skills, "Skill",
            lambda s: {"id": s.id, "name": s.name, "category": s.category},
            "id"
        )

    def _batch_load_programs(self, batch: BatchData) -> None:
        """Load program nodes in batch."""
        self._batch_load_simple_nodes(
            batch.programs, "Program",
            lambda p: {"id": p.id, "name": p.name, "cohortCode": p.cohort_code, "provider": p.provider},
            "id"
        )

    def _batch_load_companies(self, batch: BatchData) -> None:
        """Load company nodes in batch."""
        self._batch_load_simple_nodes(
            batch.companies, "Company",
            lambda c: {"id": c.id, "name": c.name, "industry": c.industry, "countryCode": c.country_code},
            "id"
        )

    def _batch_load_learners(self, batch: BatchData) -> None:
        """Load learner nodes in batch."""
        if not batch.learners:
            return

        # Filter to only include learners with hashedEmail (required for MERGE)
        valid_learners = [learner for learner in batch.learners if learner.hashed_email is not None]

        if not valid_learners:
            self.logger.warning("No valid learners with hashedEmail in batch")
            return

        records = [self._learner_to_dict(learner) for learner in valid_learners]
        self.batch_ops.batch_create_nodes("Learner", records, "hashedEmail")

    def _learner_to_dict(self, learner) -> dict[str, Any]:
        """Convert learner node to dictionary for batch operations."""
        fields = [
            ("hashedEmail", "hashed_email"), ("sandId", "sand_id"), ("fullName", "full_name"),
            ("profilePhotoUrl", "profile_photo_url"), ("bio", "bio"), ("gender", "gender"),
            ("educationLevel", "education_level"), ("educationField", "education_field"),
            ("countryOfResidenceCode", "country_of_residence_code"),
            ("countryOfOriginCode", "country_of_origin_code"),
            ("cityOfResidenceId", "city_of_residence_id"),
            ("currentLearningState", "current_learning_state"),
            ("currentProfessionalStatus", "current_professional_status"),
            ("isPlaced", "is_placed"), ("isFeatured", "is_featured"), ("isRural", "is_rural"),
            ("descriptionOfLivingLocation", "description_of_living_location"),
            ("hasDisability", "has_disability"), ("typeOfDisability", "type_of_disability"),
            ("isFromLowIncomeHousehold", "is_from_low_income_household"),
            ("snapshotId", "snapshot_id"), ("createdAt", "created_at"), ("updatedAt", "updated_at"),
        ]
        return {neo4j_key: getattr(learner, attr) for neo4j_key, attr in fields}

    def _batch_load_learning_states(self, batch: BatchData) -> None:
        """Load learning state nodes in batch."""
        if not batch.learning_states:
            return
        records = [
            {"state": s.state, "startDate": s.start_date, "endDate": s.end_date,
             "isCurrent": s.is_current, "reason": s.reason}
            for s in batch.learning_states
        ]
        self.batch_ops.batch_execute("""
            UNWIND $records AS record
            MERGE (s:LearningState {state: record.state, startDate: record.startDate})
            SET s.endDate = record.endDate, s.isCurrent = record.isCurrent, s.reason = record.reason
        """, records)

    def _batch_load_professional_statuses(self, batch: BatchData) -> None:
        """Load professional status nodes in batch."""
        if not batch.professional_statuses:
            return
        records = [
            {"status": s.status, "startDate": s.start_date, "endDate": s.end_date,
             "isCurrent": s.is_current, "details": s.details}
            for s in batch.professional_statuses
        ]
        self.batch_ops.batch_execute("""
            UNWIND $records AS record
            MERGE (ps:ProfessionalStatus {status: record.status, startDate: record.startDate})
            SET ps.endDate = record.endDate, ps.isCurrent = record.isCurrent, ps.details = record.details
        """, records)

    def _batch_create_skill_relationships(self, batch: BatchData) -> None:
        """Create HAS_SKILL relationships in batch."""
        if not batch.skill_associations:
            return

        records = [
            {
                "from_id": hashed_email,
                "to_id": skill_id,
                "properties": {"proficiencyLevel": None, "yearsOfExperience": None},
            }
            for hashed_email, skill_id in batch.skill_associations
            if hashed_email is not None
        ]

        if records:
            self.batch_ops.batch_create_relationships(
                "HAS_SKILL", "Learner", "hashedEmail", "Skill", "id", records
            )

    def _batch_create_enrollment_relationships(self, batch: BatchData) -> None:
        """Create ENROLLED_IN relationships in batch."""
        if not batch.learning_entries:
            return

        from transformers.date_converter import DateConverter
        date_converter = DateConverter(logger=self.logger)

        records = []
        for hashed_email, entry in batch.learning_entries:
            if hashed_email is None:
                continue

            records.append({
                "from_id": hashed_email,
                "to_id": entry.cohort_code,
                "properties": {
                    "index": int(entry.index), "cohortCode": entry.cohort_code,
                    "enrollmentStatus": entry.enrollment_status,
                    "startDate": date_converter.convert_date(entry.program_start_date),
                    "endDate": date_converter.convert_date(entry.program_end_date),
                    "graduationDate": date_converter.convert_date(entry.program_graduation_date),
                    "lmsOverallScore": self._parse_float(entry.lms_overall_score),
                    "completionRate": self._parse_float(entry.completion_rate),
                    "numberOfAssignments": self._parse_int(entry.no_of_assignments),
                    "numberOfSubmissions": self._parse_int(entry.no_of_submissions),
                    "numberOfAssignmentsPassed": self._parse_int(entry.no_of_assignment_passed),
                    "assignmentCompletionRate": self._parse_float(entry.assignment_completion_rate),
                    "numberOfMilestones": self._parse_int(entry.no_of_milestone),
                    "numberOfMilestonesSubmitted": self._parse_int(entry.no_of_milestone_submitted),
                    "numberOfMilestonesPassed": self._parse_int(entry.no_of_milestone_passed),
                    "milestoneCompletionRate": self._parse_float(entry.milestone_completion_rate),
                    "numberOfTests": self._parse_int(entry.no_of_test),
                    "numberOfTestsSubmitted": self._parse_int(entry.no_of_test_submitted),
                    "numberOfTestsPassed": self._parse_int(entry.no_of_test_passed),
                    "testCompletionRate": self._parse_float(entry.test_completion_rate),
                },
            })

        if records:
            self.batch_ops.batch_create_relationships(
                "ENROLLED_IN", "Learner", "hashedEmail", "Program", "id", records
            )

    def _batch_create_employment_relationships(self, batch: BatchData) -> None:
        """Create WORKS_FOR relationships in batch."""
        if not batch.employment_entries:
            return

        from transformers.date_converter import DateConverter
        from utils.helpers import generate_id

        date_converter = DateConverter(logger=self.logger)

        records = []
        for hashed_email, entry in batch.employment_entries:
            if hashed_email is None:
                continue

            company_id = generate_id(entry.organization_name)
            records.append({
                "from_id": hashed_email,
                "to_id": company_id,
                "properties": {
                    "position": entry.job_title,
                    "startDate": date_converter.convert_date(entry.start_date),
                    "endDate": date_converter.convert_date(entry.end_date),
                    "isCurrent": entry.is_current == "1",
                    "source": "employment_details",
                },
            })

        if records:
            self.batch_ops.batch_create_relationships(
                "WORKS_FOR", "Learner", "hashedEmail", "Company", "id", records
            )

    def _batch_create_temporal_relationships(
        self, batch: BatchData, rel_type: str, state_attr: str, states_list: list
    ) -> None:
        """Generic method for creating temporal state relationships."""
        if not states_list:
            return
        records = []
        for learner in batch.learners:
            current_state = getattr(learner, state_attr, None)
            if not learner.sand_id or not current_state:
                continue
            for state in states_list:
                state_value = state.state if hasattr(state, 'state') else state.status
                if state_value == current_state:
                    state_key = "state" if hasattr(state, 'state') else "status"
                    records.append({
                        "learner_id": learner.sand_id,
                        state_key: state_value,
                        "start_date": state.start_date,
                        "end_date": state.end_date,
                        "is_current": state.is_current,
                    })
                    break
        if records:
            state_key = "state" if rel_type == "HAS_LEARNING_STATE" else "status"
            node_label = "LearningState" if rel_type == "HAS_LEARNING_STATE" else "ProfessionalStatus"
            self.batch_ops.batch_execute(f"""
                UNWIND $records AS record
                MATCH (l:Learner {{sandId: record.learner_id}})
                MATCH (n:{node_label} {{{state_key}: record.{state_key}, startDate: record.start_date}})
                MERGE (l)-[r:{rel_type}]->(n)
                SET r.validFrom = record.start_date, r.validTo = record.end_date,
                    r.isCurrent = record.is_current
            """, records)

    def _batch_create_learning_state_relationships(self, batch: BatchData) -> None:
        """Create HAS_LEARNING_STATE relationships in batch."""
        self._batch_create_temporal_relationships(
            batch, "HAS_LEARNING_STATE", "current_learning_state", batch.learning_states
        )

    def _batch_create_professional_status_relationships(self, batch: BatchData) -> None:
        """Create HAS_PROFESSIONAL_STATUS relationships in batch."""
        self._batch_create_temporal_relationships(
            batch, "HAS_PROFESSIONAL_STATUS", "current_professional_status",
            batch.professional_statuses
        )

    # ====================
    # Two-Phase Pipeline Helper Methods
    # ====================

    def _batch_create_enrollment_relationships_from_list(self, learning_entries: list) -> None:
        """
        Create ENROLLED_IN relationships from a list (for two-phase pipeline).

        Args:
            learning_entries: List of (sand_id, entry) tuples
        """
        if not learning_entries:
            return

        from transformers.date_converter import DateConverter
        date_converter = DateConverter(logger=self.logger)

        records = []
        for sand_id, entry in learning_entries:
            if sand_id is None:
                continue

            records.append({
                "from_id": sand_id,
                "to_id": entry.cohort_code,
                "properties": {
                    "index": int(entry.index), "cohortCode": entry.cohort_code,
                    "enrollmentStatus": entry.enrollment_status,
                    "startDate": date_converter.convert_date(entry.program_start_date),
                    "endDate": date_converter.convert_date(entry.program_end_date),
                    "graduationDate": date_converter.convert_date(entry.program_graduation_date),
                    "lmsOverallScore": self._parse_float(entry.lms_overall_score),
                    "completionRate": self._parse_float(entry.completion_rate),
                    "numberOfAssignments": self._parse_int(entry.no_of_assignments),
                    "numberOfSubmissions": self._parse_int(entry.no_of_submissions),
                    "numberOfAssignmentsPassed": self._parse_int(entry.no_of_assignment_passed),
                    "assignmentCompletionRate": self._parse_float(entry.assignment_completion_rate),
                    "numberOfMilestones": self._parse_int(entry.no_of_milestone),
                    "numberOfMilestonesSubmitted": self._parse_int(entry.no_of_milestone_submitted),
                    "numberOfMilestonesPassed": self._parse_int(entry.no_of_milestone_passed),
                    "milestoneCompletionRate": self._parse_float(entry.milestone_completion_rate),
                    "numberOfTests": self._parse_int(entry.no_of_test),
                    "numberOfTestsSubmitted": self._parse_int(entry.no_of_test_submitted),
                    "numberOfTestsPassed": self._parse_int(entry.no_of_test_passed),
                    "testCompletionRate": self._parse_float(entry.test_completion_rate),
                },
            })

        if records:
            self.batch_ops.batch_create_relationships(
                "ENROLLED_IN", "Learner", "sandId", "Program", "id", records
            )

    def _batch_create_employment_relationships_from_list(self, employment_entries: list) -> None:
        """
        Create WORKS_FOR relationships from a list (for two-phase pipeline).

        Args:
            employment_entries: List of (sand_id, entry) tuples
        """
        if not employment_entries:
            return

        from transformers.date_converter import DateConverter
        from utils.helpers import generate_id

        date_converter = DateConverter(logger=self.logger)

        records = []
        for sand_id, entry in employment_entries:
            if sand_id is None:
                continue

            company_id = generate_id(entry.organization_name)
            records.append({
                "from_id": sand_id,
                "to_id": company_id,
                "properties": {
                    "position": entry.job_title,
                    "startDate": date_converter.convert_date(entry.start_date),
                    "endDate": date_converter.convert_date(entry.end_date),
                    "isCurrent": entry.is_current == "1",
                    "source": "employment_details",
                },
            })

        if records:
            self.batch_ops.batch_create_relationships(
                "WORKS_FOR", "Learner", "sandId", "Company", "id", records
            )


__all__ = ["Loader"]
