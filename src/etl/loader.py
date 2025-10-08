"""
ETL Loader.

Loads graph entities into Neo4j database.
"""

from structlog.types import FilteringBoundLogger

from etl.transformer import GraphEntities
from models.relationships import HasSkillRelationship, EnrolledInRelationship, WorksForRelationship
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

    def load_entities(self, entities: GraphEntities) -> None:
        """
        Load all entities from GraphEntities to Neo4j.

        Args:
            entities: GraphEntities container
        """
        try:
            # Load reference nodes first (to satisfy foreign key constraints)
            self._load_countries(entities)
            self._load_cities(entities)
            self._load_skills(entities)
            self._load_programs(entities)
            self._load_companies(entities)

            # Load learner node
            if entities.learner:
                self.node_creator.create_learner(entities.learner)

            # Load temporal state nodes
            self._load_states(entities)

            # Create relationships (after all nodes exist)
            self._create_relationships(entities)

        except Exception as e:
            self.logger.error(
                "Failed to load entities",
                sand_id=entities.learner.sand_id if entities.learner else None,
                error=str(e),
            )
            raise

    def _load_countries(self, entities: GraphEntities) -> None:
        """Load country nodes."""
        for country in entities.countries:
            try:
                self.node_creator.create_country(country)
            except Exception as e:
                self.logger.warning(
                    "Failed to create country",
                    country_code=country.code,
                    error=str(e),
                )

    def _load_cities(self, entities: GraphEntities) -> None:
        """Load city nodes."""
        for city in entities.cities:
            try:
                self.node_creator.create_city(city)
            except Exception as e:
                self.logger.warning(
                    "Failed to create city",
                    city_id=city.id,
                    error=str(e),
                )

    def _load_skills(self, entities: GraphEntities) -> None:
        """Load skill nodes."""
        for skill in entities.skills:
            try:
                self.node_creator.create_skill(skill)
            except Exception as e:
                self.logger.warning(
                    "Failed to create skill",
                    skill_id=skill.id,
                    error=str(e),
                )

    def _load_programs(self, entities: GraphEntities) -> None:
        """Load program nodes."""
        for program in entities.programs:
            try:
                self.node_creator.create_program(program)
            except Exception as e:
                self.logger.warning(
                    "Failed to create program",
                    program_id=program.id,
                    error=str(e),
                )

    def _load_companies(self, entities: GraphEntities) -> None:
        """Load company nodes."""
        for company in entities.companies:
            try:
                self.node_creator.create_company(company)
            except Exception as e:
                self.logger.warning(
                    "Failed to create company",
                    company_id=company.id,
                    error=str(e),
                )

    def _load_states(self, entities: GraphEntities) -> None:
        """Load temporal state nodes."""
        for state in entities.learning_states:
            try:
                self.node_creator.create_learning_state(state)
            except Exception as e:
                self.logger.warning("Failed to create learning state", error=str(e))

        for status in entities.professional_statuses:
            try:
                self.node_creator.create_professional_status(status)
            except Exception as e:
                self.logger.warning("Failed to create professional status", error=str(e))

    def _create_relationships(self, entities: GraphEntities) -> None:
        """Create all relationships for the learner."""
        if not entities.learner:
            return

        learner_id = entities.learner.sand_id or entities.learner.hashed_email
        if not learner_id:
            return

        # Debug logging
        self.logger.info(
            "Creating relationships",
            learner_id=learner_id,
            skills_count=len(entities.skills),
            programs_count=len(entities.programs),
            companies_count=len(entities.companies),
        )

        # Skills relationships
        for skill in entities.skills:
            try:
                rel = HasSkillRelationship(
                    proficiency_level=None,
                    years_of_experience=None
                )
                self.relationship_creator.create_has_skill(learner_id, skill.id, rel)
            except Exception as e:
                self.logger.warning("Failed to create skill relationship", error=str(e))

        # Program enrollment relationships
        for entry in entities.learning_details_entries:
            try:
                self.logger.debug(
                    "Creating program relationship",
                    learner_id=learner_id,
                    program_id=entry.cohort_code,
                    cohort_code=entry.cohort_code,
                )

                # Parse dates
                from transformers.date_converter import DateConverter
                date_converter = DateConverter(logger=self.logger)

                start_date = date_converter.convert_date(entry.program_start_date)
                end_date = date_converter.convert_date(entry.program_end_date)
                graduation_date = date_converter.convert_date(entry.program_graduation_date)

                # Parse numeric values
                def parse_float(value: str) -> float | None:
                    try:
                        f = float(value)
                        return None if f == -99.0 else f
                    except (ValueError, TypeError):
                        return None

                def parse_int(value: str) -> int | None:
                    try:
                        return int(float(value))
                    except (ValueError, TypeError):
                        return None

                rel = EnrolledInRelationship(
                    index=int(entry.index),
                    cohort_code=entry.cohort_code,
                    enrollment_status=entry.enrollment_status,
                    start_date=start_date,
                    end_date=end_date,
                    graduation_date=graduation_date,
                    lms_overall_score=parse_float(entry.lms_overall_score),
                    completion_rate=parse_float(entry.completion_rate),
                    number_of_assignments=parse_int(entry.no_of_assignments),
                    number_of_submissions=parse_int(entry.no_of_submissions),
                    number_of_assignments_passed=parse_int(entry.no_of_assignment_passed),
                    assignment_completion_rate=parse_float(entry.assignment_completion_rate),
                    number_of_milestones=parse_int(entry.no_of_milestone),
                    number_of_milestones_submitted=parse_int(entry.no_of_milestone_submitted),
                    number_of_milestones_passed=parse_int(entry.no_of_milestone_passed),
                    milestone_completion_rate=parse_float(entry.milestone_completion_rate),
                    number_of_tests=parse_int(entry.no_of_test),
                    number_of_tests_submitted=parse_int(entry.no_of_test_submitted),
                    number_of_tests_passed=parse_int(entry.no_of_test_passed),
                    test_completion_rate=parse_float(entry.test_completion_rate),
                )
                self.relationship_creator.create_enrolled_in(learner_id, entry.cohort_code, rel)
                self.logger.debug("Program relationship created successfully")
            except Exception as e:
                self.logger.warning(
                    "Failed to create program relationship",
                    learner_id=learner_id,
                    error=str(e)
                )

        # Employment relationships
        for entry in entities.employment_details_entries:
            try:
                from transformers.date_converter import DateConverter
                from utils.helpers import generate_id

                date_converter = DateConverter(logger=self.logger)
                company_id = generate_id(entry.organization_name)

                self.logger.debug(
                    "Creating employment relationship",
                    learner_id=learner_id,
                    company_id=company_id,
                )

                start_date = date_converter.convert_date(entry.start_date)
                end_date = date_converter.convert_date(entry.end_date)
                is_current = entry.is_current == "1"

                rel = WorksForRelationship(
                    position=entry.job_title,
                    department=None,
                    employment_type=None,
                    start_date=start_date,
                    end_date=end_date,
                    is_current=is_current,
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

        # Learning state relationships
        for state in entities.learning_states:
            try:
                # Link learner to learning state with temporal properties
                query = """
                MATCH (l:Learner {sandId: $learner_id})
                MATCH (s:LearningState {state: $state, startDate: $start_date})
                MERGE (l)-[r:HAS_LEARNING_STATE]->(s)
                SET r.validFrom = $start_date,
                    r.validTo = $end_date,
                    r.isCurrent = $is_current
                """
                with self.connection.get_session() as session:
                    session.run(query, {
                        "learner_id": learner_id,
                        "state": state.state,
                        "start_date": state.start_date,
                        "end_date": state.end_date,
                        "is_current": state.is_current
                    })
            except Exception as e:
                self.logger.warning("Failed to create learning state relationship", error=str(e))

        # Professional status relationships
        for status in entities.professional_statuses:
            try:
                query = """
                MATCH (l:Learner {sandId: $learner_id})
                MATCH (ps:ProfessionalStatus {status: $status, startDate: $start_date})
                MERGE (l)-[r:HAS_PROFESSIONAL_STATUS]->(ps)
                SET r.validFrom = $start_date,
                    r.validTo = $end_date,
                    r.isCurrent = $is_current
                """
                with self.connection.get_session() as session:
                    session.run(query, {
                        "learner_id": learner_id,
                        "status": status.status,
                        "start_date": status.start_date,
                        "end_date": status.end_date,
                        "is_current": status.is_current
                    })
            except Exception as e:
                self.logger.warning("Failed to create professional status relationship", error=str(e))


__all__ = ["Loader"]
