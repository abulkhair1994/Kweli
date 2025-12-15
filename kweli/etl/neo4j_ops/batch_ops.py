"""
Batch operations for Neo4j.

Handles batch processing of nodes and relationships for performance.
Includes retry logic for cloud deployments (Neo4j Aura).
"""

from __future__ import annotations

import random
import time
from typing import TYPE_CHECKING, Any

from neo4j.exceptions import ServiceUnavailable, SessionExpired, TransientError

from kweli.etl.neo4j_ops.connection import Neo4jConnection
from kweli.etl.utils.logger import get_logger

if TYPE_CHECKING:
    from structlog.types import FilteringBoundLogger


class BatchOperations:
    """
    Batch operations for efficient Neo4j writes.

    Includes retry logic with exponential backoff and jitter for transient errors,
    which is especially important for cloud deployments like Neo4j Aura
    and parallel processing scenarios where deadlocks can occur.
    """

    def __init__(
        self,
        connection: Neo4jConnection,
        batch_size: int = 1000,
        max_retries: int = 5,
        retry_delay: float = 1.0,
        logger: FilteringBoundLogger | None = None,
    ) -> None:
        """
        Initialize batch operations.

        Args:
            connection: Neo4j connection instance
            batch_size: Number of records per batch
            max_retries: Number of retries for transient errors (default 5 for deadlocks)
            retry_delay: Initial delay between retries (exponential backoff)
            logger: Optional logger instance
        """
        self.connection = connection
        self.batch_size = batch_size
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.logger = logger or get_logger(__name__)

    def _execute_with_retry(
        self,
        query: str,
        parameters: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """
        Execute a query with retry logic for transient errors.

        Args:
            query: Cypher query string
            parameters: Query parameters

        Returns:
            Query results

        Raises:
            Exception: If all retries are exhausted
        """
        last_exception: Exception | None = None

        for attempt in range(self.max_retries):
            try:
                return self.connection.execute_query(query, parameters)

            except (ServiceUnavailable, SessionExpired, TransientError) as e:
                last_exception = e
                is_deadlock = "DeadlockDetected" in str(type(e).__name__) or "Deadlock" in str(e)

                if attempt < self.max_retries - 1:
                    # Exponential backoff with jitter to prevent synchronized retries
                    base_sleep = self.retry_delay * (2**attempt)
                    # Add 0-50% jitter to desynchronize parallel workers
                    jitter = random.uniform(0, base_sleep * 0.5)  # noqa: S311
                    sleep_time = base_sleep + jitter

                    self.logger.warning(
                        "Retrying batch after transient error",
                        attempt=attempt + 1,
                        max_retries=self.max_retries,
                        sleep_time=round(sleep_time, 2),
                        is_deadlock=is_deadlock,
                        error=str(e)[:200],
                    )

                    time.sleep(sleep_time)

        self.logger.error(
            "Batch operation failed after all retries",
            max_retries=self.max_retries,
            error=str(last_exception),
        )
        if last_exception:
            raise last_exception
        raise RuntimeError("Batch operation failed with no exception captured")

    def batch_create_nodes(
        self,
        node_type: str,
        records: list[dict[str, Any]],
        merge_on: str,
        use_retry: bool = True,
    ) -> int:
        """
        Create nodes in batches using UNWIND.

        Args:
            node_type: Node label (e.g., "Learner", "Skill")
            records: List of node property dictionaries
            merge_on: Property name to merge on (e.g., "sandId", "id")
            use_retry: Whether to use retry logic (default True)

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

            if use_retry:
                result = self._execute_with_retry(query, {"records": batch})
            else:
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
        use_retry: bool = True,
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
            use_retry: Whether to use retry logic (default True)

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

            if use_retry:
                result = self._execute_with_retry(query, {"records": batch})
            else:
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
        use_retry: bool = True,
    ) -> list[Any]:
        """
        Execute a custom query in batches using UNWIND.

        Args:
            query: Cypher query with $records parameter
            records: List of parameter dictionaries
            use_retry: Whether to use retry logic (default True)

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

            if use_retry:
                result = self._execute_with_retry(query, {"records": batch})
            else:
                result = self.connection.execute_query(query, {"records": batch})

            all_results.extend(result)

            self.logger.debug(
                "Executed batch query",
                batch_size=len(batch),
                total_results=len(all_results),
            )

        return all_results

    def batch_execute_with_retry(
        self,
        query: str,
        records: list[dict[str, Any]],
    ) -> int:
        """
        Execute a batch query with retry logic.

        This is an alias for batch_execute with use_retry=True that returns
        the count of processed records instead of results.

        Args:
            query: Cypher query with $batch parameter
            records: List of records to process

        Returns:
            Number of records processed

        Raises:
            Exception: If all retries exhausted
        """
        self.batch_execute(query, records, use_retry=True)
        return len(records)


__all__ = ["BatchOperations"]
