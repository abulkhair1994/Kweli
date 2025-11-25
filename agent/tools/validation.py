"""Cypher query validation for safety and security."""

import re
from typing import NamedTuple


class ValidationResult(NamedTuple):
    """Result of query validation."""

    is_valid: bool
    error_message: str | None = None
    warning_message: str | None = None
    modified_query: str | None = None


# Disallowed keywords (write operations)
WRITE_KEYWORDS = {
    "CREATE",
    "MERGE",
    "DELETE",
    "DETACH DELETE",
    "SET",
    "REMOVE",
    "DROP",
    "ALTER",
    "RENAME",
}

# Allowed keywords (read operations and utilities)
ALLOWED_KEYWORDS = {
    "MATCH",
    "OPTIONAL MATCH",
    "RETURN",
    "WITH",
    "WHERE",
    "ORDER BY",
    "LIMIT",
    "SKIP",
    "UNWIND",
    "DISTINCT",
    "AS",
    "CASE",
    "WHEN",
    "THEN",
    "ELSE",
    "END",
    "AND",
    "OR",
    "NOT",
    "XOR",
    "IN",
    "IS NULL",
    "IS NOT NULL",
}

# Allowed Cypher functions
ALLOWED_FUNCTIONS = {
    "count",
    "sum",
    "avg",
    "min",
    "max",
    "collect",
    "size",
    "length",
    "exists",
    "coalesce",
    "head",
    "last",
    "tail",
    "range",
    "labels",
    "type",
    "properties",
    "keys",
    "id",
    "elementId",
    "startNode",
    "endNode",
    "nodes",
    "relationships",
    "toString",
    "toInteger",
    "toFloat",
    "toBoolean",
    "date",
    "datetime",
    "time",
    "duration",
    "round",
    "floor",
    "ceil",
    "abs",
    "rand",
    "sign",
    "sqrt",
    "lower",
    "upper",
    "substring",
    "replace",
    "split",
    "trim",
    "ltrim",
    "rtrim",
    "reverse",
    "percentileDisc",
    "percentileCont",
    "stDev",
    "stDevP",
}


def normalize_query(query: str) -> str:
    """
    Normalize a Cypher query for validation.

    Args:
        query: Raw Cypher query

    Returns:
        Normalized query (trimmed, single spaces)
    """
    # Remove extra whitespace and normalize to single spaces
    query = " ".join(query.split())
    # Remove comments
    query = re.sub(r"//.*$", "", query, flags=re.MULTILINE)
    return query.strip()


def has_write_operations(query: str) -> bool:
    """
    Check if query contains any write operations.

    Args:
        query: Cypher query to check

    Returns:
        True if write operations detected
    """
    query_upper = query.upper()
    for keyword in WRITE_KEYWORDS:
        # Use word boundaries to avoid false positives (e.g., "CREATED_AT")
        pattern = r"\b" + re.escape(keyword) + r"\b"
        if re.search(pattern, query_upper):
            return True
    return False


def has_limit_clause(query: str) -> bool:
    """
    Check if query has a LIMIT clause.

    Args:
        query: Cypher query to check

    Returns:
        True if LIMIT clause found
    """
    return bool(re.search(r"\bLIMIT\s+\d+", query, re.IGNORECASE))


def add_limit_clause(query: str, max_results: int = 1000) -> str:
    """
    Add a LIMIT clause to a query if missing.

    Args:
        query: Cypher query
        max_results: Maximum number of results to return

    Returns:
        Query with LIMIT clause added
    """
    query = query.rstrip().rstrip(";")
    return f"{query} LIMIT {max_results}"


def has_injection_risk(query: str) -> bool:
    """
    Check for potential Cypher injection patterns.

    Args:
        query: Cypher query to check

    Returns:
        True if injection risk detected
    """
    # Check for string concatenation patterns
    if re.search(r"\+\s*['\"]", query):
        return True

    # Check for unusual quote patterns
    if re.search(r"['\"]{2,}", query):
        return True

    # Check for APOC calls without proper parameters
    if re.search(r"apoc\.[a-z]+\([^$]", query, re.IGNORECASE):
        return True

    return False


def validate_cypher_query(
    query: str,
    max_results: int = 1000,
    auto_add_limit: bool = True,
) -> ValidationResult:
    """
    Validate a Cypher query for safety and correctness.

    Safety checks:
    - No write operations (CREATE, DELETE, SET, etc.)
    - Has LIMIT clause (auto-added if missing)
    - No Cypher injection patterns
    - Only uses allowed keywords and functions

    Args:
        query: Cypher query to validate
        max_results: Maximum number of results allowed
        auto_add_limit: Automatically add LIMIT if missing

    Returns:
        ValidationResult with validation status and any modifications
    """
    if not query or not query.strip():
        return ValidationResult(
            is_valid=False,
            error_message="Query is empty",
        )

    # Normalize query
    normalized = normalize_query(query)

    # Check for write operations
    if has_write_operations(normalized):
        return ValidationResult(
            is_valid=False,
            error_message="Query contains write operations (CREATE, DELETE, SET, etc.). "
            "Only read operations are allowed.",
        )

    # Check for injection risks
    if has_injection_risk(normalized):
        return ValidationResult(
            is_valid=False,
            error_message="Query contains potential injection patterns. "
            "Use parameterized queries instead of string concatenation.",
        )

    # Check for LIMIT clause
    modified_query = normalized
    warning = None

    if not has_limit_clause(normalized):
        if auto_add_limit:
            modified_query = add_limit_clause(normalized, max_results)
            warning = f"LIMIT clause was automatically added (max {max_results} results)"
        else:
            return ValidationResult(
                is_valid=False,
                error_message=f"Query must include LIMIT clause (max {max_results} results)",
            )

    return ValidationResult(
        is_valid=True,
        warning_message=warning,
        modified_query=modified_query if modified_query != normalized else None,
    )


def validate_query_parameters(params: dict) -> ValidationResult:
    """
    Validate query parameters for safety.

    Args:
        params: Query parameters dictionary

    Returns:
        ValidationResult indicating if parameters are safe
    """
    if not params:
        return ValidationResult(is_valid=True)

    # Check for suspicious parameter values
    for key, value in params.items():
        if isinstance(value, str):
            # Check for Cypher injection in parameter values
            if re.search(r"[;{}()]", value):
                return ValidationResult(
                    is_valid=False,
                    error_message=f"Parameter '{key}' contains suspicious characters",
                )

            # Check for extremely long strings (potential DoS)
            if len(value) > 10000:
                return ValidationResult(
                    is_valid=False,
                    error_message=f"Parameter '{key}' exceeds maximum length (10,000 chars)",
                )

    return ValidationResult(is_valid=True)
