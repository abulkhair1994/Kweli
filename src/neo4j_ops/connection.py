"""
Neo4j connection manager.

Manages connection pool, transactions, and health checks.
"""

import os
from typing import Any

from structlog.types import FilteringBoundLogger

from neo4j import Driver, GraphDatabase, Session
from neo4j.exceptions import ServiceUnavailable
from utils.logger import get_logger


class Neo4jConnection:
    """Manage Neo4j database connection."""

    def __init__(
        self,
        uri: str | None = None,
        user: str | None = None,
        password: str | None = None,
        database: str = "neo4j",
        max_connection_pool_size: int = 50,
        connection_timeout: int = 30,
        logger: FilteringBoundLogger | None = None,
    ) -> None:
        """
        Initialize Neo4j connection.

        Args:
            uri: Neo4j URI (default: from NEO4J_URI env)
            user: Username (default: from NEO4J_USER env)
            password: Password (default: from NEO4J_PASSWORD env)
            database: Database name
            max_connection_pool_size: Max connections in pool
            connection_timeout: Connection timeout in seconds
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

        # Driver instance
        self._driver: Driver | None = None

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
            )

            # Verify connection
            self._driver.verify_connectivity()

            self.logger.info(
                "Connected to Neo4j",
                uri=self.uri,
                database=self.database,
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

    def __enter__(self) -> "Neo4jConnection":
        """Context manager entry."""
        self.connect()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Context manager exit."""
        self.close()


__all__ = ["Neo4jConnection"]
