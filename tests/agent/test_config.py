"""Tests for agent configuration."""



from kweli.agent.config import (
    AgentConfig,
    CachingConfig,
    Config,
    LLMConfig,
    Neo4jConfig,
    get_config,
    reset_config,
)


class TestNeo4jConfig:
    """Tests for Neo4jConfig."""

    def test_default_values(self):
        """Test default configuration values."""
        config = Neo4jConfig()
        assert config.uri == "bolt://localhost:7688"
        assert config.user == "neo4j"
        assert config.password == "password123"

    def test_from_env(self, monkeypatch):
        """Test loading from environment variables."""
        monkeypatch.setenv("NEO4J_URI", "bolt://custom:7687")
        monkeypatch.setenv("NEO4J_USER", "admin")
        monkeypatch.setenv("NEO4J_PASSWORD", "secret")

        config = Neo4jConfig.from_env()
        assert config.uri == "bolt://custom:7687"
        assert config.user == "admin"
        assert config.password == "secret"


class TestLLMConfig:
    """Tests for LLMConfig."""

    def test_default_values(self):
        """Test default configuration values."""
        config = LLMConfig()
        assert config.provider == "anthropic"
        assert config.model == "claude-3-5-sonnet-20241022"
        assert config.temperature == 0.0
        assert config.max_tokens == 4096

    def test_from_env_anthropic(self, monkeypatch):
        """Test loading Anthropic config from env."""
        monkeypatch.setenv("LLM_PROVIDER", "anthropic")
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
        monkeypatch.setenv("LLM_MODEL", "claude-3-opus-20240229")
        monkeypatch.setenv("LLM_TEMPERATURE", "0.7")

        config = LLMConfig.from_env()
        assert config.provider == "anthropic"
        assert config.api_key == "test-key"
        assert config.model == "claude-3-opus-20240229"
        assert config.temperature == 0.7

    def test_from_env_openai(self, monkeypatch):
        """Test loading OpenAI config from env."""
        monkeypatch.setenv("LLM_PROVIDER", "openai")
        monkeypatch.setenv("OPENAI_API_KEY", "test-key")
        monkeypatch.setenv("LLM_MODEL", "gpt-4")

        config = LLMConfig.from_env()
        assert config.provider == "openai"
        assert config.api_key == "test-key"
        assert config.model == "gpt-4"


class TestAgentConfig:
    """Tests for AgentConfig."""

    def test_default_values(self):
        """Test default configuration values."""
        config = AgentConfig()
        assert config.max_iterations == 10
        assert config.query_timeout == 30
        assert config.max_results == 1000
        assert config.enable_caching is True


class TestCachingConfig:
    """Tests for CachingConfig."""

    def test_default_values(self):
        """Test default configuration values."""
        config = CachingConfig()
        assert config.enable is True
        assert config.schema_ttl == 900
        assert config.metadata_ttl == 900
        assert config.query_results_ttl == 300


class TestConfig:
    """Tests for main Config class."""

    def test_load_default(self):
        """Test loading default configuration."""
        config = Config.load()
        assert isinstance(config.neo4j, Neo4jConfig)
        assert isinstance(config.llm, LLMConfig)
        assert isinstance(config.agent, AgentConfig)
        assert isinstance(config.caching, CachingConfig)

    def test_get_config_singleton(self):
        """Test that get_config returns singleton."""
        reset_config()
        config1 = get_config()
        config2 = get_config()
        assert config1 is config2

    def test_reset_config(self):
        """Test config reset."""
        reset_config()
        config1 = get_config()
        reset_config()
        config2 = get_config()
        assert config1 is not config2
