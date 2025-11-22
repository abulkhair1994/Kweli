# ETL Performance Optimization Plan

**Date**: November 16, 2025
**Status**: Planning Phase
**Priority**: CRITICAL - Current ETL takes 24 hours (unacceptable)

---

## Current State Analysis

### Performance Metrics (Before Optimization)

**Test Run Results:**
- **Rows Processed**: 8,000 / 1,701,184 (0.47%)
- **Processing Rate**: 19-45 rows/second (average ~25 rows/s)
- **Elapsed Time**: ~7 minutes
- **Estimated Total Time**: **~19-24 hours** ⛔
- **Failed Records**: 0
- **Checkpoint**: Working correctly (saved at 5,000 rows)

**Expected vs Actual:**
- Expected: 15-30 minutes
- Actual: 19-24 hours
- **Performance Gap**: ~50x slower than expected

### Architecture Analysis

**Current Flow (INEFFICIENT):**

```
CSV → Read in chunks (10K rows)
    ↓
For each row:
    ↓
    Transform row → GraphEntities
    ↓
    Load entities (ONE row at a time):
        ├─ Create country nodes (individual calls)
        ├─ Create city nodes (individual calls)
        ├─ Create skill nodes (individual calls)
        ├─ Create program nodes (individual calls)
        ├─ Create company nodes (individual calls)
        ├─ Create learner node (individual call)
        ├─ Create state nodes (individual calls)
        └─ Create relationships (individual calls)
```

**Key Files:**
- `src/etl/pipeline.py:156-158` - Processes ONE row at a time
- `src/etl/loader.py:37-318` - Creates nodes/relationships individually
- `src/neo4j_ops/batch_ops.py` - **EXISTS BUT NOT USED** ⚠️

---

## Problem Diagnosis

### Root Cause

**BatchOperations class exists but is completely unused!**

The ETL creates entities one-by-one instead of batching them:

```python
# Current (SLOW) - src/etl/loader.py:72-80
for country in entities.countries:
    self.node_creator.create_country(country)  # Individual Neo4j transaction
```

**Should be (FAST):**
```python
# Batch all countries from multiple rows
batch_ops.batch_create_nodes("Country", all_countries, "code")  # Single UNWIND query
```

### Transaction Count Analysis

**For 1.7M learners:**

Assuming each learner has:
- 1 learner node
- 2 country nodes (residence + origin)
- 1 city node
- 5 skill nodes
- 1 program node
- 3 company nodes
- 2 state nodes (learning + professional)

**Nodes**: ~15 nodes/learner × 1.7M = **25.5M individual transactions**

Assuming each learner has:
- 5 skill relationships
- 1 program enrollment relationship
- 3 employment relationships
- 2 state relationships

**Relationships**: ~11 rels/learner × 1.7M = **18.7M individual transactions**

**TOTAL**: **44.2 MILLION individual Neo4j transactions** 🔥

Each transaction has:
- Network round-trip
- Session management overhead
- Transaction begin/commit overhead
- Cypher query parsing

At ~25 rows/sec, this explains the 24-hour duration.

### Why Batching Wasn't Implemented

Looking at git history and code structure, it appears:
1. `BatchOperations` class was written
2. Individual node creators were written for testing
3. ETL was built using individual creators (easier to debug)
4. **Batch integration was never completed**

---

## Optimization Plan

### Phase 1: Implement Batch Processing (HIGH PRIORITY)

#### 1.1 Modify ETL Pipeline Architecture

**Current**: Process one row → load immediately
**New**: Accumulate rows → batch load

**File**: `src/etl/pipeline.py`

```python
# New approach:
def _process_chunks(self):
    batch_accumulator = BatchAccumulator(batch_size=1000)

    for chunk_df in self.extractor.extract_chunks():
        rows = chunk_df.to_dicts()

        for row in rows:
            # Transform row
            entities = self.transformer.transform_row(row)

            # Add to batch accumulator
            batch_accumulator.add(entities)

            # When batch is full, flush to Neo4j
            if batch_accumulator.is_full():
                self.loader.load_batch(batch_accumulator.get_batch())
                batch_accumulator.clear()

    # Flush remaining
    if not batch_accumulator.is_empty():
        self.loader.load_batch(batch_accumulator.get_batch())
```

#### 1.2 Create BatchAccumulator Class

**New File**: `src/etl/batch_accumulator.py`

Responsibilities:
- Accumulate entities from multiple rows
- De-duplicate nodes (countries, cities, skills, programs, companies)
- Organize relationships by type
- Provide batch data in format ready for BatchOperations

**Structure**:
```python
class BatchAccumulator:
    def __init__(self, batch_size=1000):
        self.batch_size = batch_size
        self.learners = []
        self.countries = {}  # De-duplicated by code
        self.cities = {}     # De-duplicated by id
        self.skills = {}     # De-duplicated by id
        self.programs = {}   # De-duplicated by id
        self.companies = {}  # De-duplicated by id
        self.states = []
        self.relationships = {
            'has_skill': [],
            'enrolled_in': [],
            'works_for': [],
            'has_state': [],
        }
```

#### 1.3 Modify Loader for Batch Operations

**File**: `src/etl/loader.py`

New methods:
```python
class Loader:
    def load_batch(self, batch: BatchData):
        """Load a batch of entities using BatchOperations."""
        # Use batch_ops for all operations
        self.batch_ops.batch_create_nodes("Country", batch.countries, "code")
        self.batch_ops.batch_create_nodes("City", batch.cities, "id")
        self.batch_ops.batch_create_nodes("Skill", batch.skills, "id")
        self.batch_ops.batch_create_nodes("Program", batch.programs, "id")
        self.batch_ops.batch_create_nodes("Company", batch.companies, "id")
        self.batch_ops.batch_create_nodes("Learner", batch.learners, "sandId")
        # ... etc
```

#### 1.4 Update BatchOperations

**File**: `src/neo4j_ops/batch_ops.py`

Enhancements needed:
- Handle NULL values in node properties
- Support nested property dictionaries
- Add retry logic for transient errors
- Add progress logging

### Phase 2: Database Management

#### 2.1 Empty Neo4j Before ETL

**New CLI Command**: `src/cli.py`

```python
@cli.command()
def clear-database():
    """Clear all nodes and relationships from Neo4j."""
    click.confirm("This will delete ALL data. Continue?", abort=True)

    with connection.get_session() as session:
        # Delete all relationships
        session.run("MATCH ()-[r]->() DELETE r")

        # Delete all nodes
        session.run("MATCH (n) DELETE n")

    click.echo("✓ Database cleared")
```

**Usage**:
```bash
uv run python src/cli.py clear-database
uv run python src/cli.py run
```

#### 2.2 Optimize Indexes

Before running ETL, ensure all indexes exist:
```cypher
// Already handled by src/neo4j_ops/indexes.py
// Verify they're all created before ETL starts
```

### Phase 3: Testing & Validation

#### 3.1 Test with Sample Data

1. Run on 1,000 rows sample
2. Validate all nodes created correctly
3. Validate all relationships exist
4. Compare with current non-batched results
5. Measure performance improvement

#### 3.2 Test with Medium Dataset

1. Run on 100,000 rows
2. Measure processing rate
3. Verify checkpoint/resume works
4. Check memory usage

#### 3.3 Production Run

1. Clear database
2. Run full 1.7M rows
3. Monitor progress
4. Validate final results

---

## Implementation Steps

### Step 1: Document Current State ✅
- [x] Create this document
- [x] Analyze current code
- [x] Identify bottleneck

### Step 2: Create BatchAccumulator Class
- [ ] Create `src/etl/batch_accumulator.py`
- [ ] Implement accumulation logic
- [ ] Implement de-duplication
- [ ] Add unit tests

### Step 3: Modify Pipeline
- [ ] Update `src/etl/pipeline.py`
- [ ] Integrate BatchAccumulator
- [ ] Update progress tracking
- [ ] Update checkpoint logic

### Step 4: Modify Loader
- [ ] Update `src/etl/loader.py`
- [ ] Implement `load_batch()` method
- [ ] Use BatchOperations throughout
- [ ] Remove individual create calls

### Step 5: Enhance BatchOperations
- [ ] Update `src/neo4j_ops/batch_ops.py`
- [ ] Add NULL handling
- [ ] Add retry logic
- [ ] Improve logging

### Step 6: Add Database Management
- [ ] Add `clear-database` CLI command
- [ ] Add database stats command
- [ ] Update documentation

### Step 7: Testing
- [ ] Test with 1K rows
- [ ] Test with 100K rows
- [ ] Test checkpoint/resume
- [ ] Test error handling

### Step 8: Production Deployment
- [ ] Clear Neo4j database
- [ ] Run full ETL (1.7M rows)
- [ ] Validate results
- [ ] Generate analytics

---

## Expected Results After Optimization

### Performance Targets

**Current**:
- Processing Rate: 25 rows/second
- Total Time: 19-24 hours
- Transactions: 44.2M individual

**Expected After Optimization**:
- Processing Rate: 1,000-2,000 rows/second
- Total Time: **15-30 minutes**
- Transactions: ~44,000 batch operations (1000 records/batch)

**Improvement**: **~40-50x faster**

### Transaction Reduction

| Operation | Before | After | Improvement |
|-----------|--------|-------|-------------|
| Node Creation | 25.5M individual | 25,500 batches | 1000x |
| Relationship Creation | 18.7M individual | 18,700 batches | 1000x |
| **Total** | **44.2M** | **44,200** | **~1000x** |

### Resource Usage

**Network**:
- Before: 44.2M round-trips
- After: 44,200 round-trips
- Reduction: 99.9%

**Neo4j Sessions**:
- Before: Constant session creation/destruction
- After: Reuse sessions for batches
- Improvement: Significant overhead reduction

**Memory**:
- Before: Minimal (one row at a time)
- After: ~1000 rows buffered
- Impact: Negligible (~10-20MB per batch)

---

## Risk Mitigation

### Potential Issues

1. **Memory Usage**
   - Risk: Accumulating 1000 rows might use too much memory
   - Mitigation: Monitor and adjust batch_size if needed
   - Fallback: Reduce to 500 or 100 if necessary

2. **Transaction Failures**
   - Risk: Batch failures lose entire batch
   - Mitigation: Implement retry logic with exponential backoff
   - Fallback: Checkpoint after each batch

3. **Data Quality**
   - Risk: Batch operations harder to debug
   - Mitigation: Comprehensive logging, validate with samples first
   - Fallback: Keep individual create methods for debugging

4. **Checkpoint Complexity**
   - Risk: Checkpoint logic more complex with batching
   - Mitigation: Save checkpoint after each batch flush
   - Fallback: Accept slightly coarser checkpoint granularity

### Rollback Plan

If batching causes issues:
1. Keep current code in git branch `feature/batch-optimization`
2. Can revert to `main` branch anytime
3. Individual creates are slower but more reliable for debugging

---

## Code Quality Checks

Before committing:
- [ ] All files under 500 lines
- [ ] `uv run ruff check --fix` passes
- [ ] `uv run vulture src/` clean
- [ ] `uv run pytest` all tests pass
- [ ] Test coverage >80%

---

## Success Metrics

### Must Have
- ✅ ETL completes 1.7M rows in <30 minutes
- ✅ All 99 tests still pass
- ✅ Zero data loss compared to current approach
- ✅ Checkpoint/resume works correctly

### Nice to Have
- 📊 Processing rate >1000 rows/second
- 📊 Memory usage <500MB peak
- 📊 Real-time progress monitoring
- 📊 Automatic performance benchmarking

---

## Timeline

| Phase | Duration | Deliverable |
|-------|----------|-------------|
| Planning & Documentation | 30 min | ✅ This document |
| Implement BatchAccumulator | 1 hour | Working class with tests |
| Modify Pipeline & Loader | 2 hours | Integrated batch processing |
| Testing (samples) | 1 hour | Validated on 1K + 100K rows |
| Production Run | 30 min | Full 1.7M ETL complete |
| **TOTAL** | **~5 hours** | Optimized ETL system |

---

## Post-Optimization

### Monitoring
- Track processing rates per chunk
- Monitor Neo4j memory/CPU usage
- Log batch operation timings
- Generate performance reports

### Future Optimizations (Optional)
1. Parallel batch processing (multiple workers)
2. Async Neo4j operations
3. Pre-computed indexes
4. Materialized views for common queries
5. Graph algorithms for analysis

---

## Notes

- Current code is CORRECT, just SLOW - no logic bugs
- BatchOperations class already exists and is well-designed
- Main work is plumbing to connect existing components
- This is a pure performance optimization, not a feature change
- All existing tests should pass without modification

---

**Status**: Ready for Implementation
**Assigned**: Claude (AI Assistant)
**Estimated Completion**: ~5 hours from start
