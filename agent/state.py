"""LangGraph state schema for the analytics agent."""

from typing import Annotated, Literal, TypedDict

from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages

# Intent categories for query classification
Intent = Literal[
    "demographics",  # Geographic, gender, education, socio-economic
    "programs",  # Enrollment, completion, performance
    "skills",  # Skills analysis, combinations
    "employment",  # Employment rates, companies, salaries
    "journey",  # Individual learner profiles
    "general",  # Schema, metadata, counts
    "unknown",  # Cannot determine intent
]


class AgentState(TypedDict):
    """State for the analytics agent graph."""

    # Messages exchanged with the user and LLM
    messages: Annotated[list[AnyMessage], add_messages]

    # Query understanding
    user_query: str  # Original user query
    identified_intent: Intent | None  # Classified intent
    query_params: dict  # Extracted parameters (country, program, limit, etc.)

    # Query execution
    cypher_query: str | None  # Generated or selected Cypher query
    query_results: list[dict] | None  # Results from Neo4j
    error: str | None  # Error message if query failed

    # Control flow
    iteration_count: int  # Number of iterations (prevent infinite loops)
    max_iterations: int  # Maximum allowed iterations
    should_continue: bool  # Whether to continue or finish


def create_initial_state(user_query: str, max_iterations: int = 10) -> AgentState:
    """
    Create the initial agent state.

    Args:
        user_query: The user's query
        max_iterations: Maximum number of iterations

    Returns:
        Initial AgentState
    """
    return {
        "messages": [],
        "user_query": user_query,
        "identified_intent": None,
        "query_params": {},
        "cypher_query": None,
        "query_results": None,
        "error": None,
        "iteration_count": 0,
        "max_iterations": max_iterations,
        "should_continue": True,
    }
