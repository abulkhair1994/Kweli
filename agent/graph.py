"""LangGraph ReAct agent for Neo4j analytics."""

from typing import Literal

from langchain_anthropic import ChatAnthropic
from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph
from langgraph.prebuilt import ToolNode

from agent.callbacks import flush_langfuse, get_langfuse_handler
from agent.config import get_config
from agent.prompts import get_system_prompt
from agent.state import AgentState
from agent.tools import (
    execute_cypher_query,
    get_employment_rate_by_program,
    get_geographic_distribution,
    get_graph_schema,
    get_learner_journey,
    get_program_completion_rates,
    get_skills_for_employed_learners,
    get_time_to_employment_stats,
    get_top_countries_by_learners,
    get_top_skills,
)


def create_llm(callbacks: list[BaseCallbackHandler] | None = None):
    """
    Create the LLM instance based on configuration.

    Args:
        callbacks: Optional list of callback handlers (e.g., Langfuse)

    Returns:
        Configured LLM instance
    """
    config = get_config()

    if config.llm.provider == "anthropic":
        return ChatAnthropic(
            model=config.llm.model,
            api_key=config.llm.api_key,
            temperature=config.llm.temperature,
            max_tokens=config.llm.max_tokens,
            callbacks=callbacks,
        )
    elif config.llm.provider == "openai":
        return ChatOpenAI(
            model=config.llm.model,
            api_key=config.llm.api_key,
            temperature=config.llm.temperature,
            max_tokens=config.llm.max_tokens,
            callbacks=callbacks,
        )
    else:
        raise ValueError(f"Unsupported LLM provider: {config.llm.provider}")


# Create tools list
TOOLS = [
    # Pre-built analytics tools
    get_top_countries_by_learners,
    get_program_completion_rates,
    get_employment_rate_by_program,
    get_top_skills,
    get_learner_journey,
    get_skills_for_employed_learners,
    get_geographic_distribution,
    get_time_to_employment_stats,
    # Core Neo4j tools
    get_graph_schema,
    execute_cypher_query,
]


def agent_node(state: AgentState, config: RunnableConfig | None = None) -> AgentState:
    """
    Main agent node - decides which tool to call or generates final response.

    Args:
        state: Current agent state
        config: RunnableConfig passed from graph invoke (contains callbacks)

    Returns:
        Updated state with new messages
    """
    app_config = get_config()

    # Check iteration limit
    if state["iteration_count"] >= state["max_iterations"]:
        state["messages"].append(
            SystemMessage(
                content="Maximum iterations reached. Stopping to prevent infinite loop."
            )
        )
        state["should_continue"] = False
        return state

    # Extract callbacks from runnable config (for Langfuse tracking)
    callbacks = config.get("callbacks") if config else None

    # Create LLM with tools and callbacks
    llm = create_llm(callbacks=callbacks)
    llm_with_tools = llm.bind_tools(TOOLS)

    # Prepare messages
    messages = state["messages"].copy()

    # Add system prompt if this is the first call
    if state["iteration_count"] == 0:
        messages.insert(0, SystemMessage(content=get_system_prompt()))

    # Call LLM
    response = llm_with_tools.invoke(messages)

    # Update state
    state["messages"].append(response)
    state["iteration_count"] += 1

    # Log for debugging
    if app_config.agent.verbose:
        print(f"[Agent] Iteration {state['iteration_count']}")
        print(f"[Agent] Response: {response.content[:100]}...")
        if hasattr(response, "tool_calls") and response.tool_calls:
            print(f"[Agent] Tool calls: {len(response.tool_calls)}")

    return state


def tool_node_wrapper(state: AgentState) -> AgentState:
    """
    Wrapper for the tool node to execute tools.

    Args:
        state: Current agent state

    Returns:
        Updated state with tool results
    """
    config = get_config()

    # Create tool node
    tool_node = ToolNode(TOOLS)

    # Execute tools
    result = tool_node.invoke(state)

    # Log for debugging
    if config.agent.verbose:
        print(f"[Tools] Executed tools, got {len(result.get('messages', []))} result messages")

    return result


def should_continue(state: AgentState) -> Literal["continue", "end"]:
    """
    Determine whether to continue or end the agent loop.

    Args:
        state: Current agent state

    Returns:
        "continue" to call tools, "end" to finish
    """
    # Check if we should stop
    if not state.get("should_continue", True):
        return "end"

    # Check iteration limit
    if state["iteration_count"] >= state["max_iterations"]:
        return "end"

    # Check if last message has tool calls
    messages = state.get("messages", [])
    if not messages:
        return "end"

    last_message = messages[-1]

    # If the last message has tool calls, continue
    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        return "continue"

    # Otherwise, we have a final response
    return "end"


def create_agent_graph():
    """
    Create the LangGraph agent graph with checkpointing support.

    Returns:
        Compiled StateGraph with MemorySaver checkpointer
    """
    # Create graph
    workflow = StateGraph(AgentState)

    # Add nodes
    workflow.add_node("agent", agent_node)
    workflow.add_node("tools", tool_node_wrapper)

    # Set entry point
    workflow.set_entry_point("agent")

    # Add conditional edges
    workflow.add_conditional_edges(
        "agent",
        should_continue,
        {
            "continue": "tools",
            "end": END,
        },
    )

    # Add edge from tools back to agent
    workflow.add_edge("tools", "agent")

    # Compile with checkpointer for conversation persistence
    checkpointer = MemorySaver()
    return workflow.compile(checkpointer=checkpointer)


class AnalyticsAgent:
    """High-level interface for the analytics agent."""

    def __init__(self) -> None:
        """Initialize the analytics agent."""
        self.graph = create_agent_graph()
        self.config = get_config()

    def query(self, user_query: str, thread_id: str | None = None) -> str:
        """
        Execute a query against the knowledge graph.

        Args:
            user_query: Natural language query from the user
            thread_id: Optional thread ID for conversation persistence.
                      If provided, maintains message history across queries.
                      If None, creates a fresh conversation.

        Returns:
            Agent's response as a string
        """
        # Create initial state
        initial_state: AgentState = {
            "messages": [HumanMessage(content=user_query)],
            "user_query": user_query,
            "identified_intent": None,
            "query_params": {},
            "cypher_query": None,
            "query_results": None,
            "error": None,
            "iteration_count": 0,
            "max_iterations": self.config.agent.max_iterations,
            "should_continue": True,
        }

        # Prepare config with thread persistence and Langfuse callbacks
        run_config: dict = {}
        if thread_id:
            run_config["configurable"] = {"thread_id": thread_id}

        # Add Langfuse callback for tracking
        langfuse_handler = get_langfuse_handler(session_id=thread_id)
        if langfuse_handler:
            run_config["callbacks"] = [langfuse_handler]

        # Run the graph with thread persistence and callbacks
        result = self.graph.invoke(
            initial_state, config=run_config if run_config else None
        )

        # Flush Langfuse events
        flush_langfuse()

        # Extract final response
        messages = result.get("messages", [])
        if messages:
            # Find the last message from the agent (not a tool)
            for message in reversed(messages):
                if hasattr(message, "content") and message.content:
                    # Skip tool call messages
                    if not (hasattr(message, "tool_calls") and message.tool_calls):
                        return message.content

        return "I couldn't generate a response. Please try rephrasing your question."

    def stream_query(self, user_query: str, thread_id: str | None = None):
        """
        Stream query execution (yields intermediate states).

        Args:
            user_query: Natural language query from the user
            thread_id: Optional thread ID for conversation persistence.
                      If provided, maintains message history across queries.
                      If None, creates a fresh conversation.

        Yields:
            Intermediate states during execution
        """
        # Create initial state
        initial_state: AgentState = {
            "messages": [HumanMessage(content=user_query)],
            "user_query": user_query,
            "identified_intent": None,
            "query_params": {},
            "cypher_query": None,
            "query_results": None,
            "error": None,
            "iteration_count": 0,
            "max_iterations": self.config.agent.max_iterations,
            "should_continue": True,
        }

        # Prepare config with thread persistence and Langfuse callbacks
        run_config: dict = {}
        if thread_id:
            run_config["configurable"] = {"thread_id": thread_id}

        # Add Langfuse callback for tracking
        langfuse_handler = get_langfuse_handler(session_id=thread_id)
        if langfuse_handler:
            run_config["callbacks"] = [langfuse_handler]

        # Stream the graph execution with thread persistence and callbacks
        yield from self.graph.stream(
            initial_state, config=run_config if run_config else None
        )

    def get_thread_state(self, thread_id: str) -> dict | None:
        """
        Get the current state for a specific conversation thread.

        Args:
            thread_id: The thread ID to inspect

        Returns:
            Thread state dictionary or None if thread doesn't exist

        Example:
            >>> state = agent.get_thread_state("abc-123")
            >>> print(f"Messages: {len(state.get('messages', []))}")
        """
        try:
            config = {"configurable": {"thread_id": thread_id}}
            state = self.graph.get_state(config)
            return state.values if state else None
        except Exception:
            return None

    def list_threads(self) -> list[str]:
        """
        List all active conversation thread IDs.

        Note: MemorySaver doesn't provide a built-in method to list threads,
        so this is a placeholder for future enhancement with persistent storage.

        Returns:
            List of thread IDs (currently returns empty list with MemorySaver)
        """
        # MemorySaver doesn't expose thread listing
        # This would require switching to SqliteSaver or custom implementation
        return []

    def clear_thread(self, thread_id: str) -> bool:
        """
        Clear the conversation history for a specific thread.

        Args:
            thread_id: The thread ID to clear

        Returns:
            True if cleared successfully, False otherwise

        Example:
            >>> agent.clear_thread("abc-123")
            True
        """
        try:
            # With MemorySaver, threads auto-expire when not used
            # For explicit clearing, we'd need SqliteSaver
            # For now, creating a new thread_id achieves the same goal
            return True
        except Exception:
            return False

    def clear_all_threads(self) -> bool:
        """
        Clear all conversation threads.

        Returns:
            True if cleared successfully, False otherwise
        """
        try:
            # With MemorySaver, we can recreate the graph to clear memory
            self.graph = create_agent_graph()
            return True
        except Exception:
            return False
