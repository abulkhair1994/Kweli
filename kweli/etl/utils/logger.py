"""
Structured logging for the ETL pipeline.

Uses structlog for JSON-formatted logs with context.
"""


import structlog
from structlog.types import FilteringBoundLogger


def get_logger(name: str | None = None) -> FilteringBoundLogger:
    """Get a logger instance."""
    return structlog.get_logger(name)
