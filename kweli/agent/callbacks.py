"""Langfuse callback handler for conversation tracking."""

import os

from langfuse.langchain import CallbackHandler

from kweli.agent.config import get_config


def get_langfuse_handler(
    session_id: str | None = None,
    user_id: str | None = None,
    trace_name: str = "kweli-analytics",
) -> CallbackHandler | None:
    """
    Create a Langfuse callback handler for LangChain/LangGraph tracking.

    Langfuse reads credentials from environment variables:
    - LANGFUSE_SECRET_KEY
    - LANGFUSE_PUBLIC_KEY
    - LANGFUSE_HOST

    Args:
        session_id: Session ID for conversation grouping (maps to thread_id)
        user_id: Optional user identifier
        trace_name: Name for the trace in Langfuse

    Returns:
        CallbackHandler if Langfuse is enabled, None otherwise
    """
    config = get_config()

    if not config.langfuse.enabled:
        return None

    # Langfuse reads from env vars, but we can ensure they're set
    # from our config (in case loaded from .env differently)
    if config.langfuse.secret_key:
        os.environ["LANGFUSE_SECRET_KEY"] = config.langfuse.secret_key
    if config.langfuse.public_key:
        os.environ["LANGFUSE_PUBLIC_KEY"] = config.langfuse.public_key
    if config.langfuse.host:
        os.environ["LANGFUSE_HOST"] = config.langfuse.host

    # Create handler - it will pick up credentials from env vars
    # We can pass session_id and user_id via tags/metadata
    handler = CallbackHandler()

    # Set session/user context via update_stateful_client
    # This creates a trace context for the conversation
    if session_id or user_id:
        handler.session_id = session_id
        handler.user_id = user_id
        handler.trace_name = trace_name

    return handler


def flush_langfuse() -> None:
    """Flush any pending Langfuse events (call before exit)."""
    try:
        from langfuse import Langfuse

        config = get_config()
        if config.langfuse.enabled:
            langfuse = Langfuse()
            langfuse.flush()
    except Exception:
        pass  # Silently ignore flush errors
