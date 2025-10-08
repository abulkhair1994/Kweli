"""
Configuration management for the ETL pipeline.

Loads settings from YAML files and environment variables.
"""

import json
from pathlib import Path

import yaml
from pydantic import BaseModel, Field


class ETLConfig(BaseModel):
    """ETL pipeline configuration."""

    chunk_size: int = Field(10000, description="Rows to process per chunk")
    batch_size: int = Field(1000, description="Records to send to Neo4j per batch")
    max_workers: int = Field(4, description="Parallel workers")
    enable_checkpoints: bool = Field(True, description="Enable checkpoint/resume")
    checkpoint_interval: int = Field(5000, description="Save checkpoint every N rows")
    enable_progress_bar: bool = Field(True, description="Show progress bar")
    log_interval: int = Field(1000, description="Log progress every N rows")


class Neo4jConfig(BaseModel):
    """Neo4j connection configuration."""

    max_connection_pool_size: int = Field(50, description="Max connection pool size")
    connection_timeout: int = Field(30, description="Connection timeout in seconds")
    max_transaction_retry_time: int = Field(30, description="Max retry time in seconds")
    batch_size: int = Field(1000, description="Batch size for operations")
    batch_timeout: int = Field(60, description="Batch timeout in seconds")


class ValidationConfig(BaseModel):
    """Data validation configuration."""

    max_error_rate: float = Field(0.05, description="Maximum allowed error rate")
    required_fields: list[str] = Field(
        default_factory=lambda: ["sand_id", "hashed_email", "full_name"]
    )
    min_year: int = Field(1970, description="Minimum valid year")
    max_year: int = Field(2030, description="Maximum valid year")
    invalid_date_markers: list[str] = Field(
        default_factory=lambda: ["1970-01-01", "9999-12-31"]
    )
    missing_value_markers: list[str | int] = Field(default_factory=lambda: [-99, "-99"])


class SkillsConfig(BaseModel):
    """Skills parsing configuration."""

    delimiter: str = Field(",", description="Delimiter for skills list")
    normalize: bool = Field(True, description="Normalize skill names")
    max_skills_per_learner: int = Field(50, description="Max skills per learner")


class GeographyConfig(BaseModel):
    """Geography configuration."""

    use_hybrid_approach: bool = Field(True, description="Use HYBRID approach for countries")
    normalize_country_codes: bool = Field(True, description="Normalize country codes")


class TemporalConfig(BaseModel):
    """Temporal tracking configuration."""

    enable_learning_state_tracking: bool = Field(True, description="Track learning states")
    enable_professional_status_tracking: bool = Field(
        True, description="Track professional status"
    )
    default_snapshot_date: str = Field("2025-10-06", description="Default snapshot date")


class TransformersConfig(BaseModel):
    """Transformers configuration."""

    skills: SkillsConfig = Field(default_factory=SkillsConfig)
    geography: GeographyConfig = Field(default_factory=GeographyConfig)
    temporal: TemporalConfig = Field(default_factory=TemporalConfig)


class Settings(BaseModel):
    """Complete application settings."""

    etl: ETLConfig = Field(default_factory=ETLConfig)
    neo4j: Neo4jConfig = Field(default_factory=Neo4jConfig)
    validation: ValidationConfig = Field(default_factory=ValidationConfig)
    transformers: TransformersConfig = Field(default_factory=TransformersConfig)


class ConfigLoader:
    """Load configuration from YAML files."""

    def __init__(self, config_path: Path | str = "config/settings.yaml") -> None:
        """Initialize configuration loader."""
        self.config_path = Path(config_path)

    def load(self) -> Settings:
        """Load settings from YAML file."""
        if not self.config_path.exists():
            return Settings()  # Return defaults

        with open(self.config_path) as f:
            config_data = yaml.safe_load(f)

        return Settings(**config_data)

    @staticmethod
    def load_country_mapping(mapping_path: Path | str = "config/country_mapping.json") -> dict[str, str]:
        """Load country name to ISO code mapping."""
        path = Path(mapping_path)
        if not path.exists():
            return {}

        with open(path) as f:
            data = json.load(f)

        # Merge mappings and aliases
        mapping = data.get("mappings", {})
        aliases = data.get("aliases", {})
        mapping.update(aliases)

        return mapping


# Global settings instance
_settings: Settings | None = None


def get_settings(config_path: Path | str | None = None) -> Settings:
    """Get global settings instance."""
    global _settings
    if _settings is None:
        loader = ConfigLoader(config_path or "config/settings.yaml")
        _settings = loader.load()
    return _settings


def reload_settings(config_path: Path | str | None = None) -> Settings:
    """Reload settings from file."""
    global _settings
    loader = ConfigLoader(config_path or "config/settings.yaml")
    _settings = loader.load()
    return _settings
