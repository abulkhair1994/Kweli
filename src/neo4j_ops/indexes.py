"""
Index and constraint management for Neo4j.

Creates constraints and indexes as defined in init.cypher.
"""

from structlog.types import FilteringBoundLogger

from neo4j_ops.connection import Neo4jConnection
from utils.logger import get_logger


class IndexManager:
    """Manage indexes and constraints in Neo4j."""

    def __init__(
        self,
        connection: Neo4jConnection,
        logger: FilteringBoundLogger | None = None,
    ) -> None:
        """
        Initialize index manager.

        Args:
            connection: Neo4j connection instance
            logger: Optional logger instance
        """
        self.connection = connection
        self.logger = logger or get_logger(__name__)

    def create_all_constraints_and_indexes(self) -> None:
        """Create all constraints and indexes."""
        self.logger.info("Creating constraints and indexes")

        # Create constraints first (includes implicit indexes)
        self._create_constraints()

        # Create additional indexes
        self._create_indexes()

        self.logger.info("Finished creating constraints and indexes")

    def _create_constraints(self) -> None:
        """Create uniqueness constraints."""
        constraints = [
            # Learner constraint (hashedEmail is primary unique identifier)
            "CREATE CONSTRAINT learner_hashed_email IF NOT EXISTS "
            "FOR (l:Learner) REQUIRE l.hashedEmail IS UNIQUE",
            # Country constraint
            "CREATE CONSTRAINT country_code IF NOT EXISTS "
            "FOR (c:Country) REQUIRE c.code IS UNIQUE",
            # City constraint
            "CREATE CONSTRAINT city_id IF NOT EXISTS "
            "FOR (c:City) REQUIRE c.id IS UNIQUE",
            # Skill constraint
            "CREATE CONSTRAINT skill_id IF NOT EXISTS "
            "FOR (s:Skill) REQUIRE s.id IS UNIQUE",
            # Program constraint
            "CREATE CONSTRAINT program_id IF NOT EXISTS "
            "FOR (p:Program) REQUIRE p.id IS UNIQUE",
            # Company constraint
            "CREATE CONSTRAINT company_id IF NOT EXISTS "
            "FOR (c:Company) REQUIRE c.id IS UNIQUE",
        ]

        for constraint in constraints:
            try:
                self.connection.execute_write(constraint)
                self.logger.debug("Created constraint", constraint=constraint[:50])
            except Exception as e:
                self.logger.warning("Failed to create constraint", error=str(e))

    def _create_indexes(self) -> None:
        """Create performance indexes."""
        indexes = [
            # Learner indexes (for HYBRID property lookups)
            "CREATE INDEX learner_country IF NOT EXISTS "
            "FOR (l:Learner) ON (l.countryOfResidenceCode)",
            "CREATE INDEX learner_city IF NOT EXISTS "
            "FOR (l:Learner) ON (l.cityOfResidenceId)",
            "CREATE INDEX learner_learning_state IF NOT EXISTS "
            "FOR (l:Learner) ON (l.currentLearningState)",
            "CREATE INDEX learner_professional_status IF NOT EXISTS "
            "FOR (l:Learner) ON (l.currentProfessionalStatus)",
            # Country index
            "CREATE INDEX country_name IF NOT EXISTS "
            "FOR (c:Country) ON (c.name)",
            # City indexes
            "CREATE INDEX city_name IF NOT EXISTS "
            "FOR (c:City) ON (c.name)",
            "CREATE INDEX city_country IF NOT EXISTS "
            "FOR (c:City) ON (c.countryCode)",
            # Skill indexes
            "CREATE INDEX skill_name IF NOT EXISTS "
            "FOR (s:Skill) ON (s.name)",
            "CREATE INDEX skill_category IF NOT EXISTS "
            "FOR (s:Skill) ON (s.category)",
            # Program indexes
            "CREATE INDEX program_cohort IF NOT EXISTS "
            "FOR (p:Program) ON (p.cohortCode)",
            "CREATE INDEX program_name IF NOT EXISTS "
            "FOR (p:Program) ON (p.name)",
            # Company indexes
            "CREATE INDEX company_name IF NOT EXISTS "
            "FOR (c:Company) ON (c.name)",
            "CREATE INDEX company_country IF NOT EXISTS "
            "FOR (c:Company) ON (c.countryCode)",
            # LearningState indexes
            "CREATE INDEX learning_state_state IF NOT EXISTS "
            "FOR (ls:LearningState) ON (ls.state)",
            "CREATE INDEX learning_state_current IF NOT EXISTS "
            "FOR (ls:LearningState) ON (ls.isCurrent)",
            # ProfessionalStatus indexes
            "CREATE INDEX prof_status_status IF NOT EXISTS "
            "FOR (ps:ProfessionalStatus) ON (ps.status)",
            "CREATE INDEX prof_status_current IF NOT EXISTS "
            "FOR (ps:ProfessionalStatus) ON (ps.isCurrent)",
        ]

        for index in indexes:
            try:
                self.connection.execute_write(index)
                self.logger.debug("Created index", index=index[:50])
            except Exception as e:
                self.logger.warning("Failed to create index", error=str(e))

    def list_constraints(self) -> list[dict[str, str]]:
        """List all constraints."""
        result = self.connection.execute_query("SHOW CONSTRAINTS")
        return result

    def list_indexes(self) -> list[dict[str, str]]:
        """List all indexes."""
        result = self.connection.execute_query("SHOW INDEXES")
        return result


def setup_indexes(connection):
    """Convenience function to setup all indexes and constraints."""
    manager = IndexManager(connection)
    manager.create_all_constraints_and_indexes()


__all__ = ["IndexManager", "setup_indexes"]
