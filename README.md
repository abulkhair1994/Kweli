# Impact Learners Knowledge Graph

ETL pipeline to transform Impact Learners CSV data (1.7M rows, 2.5GB) into a Neo4j knowledge graph.

## Features

- **Test-Driven Development**: 99+ tests with 83% coverage
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

**Using CLI (recommended):**

```bash
# Run full ETL
uv run python src/cli.py run

# Resume from checkpoint
uv run python src/cli.py run --resume

# Check checkpoint status
uv run python src/cli.py checkpoint-status

# Clear checkpoint
uv run python src/cli.py checkpoint-clear

# Test Neo4j connection
uv run python src/cli.py test-connection
```

**Using Python script:**

```bash
uv run python src/run_etl.py
```

## Project Structure

```
Impact/
├── config/
│   ├── settings.yaml              # ETL configuration
│   └── country_mapping.json       # Country normalization
├── data/
│   ├── raw/                       # Input CSV files
│   ├── checkpoints/               # Resume checkpoints
│   ├── logs/                      # Structured logs
│   └── reports/                   # Quality reports
├── src/
│   ├── models/                    # Pydantic data models
│   │   ├── nodes.py              # 8 node types
│   │   ├── relationships.py       # 7 relationship types
│   │   ├── enums.py              # Enum definitions
│   │   └── parsers.py            # JSON parser models
│   ├── transformers/              # Data transformation
│   │   ├── csv_reader.py         # Polars chunked reading
│   │   ├── field_mapper.py       # CSV → Pydantic mapping
│   │   ├── geo_normalizer.py     # Country/city normalization
│   │   ├── skills_parser.py      # Skills extraction
│   │   ├── state_deriver.py      # State derivation logic
│   │   ├── date_converter.py     # Date parsing
│   │   └── json_parser.py        # JSON field parsing
│   ├── validators/                # Data quality
│   │   ├── learner_validator.py  # Learner validation
│   │   ├── relationship_validator.py
│   │   └── data_quality.py       # Quality metrics
│   ├── neo4j/                     # Neo4j layer
│   │   ├── connection.py         # Connection manager
│   │   ├── cypher_builder.py     # Query builder
│   │   ├── node_creator.py       # Node creation
│   │   ├── relationship_creator.py
│   │   ├── indexes.py            # Schema setup
│   │   └── batch_ops.py          # Batch operations
│   ├── etl/                       # ETL pipeline
│   │   ├── extractor.py          # CSV extraction
│   │   ├── transformer.py        # Row transformation
│   │   ├── loader.py             # Neo4j loading
│   │   ├── checkpoint.py         # Resume system
│   │   ├── progress.py           # Progress tracking
│   │   └── pipeline.py           # Orchestrator
│   ├── utils/                     # Utilities
│   │   ├── config.py             # Config loader
│   │   ├── logger.py             # Structured logging
│   │   └── helpers.py            # Helper functions
│   ├── cli.py                     # CLI commands
│   └── run_etl.py                # Main script
├── tests/
│   ├── unit/                      # Unit tests (99 tests)
│   └── integration/               # Integration tests
├── docs/                          # Documentation & analysis
├── docker/
│   └── docker-compose.yml        # Neo4j setup
└── pyproject.toml                # Project config
```

## Graph Schema

### Nodes (8 types)

1. **Learner** - Core learner profile
2. **Country** - Countries (HYBRID approach)
3. **City** - Cities (HYBRID approach)
4. **Skill** - Skills and competencies
5. **Program** - Learning programs/cohorts
6. **Company** - Employer organizations
7. **LearningState** - Temporal learning states (SCD Type 2)
8. **ProfessionalStatus** - Temporal professional states (SCD Type 2)

### Relationships (7 types)

1. **RESIDES_IN** - Learner → Country/City
2. **FROM_COUNTRY** - Learner → Country
3. **HAS_SKILL** - Learner → Skill (with proficiency)
4. **ENROLLED_IN** - Learner → Program (with scores)
5. **WORKS_FOR** - Learner → Company (with dates)
6. **HAS_LEARNING_STATE** - Learner → LearningState (temporal)
7. **HAS_PROFESSIONAL_STATUS** - Learner → ProfessionalStatus (temporal)

## Development

### Running Tests

```bash
# All tests
uv run pytest

# With coverage
uv run pytest --cov=src --cov-report=html

# Specific test file
uv run pytest tests/unit/test_models.py -v
```

### Code Quality

```bash
# Ruff linting
uv run ruff check src/

# Auto-fix issues
uv run ruff check src/ --fix

# Dead code detection
uv run vulture src/ --min-confidence 80

# Type checking
uv run mypy src/
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
- **has_* flags**: Analysis showed only 2/8 flags are reliable (see [docs/has_flags_analysis.md](docs/has_flags_analysis.md))

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
uv run python src/cli.py checkpoint-status

# Resume
uv run python src/cli.py run --resume
```

### Out of Memory

Reduce chunk size in `config/settings.yaml`:

```yaml
etl:
  chunk_size: 5000  # Reduced from 10000
  batch_size: 500   # Reduced from 1000
```

## Documentation

- [docs/has_flags_analysis.md](docs/has_flags_analysis.md) - Analysis of has_* flags reliability
- [docs/employment_analysis_findings.md](docs/employment_analysis_findings.md) - Employment data patterns
- [docs/ModelIdea.md](docs/ModelIdea.md) - Complete graph schema design

## License

MIT
