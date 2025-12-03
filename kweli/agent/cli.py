"""CLI interface for Kweli - The Impact Learners Analytics Agent."""

import sys
import threading
import time
import uuid

import click
from rich.console import Console
from rich.live import Live
from rich.markdown import Markdown
from rich.panel import Panel
from rich.spinner import Spinner

from kweli.agent.callbacks import flush_langfuse
from kweli.agent.config import get_config, reset_config
from kweli.agent.context import ContextExtractor
from kweli.agent.graph import AnalyticsAgent
from kweli.agent.query_status import is_query_active
from kweli.agent.query_status import reset as reset_query_status
from kweli.agent.tools.neo4j_tools import get_executor

console = Console()


def run_with_query_spinner(
    agent: AnalyticsAgent,
    query: str,
    thread_id: str | None = None,
) -> str:
    """Run agent query with spinner that shows only during DB operations."""
    result: str | None = None
    error: Exception | None = None

    def worker():
        nonlocal result, error
        try:
            if thread_id:
                result = agent.query(query, thread_id=thread_id)
            else:
                result = agent.query(query)
        except Exception as e:
            error = e

    # Start worker thread
    thread = threading.Thread(target=worker, daemon=True)
    thread.start()

    # Monitor and display spinner only during DB queries
    spinner = Spinner("dots", text="[dim cyan]querying...[/dim cyan]")
    empty = ""

    with Live(empty, console=console, transient=True, refresh_per_second=10) as live:
        while thread.is_alive():
            if is_query_active():
                live.update(spinner)
            else:
                live.update(empty)
            time.sleep(0.05)

    thread.join()
    reset_query_status()

    if error:
        raise error
    return result  # type: ignore


@click.group()
@click.version_option(version="0.1.0")
def cli():
    """Kweli - Your truthful guide to Impact Learners data."""
    pass


@cli.command()
@click.option("--verbose", is_flag=True, help="Enable verbose output")
@click.option("--show-tools", is_flag=True, help="Show tool execution details")
def chat(verbose: bool, show_tools: bool):
    """
    Start an interactive chat session with the analytics agent.

    Example:
        $ impact-agent chat
        >>> How many learners are from Egypt?
    """
    # Set verbose mode
    if verbose:
        import os

        os.environ["AGENT_VERBOSE"] = "true"
        reset_config()

    config = get_config()

    # Check if API key is set
    if not config.llm.api_key:
        console.print(
            "[red]Error: LLM API key not set.[/red]\n"
            f"Please set {'ANTHROPIC_API_KEY' if config.llm.provider == 'anthropic' else 'OPENAI_API_KEY'} "
            "environment variable.",
            style="bold",
        )
        sys.exit(1)

    # Welcome message (compact)
    console.print("[bold cyan]✨ Kweli[/bold cyan] - Your Truthful Guide to Impact Learners Data")
    console.print("[dim]Commands: reset | context | exit • Type 'examples' for query ideas[/dim]")
    console.rule(style="dim cyan")

    # Initialize agent
    try:
        agent = AnalyticsAgent()
    except Exception as e:
        console.print(f"[red]Error initializing agent: {e}[/red]")
        sys.exit(1)

    # Generate session thread ID for conversation persistence
    thread_id = str(uuid.uuid4())

    # Track active filters for context display
    active_filters = {}

    # Chat loop
    while True:
        try:
            # Get user input
            user_query = console.input("[bold blue]You:[/bold blue] ")

            # Check for exit
            if user_query.lower() in ["exit", "quit", "q"]:
                console.print("\n[cyan]Goodbye! 👋[/cyan]")
                break

            # Handle reset command - generate new thread ID
            if user_query.lower() == "reset":
                thread_id = str(uuid.uuid4())
                active_filters = {}
                console.print(f"[green]✓[/green] Context reset. New session: {thread_id[:8]}...\n")
                continue

            # Handle examples command - show query examples
            if user_query.lower() == "examples":
                console.print(
                    "[dim]Example queries:[/dim]\n"
                    "  • How many learners are from Egypt?\n"
                    "  • What's the completion rate for Software Engineering?\n"
                    "  • Show me the top 10 skills for employed learners\n"
                    "  • What's the employment rate by program?\n"
                )
                continue

            # Handle context command - show active filters
            if user_query.lower() == "context":
                if active_filters:
                    filter_display = "\n".join(f"  • [cyan]{k}[/cyan]: {v}" for k, v in active_filters.items())
                    console.print(
                        Panel(
                            f"[bold]Active Filters:[/bold]\n{filter_display}",
                            title="📊 Session Context",
                            border_style="cyan",
                        )
                    )
                else:
                    console.print("[dim]No active filters in current session[/dim]")
                console.print()
                continue

            # Skip empty queries
            if not user_query.strip():
                continue

            # Show status indicator with tool execution details
            if show_tools or verbose:

                # Stream execution to show tools
                for state in agent.stream_query(user_query, thread_id=thread_id):
                    if "agent" in state:
                        agent_state = state["agent"]
                        messages = agent_state.get("messages", [])
                        if messages:
                            last_msg = messages[-1]
                            if hasattr(last_msg, "tool_calls") and last_msg.tool_calls:
                                for tool_call in last_msg.tool_calls:
                                    tool_name = tool_call.get("name", "unknown")
                                    console.print(f"[dim]🔍 Calling tool: [cyan]{tool_name}[/cyan][/dim]")

                        # Extract filters from query params and cypher
                        cypher = agent_state.get("cypher_query")
                        params = agent_state.get("query_params", {})
                        if cypher or params:
                            extracted = ContextExtractor.extract_all(cypher, params)
                            if extracted:
                                active_filters.update(extracted)
                    elif "tools" in state:
                        console.print("[dim]⚙️  Processing results...[/dim]")

                # Get final response
                response = agent.query(user_query, thread_id=thread_id)
            else:
                response = run_with_query_spinner(agent, user_query, thread_id)

            # Display response
            console.print(
                Panel(
                    Markdown(response),
                    title="✨ Kweli",
                    border_style="green",
                    padding=(1, 2),
                )
            )

            # Show active context indicator if filters are present
            if active_filters:
                filter_str = ContextExtractor.format_filters(active_filters)
                console.print(f"[dim]💡 Active context: {filter_str}[/dim]")

            console.print()

        except KeyboardInterrupt:
            console.print("\n[cyan]Goodbye! 👋[/cyan]")
            break
        except Exception as e:
            console.print(f"[red]Error: {e}[/red]\n")

    # Cleanup
    flush_langfuse()  # Ensure all Langfuse events are sent
    executor = get_executor()
    executor.close()


@cli.command()
@click.argument("query")
@click.option("--verbose", is_flag=True, help="Enable verbose output")
def query(query: str, verbose: bool):
    """
    Execute a single query and display the result.

    Example:
        $ impact-agent query "How many learners are from Egypt?"
    """
    # Set verbose mode
    if verbose:
        import os

        os.environ["AGENT_VERBOSE"] = "true"
        reset_config()

    config = get_config()

    # Check if API key is set
    if not config.llm.api_key:
        console.print(
            f"[red]Error: {'ANTHROPIC_API_KEY' if config.llm.provider == 'anthropic' else 'OPENAI_API_KEY'} "
            "environment variable not set.[/red]"
        )
        sys.exit(1)

    # Initialize agent
    try:
        agent = AnalyticsAgent()
    except Exception as e:
        console.print(f"[red]Error initializing agent: {e}[/red]")
        sys.exit(1)

    # Execute query
    try:
        response = run_with_query_spinner(agent, query)

        # Display response
        console.print(Markdown(response))

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        sys.exit(1)
    finally:
        # Cleanup
        flush_langfuse()  # Ensure all Langfuse events are sent
        executor = get_executor()
        executor.close()


@cli.command()
def test_connection():
    """Test the connection to Neo4j database."""
    console.print("[yellow]Testing Neo4j connection...[/yellow]\n")

    try:
        executor = get_executor()

        # Test query
        result = executor.execute_query("MATCH (n) RETURN count(n) as total LIMIT 1")

        if result:
            total_nodes = result[0].get("total", 0)
            console.print("[green]✓[/green] Connection successful!")
            console.print(f"[green]✓[/green] Total nodes in database: {total_nodes:,}")
        else:
            console.print("[red]✗[/red] Query returned no results")

        # Get schema
        schema = executor.get_schema()
        console.print(f"[green]✓[/green] Node types: {len(schema['node_types'])}")
        console.print(f"[green]✓[/green] Relationship types: {len(schema['relationship_types'])}")

        executor.close()

    except Exception as e:
        console.print(f"[red]✗[/red] Connection failed: {e}")
        sys.exit(1)


@cli.command()
def config_info():
    """Display current agent configuration."""
    config = get_config()

    console.print(
        Panel(
            f"[bold]LLM Provider:[/bold] {config.llm.provider}\n"
            f"[bold]Model:[/bold] {config.llm.model}\n"
            f"[bold]Temperature:[/bold] {config.llm.temperature}\n"
            f"[bold]Max Tokens:[/bold] {config.llm.max_tokens}\n\n"
            f"[bold]Neo4j URI:[/bold] {config.neo4j.uri}\n"
            f"[bold]Neo4j User:[/bold] {config.neo4j.user}\n\n"
            f"[bold]Max Iterations:[/bold] {config.agent.max_iterations}\n"
            f"[bold]Query Timeout:[/bold] {config.agent.query_timeout}s\n"
            f"[bold]Max Results:[/bold] {config.agent.max_results}\n"
            f"[bold]Caching:[/bold] {'Enabled' if config.agent.enable_caching else 'Disabled'}\n"
            f"[bold]Verbose:[/bold] {'Yes' if config.agent.verbose else 'No'}",
            title="📋 Kweli Configuration",
            border_style="blue",
        )
    )


@cli.command()
def examples():
    """Show example queries you can ask the agent."""
    examples_text = """
## Demographics & Geographic

- How many learners are from Egypt?
- Show me the top 10 countries by learner count
- What's the distribution of learners by country?
- How many learners are from rural areas?

## Programs

- What's the completion rate for Software Engineering program?
- Show me program completion rates for all programs
- Which programs have the best employment outcomes?
- Compare completion rates across programs

## Skills

- What are the top 20 skills among learners?
- Show me the most common skills for employed learners
- What skills do Software Engineering graduates have?
- Which skills are most common in Egypt?

## Employment

- What's the employment rate for graduates?
- What's the employment rate by program?
- How long does it take graduates to find employment?
- Show me the top employers for our learners

## Learner Journeys

- Show me the profile for learner [email_hash]
- What's the complete journey for learner [email_hash]?

## General

- What data is available in the knowledge graph?
- How many nodes and relationships are there?
- What node types exist?
"""

    console.print(Panel(Markdown(examples_text), title="💡 Example Queries", border_style="yellow"))


if __name__ == "__main__":
    cli()
