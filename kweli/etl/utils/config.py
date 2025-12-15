"""
Configuration management for the ETL pipeline.

Loads settings from YAML files and environment variables.
"""

from __future__ import annotations

import json
import os
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
    max_transaction_retry_time: int = Field(60, description="Max retry time in seconds")
    batch_size: int = Field(1000, description="Batch size for operations")
    batch_timeout: int = Field(60, description="Batch timeout in seconds")
    max_retries: int = Field(3, description="Max retries for transient errors")
    retry_delay: float = Field(1.0, description="Initial delay between retries")


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

    # Basic temporal tracking (snapshot mode)
    enable_learning_state_tracking: bool = Field(True, description="Track learning states")
    enable_professional_status_tracking: bool = Field(
        True, description="Track professional status"
    )
    default_snapshot_date: str = Field("2025-10-06", description="Default snapshot date")

    # Temporal history tracking (SCD Type 2 mode)
    enable_learning_state_history: bool = Field(
        True, description="Build full learning state history from learning_details"
    )
    enable_professional_status_history: bool = Field(
        True, description="Build full professional status history from employment_details"
    )
    inactive_gap_months: int = Field(
        6, description="Gap in months to consider learner inactive between programs"
    )
    unemployment_gap_months: int = Field(
        1, description="Gap in months to consider learner unemployed between jobs"
    )
    infer_initial_unemployment: bool = Field(
        True, description="Create unemployed status before first job"
    )


class TransformersConfig(BaseModel):
    """Transformers configuration."""

    skills: SkillsConfig = Field(default_factory=SkillsConfig)
    geography: GeographyConfig = Field(default_factory=GeographyConfig)
    temporal: TemporalConfig = Field(default_factory=TemporalConfig)


class MySQLConfig(BaseModel):
    """MySQL connection configuration."""

    host: str = Field("", description="MySQL server hostname")
    port: int = Field(3306, description="MySQL port")
    database: str = Field("", description="Database name")
    table: str = Field("impact_learners_profile", description="Table to read from")
    user: str = Field("", description="MySQL username")
    password: str = Field("", description="MySQL password (from environment)")
    use_ssl: bool = Field(True, description="Use SSL for connection")
    connection_timeout: int = Field(30, description="Connection timeout in seconds")
    read_timeout: int = Field(120, description="Read timeout for large queries")
    pool_size: int = Field(3, description="Connection pool size")

    @classmethod
    def from_env(cls) -> MySQLConfig:
        """
        Load MySQL configuration from environment variables.

        Environment variables:
            MYSQL_HOST: MySQL server hostname
            MYSQL_PORT: MySQL port (default 3306)
            MYSQL_DATABASE: Database name
            MYSQL_TABLE: Table name (default impact_learners_profile)
            MYSQL_USER: MySQL username
            MYSQL_PASSWORD: MySQL password
        """
        return cls(
            host=os.getenv("MYSQL_HOST", ""),
            port=int(os.getenv("MYSQL_PORT", "3306")),
            database=os.getenv("MYSQL_DATABASE", ""),
            table=os.getenv("MYSQL_TABLE", "impact_learners_profile"),
            user=os.getenv("MYSQL_USER", ""),
            password=os.getenv("MYSQL_PASSWORD", ""),
            use_ssl=os.getenv("MYSQL_USE_SSL", "true").lower() == "true",
        )


class DataSourceConfig(BaseModel):
    """Data source configuration supporting multiple source types."""

    type: str = Field("csv", description="Data source type: csv or mysql")

    # CSV configuration
    csv_path: str | None = Field(None, description="Path to CSV file")

    # MySQL configuration (loaded from environment for security)
    mysql: MySQLConfig = Field(default_factory=MySQLConfig)

    # Common settings
    chunk_size: int = Field(10000, description="Rows per chunk")


class Settings(BaseModel):
    """Complete application settings."""

    etl: ETLConfig = Field(default_factory=ETLConfig)
    neo4j: Neo4jConfig = Field(default_factory=Neo4jConfig)
    validation: ValidationConfig = Field(default_factory=ValidationConfig)
    transformers: TransformersConfig = Field(default_factory=TransformersConfig)
    data_source: DataSourceConfig = Field(default_factory=DataSourceConfig)


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
