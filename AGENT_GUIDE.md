# Kweli Analytics Agent - Complete Guide

**Version:** 1.0
**Last Updated:** 2025-11-26
**Agent Name:** Kweli (Swahili for "truth")

---

## Table of Contents

1. [Overview](#overview)
2. [Installation](#installation)
3. [Configuration](#configuration)
4. [Usage](#usage)
5. [Architecture](#architecture)
6. [Safety & Validation](#safety--validation)
7. [Context Persistence](#context-persistence)
8. [Testing](#testing)
9. [Troubleshooting](#troubleshooting)

---

## Overview

Kweli is a LangGraph-powered ReAct agent that intelligently queries the Impact Learners Knowledge Graph using natural language. It provides truthful, data-driven insights about learners, programs, skills, and employment outcomes.

### Key Features

- **Natural Language Queries**: Ask questions in plain English
- **Pre-built Analytics**: 8 optimized query templates
- **Safety First**: Read-only queries with injection protection
- **HYBRID Geography**: Efficient geographic queries
- **Streaming Support**: Real-time results as they're generated
- **Multiple LLMs**: Support for Anthropic Claude and OpenAI GPT
- **Context Persistence**: Multi-turn conversations with memory
- **Verified Execution**: Actually calls database tools (not hallucinating)

### Statistics

- **Database**: 1.6M+ learners across 168 countries
- **Relationships**: 6.9M+ (skills, enrollments, employment)
- **Node Types**: 8 (Learner, Country, City, Skill, Program, Company, LearningState, ProfessionalStatus)
- **Query Response**: 2-5 seconds average

---

## Installation

```bash
# Install dependencies
uv sync

# Or install specific packages
uv pip install langgraph langchain-core langchain-anthropic httpx
```

---

## Configuration

### Environment Variables

```bash
# LLM Provider (required - choose one)
export ANTHROPIC_API_KEY="your-anthropic-key"
# OR
export OPENAI_API_KEY="your-openai-key"

# Optional LLM Configuration
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

# Neo4j Connection (uses config/settings.yaml by default)
export NEO4J_URI="bolt://localhost:7688"
export NEO4J_USER="neo4j"
export NEO4J_PASSWORD="password123"
```

### Settings File

Neo4j connection loaded from `config/settings.yaml`:

```yaml
neo4j:
  uri: "bolt://localhost:7688"
  user: "neo4j"
  password: "password123"
  max_connection_pool_size: 100
```

---

## Usage

### CLI Commands

#### 1. Interactive Chat Mode

```bash
# Basic chat
python -m agent.cli chat

# With tool execution visibility
python -m agent.cli chat --show-tools

# With full verbose output
python -m agent.cli chat --verbose
```

**Features**:
- 🔄 Multi-turn conversation with context
- 🎨 Rich formatting with panels and markdown
- 📊 Real-time status indicators
- 🔍 Tool execution visibility

**Visual Indicators**:
- 🤔 **Analyzing query...** - Agent reasoning
- 🔍 **Calling tool: [name]** - Database query executing
- ⚙️ **Processing results...** - Interpreting data
- ✨ **Response** - Final answer

**Exit**: Type `exit` or `quit`

#### 2. Single Query Mode

```bash
# Basic query
python -m agent.cli query "How many learners are from Egypt?"

# With verbose output
python -m agent.cli query "What are the top 5 countries?" --verbose
```

#### 3. Utility Commands

```bash
# Test Neo4j connection
python -m agent.cli test-connection

# Show configuration
python -m agent.cli config-info

# Show example queries
python -m agent.cli examples
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
for state in agent.stream_query("Show me the top 10 skills"):
    print(state)
```

### Using Tools Directly

```python
from agent.tools import (
    get_top_countries_by_learners,
    get_program_completion_rates,
    execute_cypher_query,
)

# Use pre-built analytics
result = get_top_countries_by_learners.invoke({"limit": 10})
print(result["query"])   # View Cypher query
print(result["results"]) # View data

# Execute custom Cypher
result = execute_cypher_query.invoke({
    "query": "MATCH (l:Learner) WHERE l.countryOfResidenceCode = $code RETURN count(l)",
    "params": {"code": "EG"}
})
```

---

## Example Queries

### Demographics & Geography

```
How many learners are from Egypt?
Show me the top 10 countries by learner count
What's the distribution of learners by country?
How many learners are from rural areas?
What's the gender distribution?
```

### Programs & Learning

```
What's the completion rate for Software Engineering program?
Show me program completion rates for all programs
Which programs have the best employment outcomes?
Compare completion rates across programs
What's the average LMS score by program?
```

### Skills

```
What are the top 20 skills among learners?
Show me the most common skills for employed learners
What skills do Software Engineering graduates have?
Which skills are most common in Egypt?
What skill combinations are most valuable?
```

### Employment

```
What's the employment rate for graduates?
What's the employment rate by program?
How long does it take graduates to find employment?
Show me the top employers for our learners
What's the salary distribution?
```

### Individual Learner

```
Show me the profile for learner [email_hash]
What's the complete journey for learner [sand_id]?
```

---

## Architecture

### Components

```
agent/
├── __init__.py          # Package initialization
├── config.py            # Configuration management
├── state.py             # LangGraph state schema
├── prompts.py           # System prompts & templates
├── graph.py             # LangGraph ReAct agent
├── cli.py               # CLI interface
├── context/             # Context persistence system
│   ├── manager.py       # Conversation management
│   └── storage.py       # SQLite storage
└── tools/
    ├── __init__.py
    ├── validation.py    # Query safety validation
    ├── neo4j_tools.py   # Core Neo4j operations
    └── analytics_tools.py # Pre-built analytics
```

### Agent Flow

1. **User Query** → Natural language input
2. **Intent Classification** → Determine query category
3. **Tool Selection** → Choose pre-built tool or generate Cypher
4. **Validation** → Ensure query safety
5. **Execution** → Run against Neo4j
6. **Interpretation** → Format and explain results
7. **Response** → Natural language output with insights

### LangGraph Architecture

```
┌─────────────────┐
│  User Input     │
└────────┬────────┘
         │
         v
┌─────────────────┐
│  Agent Node     │ ◄─┐
│  (LLM Reasoning)│   │
└────────┬────────┘   │
         │            │
         v            │
┌─────────────────┐   │
│  Tool Node      │   │
│  (Execute Tool) │   │
└────────┬────────┘   │
         │            │
         v            │
┌─────────────────┐   │
│  Should Continue?│───┘
│  (Router)       │    Loop until done
└────────┬────────┘
         │
         v
┌─────────────────┐
│  Final Output   │
└─────────────────┘
```

---

## Safety & Validation

### Read-Only Enforcement

```python
# Blocked operations
WRITE_OPERATIONS = [
    "CREATE", "DELETE", "REMOVE", "SET",
    "MERGE", "DROP", "DETACH"
]

# Only SELECT queries allowed
validator.validate_query(query)  # Raises error if writes detected
```

### Query Safety Features

- ✅ **Read-only queries** - Write operations blocked
- ✅ **LIMIT enforcement** - Auto-adds LIMIT (max 1000)
- ✅ **Injection protection** - Validates parameters
- ✅ **Query timeout** - 30 second timeout
- ✅ **Parameter validation** - Sanitizes inputs

### Example: Automatic LIMIT Addition

```cypher
// User's query
MATCH (l:Learner) RETURN l

// Auto-modified by validator
MATCH (l:Learner) RETURN l LIMIT 1000
```

---

## Pre-built Analytics Tools

### 1. get_top_countries_by_learners
Geographic distribution by country

```python
tool.invoke({"limit": 10})
```

### 2. get_program_completion_rates
Program performance metrics

```python
tool.invoke({})
```

### 3. get_employment_rate_by_program
Employment outcomes by program

```python
tool.invoke({})
```

### 4. get_top_skills
Most common skills

```python
tool.invoke({"limit": 20})
```

### 5. get_learner_journey
Individual learner profile and history

```python
tool.invoke({"hashed_email": "abc123"})
```

### 6. get_skills_for_employed_learners
Skills of employed learners

```python
tool.invoke({"limit": 20})
```

### 7. get_geographic_distribution
Multi-metric geographic analysis

```python
tool.invoke({})
```

### 8. get_time_to_employment_stats
Time from graduation to employment

```python
tool.invoke({})
```

---

## Context Persistence

### Overview

Kweli uses a context persistence system to maintain conversation history across multiple sessions, enabling:
- Multi-turn conversations with memory
- Reference to previous queries
- Follow-up questions without repeating context

### Architecture

```
┌──────────────────────┐
│  Context Manager     │
│  - Create/Load/Save  │
└──────────┬───────────┘
           │
           v
┌──────────────────────┐
│  SQLite Storage      │
│  - Conversations     │
│  - Messages          │
│  - Tool Calls        │
└──────────────────────┘
```

### Database Schema

```sql
-- conversations table
CREATE TABLE conversations (
    id INTEGER PRIMARY KEY,
    conversation_id TEXT UNIQUE,
    title TEXT,
    created_at TIMESTAMP,
    updated_at TIMESTAMP
);

-- messages table
CREATE TABLE messages (
    id INTEGER PRIMARY KEY,
    conversation_id TEXT,
    role TEXT,
    content TEXT,
    timestamp TIMESTAMP,
    FOREIGN KEY (conversation_id) REFERENCES conversations(conversation_id)
);

-- tool_calls table
CREATE TABLE tool_calls (
    id INTEGER PRIMARY KEY,
    message_id INTEGER,
    tool_name TEXT,
    tool_input TEXT,
    tool_output TEXT,
    timestamp TIMESTAMP,
    FOREIGN KEY (message_id) REFERENCES messages(id)
);
```

### Usage

```python
from agent.context import ContextManager

# Create manager
manager = ContextManager(storage_path="data/contexts/")

# Create new conversation
conv_id = manager.create_conversation(title="Employment Analysis")

# Add messages
manager.add_message(conv_id, role="user", content="How many learners?")
manager.add_message(conv_id, role="assistant", content="168,256 learners")

# Load conversation
history = manager.load_conversation(conv_id)

# List all conversations
conversations = manager.list_conversations()
```

### Conversation Lifecycle

```
1. Start Chat → Create Conversation
2. User Message → Store with timestamp
3. Agent Response → Store with tool calls
4. Follow-up → Load context, continue
5. End Chat → Save final state
```

---

## Testing

### Unit Tests

```bash
# Validation tests
uv run pytest tests/test_agent/test_validation.py -v

# Config tests
uv run pytest tests/test_agent/test_config.py -v

# Analytics tools tests
uv run pytest tests/test_agent/test_analytics_tools.py -v

# Context persistence tests
uv run pytest tests/test_agent/test_context_persistence.py -v
```

### Integration Tests

```bash
# Requires Neo4j running
TEST_NEO4J_INTEGRATION=1 uv run pytest tests/test_agent/test_integration.py -v

# Requires LLM API key
TEST_AGENT_INTEGRATION=1 uv run pytest tests/test_agent/test_integration.py -v

# All tests
uv run pytest tests/test_agent/ -v

# With coverage
uv run pytest tests/test_agent/ --cov=agent --cov-report=html
```

### Verification

Kweli's tool execution has been verified:
- ✅ Tools are actually called (not hallucinated)
- ✅ Database queries execute correctly
- ✅ Results match manual queries
- ✅ Numbers are accurate

See `docs/kweli_verification.md` (archived) for proof.

---

## Troubleshooting

### LLM API Key Not Set

```bash
export ANTHROPIC_API_KEY="your-key"
# OR
export OPENAI_API_KEY="your-key"
```

### Neo4j Connection Failed

```bash
# Check Neo4j status
docker ps | grep neo4j

# Test connection
python -m agent.cli test-connection

# Check config
python -m agent.cli config-info
```

### Query Validation Failed

The agent only allows read-only queries. Write operations are blocked for safety.

**Error**: `ValueError: Query contains write operations`
**Solution**: Rephrase query to request data retrieval, not modification

### Maximum Iterations Reached

Agent hit iteration limit (default: 10).

**Solution**: Increase limit:
```bash
export AGENT_MAX_ITERATIONS="20"
```

Or simplify query to require fewer reasoning steps.

### Slow Query Performance

- Check Neo4j indexes are created
- Reduce result limit in query
- Use pre-built analytics tools instead of custom Cypher
- Check Neo4j server resources

### Context Persistence Errors

```bash
# Check storage directory exists
ls data/contexts/

# Create if missing
mkdir -p data/contexts/

# Check permissions
chmod 755 data/contexts/
```

---

## Advanced Usage

### Custom LLM Configuration

```python
from agent.config import Config, LLMConfig

config = Config(
    llm=LLMConfig(
        provider="anthropic",
        model="claude-3-opus-20240229",
        temperature=0.2,
        max_tokens=8192,
    )
)

from agent.graph import AnalyticsAgent
agent = AnalyticsAgent()
```

### Adding Custom Tools

```python
from langchain_core.tools import tool
from agent.tools.neo4j_tools import get_executor

@tool
def my_custom_analytics(param: str) -> dict:
    """Your custom analytics description."""
    executor = get_executor()
    result = executor.execute_query(
        "MATCH (l:Learner) WHERE ... RETURN ...",
        params={"param": param}
    )
    return {"query": "...", "results": result}

# Add to TOOLS list in agent/graph.py
```

### Streaming Responses

```python
agent = AnalyticsAgent()

for state in agent.stream_query("What are the top skills?"):
    if "messages" in state:
        latest = state["messages"][-1]
        if latest.content:
            print(latest.content)
```

---

## Performance

- **Query Response**: 2-5 seconds average
- **Streaming**: Real-time updates
- **Caching**: Schema cached for 15 minutes
- **Connection Pool**: Up to 100 concurrent connections
- **Tool Execution**: <1 second for pre-built tools

---

## Code Quality

```bash
# Linting
uv run ruff check agent/ tests/test_agent/

# Auto-fix
uv run ruff check agent/ tests/test_agent/ --fix

# Dead code detection
uv run vulture agent/ --min-confidence 80
```

---

## Contributing

1. Follow code style (<500 lines per file)
2. Add tests for new features
3. Run `ruff check --fix` before committing
4. Update documentation
5. Verify tool execution with integration tests

---

## References

- **LangGraph**: https://langchain-ai.github.io/langgraph/
- **LangChain**: https://python.langchain.com/
- **Neo4j Python Driver**: https://neo4j.com/docs/python-manual/
- **Project Guide**: See PROJECT_GUIDE.md for ETL and schema details
- **Session History**: See CLAUDE.md for development timeline

---

**Built with:**
- LangGraph - Agent orchestration
- LangChain - LLM integration
- Neo4j - Graph database
- Claude/GPT - Language models
- SQLite - Context persistence

**License**: MIT
**Status**: Production Ready
