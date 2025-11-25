# Kweli Usage Guide

## Overview

**Kweli** (meaning "truth" in Swahili) is your truthful guide to Impact Learners data - a LangGraph-powered ReAct agent that uses MCP-style tools to query the Neo4j knowledge graph.

## ✅ Verified: Tools Are Actually Being Called

Kweli is **NOT** making up numbers - it's genuinely executing database queries through MCP tools. See [kweli_verification.md](./kweli_verification.md) for proof.

---

## CLI Commands

### 1. Interactive Chat Mode

```bash
# Basic chat
python -m agent.cli chat

# With tool execution visibility
python -m agent.cli chat --show-tools

# With full verbose output
python -m agent.cli chat --verbose
```

**Features:**
- 🔄 Multi-turn conversation with context
- 🎨 Rich formatting with panels and markdown
- 📊 Real-time status indicators
- 🔍 Tool execution visibility (with flags)

**Visual Indicators:**
- 🤔 **Analyzing query...** - Agent is reasoning about your question
- 🔍 **Calling tool: [tool_name]** - Database/analytics tool is being executed
- ⚙️  **Processing results...** - Agent is interpreting tool output
- ✨ **Response** - Final answer with insights

**Exit:** Type `exit` or `quit` to end the session

---

### 2. Single Query Mode

```bash
# Basic query
python -m agent.cli query "How many learners are from Egypt?"

# With verbose output (shows tool calls)
python -m agent.cli query "What are the top 5 countries?" --verbose
```

**Features:**
- ⚡ Fast single-shot queries
- 📝 Markdown-formatted responses
- 🔍 Verbose mode shows full execution trace

**Use when:** You need a quick answer without starting a chat session

---

### 3. Other Commands

```bash
# Test Neo4j connection
python -m agent.cli test-connection

# Show configuration
python -m agent.cli config-info

# Show example queries
python -m agent.cli examples
```

---

## Visualization Modes

### Normal Mode (Default)

**What you see:**
```
You: How many learners are from Egypt?
🔍 Analyzing query...  [spinner]

╭─── ✨ Kweli ────╮
│ 174,772 learners│
╰─────────────────╯
```

**When to use:** Regular queries where you just want the answer

---

### --show-tools Mode

**What you see:**
```
You: How many learners are from Egypt?

🤔 Analyzing query...
🔍 Calling tool: execute_cypher_query
⚙️  Processing results...

╭─── ✨ Kweli ────────────────────────╮
│ There are 174,772 learners from    │
│ Egypt in the database.              │
╰─────────────────────────────────────╯
```

**When to use:**
- Want to see which tools are being called
- Verify database queries are happening
- Understand agent's decision-making

---

### --verbose Mode

**What you see:**
```
You: How many learners are from Egypt?

[Agent] Iteration 1
[Agent] Tool calls: 1
[Agent] Calling tool: execute_cypher_query
  Query: MATCH (l:Learner) WHERE l.countryOfResidenceCode = $code RETURN count(l)
  Params: {'code': 'EG'}

[Tools] Executed tools, got 1 result messages

[Agent] Iteration 2
[Agent] Response: There are 174,772 learners from Egypt

╭─── ✨ Kweli ────────────────────────╮
│ There are 174,772 learners from    │
│ Egypt in the database.              │
╰─────────────────────────────────────╯
```

**When to use:**
- Debugging query issues
- Understanding full agent execution flow
- Seeing actual Cypher queries and parameters
- Verifying tool execution (100% proof)

---

## Example Queries

### Demographics & Geography

```bash
"How many learners are from Egypt?"
"Show me the top 10 countries by learner count"
"What's the geographic distribution of learners?"
"How many learners are in Cairo?"
```

### Programs & Education

```bash
"What's the completion rate for Software Engineering?"
"Show me the top 5 programs by completion rate"
"Which programs have the highest dropout rates?"
"List all available programs"
```

### Skills & Employment

```bash
"What are the top 10 skills?"
"Show me the most common skills for employed learners"
"What's the employment rate by program?"
"Which skills are most valuable for getting a job?"
```

### Individual Learners

```bash
"Show me the journey for learner ID 12345"
"What skills does learner 12345 have?"
"Tell me about learner 12345's employment history"
```

### Advanced Analytics

```bash
"What's the average time to employment?"
"Compare completion rates across programs"
"Show me employment outcomes by program"
"Which programs lead to the highest employment rates?"
```

---

## Understanding Tool Execution

### 10 Available Tools

**Pre-built Analytics (8 tools):**
1. `get_top_countries_by_learners` - Geographic distribution
2. `get_program_completion_rates` - Program performance metrics
3. `get_employment_rate_by_program` - Employment outcomes
4. `get_top_skills` - Skills analysis
5. `get_learner_journey` - Individual learner profiles
6. `get_skills_for_employed_learners` - Employment-skill correlation
7. `get_geographic_distribution` - Multi-metric geographic analysis
8. `get_time_to_employment_stats` - Time-to-employment metrics

**Core Neo4j Tools (2 tools):**
9. `get_graph_schema` - Database schema information
10. `execute_cypher_query` - Execute custom Cypher queries

### How Kweli Chooses Tools

1. **Analyzes your question** - Identifies intent (demographics, programs, skills, etc.)
2. **Selects appropriate tool** - Uses pre-built tool if available, generates custom Cypher otherwise
3. **Validates query** - 5-layer safety system (read-only, injection protection, LIMIT enforcement)
4. **Executes against Neo4j** - Real database query through MCP
5. **Interprets results** - Formats data into natural language response

---

## Configuration

### Environment Variables

```bash
# LLM Configuration (Required)
ANTHROPIC_API_KEY=sk-ant-...        # Your Anthropic API key
LLM_PROVIDER=anthropic              # or "openai"
LLM_MODEL=claude-sonnet-4-5         # Model to use
LLM_TEMPERATURE=0.0                 # 0.0 = deterministic
LLM_MAX_TOKENS=8192                 # Max output tokens

# Agent Settings (Optional)
AGENT_NAME=Kweli                    # Agent name
AGENT_MAX_ITERATIONS=10             # Max reasoning loops
AGENT_QUERY_TIMEOUT=30              # Query timeout (seconds)
AGENT_MAX_RESULTS=1000              # Max results per query
AGENT_VERBOSE=false                 # Verbose logging

# Neo4j Connection
NEO4J_URI=bolt://localhost:7688     # Neo4j connection URI
NEO4J_USER=neo4j                    # Neo4j username
NEO4J_PASSWORD=password123          # Neo4j password
NEO4J_DATABASE=neo4j                # Database name
```

---

## Performance

**Typical Query Response Times:**
- Simple count queries: 1-2 seconds
- Analytics queries: 2-5 seconds
- Complex multi-step queries: 5-10 seconds

**Optimizations:**
- Schema caching (15 min TTL)
- Pre-built analytics queries
- Connection pooling (up to 100 connections)
- Result limits (max 1000 records)
- Query timeouts (30s default)

---

## Troubleshooting

### Connection Issues

**Problem:** `Neo4j connection failed`

**Solution:**
1. Check Neo4j is running: `docker ps`
2. Verify port mapping: `docker port <container_id>`
3. Test connection: `python -m agent.cli test-connection`
4. Check `.env` file has correct `NEO4J_URI`

### API Key Issues

**Problem:** `Error: LLM API key not set`

**Solution:**
1. Check `.env` file has `ANTHROPIC_API_KEY` or `OPENAI_API_KEY`
2. Verify key is valid (starts with `sk-ant-` for Anthropic)
3. Restart terminal to reload environment

### Slow Queries

**Problem:** Queries taking > 10 seconds

**Solution:**
1. Check Neo4j indexes: `python -m agent.cli test-connection`
2. Use pre-built tools when possible (they're optimized)
3. Add filters to narrow results (e.g., specific country, program)
4. Consider reducing `AGENT_MAX_RESULTS` in `.env`

---

## Tips & Best Practices

### For Best Results

✅ **Do:**
- Be specific with your questions
- Use natural language (Kweli understands context)
- Filter by specific entities when possible (country, program, etc.)
- Use verbose mode when debugging

❌ **Don't:**
- Request more than 1000 results (auto-limited for performance)
- Try to modify data (read-only database)
- Chain too many complex questions in one query

### Example: Good vs. Vague Questions

**❌ Vague:**
```
"Tell me about learners"
```

**✅ Specific:**
```
"How many learners are from Egypt and enrolled in Software Engineering?"
```

**❌ Too broad:**
```
"Show me everything about all programs"
```

**✅ Focused:**
```
"What are the top 5 programs by completion rate?"
```

---

## Additional Resources

- **Verification Proof:** [kweli_verification.md](./kweli_verification.md)
- **Implementation Details:** [agent_implementation.md](./agent_implementation.md)
- **Full Documentation:** [../agent/README.md](../agent/README.md)
- **Neo4j Graph Schema:** Run `python -m agent.cli test-connection` to see schema

---

## Quick Start

```bash
# 1. Ensure Neo4j is running
docker ps

# 2. Test connection
python -m agent.cli test-connection

# 3. Start chatting!
python -m agent.cli chat

# 4. Try a query
>>> How many learners are from Egypt?
>>> What are the top 5 programs by completion rate?
>>> Show me the geographic distribution of learners
```

---

**Kweli means "truth" - and we deliver truthful insights from real data! 🎯**
