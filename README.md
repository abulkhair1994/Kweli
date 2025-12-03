# Kweli - Impact Learners Knowledge Graph

ETL pipeline and analytics agent to transform Impact Learners CSV data (1.7M rows, 2.5GB) into a Neo4j knowledge graph with natural language querying.

**Kweli** means "truth" in Swahili - your truthful guide to Impact Learners data.

## Features

- **ETL Pipeline**: Transform CSV data into Neo4j knowledge graph
- **Analytics Agent**: Natural language queries powered by LangGraph + Claude/GPT
- **Test-Driven Development**: 200+ tests with comprehensive coverage
- **HYBRID Graph Architecture**: Property references + nodes to avoid supernodes
- **Temporal State Tracking**: SCD Type 2 pattern for learning/professional states
- **Resume Capability**: Checkpoint system to resume interrupted ETL runs
- **Performance Optimized**: Chunked processing, batch operations, Polars for CSV
- **Rich Progress Tracking**: Real-time progress bars with rate metrics
- **Data Quality Validation**: Pydantic models with edge case handling
- **Modular Code**: All files <500 lines, clean architecture

## Quick Start

### 1. Setup

```bash
# Install dependencies
uv sync

# Start Neo4j
docker compose -f docker/docker-compose.yml up -d

# Wait for Neo4j to be ready
docker compose -f docker/docker-compose.yml ps
```

### 2. Configure

Edit `config/settings.yaml`:

```yaml
etl:
  chunk_size: 10000        # CSV rows per chunk
  batch_size: 1000         # Neo4j batch size
  checkpoint_interval: 5000 # Save checkpoint every N rows
  resume_from_checkpoint: false

neo4j:
  uri: "bolt://localhost:7687"
  user: "neo4j"
  password: "your_password"
```

### 3. Run ETL

```bash
# Run full ETL
kweli-etl run

# Resume from checkpoint
kweli-etl run --resume

# Check checkpoint status
kweli-etl checkpoint-status

# Clear checkpoint
kweli-etl checkpoint-clear

# Test Neo4j connection
kweli-etl test-connection

# Clear database
kweli-etl clear-database
```

### 4. Query with Analytics Agent

```bash
# Set API key
export ANTHROPIC_API_KEY="your-key"

# Interactive chat
kweli-agent chat

# Single query
kweli-agent query "How many learners are from Egypt?"

# Show example queries
kweli-agent examples

# Test connection
kweli-agent test-connection
```

## Project Structure

```
kweli/
├── config/
│   ├── settings.yaml              # ETL configuration
│   └── country_mapping.json       # Country normalization
├── data/
│   ├── raw/                       # Input CSV files
│   ├── checkpoints/               # Resume checkpoints
│   ├── logs/                      # Structured logs
│   └── reports/                   # Quality reports
├── kweli/                         # Main package
│   ├── agent/                     # Analytics agent (LangGraph)
│   │   ├── cli.py                # Agent CLI (kweli-agent)
│   │   ├── graph.py              # LangGraph ReAct agent
│   │   ├── prompts.py            # System prompts
│   │   ├── config.py             # Agent configuration
│   │   ├── state.py              # Agent state schema
│   │   ├── context/              # Context management
│   │   └── tools/                # Agent tools
│   │       ├── analytics_tools.py # Pre-built analytics queries
│   │       ├── neo4j_tools.py    # Neo4j executor
│   │       └── validation.py     # Query validation
│   └── etl/                       # ETL pipeline
│       ├── cli.py                # ETL CLI (kweli-etl)
│       ├── models/               # Pydantic data models
│       │   ├── nodes.py          # 8 node types
│       │   ├── relationships.py  # 7 relationship types
│       │   ├── enums.py          # Enum definitions
│       │   └── parsers.py        # JSON parser models
│       ├── transformers/         # Data transformation
│       │   ├── csv_reader.py     # Polars chunked reading
│       │   ├── field_mapper.py   # CSV → Pydantic mapping
│       │   ├── geo_normalizer.py # Country/city normalization
│       │   ├── skills_parser.py  # Skills extraction
│       │   ├── state_deriver.py  # State derivation logic
│       │   └── json_parser.py    # JSON field parsing
│       ├── validators/           # Data quality
│       │   ├── learner_validator.py
│       │   ├── relationship_validator.py
│       │   └── data_quality.py
│       ├── neo4j_ops/            # Neo4j operations
│       │   ├── connection.py     # Connection manager
│       │   ├── cypher_builder.py # Query builder
│       │   ├── node_creator.py   # Node creation
│       │   └── batch_ops.py      # Batch operations
│       ├── pipeline/             # ETL orchestration
│       │   ├── pipeline.py       # Main orchestrator
│       │   ├── extractor.py      # CSV extraction
│       │   ├── transformer.py    # Row transformation
│       │   ├── loader.py         # Neo4j loading
│       │   ├── checkpoint.py     # Resume system
│       │   └── progress.py       # Progress tracking
│       └── utils/                # Utilities
│           ├── config.py         # Config loader
│           ├── logger.py         # Structured logging
│           └── helpers.py        # Helper functions
├── tests/
│   ├── unit/                     # Unit tests (140+ tests)
│   ├── agent/                    # Agent tests (60+ tests)
│   ├── integration/              # Integration tests
│   └── e2e/                      # End-to-end tests
├── docs/                         # Documentation
├── notebooks/                    # Jupyter notebooks
├── docker/
│   └── docker-compose.yml        # Neo4j setup
└── pyproject.toml                # Project config
```

## Graph Schema

### Nodes (8 types)

1. **Learner** - Core learner profile (1.6M nodes)
2. **Country** - Countries (HYBRID approach, 168 nodes)
3. **City** - Cities (HYBRID approach, 4.4K nodes)
4. **Skill** - Skills and competencies (3.3K nodes)
5. **Program** - Learning programs/cohorts (121 nodes)
6. **Company** - Employer organizations (462K nodes)
7. **LearningState** - Temporal learning states (4 nodes)
8. **ProfessionalStatus** - Temporal professional states (5 nodes)

### Relationships (7 types)

1. **HAS_SKILL** - Learner → Skill (4.4M relationships)
2. **ENROLLED_IN** - Learner → Program (1.6M relationships)
3. **WORKS_FOR** - Learner → Company (902K relationships)
4. **HAS_LEARNING_STATE** - Learner → LearningState (temporal)
5. **HAS_PROFESSIONAL_STATUS** - Learner → ProfessionalStatus (temporal)
6. **RESIDES_IN** - Learner → Country/City
7. **FROM_COUNTRY** - Learner → Country

## Analytics Agent

The Kweli agent supports natural language queries:

```
# Demographics
"How many learners are from Egypt?"
"Show me the top 10 countries by learner count"

# Programs
"What's the completion rate for Software Engineering?"
"Which programs have the best employment outcomes?"

# Skills
"What are the top 20 skills among learners?"
"Which skills lead to employment?"

# Employment
"What's the employment rate for graduates?"
"What are the top companies hiring Egyptian learners?"
```

## Development

### Running Tests

```bash
# All tests
uv run pytest

# With coverage
uv run pytest --cov=kweli --cov-report=html

# Specific test file
uv run pytest tests/unit/test_models.py -v

# Agent tests only
uv run pytest tests/agent/ -v
```

### Code Quality

```bash
# Ruff linting
uv run ruff check kweli/

# Auto-fix issues
uv run ruff check kweli/ --fix

# Dead code detection
uv run vulture kweli/ --min-confidence 80
```

## Key Design Decisions

### HYBRID Country/City Approach

**Problem**: Countries/cities would become supernodes (millions of connections)

**Solution**: Store country codes and city IDs as properties on Learner nodes, but also create Country/City nodes for metadata and traversal.

```cypher
// Find learners by country (using property - fast)
MATCH (l:Learner {countryOfResidenceCode: "EG"})

// Get country metadata (using node)
MATCH (c:Country {code: "EG"})
RETURN c.name, c.region
```

### Temporal State Tracking (SCD Type 2)

Learning states and professional statuses change over time. We use temporal nodes with validity periods:

```cypher
MATCH (l:Learner)-[r:HAS_LEARNING_STATE]->(s:LearningState)
WHERE r.validFrom <= date() AND (r.validTo IS NULL OR r.validTo >= date())
RETURN s.state
```

### Edge Case Handling

- **-99 values**: Sentinel for missing data → converted to NULL
- **1970-01-01 dates**: Invalid date marker → converted to NULL
- **Empty JSON arrays "[]"**: Properly distinguished from missing data
- **N/A company names**: Filtered out in analytics queries

## Performance

- **CSV Reading**: Polars with 10K row chunks
- **Neo4j Writes**: UNWIND batch operations (1K records/batch)
- **Memory**: Streaming architecture, low memory footprint
- **Expected Rate**: ~1000-2000 rows/second
- **Total Time**: ~15-30 minutes for 1.7M rows

## Troubleshooting

### Neo4j Connection Failed

```bash
# Check Neo4j is running
docker compose -f docker/docker-compose.yml ps

# View logs
docker compose -f docker/docker-compose.yml logs neo4j

# Restart
docker compose -f docker/docker-compose.yml restart neo4j
```

### ETL Interrupted

```bash
# Check checkpoint
kweli-etl checkpoint-status

# Resume
kweli-etl run --resume
```

### Out of Memory

Reduce chunk size in `config/settings.yaml`:

```yaml
etl:
  chunk_size: 5000  # Reduced from 10000
  batch_size: 500   # Reduced from 1000
```

## Documentation

- [docs/agent_guide.md](docs/agent_guide.md) - Analytics agent documentation
- [docs/has_flags_analysis.md](docs/has_flags_analysis.md) - Analysis of has_* flags reliability
- [docs/DEVELOPMENT_STATUS.md](docs/DEVELOPMENT_STATUS.md) - Development status

## License

MIT
