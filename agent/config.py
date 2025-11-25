"""Agent configuration management."""

import os
from pathlib import Path
from typing import Literal

import yaml
from dotenv import load_dotenv
from pydantic import BaseModel, Field

# Load environment variables from .env file (override any existing vars)
load_dotenv(override=True)


class Neo4jConfig(BaseModel):
    """Neo4j connection configuration."""

    uri: str = Field(default="bolt://localhost:7688")
    user: str = Field(default="neo4j")
    password: str = Field(default="password123")
    max_connection_pool_size: int = Field(default=100)
    connection_timeout: int = Field(default=30)

    @classmethod
    def from_env(cls) -> "Neo4jConfig":
        """Load Neo4j config from environment variables."""
        return cls(
            uri=os.getenv("NEO4J_URI", "bolt://localhost:7688"),
            user=os.getenv("NEO4J_USER", "neo4j"),
            password=os.getenv("NEO4J_PASSWORD", "password123"),
        )


class LLMConfig(BaseModel):
    """LLM provider configuration."""

    provider: Literal["anthropic", "openai"] = Field(default="anthropic")
    model: str = Field(default="claude-3-5-sonnet-20241022")
    api_key: str | None = Field(default=None)
    temperature: float = Field(default=0.0, ge=0.0, le=2.0)
    max_tokens: int = Field(default=4096)

    @classmethod
    def from_env(cls) -> "LLMConfig":
        """Load LLM config from environment variables."""
        provider = os.getenv("LLM_PROVIDER", "anthropic")
        api_key_var = "ANTHROPIC_API_KEY" if provider == "anthropic" else "OPENAI_API_KEY"

        return cls(
            provider=provider,  # type: ignore
            model=os.getenv("LLM_MODEL", "claude-3-5-sonnet-20241022"),
            api_key=os.getenv(api_key_var),
            temperature=float(os.getenv("LLM_TEMPERATURE", "0.0")),
            max_tokens=int(os.getenv("LLM_MAX_TOKENS", "4096")),
        )


class AgentConfig(BaseModel):
    """Agent-specific configuration."""

    max_iterations: int = Field(default=10)
    query_timeout: int = Field(default=30)  # seconds
    max_results: int = Field(default=1000)
    enable_caching: bool = Field(default=True)
    cache_ttl: int = Field(default=900)  # 15 minutes
    verbose: bool = Field(default=False)


class CachingConfig(BaseModel):
    """Query result caching configuration."""

    enable: bool = Field(default=True)
    schema_ttl: int = Field(default=900)  # 15 minutes
    metadata_ttl: int = Field(default=900)  # 15 minutes (countries, programs)
    query_results_ttl: int = Field(default=300)  # 5 minutes
    max_cache_size: int = Field(default=100)  # Max cached items


class Config(BaseModel):
    """Complete configuration for the Analytics Agent."""

    neo4j: Neo4jConfig
    llm: LLMConfig
    agent: AgentConfig
    caching: CachingConfig

    @classmethod
    def load(cls, config_file: str | Path | None = None) -> "Config":
        """
        Load configuration from YAML file and environment variables.

        Args:
            config_file: Path to settings.yaml. Defaults to config/settings.yaml

        Returns:
            Loaded configuration
        """
        # Load Neo4j settings from existing settings.yaml
        if config_file is None:
            project_root = Path(__file__).parent.parent
            config_file = project_root / "config" / "settings.yaml"

        neo4j_config = Neo4jConfig()
        if Path(config_file).exists():
            with open(config_file) as f:
                settings = yaml.safe_load(f)
                neo4j_settings = settings.get("neo4j", {})
                neo4j_config = Neo4jConfig(**neo4j_settings)

        # Override with environment variables if set
        if os.getenv("NEO4J_URI"):
            neo4j_config = Neo4jConfig.from_env()

        # Load LLM config from environment
        llm_config = LLMConfig.from_env()

        # Agent config (can be overridden by env vars)
        agent_config = AgentConfig(
            max_iterations=int(os.getenv("AGENT_MAX_ITERATIONS", "10")),
            query_timeout=int(os.getenv("AGENT_QUERY_TIMEOUT", "30")),
            max_results=int(os.getenv("AGENT_MAX_RESULTS", "1000")),
            enable_caching=os.getenv("AGENT_ENABLE_CACHING", "true").lower() == "true",
            cache_ttl=int(os.getenv("AGENT_CACHE_TTL", "900")),
            verbose=os.getenv("AGENT_VERBOSE", "false").lower() == "true",
        )

        # Caching config
        caching_config = CachingConfig(
            enable=agent_config.enable_caching,
            schema_ttl=int(os.getenv("CACHE_SCHEMA_TTL", "900")),
            metadata_ttl=int(os.getenv("CACHE_METADATA_TTL", "900")),
            query_results_ttl=int(os.getenv("CACHE_RESULTS_TTL", "300")),
            max_cache_size=int(os.getenv("CACHE_MAX_SIZE", "100")),
        )

        return cls(
            neo4j=neo4j_config,
            llm=llm_config,
            agent=agent_config,
            caching=caching_config,
        )


# Global config instance
_config: Config | None = None


def get_config() -> Config:
    """Get the global configuration instance."""
    global _config
    if _config is None:
        _config = Config.load()
    return _config


def reset_config() -> None:
    """Reset the global configuration (useful for testing)."""
    global _config
    _config = None
