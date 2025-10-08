"""
Structured logging for the ETL pipeline.

Uses structlog for JSON-formatted logs with context.
"""

import logging
import sys
from pathlib import Path
from typing import Any

import structlog
from structlog.types import FilteringBoundLogger


def setup_logging(
    log_level: str = "INFO",
    log_format: str = "json",
    log_file: Path | str | None = None,
) -> FilteringBoundLogger:
    """
    Setup structured logging.

    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR)
        log_format: Format ('json' or 'console')
        log_file: Optional log file path

    Returns:
        Configured logger instance
    """
    # Configure standard logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, log_level.upper()),
    )

    # Processors for structlog
    processors: list[Any] = [
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    # Add format-specific processor
    if log_format == "json":
        processors.append(structlog.processors.JSONRenderer())
    else:
        processors.append(structlog.dev.ConsoleRenderer())

    # Configure structlog
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Add file handler if specified
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)

        file_handler = logging.FileHandler(log_path)
        file_handler.setLevel(getattr(logging, log_level.upper()))
        logging.getLogger().addHandler(file_handler)

    return structlog.get_logger()


def get_logger(name: str | None = None) -> FilteringBoundLogger:
    """Get a logger instance."""
    return structlog.get_logger(name)
