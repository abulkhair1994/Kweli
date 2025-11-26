"""Extract filters from executed Cypher queries for context tracking."""

import re
from typing import Any


class ContextExtractor:
    """Extracts filters from Cypher queries and query parameters for context persistence."""

    # Regex patterns for common WHERE clause filters
    FILTER_PATTERNS = {
        "country": [
            r"country(?:OfResidence)?(?:Code)?\s*=\s*['\"](\w{2})['\"]",
            r"\.country\s*=\s*['\"]([^'\"]+)['\"]",
            r"l\.countryOfResidenceCode\s*=\s*['\"](\w{2})['\"]",
        ],
        "program": [
            r"program(?:Name)?\s*=\s*['\"]([^'\"]+)['\"]",
            r"p\.name\s*=\s*['\"]([^'\"]+)['\"]",
            r"toLower\(p\.name\)\s*CONTAINS\s*toLower\(['\"]([^'\"]+)['\"]\)",
        ],
        "cohort": [
            r"cohort(?:Name)?\s*=\s*['\"]([^'\"]+)['\"]",
            r"cohort\s*=\s*(\d+)",
        ],
        "learning_state": [
            r"learningState\s*=\s*['\"]([^'\"]+)['\"]",
            r"ls\.state\s*=\s*['\"]([^'\"]+)['\"]",
        ],
        "professional_status": [
            r"professionalStatus\s*=\s*['\"]([^'\"]+)['\"]",
            r"ps\.status\s*=\s*['\"]([^'\"]+)['\"]",
        ],
        "skill": [
            r"skill(?:Name)?\s*=\s*['\"]([^'\"]+)['\"]",
            r"s\.name\s*=\s*['\"]([^'\"]+)['\"]",
        ],
        "city": [
            r"city(?:OfResidence)?(?:Id)?\s*=\s*['\"]([^'\"]+)['\"]",
            r"c\.name\s*=\s*['\"]([^'\"]+)['\"]",
        ],
        "employment_status": [
            r"isEmployed\s*=\s*(true|false)",
            r"employment.*status",
        ],
    }

    @classmethod
    def extract_from_cypher(cls, cypher_query: str) -> dict[str, Any]:
        """
        Extract filters from a Cypher query string.

        Args:
            cypher_query: Executed Cypher query string

        Returns:
            Dictionary of extracted filters (empty if none found)

        Example:
            >>> extract_from_cypher("WHERE l.country = 'EG' AND p.name = 'Data Analytics'")
            {'country': 'EG', 'program': 'Data Analytics'}
        """
        if not cypher_query:
            return {}

        filters = {}

        for filter_name, patterns in cls.FILTER_PATTERNS.items():
            for pattern in patterns:
                match = re.search(pattern, cypher_query, re.IGNORECASE)
                if match:
                    filters[filter_name] = match.group(1)
                    break  # Use first matching pattern

        return filters

    @classmethod
    def extract_from_params(cls, query_params: dict) -> dict[str, Any]:
        """
        Extract filters from query_params dictionary.

        Args:
            query_params: Dictionary from AgentState.query_params

        Returns:
            Normalized filter dictionary

        Example:
            >>> extract_from_params({"country": "EG", "program_name": "Data Analytics"})
            {'country': 'EG', 'program': 'Data Analytics'}
        """
        filters = {}

        # Direct mappings from common parameter names to filter names
        param_mappings = {
            "country": ["country", "country_code", "countryOfResidence", "countryCode"],
            "program": ["program", "program_name", "programName"],
            "cohort": ["cohort", "cohort_name", "cohortName"],
            "learning_state": ["learning_state", "learningState", "state"],
            "professional_status": [
                "professional_status",
                "professionalStatus",
                "status",
            ],
            "skill": ["skill", "skill_name", "skillName"],
            "city": ["city", "city_name", "cityOfResidence", "cityId"],
        }

        for filter_name, param_keys in param_mappings.items():
            for key in param_keys:
                if key in query_params and query_params[key]:
                    filters[filter_name] = query_params[key]
                    break

        return filters

    @classmethod
    def extract_all(cls, cypher_query: str | None, query_params: dict) -> dict[str, Any]:
        """
        Extract filters from both Cypher query and params.

        Combines filters from both sources, with params taking precedence.

        Args:
            cypher_query: Executed Cypher query string (optional)
            query_params: Dictionary from AgentState.query_params

        Returns:
            Combined filter dictionary

        Example:
            >>> extract_all("WHERE l.country = 'EG'", {"program": "Data Analytics"})
            {'country': 'EG', 'program': 'Data Analytics'}
        """
        filters = {}

        # Extract from Cypher
        if cypher_query:
            filters.update(cls.extract_from_cypher(cypher_query))

        # Extract from params (overwrites Cypher if conflict)
        filters.update(cls.extract_from_params(query_params))

        return filters

    @classmethod
    def format_filters(cls, filters: dict[str, Any]) -> str:
        """
        Format filters as a human-readable string.

        Args:
            filters: Dictionary of filters

        Returns:
            Formatted string representation

        Example:
            >>> format_filters({"country": "EG", "program": "Data Analytics"})
            'country=EG, program=Data Analytics'
        """
        if not filters:
            return "No active filters"

        return ", ".join(f"{k}={v}" for k, v in filters.items())
