"""
Geographic data normalizer.

Converts country names to ISO codes and creates city IDs.
Implements HYBRID approach to avoid supernodes.
"""

from pathlib import Path

from structlog.types import FilteringBoundLogger

from models.nodes import CityNode, CountryNode
from utils.config import ConfigLoader
from utils.helpers import create_city_id, normalize_string
from utils.logger import get_logger


class GeoNormalizer:
    """Normalize geographic data (countries and cities)."""

    def __init__(
        self,
        country_mapping_path: Path | str = "config/country_mapping.json",
        logger: FilteringBoundLogger | None = None,
    ) -> None:
        """
        Initialize geographic normalizer.

        Args:
            country_mapping_path: Path to country mapping JSON
            logger: Optional logger instance
        """
        self.logger = logger or get_logger(__name__)
        self.country_mapping = ConfigLoader.load_country_mapping(country_mapping_path)

    def normalize_country_code(self, country_name: str | None) -> str | None:
        """
        Convert country name to ISO 3166-1 alpha-2 code.

        Args:
            country_name: Country name

        Returns:
            ISO country code or None

        Examples:
            "Egypt" -> "EG"
            "United States" -> "US"
            "Ghana" -> "GH"
        """
        if not country_name:
            return None

        # Normalize name
        normalized_name = normalize_string(country_name)
        if not normalized_name:
            return None

        # Check mapping (case-insensitive)
        for name, code in self.country_mapping.items():
            if name.lower() == normalized_name.lower():
                return code.upper()

        # If not found, log warning and return first 2 letters
        self.logger.warning("Country not found in mapping", country=country_name)
        return normalized_name[:2].upper()

    def create_country_node(
        self,
        country_name: str | None,
        latitude: float | None = None,
        longitude: float | None = None,
    ) -> CountryNode | None:
        """
        Create CountryNode from country name.

        Args:
            country_name: Country name
            latitude: Country centroid latitude
            longitude: Country centroid longitude

        Returns:
            CountryNode or None
        """
        code = self.normalize_country_code(country_name)
        if not code or not country_name:
            return None

        normalized_name = normalize_string(country_name)
        if not normalized_name:
            return None

        return CountryNode(
            code=code,
            name=normalized_name,
            latitude=latitude,
            longitude=longitude,
        )

    def create_city_node(
        self,
        city_name: str | None,
        country_code: str | None,
        latitude: float | None = None,
        longitude: float | None = None,
    ) -> CityNode | None:
        """
        Create CityNode with unique ID.

        Args:
            city_name: City name
            country_code: ISO country code
            latitude: City latitude
            longitude: City longitude

        Returns:
            CityNode or None
        """
        if not city_name or not country_code:
            return None

        normalized_city = normalize_string(city_name)
        if not normalized_city:
            return None

        city_id = create_city_id(normalized_city, country_code)
        if not city_id:
            return None

        return CityNode(
            id=city_id,
            name=normalized_city,
            country_code=country_code.upper(),
            latitude=latitude,
            longitude=longitude,
        )


__all__ = ["GeoNormalizer"]
