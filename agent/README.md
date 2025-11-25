# Impact Learners Analytics Agent

A LangGraph-powered ReAct agent that intelligently queries the Impact Learners Knowledge Graph using natural language.

## Overview

This agent enables natural language queries against a Neo4j graph database containing:
- **1.6 million learners** across 168 countries
- **6.9 million relationships** (skills, enrollments, employment)
- **8 node types** (Learner, Country, City, Skill, Program, Company, LearningState, ProfessionalStatus)
- **Rich analytics** on education, skills, and employment outcomes

## Features

- **Natural Language Queries**: Ask questions in plain English
- **Pre-built Analytics**: 8 optimized query templates for common requests
- **Safety First**: Read-only queries with injection protection
- **HYBRID Geography**: Efficient handling of geographic data
- **Streaming Support**: Get results as they're generated
- **Multiple LLMs**: Support for Anthropic Claude and OpenAI GPT models

## Installation

```bash
# Install dependencies
uv pip install langgraph langchain-core langchain-anthropic httpx

# Or install from project root
cd /path/to/Impact
uv sync
```

## Configuration

### Environment Variables

```bash
# LLM Provider (required)
export ANTHROPIC_API_KEY="your-api-key-here"
# OR
export OPENAI_API_KEY="your-api-key-here"

# Optional Configuration
export LLM_PROVIDER="anthropic"  # or "openai"
export LLM_MODEL="claude-3-5-sonnet-20241022"
export LLM_TEMPERATURE="0.0"
export LLM_MAX_TOKENS="4096"

# Agent Configuration
export AGENT_MAX_ITERATIONS="10"
export AGENT_QUERY_TIMEOUT="30"
export AGENT_MAX_RESULTS="1000"
export AGENT_ENABLE_CACHING="true"
export AGENT_VERBOSE="false"

# Neo4j Connection (defaults to config/settings.yaml)
export NEO4J_URI="bolt://localhost:7688"
export NEO4J_USER="neo4j"
export NEO4J_PASSWORD="password123"
```

### Settings File

Neo4j connection settings are loaded from `config/settings.yaml` by default.

## Usage

### CLI Commands

#### Interactive Chat

```bash
# Start interactive session
uv run impact-agent chat

# With verbose output
uv run impact-agent chat --verbose
```

#### Single Query

```bash
# Execute a single query
uv run impact-agent query "How many learners are from Egypt?"

# With verbose output
uv run impact-agent query "Show top 10 programs by completion rate" --verbose
```

#### Test Connection

```bash
# Test Neo4j connection
uv run impact-agent test-connection
```

#### Show Configuration

```bash
# Display current configuration
uv run impact-agent config-info
```

#### Example Queries

```bash
# See example queries
uv run impact-agent examples
```

### Python API

```python
from agent.graph import AnalyticsAgent

# Initialize agent
agent = AnalyticsAgent()

# Execute query
response = agent.query("What's the employment rate by program?")
print(response)

# Stream query execution
for state in agent.stream_query("Show me the top 10 skills for employed learners"):
    print(state)
```

### Using Tools Directly

```python
from agent.tools import (
    get_top_countries_by_learners,
    get_program_completion_rates,
    execute_cypher_query,
)

# Use pre-built analytics tools
result = get_top_countries_by_learners.invoke({"limit": 10})
print(result["query"])  # View the Cypher query
print(result["params"])  # View the parameters

# Execute custom Cypher
result = execute_cypher_query.invoke({
    "query": "MATCH (l:Learner) WHERE l.countryOfResidenceCode = $code RETURN count(l)",
    "params": {"code": "EG"}
})
print(result)
```

## Example Queries

### Demographics & Geography

```
How many learners are from Egypt?
Show me the top 10 countries by learner count
What's the distribution of learners by country?
How many learners are from rural areas?
```

### Programs

```
What's the completion rate for Software Engineering program?
Show me program completion rates for all programs
Which programs have the best employment outcomes?
Compare completion rates across programs
```

### Skills

```
What are the top 20 skills among learners?
Show me the most common skills for employed learners
What skills do Software Engineering graduates have?
Which skills are most common in Egypt?
```

### Employment

```
What's the employment rate for graduates?
What's the employment rate by program?
How long does it take graduates to find employment?
Show me the top employers for our learners
```

### Learner Journeys

```
Show me the profile for learner [email_hash]
What's the complete journey for learner [email_hash]?
```

## Architecture

### Components

```
agent/
├── __init__.py              # Package initialization
├── config.py                # Configuration management
├── state.py                 # LangGraph state schema
├── prompts.py               # System prompts & templates
├── graph.py                 # LangGraph ReAct agent
├── cli.py                   # CLI interface
└── tools/
    ├── __init__.py
    ├── validation.py        # Query safety validation
    ├── neo4j_tools.py       # Core Neo4j operations
    └── analytics_tools.py   # Pre-built analytics queries
```

### Agent Flow

1. **User Query** → Natural language input
2. **Intent Classification** → Determine query category
3. **Tool Selection** → Choose pre-built tool or generate custom Cypher
4. **Validation** → Ensure query safety (read-only, no injection)
5. **Execution** → Run against Neo4j
6. **Interpretation** → Format and explain results
7. **Response** → Natural language output with insights

### Safety Features

- ✅ **Read-only queries** - Write operations (CREATE, DELETE, SET) are blocked
- ✅ **LIMIT enforcement** - Automatically adds LIMIT clause (max 1000 results)
- ✅ **Injection protection** - Validates parameters and query patterns
- ✅ **Query timeout** - 30 second timeout to prevent long-running queries
- ✅ **Parameter validation** - Sanitizes all user inputs

### Pre-built Analytics Tools

1. **get_top_countries_by_learners** - Geographic distribution
2. **get_program_completion_rates** - Program performance
3. **get_employment_rate_by_program** - Employment outcomes
4. **get_top_skills** - Skills analysis
5. **get_learner_journey** - Individual learner profiles
6. **get_skills_for_employed_learners** - Employment-skill correlation
7. **get_geographic_distribution** - Multi-metric geographic analysis
8. **get_time_to_employment_stats** - Time-to-employment metrics

## Testing

```bash
# Run unit tests
uv run pytest tests/test_agent/test_validation.py -v
uv run pytest tests/test_agent/test_config.py -v
uv run pytest tests/test_agent/test_analytics_tools.py -v

# Run integration tests (requires Neo4j)
TEST_NEO4J_INTEGRATION=1 uv run pytest tests/test_agent/test_integration.py -v

# Run full agent tests (requires LLM API key)
TEST_AGENT_INTEGRATION=1 uv run pytest tests/test_agent/test_integration.py -v

# Run all tests
uv run pytest tests/test_agent/ -v

# With coverage
uv run pytest tests/test_agent/ --cov=agent --cov-report=html
```

## Code Quality

```bash
# Run ruff linter
uv run ruff check agent/ tests/test_agent/

# Auto-fix issues
uv run ruff check agent/ tests/test_agent/ --fix

# Run vulture (dead code detection)
uv run vulture agent/ --min-confidence 80
```

## Performance

- **Query Response Time**: 2-5 seconds average
- **Streaming**: Real-time updates during execution
- **Caching**: Schema and metadata cached for 15 minutes
- **Connection Pooling**: Up to 100 concurrent connections

## Troubleshooting

### "LLM API key not set"

```bash
export ANTHROPIC_API_KEY="your-key"
# OR
export OPENAI_API_KEY="your-key"
```

### "Connection failed"

Check Neo4j is running:
```bash
docker ps | grep neo4j
```

Test connection:
```bash
uv run impact-agent test-connection
```

### "Query validation failed"

The agent only allows read-only queries. Write operations (CREATE, DELETE, SET) are blocked for safety.

### "Maximum iterations reached"

The agent hit the iteration limit (default: 10). Try simplifying your query or increasing the limit:
```bash
export AGENT_MAX_ITERATIONS="20"
```

## Advanced Usage

### Custom LLM Configuration

```python
from agent.config import Config, LLMConfig

# Create custom configuration
config = Config(
    llm=LLMConfig(
        provider="anthropic",
        model="claude-3-opus-20240229",
        temperature=0.2,
        max_tokens=8192,
    ),
    # ... other config
)

# Use in agent
from agent.graph import AnalyticsAgent
agent = AnalyticsAgent()
```

### Adding Custom Tools

```python
from langchain_core.tools import tool
from agent.tools.neo4j_tools import get_executor

@tool
def my_custom_analytics() -> dict:
    """Your custom analytics logic."""
    executor = get_executor()
    result = executor.execute_query(
        "MATCH (l:Learner) ... RETURN ...",
        params={}
    )
    return {"query": "...", "results": result}

# Add to TOOLS list in agent/graph.py
```

## Contributing

1. Follow existing code style (< 500 lines per file)
2. Add tests for new features
3. Run `ruff check --fix` before committing
4. Update documentation

## License

MIT

## Support

For issues and questions:
- GitHub Issues: [Impact Learners KG Issues](https://github.com/your-org/impact-learners-kg/issues)
- Documentation: See [CLAUDE.md](../CLAUDE.md) for project overview

---

**Built with:**
- [LangGraph](https://langchain-ai.github.io/langgraph/) - Agent orchestration
- [LangChain](https://python.langchain.com/) - LLM integration
- [Neo4j](https://neo4j.com/) - Graph database
- [Claude](https://www.anthropic.com/claude) / [GPT](https://openai.com/gpt-4) - Language models
