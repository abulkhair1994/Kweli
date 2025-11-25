"""Integration tests for the agent (requires running Neo4j)."""

import os

import pytest

# Mark all tests in this file as integration tests
pytestmark = pytest.mark.integration


@pytest.fixture
def neo4j_available():
    """Check if Neo4j is available for testing."""
    try:
        from agent.tools.neo4j_tools import get_executor

        executor = get_executor()
        executor.execute_query("MATCH (n) RETURN count(n) as total LIMIT 1")
        return True
    except Exception:
        return False


@pytest.fixture
def llm_available():
    """Check if LLM API key is available."""
    return (
        os.getenv("ANTHROPIC_API_KEY") is not None or os.getenv("OPENAI_API_KEY") is not None
    )


@pytest.mark.skipif(
    not os.getenv("TEST_NEO4J_INTEGRATION"),
    reason="Set TEST_NEO4J_INTEGRATION=1 to run Neo4j integration tests",
)
class TestNeo4jExecutor:
    """Integration tests for Neo4j executor."""

    def test_execute_simple_query(self, neo4j_available):
        """Test executing a simple query."""
        if not neo4j_available:
            pytest.skip("Neo4j not available")

        from agent.tools.neo4j_tools import get_executor

        executor = get_executor()
        result = executor.execute_query("MATCH (n) RETURN count(n) as total LIMIT 1")

        assert len(result) == 1
        assert "total" in result[0]
        assert isinstance(result[0]["total"], int)

        executor.close()

    def test_execute_with_parameters(self, neo4j_available):
        """Test executing a query with parameters."""
        if not neo4j_available:
            pytest.skip("Neo4j not available")

        from agent.tools.neo4j_tools import get_executor

        executor = get_executor()
        result = executor.execute_query(
            "MATCH (l:Learner) WHERE l.countryOfResidenceCode = $code "
            "RETURN count(l) as count LIMIT 1",
            {"code": "EG"},
        )

        assert len(result) == 1
        assert "count" in result[0]

        executor.close()

    def test_get_schema(self, neo4j_available):
        """Test fetching graph schema."""
        if not neo4j_available:
            pytest.skip("Neo4j not available")

        from agent.tools.neo4j_tools import get_executor

        executor = get_executor()
        schema = executor.get_schema()

        assert "node_types" in schema
        assert "relationship_types" in schema
        assert len(schema["node_types"]) > 0

        executor.close()

    def test_reject_write_operation(self, neo4j_available):
        """Test that write operations are rejected."""
        if not neo4j_available:
            pytest.skip("Neo4j not available")

        from agent.tools.neo4j_tools import get_executor

        executor = get_executor()

        with pytest.raises(ValueError, match="write operations"):
            executor.execute_query("CREATE (n:TestNode)")

        executor.close()


@pytest.mark.skipif(
    not os.getenv("TEST_AGENT_INTEGRATION"),
    reason="Set TEST_AGENT_INTEGRATION=1 to run agent integration tests",
)
class TestAnalyticsAgent:
    """Integration tests for the full agent (requires LLM API key)."""

    def test_agent_initialization(self, llm_available):
        """Test agent initialization."""
        if not llm_available:
            pytest.skip("LLM API key not available")

        from agent.graph import AnalyticsAgent

        agent = AnalyticsAgent()
        assert agent.graph is not None
        assert agent.config is not None

    def test_simple_query(self, neo4j_available, llm_available):
        """Test a simple agent query."""
        if not neo4j_available:
            pytest.skip("Neo4j not available")
        if not llm_available:
            pytest.skip("LLM API key not available")

        from agent.graph import AnalyticsAgent

        agent = AnalyticsAgent()
        response = agent.query("How many node types are in the graph?")

        assert isinstance(response, str)
        assert len(response) > 0
        # Response should mention node types
        assert "node" in response.lower() or "type" in response.lower()

    def test_demographics_query(self, neo4j_available, llm_available):
        """Test a demographics query."""
        if not neo4j_available:
            pytest.skip("Neo4j not available")
        if not llm_available:
            pytest.skip("LLM API key not available")

        from agent.graph import AnalyticsAgent

        agent = AnalyticsAgent()
        response = agent.query("How many learners are from Egypt?")

        assert isinstance(response, str)
        assert len(response) > 0

    def test_program_query(self, neo4j_available, llm_available):
        """Test a program-related query."""
        if not neo4j_available:
            pytest.skip("Neo4j not available")
        if not llm_available:
            pytest.skip("LLM API key not available")

        from agent.graph import AnalyticsAgent

        agent = AnalyticsAgent()
        response = agent.query("What are the top 5 programs by enrollment?")

        assert isinstance(response, str)
        assert len(response) > 0


@pytest.mark.skipif(
    not os.getenv("TEST_AGENT_INTEGRATION"),
    reason="Set TEST_AGENT_INTEGRATION=1 to run agent integration tests",
)
class TestAgentTools:
    """Integration tests for agent tools."""

    def test_get_graph_schema_tool(self, neo4j_available):
        """Test get_graph_schema tool."""
        if not neo4j_available:
            pytest.skip("Neo4j not available")

        from agent.tools import get_graph_schema

        result = get_graph_schema.invoke({})

        assert "node_types" in result
        assert "relationship_types" in result
        assert isinstance(result["node_types"], list)

    def test_execute_cypher_tool(self, neo4j_available):
        """Test execute_cypher_query tool."""
        if not neo4j_available:
            pytest.skip("Neo4j not available")

        from agent.tools import execute_cypher_query

        result = execute_cypher_query.invoke(
            {"query": "MATCH (n) RETURN count(n) as total LIMIT 1"}
        )

        assert isinstance(result, str)
        assert "total" in result.lower() or "result" in result.lower()

    def test_top_countries_tool(self, neo4j_available):
        """Test get_top_countries_by_learners tool."""
        if not neo4j_available:
            pytest.skip("Neo4j not available")

        from agent.tools import get_top_countries_by_learners

        result = get_top_countries_by_learners.invoke({"limit": 5})

        assert "query" in result
        assert "params" in result
        assert result["params"]["limit"] == 5
