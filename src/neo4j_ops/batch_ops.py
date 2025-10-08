"""
Batch operations for Neo4j.

Handles batch processing of nodes and relationships for performance.
"""

from typing import Any

from structlog.types import FilteringBoundLogger

from neo4j_ops.connection import Neo4jConnection
from utils.logger import get_logger


class BatchOperations:
    """Batch operations for efficient Neo4j writes."""

    def __init__(
        self,
        connection: Neo4jConnection,
        batch_size: int = 1000,
        logger: FilteringBoundLogger | None = None,
    ) -> None:
        """
        Initialize batch operations.

        Args:
            connection: Neo4j connection instance
            batch_size: Number of records per batch
            logger: Optional logger instance
        """
        self.connection = connection
        self.batch_size = batch_size
        self.logger = logger or get_logger(__name__)

    def batch_create_nodes(
        self,
        node_type: str,
        records: list[dict[str, Any]],
        merge_on: str,
    ) -> int:
        """
        Create nodes in batches using UNWIND.

        Args:
            node_type: Node label (e.g., "Learner", "Skill")
            records: List of node property dictionaries
            merge_on: Property name to merge on (e.g., "sandId", "id")

        Returns:
            Total number of nodes created/updated

        Example:
            records = [
                {"id": "skill1", "name": "Python"},
                {"id": "skill2", "name": "SQL"},
            ]
            batch_create_nodes("Skill", records, "id")
        """
        total_created = 0

        for i in range(0, len(records), self.batch_size):
            batch = records[i : i + self.batch_size]

            query = f"""
            UNWIND $records AS record
            MERGE (n:{node_type} {{{merge_on}: record.{merge_on}}})
            SET n += record
            RETURN count(n) as created
            """

            result = self.connection.execute_query(query, {"records": batch})
            count = result[0]["created"] if result else 0
            total_created += count

            self.logger.debug(
                "Created batch of nodes",
                node_type=node_type,
                batch_size=len(batch),
                total=total_created,
            )

        return total_created

    def batch_create_relationships(
        self,
        rel_type: str,
        from_label: str,
        from_property: str,
        to_label: str,
        to_property: str,
        records: list[dict[str, Any]],
    ) -> int:
        """
        Create relationships in batches.

        Args:
            rel_type: Relationship type (e.g., "HAS_SKILL")
            from_label: Source node label (e.g., "Learner")
            from_property: Source node property (e.g., "sandId")
            to_label: Target node label (e.g., "Skill")
            to_property: Target node property (e.g., "id")
            records: List of relationship dictionaries with:
                - from_id: Source node ID
                - to_id: Target node ID
                - properties: Relationship properties (optional)

        Returns:
            Total number of relationships created

        Example:
            records = [
                {
                    "from_id": "SAND123",
                    "to_id": "python",
                    "properties": {"proficiencyLevel": "Expert"}
                },
            ]
            batch_create_relationships(
                "HAS_SKILL", "Learner", "sandId", "Skill", "id", records
            )
        """
        total_created = 0

        for i in range(0, len(records), self.batch_size):
            batch = records[i : i + self.batch_size]

            query = f"""
            UNWIND $records AS record
            MATCH (from:{from_label} {{{from_property}: record.from_id}})
            MATCH (to:{to_label} {{{to_property}: record.to_id}})
            MERGE (from)-[r:{rel_type}]->(to)
            SET r += record.properties
            RETURN count(r) as created
            """

            result = self.connection.execute_query(query, {"records": batch})
            count = result[0]["created"] if result else 0
            total_created += count

            self.logger.debug(
                "Created batch of relationships",
                rel_type=rel_type,
                batch_size=len(batch),
                total=total_created,
            )

        return total_created

    def batch_execute(
        self,
        query: str,
        records: list[dict[str, Any]],
    ) -> list[Any]:
        """
        Execute a custom query in batches using UNWIND.

        Args:
            query: Cypher query with $records parameter
            records: List of parameter dictionaries

        Returns:
            List of results from all batches

        Example:
            query = '''
            UNWIND $records AS record
            MATCH (l:Learner {sandId: record.learner_id})
            SET l.isPlaced = true
            RETURN l.sandId as id
            '''
            results = batch_execute(query, records)
        """
        all_results: list[Any] = []

        for i in range(0, len(records), self.batch_size):
            batch = records[i : i + self.batch_size]

            result = self.connection.execute_query(query, {"records": batch})
            all_results.extend(result)

            self.logger.debug(
                "Executed batch query",
                batch_size=len(batch),
                total_results=len(all_results),
            )

        return all_results


__all__ = ["BatchOperations"]
