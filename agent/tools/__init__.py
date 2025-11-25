"""Agent tools for Neo4j analytics."""

from agent.tools.analytics_tools import (
    get_employment_rate_by_program,
    get_geographic_distribution,
    get_learner_journey,
    get_program_completion_rates,
    get_skills_for_employed_learners,
    get_time_to_employment_stats,
    get_top_countries_by_learners,
    get_top_skills,
)
from agent.tools.neo4j_tools import (
    execute_cypher_query,
    generate_cypher_query,
    get_graph_schema,
)
from agent.tools.validation import validate_cypher_query

__all__ = [
    # Analytics tools
    "get_employment_rate_by_program",
    "get_geographic_distribution",
    "get_learner_journey",
    "get_program_completion_rates",
    "get_skills_for_employed_learners",
    "get_time_to_employment_stats",
    "get_top_countries_by_learners",
    "get_top_skills",
    # Neo4j tools
    "execute_cypher_query",
    "generate_cypher_query",
    "get_graph_schema",
    # Validation
    "validate_cypher_query",
]
