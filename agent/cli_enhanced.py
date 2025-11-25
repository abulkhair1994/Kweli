"""Enhanced CLI with detailed status indicators."""

import sys

import click
from rich.console import Console
from rich.live import Live
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table

from agent.config import get_config, reset_config
from agent.graph import AnalyticsAgent
from agent.tools.neo4j_tools import get_executor

console = Console()


def create_status_display(iteration: int, status: str, details: str = "") -> Table:
    """Create a status display table."""
    table = Table(show_header=False, box=None, padding=(0, 1))
    table.add_column(style="cyan bold")
    table.add_column()

    # Iteration counter
    table.add_row(f"Iteration {iteration}", "")

    # Status with emoji
    status_emoji = {
        "analyzing": "🤔",
        "querying": "🔍",
        "processing": "⚙️",
        "complete": "✅",
    }
    emoji = status_emoji.get(status, "•")
    table.add_row(f"{emoji} Status:", status.capitalize())

    if details:
        table.add_row("", details)

    return table


@click.command()
@click.option("--verbose", is_flag=True, help="Show detailed execution steps")
def chat_enhanced(verbose: bool):
    """
    Enhanced interactive chat with detailed status indicators.

    Shows different indicators for:
    - 🤔 Analyzing: Agent is thinking about the query
    - 🔍 Querying: Executing database query
    - ⚙️ Processing: Interpreting results
    - ✅ Complete: Response ready
    """
    # Set verbose mode
    if verbose:
        import os
        os.environ["AGENT_VERBOSE"] = "true"
        reset_config()

    config = get_config()

    # Check API key
    if not config.llm.api_key:
        console.print(
            "[red]Error: LLM API key not set.[/red]\n"
            f"Please set {'ANTHROPIC_API_KEY' if config.llm.provider == 'anthropic' else 'OPENAI_API_KEY'} "
            "environment variable.",
            style="bold",
        )
        sys.exit(1)

    # Welcome message
    console.print(
        Panel(
            "[bold cyan]Kweli[/bold cyan] - Your Truthful Guide (Enhanced Mode)\n\n"
            "This version shows detailed execution steps:\n"
            "  🤔 Analyzing - Thinking about your query\n"
            "  🔍 Querying - Running database query\n"
            "  ⚙️ Processing - Interpreting results\n"
            "  ✅ Complete - Response ready\n\n"
            "Type 'exit' or 'quit' to end the session.",
            title="✨ Kweli Analytics (Enhanced)",
            border_style="cyan",
        )
    )

    # Initialize agent
    try:
        agent = AnalyticsAgent()
        console.print("[green]✓[/green] Agent initialized successfully\n")
    except Exception as e:
        console.print(f"[red]Error initializing agent: {e}[/red]")
        sys.exit(1)

    # Chat loop
    while True:
        try:
            # Get user input
            user_query = console.input("[bold blue]You:[/bold blue] ")

            # Check for exit
            if user_query.lower() in ["exit", "quit", "q"]:
                console.print("\n[cyan]Goodbye! 👋[/cyan]")
                break

            # Skip empty queries
            if not user_query.strip():
                continue

            # Stream the agent execution
            iteration = 0
            with Live(create_status_display(1, "analyzing"), console=console, refresh_per_second=4) as live:
                for state_update in agent.stream_query(user_query):
                    iteration += 1

                    # Check if this update contains messages
                    if "agent" in state_update:
                        agent_state = state_update["agent"]
                        messages = agent_state.get("messages", [])

                        if messages:
                            last_message = messages[-1]

                            # Check if it's a tool call
                            if hasattr(last_message, "tool_calls") and last_message.tool_calls:
                                tool_names = [tc.get("name", "unknown") for tc in last_message.tool_calls]
                                if any("execute_cypher" in name or "get_" in name for name in tool_names):
                                    live.update(create_status_display(
                                        iteration,
                                        "querying",
                                        f"Calling: {', '.join(tool_names)}"
                                    ))

                    elif "tools" in state_update:
                        live.update(create_status_display(
                            iteration,
                            "processing",
                            "Interpreting database results..."
                        ))

            # Get final response
            response = agent.query(user_query)

            # Display response
            console.print(
                Panel(
                    Markdown(response),
                    title="✨ Kweli",
                    border_style="green",
                    padding=(1, 2),
                )
            )
            console.print()

        except KeyboardInterrupt:
            console.print("\n[cyan]Goodbye! 👋[/cyan]")
            break
        except Exception as e:
            console.print(f"[red]Error: {e}[/red]\n")
            if verbose:
                import traceback
                console.print(f"[dim]{traceback.format_exc()}[/dim]")

    # Cleanup
    executor = get_executor()
    executor.close()


if __name__ == "__main__":
    chat_enhanced()
