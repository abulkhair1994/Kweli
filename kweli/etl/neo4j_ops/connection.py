"""
Neo4j connection manager.

Manages connection pool, transactions, health checks, and retry logic.
Supports both local Neo4j and Neo4j Aura (cloud).
"""

from __future__ import annotations

import os
import time
from typing import TYPE_CHECKING, Any

from neo4j import Driver, GraphDatabase
from neo4j.exceptions import ServiceUnavailable, SessionExpired, TransientError

from kweli.etl.utils.logger import get_logger

if TYPE_CHECKING:
    from neo4j import Session
    from structlog.types import FilteringBoundLogger


class Neo4jConnection:
    """
    Manage Neo4j database connection with Aura support.

    Features:
    - Connection pooling
    - Automatic encryption detection for neo4j+s:// URIs
    - Retry logic with exponential backoff for transient errors
    - Health checks
    """

    def __init__(
        self,
        uri: str | None = None,
        user: str | None = None,
        password: str | None = None,
        database: str = "neo4j",
        max_connection_pool_size: int = 50,
        connection_timeout: int = 30,
        max_transaction_retry_time: int = 60,
        max_retries: int = 3,
        retry_delay: float = 1.0,
        logger: FilteringBoundLogger | None = None,
    ) -> None:
        """
        Initialize Neo4j connection.

        Args:
            uri: Neo4j URI (default: from NEO4J_URI env)
                 Supports: bolt://, neo4j://, neo4j+s://, bolt+s://
            user: Username (default: from NEO4J_USER env)
            password: Password (default: from NEO4J_PASSWORD env)
            database: Database name
            max_connection_pool_size: Max connections in pool
            connection_timeout: Connection timeout in seconds
            max_transaction_retry_time: Max retry time for transactions
            max_retries: Number of retries for transient errors
            retry_delay: Initial delay between retries (exponential backoff)
            logger: Optional logger instance
        """
        self.logger = logger or get_logger(__name__)

        # Get connection details from env if not provided
        self.uri = uri or os.getenv("NEO4J_URI", "bolt://localhost:7687")
        self.user = user or os.getenv("NEO4J_USER", "neo4j")
        self.password = password or os.getenv("NEO4J_PASSWORD", "password123")
        self.database = database

        # Connection settings
        self.max_connection_pool_size = max_connection_pool_size
        self.connection_timeout = connection_timeout
        self.max_transaction_retry_time = max_transaction_retry_time

        # Retry settings
        self.max_retries = max_retries
        self.retry_delay = retry_delay

        # Auto-detect encryption from URI scheme
        # neo4j+s:// and bolt+s:// require encryption (used by Aura)
        self.encrypted = self.uri.startswith("neo4j+s://") or self.uri.startswith(
            "bolt+s://"
        )

        # Check if this is an Aura connection
        self.is_aura = "databases.neo4j.io" in self.uri

        # Driver instance
        self._driver: Driver | None = None

        self.logger.info(
            "Neo4j connection configured",
            uri=self.uri,
            database=self.database,
            encrypted=self.encrypted,
            is_aura=self.is_aura,
        )

    def connect(self) -> None:
        """Establish connection to Neo4j."""
        if self._driver is not None:
            self.logger.warning("Connection already established")
            return

        try:
            self._driver = GraphDatabase.driver(
                self.uri,
                auth=(self.user, self.password),
                max_connection_pool_size=self.max_connection_pool_size,
                connection_timeout=self.connection_timeout,
                max_transaction_retry_time=self.max_transaction_retry_time,
            )

            # Verify connection
            self._driver.verify_connectivity()

            self.logger.info(
                "Connected to Neo4j",
                uri=self.uri,
                database=self.database,
                encrypted=self.encrypted,
                is_aura=self.is_aura,
            )
        except ServiceUnavailable as e:
            self.logger.error("Failed to connect to Neo4j", uri=self.uri, error=str(e))
            raise

    def close(self) -> None:
        """Close connection to Neo4j."""
        if self._driver is not None:
            self._driver.close()
            self._driver = None
            self.logger.info("Closed Neo4j connection")

    def get_driver(self) -> Driver:
        """
        Get driver instance.

        Returns:
            Neo4j Driver

        Raises:
            RuntimeError: If not connected
        """
        if self._driver is None:
            raise RuntimeError("Not connected to Neo4j. Call connect() first.")
        return self._driver

    def get_session(self, **kwargs: Any) -> Session:
        """
        Get a new session.

        Args:
            **kwargs: Additional session arguments

        Returns:
            Neo4j Session
        """
        driver = self.get_driver()
        return driver.session(database=self.database, **kwargs)

    def health_check(self) -> bool:
        """
        Check if Neo4j is healthy.

        Returns:
            True if healthy, False otherwise
        """
        if self._driver is None:
            return False

        try:
            with self.get_session() as session:
                result = session.run("RETURN 1 AS health")
                record = result.single()
                return record is not None and record["health"] == 1
        except Exception as e:
            self.logger.error("Health check failed", error=str(e))
            return False

    def execute_query(
        self,
        query: str,
        parameters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """
        Execute a Cypher query and return results.

        Args:
            query: Cypher query string
            parameters: Query parameters

        Returns:
            List of result dictionaries
        """
        with self.get_session() as session:
            result = session.run(query, parameters or {})
            return [dict(record) for record in result]

    def execute_query_with_retry(
        self,
        query: str,
        parameters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """
        Execute a query with retry logic for transient errors.

        Uses exponential backoff for retries.

        Args:
            query: Cypher query string
            parameters: Query parameters

        Returns:
            List of result dictionaries

        Raises:
            Exception: If all retries are exhausted
        """
        last_exception: Exception | None = None

        for attempt in range(self.max_retries):
            try:
                return self.execute_query(query, parameters)

            except (ServiceUnavailable, SessionExpired, TransientError) as e:
                last_exception = e

                if attempt < self.max_retries - 1:
                    # Exponential backoff
                    sleep_time = self.retry_delay * (2**attempt)

                    self.logger.warning(
                        "Retrying query after transient error",
                        attempt=attempt + 1,
                        max_retries=self.max_retries,
                        sleep_time=sleep_time,
                        error=str(e),
                    )

                    time.sleep(sleep_time)

        self.logger.error(
            "All retries exhausted",
            max_retries=self.max_retries,
            error=str(last_exception),
        )
        if last_exception:
            raise last_exception
        raise RuntimeError("Query failed with no exception captured")

    def execute_write(
        self,
        query: str,
        parameters: dict[str, Any] | None = None,
    ) -> None:
        """
        Execute a write query (INSERT, UPDATE, DELETE).

        Args:
            query: Cypher query string
            parameters: Query parameters
        """
        with self.get_session() as session:
            session.run(query, parameters or {})

    def execute_write_with_retry(
        self,
        query: str,
        parameters: dict[str, Any] | None = None,
    ) -> None:
        """
        Execute a write query with retry logic for transient errors.

        Args:
            query: Cypher query string
            parameters: Query parameters

        Raises:
            Exception: If all retries are exhausted
        """
        last_exception: Exception | None = None

        for attempt in range(self.max_retries):
            try:
                self.execute_write(query, parameters)
                return

            except (ServiceUnavailable, SessionExpired, TransientError) as e:
                last_exception = e

                if attempt < self.max_retries - 1:
                    sleep_time = self.retry_delay * (2**attempt)

                    self.logger.warning(
                        "Retrying write after transient error",
                        attempt=attempt + 1,
                        max_retries=self.max_retries,
                        sleep_time=sleep_time,
                        error=str(e),
                    )

                    time.sleep(sleep_time)

        self.logger.error(
            "All retries exhausted for write",
            max_retries=self.max_retries,
            error=str(last_exception),
        )
        if last_exception:
            raise last_exception
        raise RuntimeError("Write failed with no exception captured")

    def clear_database(self) -> None:
        """
        Clear all nodes and relationships from database.

        WARNING: This deletes ALL data!
        """
        self.logger.warning("Clearing entire database")

        with self.get_session() as session:
            # Delete all relationships
            session.run("MATCH ()-[r]->() DELETE r")
            # Delete all nodes
            session.run("MATCH (n) DELETE n")

        self.logger.info("Database cleared")

    def get_node_count(self) -> int:
        """
        Get total number of nodes in the database.

        Returns:
            Node count
        """
        result = self.execute_query("MATCH (n) RETURN count(n) as count")
        return result[0]["count"] if result else 0

    def get_relationship_count(self) -> int:
        """
        Get total number of relationships in the database.

        Returns:
            Relationship count
        """
        result = self.execute_query("MATCH ()-[r]->() RETURN count(r) as count")
        return result[0]["count"] if result else 0

    def __enter__(self) -> Neo4jConnection:
        """Context manager entry."""
        self.connect()
        return self

    def __exit__(self, _exc_type: Any, _exc_val: Any, _exc_tb: Any) -> None:
        """Context manager exit."""
        self.close()


__all__ = ["Neo4jConnection"]
