"""Core Neo4j tools for the agent."""

import logging
import sys
import warnings
from pathlib import Path
from typing import Any

from langchain_core.tools import tool
from neo4j import GraphDatabase, Result

from agent.config import get_config
from agent.query_status import notify_query_end, notify_query_start
from agent.tools.validation import validate_cypher_query, validate_query_parameters

# Suppress Neo4j driver notifications/warnings
logging.getLogger("neo4j").setLevel(logging.ERROR)
warnings.filterwarnings("ignore", category=DeprecationWarning, module="neo4j")

# Add src to path to import existing Neo4j utilities
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))


class Neo4jExecutor:
    """Execute Cypher queries against Neo4j database."""

    def __init__(self) -> None:
        """Initialize Neo4j executor with configuration."""
        self.config = get_config()
        self._driver = None
        self._schema_cache: dict[str, Any] | None = None

    @property
    def driver(self) -> GraphDatabase.driver:
        """Lazy-load Neo4j driver."""
        if self._driver is None:
            # Suppress Neo4j driver notifications (warnings about missing properties, etc.)
            # By setting notifications_min_severity to "OFF", we only get critical errors
            try:
                self._driver = GraphDatabase.driver(
                    self.config.neo4j.uri,
                    auth=(self.config.neo4j.user, self.config.neo4j.password),
                    max_connection_pool_size=self.config.neo4j.max_connection_pool_size,
                    connection_timeout=self.config.neo4j.connection_timeout,
                    notifications_min_severity="OFF",  # Suppress all notifications
                )
            except TypeError:
                # Fallback for older Neo4j driver versions that don't support notifications_min_severity
                self._driver = GraphDatabase.driver(
                    self.config.neo4j.uri,
                    auth=(self.config.neo4j.user, self.config.neo4j.password),
                    max_connection_pool_size=self.config.neo4j.max_connection_pool_size,
                    connection_timeout=self.config.neo4j.connection_timeout,
                )
        return self._driver

    def close(self) -> None:
        """Close the Neo4j driver connection."""
        if self._driver:
            self._driver.close()
            self._driver = None

    def execute_query(
        self,
        query: str,
        params: dict[str, Any] | None = None,
        timeout: int | None = None,
    ) -> list[dict[str, Any]]:
        """
        Execute a Cypher query and return results.

        Args:
            query: Cypher query to execute
            params: Query parameters
            timeout: Query timeout in seconds (uses config default if not set)

        Returns:
            List of result records as dictionaries

        Raises:
            ValueError: If query validation fails
            Exception: If query execution fails
        """
        # Validate query
        validation = validate_cypher_query(
            query,
            max_results=self.config.agent.max_results,
            auto_add_limit=True,
        )

        if not validation.is_valid:
            raise ValueError(f"Query validation failed: {validation.error_message}")

        # Use modified query if LIMIT was added
        query_to_execute = validation.modified_query or query

        # Validate parameters
        if params:
            param_validation = validate_query_parameters(params)
            if not param_validation.is_valid:
                raise ValueError(f"Parameter validation failed: {param_validation.error_message}")

        # Execute query
        timeout = timeout or self.config.agent.query_timeout

        notify_query_start()
        try:
            with self.driver.session() as session:
                result: Result = session.run(
                    query_to_execute,
                    parameters=params or {},
                    timeout=timeout,
                )
                records = [dict(record) for record in result]
                return records
        except Exception as e:
            raise Exception(f"Query execution failed: {e}") from e
        finally:
            notify_query_end()

    def get_schema(self, use_cache: bool = True) -> dict[str, Any]:
        """
        Get the Neo4j graph schema.

        Args:
            use_cache: Whether to use cached schema (default: True)

        Returns:
            Dictionary containing node types, relationship types, and properties
        """
        if use_cache and self._schema_cache:
            return self._schema_cache

        schema = {
            "node_types": [],
            "relationship_types": [],
            "indexes": [],
            "constraints": [],
        }

        try:
            with self.driver.session() as session:
                # Get node labels and properties
                node_result = session.run(
                    """
                    CALL db.labels() YIELD label
                    CALL apoc.meta.nodeTypeProperties() YIELD nodeType, propertyName, propertyTypes
                    WHERE nodeType = ':' + label
                    RETURN label, collect({property: propertyName, type: propertyTypes}) as properties
                    """
                )
                schema["node_types"] = [dict(record) for record in node_result]

                # Get relationship types and properties
                rel_result = session.run(
                    """
                    CALL db.relationshipTypes() YIELD relationshipType
                    RETURN relationshipType as type
                    """
                )
                schema["relationship_types"] = [dict(record) for record in rel_result]

                # Get indexes
                index_result = session.run("SHOW INDEXES")
                schema["indexes"] = [dict(record) for record in index_result]

                # Get constraints
                constraint_result = session.run("SHOW CONSTRAINTS")
                schema["constraints"] = [dict(record) for record in constraint_result]

        except Exception:
            # Fallback if APOC is not available - use simpler queries
            try:
                with self.driver.session() as session:
                    # Get just the labels
                    node_result = session.run("CALL db.labels() YIELD label RETURN label")
                    schema["node_types"] = [
                        {"label": record["label"], "properties": []} for record in node_result
                    ]

                    # Get relationship types
                    rel_result = session.run(
                        "CALL db.relationshipTypes() YIELD relationshipType "
                        "RETURN relationshipType as type"
                    )
                    schema["relationship_types"] = [dict(record) for record in rel_result]
            except Exception as e:
                raise Exception(f"Failed to fetch schema: {e}") from e

        if use_cache:
            self._schema_cache = schema

        return schema

    def clear_cache(self) -> None:
        """Clear the schema cache."""
        self._schema_cache = None


# Global executor instance
_executor: Neo4jExecutor | None = None


def get_executor() -> Neo4jExecutor:
    """Get the global Neo4j executor instance."""
    global _executor
    if _executor is None:
        _executor = Neo4jExecutor()
    return _executor


@tool
def get_graph_schema() -> dict[str, Any]:
    """
    Get the Neo4j graph schema including node types, relationship types, and constraints.

    Returns a dictionary containing:
    - node_types: List of node labels with their properties
    - relationship_types: List of relationship types
    - indexes: List of database indexes
    - constraints: List of database constraints

    This is useful for understanding the structure of the graph database
    before generating queries.

    Returns:
        Dictionary containing schema information
    """
    executor = get_executor()
    schema = executor.get_schema(use_cache=True)

    # Format for better readability
    formatted_schema = {
        "node_types": [nt.get("label", nt.get("type", "Unknown")) for nt in schema["node_types"]],
        "relationship_types": [
            rt.get("type", rt.get("relationshipType", "Unknown"))
            for rt in schema["relationship_types"]
        ],
        "summary": f"{len(schema['node_types'])} node types, "
        f"{len(schema['relationship_types'])} relationship types",
    }

    return formatted_schema


@tool
def execute_cypher_query(query: str, params: dict[str, Any] | None = None) -> str:
    """
    Execute a Cypher query against the Neo4j database.

    Safety features:
    - Validates query for write operations (rejected)
    - Automatically adds LIMIT clause if missing
    - Validates parameters for injection risks
    - Enforces query timeout

    Args:
        query: The Cypher query to execute (read-only)
        params: Optional query parameters (use for dynamic values)

    Returns:
        Query results as formatted string

    Examples:
        >>> execute_cypher_query(
        ...     "MATCH (l:Learner) WHERE l.countryOfResidenceCode = $code RETURN count(l) as count",
        ...     {"code": "EG"}
        ... )
        "Found 150,000 learners from Egypt"
    """
    executor = get_executor()

    try:
        results = executor.execute_query(query, params)

        if not results:
            return "Query executed successfully but returned no results."

        # Format results for readability
        if len(results) == 1 and len(results[0]) == 1:
            # Single value result
            value = list(results[0].values())[0]
            return f"Result: {value}"

        # Multiple results - format as table
        output_lines = [f"Found {len(results)} result(s):"]

        # Add results (limit display to 20 rows)
        for i, record in enumerate(results[:20], 1):
            formatted_record = ", ".join(f"{k}={v}" for k, v in record.items())
            output_lines.append(f"{i}. {formatted_record}")

        if len(results) > 20:
            output_lines.append(f"... and {len(results) - 20} more results")

        return "\n".join(output_lines)

    except Exception as e:
        return f"Error executing query: {e}"


@tool
def generate_cypher_query(natural_language_query: str, _schema_context: str = "") -> str:
    """
    Generate a Cypher query from a natural language description.

    This tool is a placeholder that returns guidance for query generation.
    In the full implementation, this would be called by the LLM itself.

    Args:
        natural_language_query: The query in natural language
        _schema_context: Optional schema context for query generation (unused)

    Returns:
        Instructions for generating the query
    """
    return f"""
To generate a Cypher query for: "{natural_language_query}"

1. First call get_graph_schema() to understand available nodes and relationships
2. Identify the entities and relationships needed
3. Use the HYBRID approach for geographic queries:
   - Filter by l.countryOfResidenceCode property
   - Join with Country node for metadata if needed
4. Always include LIMIT clause (max 1000)
5. Use parameterized queries for dynamic values
6. Test with execute_cypher_query()

Example patterns:
- Count: MATCH (n:NodeType) WHERE n.property = $value RETURN count(n)
- Top N: MATCH (n:NodeType) RETURN n ORDER BY n.property DESC LIMIT $limit
- Relationships: MATCH (a:TypeA)-[:REL]->(b:TypeB) RETURN a, b
"""
