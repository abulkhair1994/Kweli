# Impact Learners Knowledge Graph - Complete Project Guide

**Version:** 2.0
**Last Updated:** 2025-11-26
**Status:** Production Ready

---

## Table of Contents

1. [Overview](#overview)
2. [Quick Start](#quick-start)
3. [Graph Schema](#graph-schema)
4. [ETL Pipeline](#etl-pipeline)
5. [Performance & Optimization](#performance--optimization)
6. [Query Examples](#query-examples)
7. [Best Practices](#best-practices)
8. [Data Quality](#data-quality)
9. [Troubleshooting](#troubleshooting)
10. [Next Steps](#next-steps)

---

## Overview

ETL pipeline transforming Impact Learners CSV data (1.7M rows, 2.5GB) into a Neo4j knowledge graph for advanced analytics.

### Key Features

- **Test-Driven Development**: 99+ tests with 83% coverage
- **HYBRID Graph Architecture**: Property references + nodes to avoid supernodes
- **Temporal State Tracking**: SCD Type 2 pattern ready (awaits historical data)
- **Resume Capability**: Checkpoint system for interrupted ETL runs
- **Performance Optimized**: 90x improvement (2,250 rows/sec)
- **Rich Progress Tracking**: Real-time progress bars
- **Data Quality Validation**: Pydantic models with edge case handling
- **Modular Code**: All files <500 lines

### Statistics

- **Learners Processed**: 168,256 (with valid sandId)
- **Total Nodes**: 577,240
- **Total Relationships**: 6.9M+
- **Countries**: 160
- **Cities**: 4,064
- **Skills**: 3,015
- **Programs**: 120
- **Companies**: 401,623

---

## Quick Start

### 1. Installation

```bash
# Install dependencies
uv sync

# Start Neo4j
docker compose -f docker/docker-compose.yml up -d
```

### 2. Configuration

Edit `config/settings.yaml`:

```yaml
etl:
  chunk_size: 10000
  batch_size: 1000
  checkpoint_interval: 5000
  num_workers: 4  # For parallel mode

neo4j:
  uri: "bolt://localhost:7687"
  user: "neo4j"
  password: "your_password"
```

### 3. Run ETL

```bash
# Sequential mode (default)
uv run python src/cli.py run

# Parallel mode (faster)
uv run python src/cli.py run --mode=parallel

# Resume from checkpoint
uv run python src/cli.py run --resume

# Check status
uv run python src/cli.py checkpoint-status
```

### 4. Clear Database (if needed)

```bash
uv run python src/cli.py clear-database
```

---

## Graph Schema

### Node Types (8)

1. **Learner** - Core learner profile with demographics
   - Primary keys: `hashedEmail`, `sandId`
   - Properties: name, gender, education, socio-economic data
   - HYBRID references: `countryOfResidenceCode`, `cityOfResidenceId`

2. **Country** - Geographic reference (HYBRID approach)
   - Key: `code` (ISO 3166-1 alpha-2)
   - Properties: name, region, latitude, longitude

3. **City** - City reference (HYBRID approach)
   - Key: `id` (e.g., "EG-CAI")
   - Properties: name, countryCode, coordinates

4. **Skill** - Skills and competencies
   - Key: `id` (normalized)
   - Properties: name, category

5. **Program** - Learning programs/cohorts
   - Key: `id` (cohort code)
   - Properties: name, cohortCode, provider

6. **Company** - Employer organizations
   - Key: `id` (normalized)
   - Properties: name, industry, countryCode

7. **LearningState** - Temporal learning states
   - States: Active, Graduate, Dropped Out, Inactive
   - Note: Currently stored as property, temporal tracking awaits historical data

8. **ProfessionalStatus** - Temporal professional states
   - Statuses: Unemployed, Wage Employed, Freelancer, Entrepreneur, Multiple
   - Note: Currently stored as property, temporal tracking awaits historical data

### Relationships (7 types)

1. **RESIDES_IN** - Learner → Country/City (via properties)
2. **FROM_COUNTRY** - Learner → Country (via property)
3. **HAS_SKILL** - Learner → Skill
   - Properties: proficiencyLevel, source, acquiredDate

4. **ENROLLED_IN** - Learner → Program
   - Properties: index, status, dates, scores, completion rates
   - Metrics: LMS scores, assignment/milestone/test completion

5. **WORKS_FOR** - Learner → Company
   - Properties: position, employmentType, dates, salaryRange, isCurrent

6. **HAS_LEARNING_STATE** - Learner → LearningState (future)
   - Will include: validFrom, validTo, isCurrent, transitionReason

7. **HAS_PROFESSIONAL_STATUS** - Learner → ProfessionalStatus (future)
   - Will include: validFrom, validTo, isCurrent, transitionType

### HYBRID Architecture

**Problem**: Countries and cities would create supernodes (millions of connections).

**Solution**: Store references as properties on Learner nodes, but also create separate Country/City nodes for metadata.

```cypher
// Fast filtering using property + index
MATCH (l:Learner {countryOfResidenceCode: "EG"})
RETURN count(l)

// Get country metadata
MATCH (c:Country {code: "EG"})
RETURN c.name, c.region
```

---

## ETL Pipeline

### Architecture

```
CSV File (1.7M rows)
    ↓
Extractor (Polars streaming)
    ↓
Transformer (Pydantic validation)
    ↓
Loader (Neo4j batch operations)
    ↓
Knowledge Graph
```

### Pipeline Modes

#### Sequential Mode
- Single-threaded processing
- Lower memory usage
- ~1,700 rows/sec
- Resume capability

#### Parallel Mode (Recommended)
- Two-phase processing
  - Phase 1: Shared entities (Country, City, Skill, Program, Company)
  - Phase 2: Learners and relationships (parallel workers)
- Higher throughput: ~2,250 rows/sec
- Uses worker pool (default: 4 workers)

### Components

**Extractor** (`src/etl/extractor.py`)
- Polars-based CSV reading with fallback to Python csv module
- Handles NUL bytes and multi-line quoted fields
- Chunks of 10,000 rows

**Transformer** (`src/etl/transformer.py`)
- CSV → Pydantic model mapping
- Field validation and normalization
- Skills parsing, geo-normalization, state derivation
- Handles -99 sentinel values, 1970-01-01 dates

**Loader** (`src/etl/loader.py`)
- Batch UNWIND operations (1,000 records/batch)
- MERGE for idempotency
- Separate node and relationship creation

**Checkpoint** (`src/etl/checkpoint.py`)
- Saves progress every 5,000 rows
- Resume from last successful checkpoint
- Stores metrics and state

### Entry Points

```bash
# CLI (recommended)
uv run python src/cli.py run [--mode=sequential|parallel] [--resume]

# Python script
uv run python src/run_etl.py
```

---

## Performance & Optimization

### Results Summary

- **Original Speed**: 25 rows/second
- **Optimized Speed**: 2,250 rows/second
- **Improvement**: 90x faster
- **Total Time**: ~12 minutes for 1.7M rows
- **Time Saved**: ~23 hours

### Key Optimizations

1. **Batch UNWIND Operations**
   - Changed from individual MERGE to batched UNWIND
   - 1,000 records per batch

2. **Polars CSV Reading**
   - Fast streaming with automatic fallback to Python csv module
   - Handles malformed data gracefully

3. **Parallel Processing**
   - Phase 1: Pre-create shared entities
   - Phase 2: Parallel learner processing

4. **Index Strategy**
   ```cypher
   // Unique constraints (include implicit index)
   CREATE CONSTRAINT learner_hashed_email FOR (l:Learner) REQUIRE l.hashedEmail IS UNIQUE
   CREATE CONSTRAINT learner_sand_id FOR (l:Learner) REQUIRE l.sandId IS UNIQUE

   // Regular indexes
   CREATE INDEX learner_country FOR (l:Learner) ON (l.countryOfResidenceCode)
   CREATE INDEX learner_city FOR (l:Learner) ON (l.cityOfResidenceId)
   CREATE INDEX skill_id FOR (s:Skill) ON (s.id)
   // ... more indexes
   ```

### Critical Fixes

**Issue**: ETL hung at 31% due to sandId lookup without index
**Fix**: Added unique constraint on sandId, ensuring index exists
**Impact**: Eliminated full table scans on relationship creation

---

## Query Examples

### Geographic Distribution

```cypher
// Learners by country
MATCH (l:Learner)
WHERE l.countryOfResidenceCode IS NOT NULL
RETURN l.countryOfResidenceCode as country, count(l) as learner_count
ORDER BY learner_count DESC

// Learners by city
MATCH (l:Learner)
WHERE l.cityOfResidenceId IS NOT NULL
RETURN l.cityOfResidenceId as city,
       l.countryOfResidenceCode as country,
       count(l) as learner_count
ORDER BY learner_count DESC
```

### Program Analytics

```cypher
// Program completion and dropout rates
MATCH (l:Learner)-[e:ENROLLED_IN]->(p:Program)
WITH p,
     sum(CASE WHEN e.isCompleted = true THEN 1 ELSE 0 END) as completed,
     sum(CASE WHEN e.isDropped = true THEN 1 ELSE 0 END) as dropped,
     count(*) as total
RETURN p.name as program,
       p.cohortCode as cohort,
       total,
       round(completed * 100.0 / total, 2) as completion_percentage,
       round(dropped * 100.0 / total, 2) as dropout_percentage
ORDER BY total DESC
```

### Employment Analysis

```cypher
// Top companies hiring Impact learners
MATCH (c:Company)<-[:WORKS_FOR]-(l:Learner)
RETURN c.name as company, count(DISTINCT l) as learner_count
ORDER BY learner_count DESC
LIMIT 10

// Employed learners with details
MATCH (l:Learner)-[w:WORKS_FOR]->(c:Company)
RETURN l.fullName as learner,
       c.name as company,
       w.position as position,
       w.startDate as start_date,
       w.isCurrent as is_current
ORDER BY w.startDate DESC
LIMIT 10
```

### Skills Analysis

```cypher
// Top skills
MATCH (l:Learner)-[:HAS_SKILL]->(s:Skill)
RETURN s.name as skill, count(l) as learner_count
ORDER BY learner_count DESC
LIMIT 20
```

---

## Best Practices

### Node vs Property Decision

**Use Node when**:
- Entity has independent identity
- Entity has relationships with other entities
- You need to traverse TO this entity
- Entity has its own attributes

**Use Property when**:
- Millions of entities would share same value
- No relationships to other entities
- Used for filtering, not traversal
- Primitive/simple data type

**Use HYBRID when**:
- High cardinality (millions of references)
- Rich entity with relationships to same type
- Need BOTH fast filtering AND graph traversal

### Avoiding Supernodes

❌ **Bad - Creates Supernode**:
```cypher
(:Learner)-[:LIVES_IN]->(:Country)
// Millions of learners → same country node
```

✅ **Good - Property Reference**:
```cypher
(:Learner {countryOfResidenceCode: "EG"})
(:Country {code: "EG", name: "Egypt"})
// Fast indexed lookup, no supernode
```

### Query Performance

```cypher
// ✅ Good - Uses index
MATCH (l:Learner {hashedEmail: "abc123"}) RETURN l

// ✅ Good - Bounded traversal
MATCH path = (l:Learner)-[*..3]-(other)
RETURN path LIMIT 100

// ❌ Bad - No index usage
MATCH (l:Learner) WHERE l.hashedEmail = "abc123" RETURN l

// ❌ Bad - Unbounded traversal
MATCH path = (l)-[*]-(other) RETURN path
```

---

## Data Quality

### Edge Cases Handled

1. **-99 Values**: Sentinel for missing data → converted to NULL
2. **1970-01-01 Dates**: Invalid date marker → converted to NULL
3. **Empty JSON Arrays "[]"**: Properly distinguished from missing data
4. **has_* Flags**: Analysis showed only 2/8 flags are reliable

### Validation

- Pydantic models enforce data types and constraints
- Required fields: `hashedEmail`, `sandId`
- Enum validation for controlled vocabularies
- Date range validation
- Relationship date consistency checks

### Known Issues

**Employment Data**: Double-encoding bug in CSV (e.g., `is_wage_employed` can be "1" or 1)
**Solution**: Transformer handles both string and int values

---

## Troubleshooting

### Neo4j Connection Failed

```bash
# Check Neo4j status
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

Reduce chunk/batch size in `config/settings.yaml`:

```yaml
etl:
  chunk_size: 5000  # Reduced from 10000
  batch_size: 500   # Reduced from 1000
```

### Slow Relationship Creation

Ensure indexes exist:

```bash
uv run python src/cli.py test-connection
# Check logs for index creation confirmation
```

---

## Next Steps

### Missing: Temporal State Tracking

**Status**: NOT IMPLEMENTED (awaits historical data)

Currently, learning states and professional statuses are stored as properties:
```cypher
(:Learner {currentLearningState: "Graduate"})
```

**Future Implementation** (when historical data available):
```cypher
(:Learner)-[HAS_LEARNING_STATE {
    validFrom: "2024-01-01",
    validTo: "2024-06-30",
    isCurrent: false
}]->(:LearningState {state: "Active"})
```

This would enable:
- Dropout risk analysis
- Time-to-employment tracking
- Career progression patterns
- Re-engagement success metrics

### Potential Enhancements

1. **Data Export**: CSV/JSON export capabilities
2. **Incremental Updates**: Update existing data vs full reload
3. **Graph Visualization**: Integration with visualization tools
4. **Advanced Analytics**: Machine learning models on graph data
5. **Event Tracking**: Attendance, engagement events (from zoom_attendance_details, circle_events)

---

## Development

### Running Tests

```bash
# All tests
uv run pytest

# With coverage
uv run pytest --cov=src --cov-report=html

# Specific module
uv run pytest tests/unit/test_models.py -v
```

### Code Quality

```bash
# Linting
uv run ruff check src/ tests/

# Auto-fix
uv run ruff check src/ tests/ --fix

# Dead code detection
uv run vulture src/ --min-confidence 80
```

### Project Structure

```
Impact/
├── src/
│   ├── models/           # Pydantic models (587 lines)
│   ├── transformers/     # Data transformation (1,045 lines)
│   ├── validators/       # Validation logic (474 lines)
│   ├── neo4j_ops/        # Neo4j operations (1,137 lines)
│   ├── etl/              # Pipeline logic (896 lines)
│   ├── utils/            # Utilities (331 lines)
│   ├── cli.py            # CLI interface
│   └── run_etl.py        # Python entry point
├── tests/                # 99+ tests
├── config/               # Configuration files
├── data/                 # Data directories
├── docker/               # Docker setup
└── docs/                 # Documentation
```

---

## References

- **Graph Schema**: See ModelIdea.md (archived) for detailed schema design
- **Best Practices**: See KG Best Practicies.md (archived) for Neo4j patterns
- **Session History**: See CLAUDE.md for development timeline
- **Agent Guide**: See AGENT_GUIDE.md for analytics agent documentation

---

**License**: MIT
**Support**: For issues, see GitHub Issues or CLAUDE.md
