# ETL Performance Fix Plan

**Date:** 2024-11-24
**Issue:** Phase 2 taking 4+ hours (expected: 15-30 minutes)
**Current Status:** ETL running but extremely slow

---

## Executive Summary

The ETL pipeline is experiencing severe performance degradation in Phase 2 (learner processing), taking over 4 hours instead of the expected 15-30 minutes. Analysis identified three critical bottlenecks that are compounding to create a ~10-50x slowdown.

**Estimated Impact:** Fixing these issues should reduce Phase 2 runtime from 4+ hours to **10-20 minutes**.

---

## Problem Analysis

### Current Performance

**Phase 1** (Shared Entity Extraction):
- ✅ **Status:** Completed successfully
- ⏱️ **Time:** 86.6 seconds
- 📊 **Rate:** 18,442 learners/second
- **Result:** Extracted 462,156 companies, 4,443 cities, 3,334 skills, 168 countries, 121 programs

**Phase 2** (Learner Processing):
- ❌ **Status:** In progress (4+ hours and counting)
- ⏱️ **Estimated Time:** 53+ hours at current rate
- 📊 **Rate:** ~1 batch per 30-60 seconds
- **Target:** Should complete in 10-20 minutes

**Current vs Expected:**
- **Current:** ~53 hours (estimated)
- **Expected:** 15-30 minutes
- **Slowdown:** ~100-200x slower than expected

---

## Root Causes

### 1. Critical: Hardcoded Batch Size (MAJOR BOTTLENECK)

**Location:** `src/etl/loader.py:41`

**Problem:**
```python
# Current code (WRONG)
self.batch_ops = BatchOperations(connection, batch_size=1000, logger=logger)
```

**Impact:**
- Config specifies `batch_size: 5000`
- Code ignores config and uses hardcoded `1000`
- **5x more database round-trips** than necessary
- **5x more network overhead**
- **5x more transaction overhead**

**Scale Impact:**
- ~6.4M total relationships to create
- At 1000/batch: **6,400 batches**
- At 5000/batch: **1,280 batches** (5x fewer)

**Fix:**
```python
# Read batch_size from config
from utils.config import Config
config = Config()
batch_size = config.get("neo4j.batch_size", 1000)
self.batch_ops = BatchOperations(connection, batch_size=batch_size, logger=logger)
```

**Expected Speedup:** 3-5x faster

---

### 2. Critical: Single-Threaded Execution Suspected

**Location:** `src/etl/two_phase_pipeline.py:277-301`

**Problem:**
- Config specifies `num_workers: 8` (8 parallel threads)
- Log patterns suggest **sequential processing** (1 thread)
- ThreadPoolExecutor may not be receiving correct num_workers value

**Evidence from Logs:**
- Relationship batches processed sequentially
- No concurrent batch messages
- Timestamps show 30-60 second gaps between batches (sequential pattern)

**Impact:**
- Expected parallelism: 8x
- Actual parallelism: 1x (suspected)
- **8x slower than expected**

**Investigation Needed:**
1. Verify `num_workers` is correctly passed from CLI to TwoPhaseETLPipeline
2. Check if ThreadPoolExecutor is actually using 8 workers
3. Confirm connection pool can handle 8 concurrent connections

**Fix:**
```python
# In src/cli.py or run_etl.py, ensure num_workers is passed correctly:
pipeline = TwoPhaseETLPipeline(
    csv_path=csv_path,
    connection=connection,
    chunk_size=config.get("etl.chunk_size", 10000),
    batch_size=config.get("etl.batch_size", 1000),
    num_workers=config.get("etl.num_workers", 1),  # ← Verify this is correct
    enable_progress_bar=enable_progress_bar,
    logger=logger,
)
```

**Expected Speedup:** 6-8x faster (if currently single-threaded)

---

### 3. Moderate: Expensive MATCH Operations in Relationship Creation

**Location:** `src/neo4j_ops/batch_ops.py:128-135`

**Problem:**
```cypher
UNWIND $records AS record
MATCH (from:Learner {sandId: record.from_id})  ← Index lookup
MATCH (to:Skill {id: record.to_id})             ← Index lookup
MERGE (from)-[r:HAS_SKILL]->(to)
```

**Impact:**
- **2 MATCH operations per relationship**
- ~6.4M relationships × 2 = **12.8M MATCH operations**
- Even with indexes, each MATCH adds ~1-5ms overhead
- Total overhead: 12.8M × 2ms = **7 hours** of pure MATCH time (worst case)

**Current Mitigation:**
- Indexes exist on `Learner.sandId`, `Skill.id`, etc. (created in Phase 0)
- Should be using indexes for MATCH operations

**Potential Optimizations (Future):**
1. Use Neo4j query profiling to verify index usage
2. Consider batching relationship creation differently
3. Investigate `CALL {} IN TRANSACTIONS` for better parallelism

**Expected Speedup:** 1.2-1.5x faster (if indexes are optimal)

---

## Priority Fix Plan

### Priority 1: Fix Hardcoded Batch Size (IMMEDIATE)

**Files to Modify:**
1. `src/etl/loader.py` (line 41)

**Changes:**
```python
# Before
self.batch_ops = BatchOperations(connection, batch_size=1000, logger=logger)

# After
from utils.config import Config
config = Config()
batch_size = config.get("neo4j.batch_size", 1000)
self.batch_ops = BatchOperations(connection, batch_size=batch_size, logger=logger)
```

**Alternative (Pass as Parameter):**
```python
# In Loader.__init__(), add batch_size parameter:
def __init__(
    self,
    connection: Neo4jConnection,
    batch_size: int = 1000,  # ← Add parameter
    logger: FilteringBoundLogger | None = None,
) -> None:
    self.connection = connection
    self.logger = logger or get_logger(__name__)
    self.node_creator = NodeCreator(connection, logger)
    self.relationship_creator = RelationshipCreator(connection, logger)
    self.batch_ops = BatchOperations(connection, batch_size=batch_size, logger=logger)
```

**Testing:**
- Run on 10K subset: `uv run python src/cli.py run --csv-path data/raw/test_10k.csv`
- Verify batch_size=5000 in logs
- Should complete in ~30 seconds

---

### Priority 2: Verify num_workers Configuration (IMMEDIATE)

**Files to Check:**
1. `src/cli.py` or `src/run_etl.py` (wherever TwoPhaseETLPipeline is instantiated)
2. `src/etl/two_phase_pipeline.py`

**Verification Steps:**
1. Add debug logging to confirm num_workers value:
   ```python
   self.logger.info("Initializing TwoPhaseETLPipeline", num_workers=num_workers)
   ```

2. In `_phase2_process_learners_parallel()`, log executor details:
   ```python
   with ThreadPoolExecutor(max_workers=self.num_workers) as executor:
       self.logger.info("ThreadPoolExecutor started", max_workers=self.num_workers)
   ```

3. Check connection pool size:
   ```python
   # Ensure connection pool >= num_workers
   max_connection_pool_size = config.get("neo4j.max_connection_pool_size", 50)
   if max_connection_pool_size < num_workers:
       self.logger.warning(
           "Connection pool too small for parallel workers",
           pool_size=max_connection_pool_size,
           num_workers=num_workers
       )
   ```

**Fix (if needed):**
- Ensure `num_workers` is read from config and passed to TwoPhaseETLPipeline
- Current config has `num_workers: 8` and `max_connection_pool_size: 100` (good)

---

### Priority 3: Index Verification (OPTIONAL - AFTER FIXES 1 & 2)

**Verification Steps:**
1. Run `EXPLAIN` on relationship creation queries to verify index usage
2. Check Neo4j logs for slow queries
3. Run query profiling:
   ```cypher
   PROFILE MATCH (l:Learner {sandId: "SAND123"})
   MATCH (s:Skill {id: "python"})
   MERGE (l)-[r:HAS_SKILL]->(s)
   RETURN r
   ```

**Expected Output:**
- Should show "NodeIndexSeek" for both MATCH operations
- If showing "NodeByLabelScan", indexes aren't being used

**Fix (if needed):**
- Indexes should already exist from Phase 0
- If missing, recreate indexes:
  ```cypher
  CREATE INDEX learner_sand_id IF NOT EXISTS FOR (l:Learner) ON (l.sandId);
  CREATE INDEX skill_id IF NOT EXISTS FOR (s:Skill) ON (s.id);
  CREATE INDEX program_id IF NOT EXISTS FOR (p:Program) ON (p.id);
  CREATE INDEX company_id IF NOT EXISTS FOR (c:Company) ON (c.id);
  ```

---

## Implementation Strategy

### Option A: Kill Current ETL and Restart with Fixes (RECOMMENDED)

**Pros:**
- Immediate benefit from fixes
- Fresh start with correct configuration
- Faster overall completion

**Cons:**
- Loses 4 hours of progress (but saves 49+ hours)
- Need to clear database first

**Steps:**
1. Kill running ETL process (PID 37606)
2. Apply Priority 1 and 2 fixes
3. Clear Neo4j database (Phase 2 data only)
4. Restart ETL with fixes

**Estimated Total Time:** 1.5 minutes (Phase 1) + 15-20 minutes (Phase 2) = **~20 minutes**

---

### Option B: Let Current ETL Finish, Apply Fixes for Next Run

**Pros:**
- No lost progress
- Can test fixes on smaller dataset first

**Cons:**
- Will take another 40-50 hours to complete
- Database will have data that may need to be regenerated

**Steps:**
1. Let current ETL finish (~50 more hours)
2. Apply fixes
3. Test on 10K dataset
4. Clear database and re-run full ETL

**Estimated Total Time:** 50 hours (current) + 20 minutes (re-run) = **50+ hours**

---

## Recommendation

**RECOMMENDED: Option A (Kill and Restart)**

**Rationale:**
- Saves ~45-50 hours of total time
- Current ETL has been running with sub-optimal configuration
- Fixes are straightforward and low-risk
- Can validate fixes on 10K dataset first (30 seconds)

**Action Plan:**
1. Kill current ETL (5 minutes)
2. Apply Priority 1 fix (5 minutes)
3. Verify Priority 2 configuration (5 minutes)
4. Test on 10K dataset (30 seconds)
5. Clear Neo4j Phase 2 data (1 minute)
6. Restart full ETL (20 minutes)

**Total Time:** ~30 minutes of work + 20 minutes ETL = **50 minutes total**

---

## Expected Results After Fixes

### Current Performance (Broken)
- **Phase 1:** 86 seconds ✅
- **Phase 2:** ~53 hours (estimated) ❌
- **Total:** ~53 hours

### Expected Performance (Fixed)
- **Phase 1:** 86 seconds ✅
- **Phase 2:** 10-20 minutes ✅
- **Total:** **~12-22 minutes** ✅

**Speedup:** 150-250x faster overall pipeline

---

## Code Changes Summary

### File 1: `src/etl/loader.py`

**Change Line 41:**
```python
# Before
self.batch_ops = BatchOperations(connection, batch_size=1000, logger=logger)

# After - Option 1 (Read from config)
from utils.config import Config
config = Config()
batch_size = config.get("neo4j.batch_size", 1000)
self.batch_ops = BatchOperations(connection, batch_size=batch_size, logger=logger)

# After - Option 2 (Pass as parameter - preferred)
def __init__(
    self,
    connection: Neo4jConnection,
    batch_size: int = 1000,
    logger: FilteringBoundLogger | None = None,
) -> None:
    """Initialize loader with configurable batch size."""
    self.connection = connection
    self.logger = logger or get_logger(__name__)
    self.node_creator = NodeCreator(connection, logger)
    self.relationship_creator = RelationshipCreator(connection, logger)
    self.batch_ops = BatchOperations(connection, batch_size=batch_size, logger=logger)
```

### File 2: `src/etl/two_phase_pipeline.py`

**Add Debug Logging (Line ~62):**
```python
def __init__(
    self,
    csv_path: Path | str,
    connection: Neo4jConnection,
    chunk_size: int = 10000,
    batch_size: int = 1000,
    num_workers: int = 4,
    checkpoint_interval: int = 5000,
    enable_progress_bar: bool = True,
    logger: FilteringBoundLogger | None = None,
) -> None:
    """Initialize two-phase ETL pipeline."""
    self.csv_path = Path(csv_path)
    self.connection = connection
    self.chunk_size = chunk_size
    self.batch_size = batch_size
    self.num_workers = num_workers

    # ← ADD THIS DEBUG LOG
    self.logger = logger or get_logger(__name__)
    self.logger.info(
        "TwoPhaseETLPipeline initialized",
        chunk_size=chunk_size,
        batch_size=batch_size,
        num_workers=num_workers,
    )
```

**Update Line 62 to pass batch_size to Loader:**
```python
# Before
self.loader = Loader(connection, logger)

# After
self.loader = Loader(connection, batch_size=batch_size, logger=logger)
```

---

## Testing Strategy

### Test 1: 10K Subset (Validation)
```bash
uv run python src/cli.py run --csv-path data/raw/test_10k.csv
```

**Expected Results:**
- Phase 1: ~5 seconds
- Phase 2: ~30-60 seconds
- Logs show `batch_size=5000`
- Logs show `num_workers=8`

### Test 2: Full Dataset (Production)
```bash
uv run python src/cli.py run --csv-path data/raw/impact_learners_profile-1759316791571.csv
```

**Expected Results:**
- Phase 1: ~86 seconds
- Phase 2: ~10-20 minutes
- Total: ~12-22 minutes

---

## Monitoring Plan

### Metrics to Watch

**Phase 2 Progress:**
- Log entries should show `batch_size=5000` (not 1000)
- Multiple concurrent "Created batch of relationships" messages
- Processing rate: ~5000-8000 learners/second (vs current ~300/second)

**Database Performance:**
- Neo4j query times: ~500ms-2s per batch (vs current ~30-60s)
- Connection pool usage: Should see 8 active connections
- No connection pool exhaustion warnings

### Success Criteria

✅ Phase 1 completes in <2 minutes
✅ Phase 2 completes in <25 minutes
✅ No errors or warnings in logs
✅ All 1,597,198 learners processed
✅ Relationships created successfully

---

## Rollback Plan

If fixes cause issues:

1. **Revert Code Changes:**
   ```bash
   git checkout src/etl/loader.py
   git checkout src/etl/two_phase_pipeline.py
   ```

2. **Restart with Original Code:**
   - Original will still be slow but will complete eventually

3. **Alternative: Use Single-Phase Pipeline:**
   - Slower but more stable
   - Fall back to `ETLPipeline` instead of `TwoPhaseETLPipeline`

---

## Questions to Answer During Investigation

1. ✅ Is batch_size hardcoded? → **YES (1000 instead of 5000)**
2. ⚠️ Is num_workers correctly passed? → **NEEDS VERIFICATION**
3. ⚠️ Are indexes being used for MATCH? → **LIKELY YES (verify with EXPLAIN)**
4. ⚠️ Is connection pool sufficient? → **YES (100 > 8 workers)**
5. ⚠️ Are there Neo4j performance issues? → **LIKELY NO (Phase 1 was fast)**

---

## Next Steps

### Immediate Actions:
1. ✅ **Document findings** (this file)
2. ⬜ **Kill current ETL** (if user approves)
3. ⬜ **Apply Priority 1 fix** (batch_size)
4. ⬜ **Verify Priority 2** (num_workers)
5. ⬜ **Test on 10K dataset**
6. ⬜ **Restart full ETL**

### Post-Fix:
7. ⬜ **Monitor Phase 2 performance**
8. ⬜ **Verify completion** (~20 minutes)
9. ⬜ **Run Neo4j query tests**
10. ⬜ **Document final performance metrics**

---

---

## Temporal State Tracking Status

**CLARIFICATION:** Temporal state tracking IS implemented, but with snapshot data limitations.

### What's Working ✅
1. **LearningStateNode** and **ProfessionalStatusNode** created with temporal properties:
   - `start_date`: Uses snapshot date (2025-10-06) for current states
   - `end_date`: NULL for current states (properly indicating ongoing)
   - `is_current`: TRUE for current states

2. **Temporal relationships** created with validity markers:
   - `HAS_LEARNING_STATE` with `validFrom`, `validTo`, `isCurrent`
   - `HAS_PROFESSIONAL_STATUS` with `validFrom`, `validTo`, `isCurrent`

3. **Actual temporal data** in relationships:
   - `ENROLLED_IN`: Real start_date, end_date, graduation_date from learning_details
   - `WORKS_FOR`: Real start_date, end_date from employment_details
   - This provides partial temporal tracking of career progression

### What's Missing ⚠️
- Historical state transitions (e.g., Active → Dropped Out → Graduate timeline)
- Multiple temporal state records per learner
- **Reason**: CSV only contains current snapshot, not historical state changes

### Implementation Status
✅ Temporal infrastructure fully implemented
✅ Current state snapshot tracked correctly
⚠️ Historical transitions blocked by data availability (see next_steps.md)

---

**Status:** APPROVED - Proceeding with performance fixes and ETL execution

**Last Updated:** 2024-11-24 (Temporal clarification + performance fixes applied)
