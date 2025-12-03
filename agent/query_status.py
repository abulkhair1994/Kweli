"""Thread-safe query status signaling for CLI spinner."""

import threading
from collections.abc import Callable

# Thread-safe event for query status
_query_active = threading.Event()

# Optional callback for custom handling
_query_callback: Callable[[str, str], None] | None = None


def notify_query_start(query: str = "") -> None:
    """Signal that a database query has started."""
    _query_active.set()
    if _query_callback:
        _query_callback("start", query)


def notify_query_end(query: str = "") -> None:
    """Signal that a database query has ended."""
    _query_active.clear()
    if _query_callback:
        _query_callback("end", query)


def is_query_active() -> bool:
    """Check if a database query is currently running."""
    return _query_active.is_set()


def set_query_callback(callback: Callable[[str, str], None] | None) -> None:
    """Set optional callback for query events."""
    global _query_callback
    _query_callback = callback


def reset() -> None:
    """Reset state (useful for testing)."""
    _query_active.clear()
    global _query_callback
    _query_callback = None
