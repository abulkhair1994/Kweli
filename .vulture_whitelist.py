"""Vulture whitelist for false positives."""


# Pydantic validators - cls parameter is used by decorators
def normalize_education_level(cls, v):  # noqa: ARG001
    """Pydantic validator."""


def handle_missing_values(cls, v):  # noqa: ARG001
    """Pydantic validator."""


def handle_invalid_graduation_date(cls, v):  # noqa: ARG001
    """Pydantic validator."""


def validate_dates(cls, values):  # noqa: ARG001
    """Pydantic validator."""


def derive_is_current(cls, values):  # noqa: ARG001
    """Pydantic validator."""


# Context manager parameters (whitelist for __exit__ method)
def context_exit(self, exc_type, exc_val, exc_tb):  # noqa: ARG001, ARG002
    """Whitelist for __exit__ context manager parameters."""
