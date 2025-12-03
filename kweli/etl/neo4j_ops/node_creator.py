"""
Node creator for Neo4j.

Creates nodes using MERGE operations to avoid duplicates.
"""

from structlog.types import FilteringBoundLogger

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
from kweli.etl.neo4j_ops.connection import Neo4jConnection
from kweli.etl.neo4j_ops.cypher_builder import CypherBuilder
from kweli.etl.utils.logger import get_logger


class NodeCreator:
    """Create nodes in Neo4j."""

    def __init__(
        self,
        connection: Neo4jConnection,
        logger: FilteringBoundLogger | None = None,
    ) -> None:
        """
        Initialize node creator.

        Args:
            connection: Neo4j connection instance
            logger: Optional logger instance
        """
        self.connection = connection
        self.logger = logger or get_logger(__name__)
        self.builder = CypherBuilder()

    def create_learner(self, learner: LearnerNode) -> None:
        """
        Create or update Learner node.

        Args:
            learner: LearnerNode instance
        """
        query, params = self.builder.build_merge_learner(learner)
        self.connection.execute_write(query, params)

    def create_country(self, country: CountryNode) -> None:
        """
        Create or update Country node.

        Args:
            country: CountryNode instance
        """
        query, params = self.builder.build_merge_country(country)
        self.connection.execute_write(query, params)

    def create_city(self, city: CityNode) -> None:
        """
        Create or update City node.

        Args:
            city: CityNode instance
        """
        query, params = self.builder.build_merge_city(city)
        self.connection.execute_write(query, params)

    def create_skill(self, skill: SkillNode) -> None:
        """
        Create or update Skill node.

        Args:
            skill: SkillNode instance
        """
        query, params = self.builder.build_merge_skill(skill)
        self.connection.execute_write(query, params)

    def create_program(self, program: ProgramNode) -> None:
        """
        Create or update Program node.

        Args:
            program: ProgramNode instance
        """
        query, params = self.builder.build_merge_program(program)
        self.connection.execute_write(query, params)

    def create_company(self, company: CompanyNode) -> None:
        """
        Create or update Company node.

        Args:
            company: CompanyNode instance
        """
        query, params = self.builder.build_merge_company(company)
        self.connection.execute_write(query, params)

    def create_learning_state(self, state: LearningStateNode) -> None:
        """
        Create LearningState node (temporal, always CREATE).

        Args:
            state: LearningStateNode instance
        """
        query, params = self.builder.build_merge_learning_state(state)
        self.connection.execute_write(query, params)

    def create_professional_status(self, status: ProfessionalStatusNode) -> None:
        """
        Create ProfessionalStatus node (temporal, always CREATE).

        Args:
            status: ProfessionalStatusNode instance
        """
        query, params = self.builder.build_merge_professional_status(status)
        self.connection.execute_write(query, params)


__all__ = ["NodeCreator"]
