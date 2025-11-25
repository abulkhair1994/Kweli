# ETL Optimization Plan: Date-Based Temporal Logic + Lightning Fast Performance

## Part 1: Date-Based Temporal Data Approach

### Current State
- Uses `is_current='1'` flag from CSV to count current employment
- Flag is self-reported and may be unreliable
- Processes ~105 learners/second (~4 hours for 1.6M records)

### Proposed Change: Date-Based Temporal Logic

#### Philosophy
1. **Preserve all data** - Keep ALL employment entries as learners reported them (jobs, training, volunteer, memberships)
2. **Temporal accuracy** - Use date fields to determine current status, not self-reported flags
3. **No filtering** - Don't judge or filter "non-job" activities
4. **Clean naming** - No "actual", "improved", "enhanced" in code

#### Implementation

**Location**: `src/etl/transformer.py` → `_process_employment()`

**Current Code** (Line 242):
```python
if entry.is_current == "1":
    entities.current_job_count += 1
```

**New Code**:
```python
# Determine current status based on end_date (temporal logic)
end_date = entry.end_date
is_current_employment = self._is_current_by_date(end_date)

if is_current_employment:
    entities.current_job_count += 1
```

**New Helper Method**:
```python
def _is_current_by_date(self, end_date: str | None) -> bool:
    """
    Determine if employment is current based on end_date.

    Logic:
    - No end_date (None, '', 'null') → Current
    - end_date = '9999-12-31' (sentinel) → Current
    - end_date >= snapshot_date → Current
    - end_date < snapshot_date → Past

    Args:
        end_date: End date string from CSV

    Returns:
        True if employment is current
    """
    # No end date means ongoing
    if not end_date or end_date.strip() in ['', 'null', 'None']:
        return True

    # Sentinel value for ongoing
    if end_date == '9999-12-31':
        return True

    # Compare with snapshot date
    try:
        from datetime import datetime
        end = datetime.strptime(end_date, '%Y-%m-%d').date()
        # Use state_deriver's snapshot_date
        return end >= self.state_deriver.snapshot_date
    except (ValueError, AttributeError):
        # If can't parse, assume current (preserve data)
        return True
```

#### Impact
- **More objective**: Based on dates, not self-reported flags
- **Temporal tracking**: Can query past vs current employment over time
- **Data preservation**: All activities kept, let analysts filter in queries
- **Consistency**: Same logic can be used for learning_details

---

## Part 2: Lightning Fast ETL Performance

### Current Performance
- **Speed**: ~105 learners/second
- **Total Time**: ~4 hours for 1.6M records
- **Bottleneck**: Single worker, sequential processing

### Target Performance
- **Speed**: 1,000-2,000 learners/second (10-20x improvement)
- **Total Time**: 15-30 minutes
- **Approach**: Parallel processing + batch optimization

### Optimization Strategies

#### 1. Increase Parallelization
**Current**: 1 worker
**Target**: 8-12 workers (based on CPU cores)

**Changes**:
- `config/settings.yaml`: Set `ETL_MAX_WORKERS: 8`
- `.env`: Set `ETL_MAX_WORKERS=8`

**Impact**: 8x speedup (theoretical)

#### 2. Batch Size Optimization
**Current**:
- Chunk size: 10,000 rows
- Batch size: 1,000 entities

**Target**:
- Chunk size: 50,000 rows (5x larger)
- Batch size: 5,000 entities (5x larger)

**Changes**:
- `config/settings.yaml`:
  ```yaml
  ETL_CHUNK_SIZE: 50000
  ETL_BATCH_SIZE: 5000
  ```

**Impact**: Reduces I/O overhead, ~2x speedup

#### 3. Remove Unnecessary Validation
**Current**: Heavy validation in parsers (warnings for every invalid entry)

**Target**: Validation only for critical fields, silent warnings

**Changes**:
- `src/transformers/json_parser.py`:
  - Remove or reduce logging in hot paths
  - Only log errors, not warnings
- `src/validators/`: Skip validation during ETL (validate in separate pass if needed)

**Impact**: ~20-30% speedup

#### 4. Database Connection Pooling
**Current**: Creating connections per batch

**Target**: Reuse connections across batches

**Changes**:
- Neo4j driver already uses connection pooling, but ensure:
  - `max_connection_pool_size=50` in driver config
  - Reuse session across batches in same worker

**Impact**: ~10-15% speedup

#### 5. Optimize Neo4j Writes
**Current**: UNWIND with 1,000 records

**Target**:
- Use larger UNWIND batches (5,000)
- Use `CALL { ... } IN TRANSACTIONS` for large batches
- Ensure indexes are created BEFORE loading (already done)

**Changes**:
- `src/neo4j/batch_ops.py`:
  ```cypher
  CALL {
    UNWIND $batch AS row
    MERGE (l:Learner {hashedEmail: row.hashedEmail})
    SET l += row.properties
  } IN TRANSACTIONS OF 5000 ROWS
  ```

**Impact**: ~30-40% speedup

#### 6. Profile and Optimize Hot Paths
**Tool**: Python cProfile or py-spy

**Steps**:
1. Profile ETL with small dataset (10K rows)
2. Identify top 10 time-consuming functions
3. Optimize:
   - Cache repeated computations
   - Use faster data structures
   - Avoid redundant parsing

**Expected findings**:
- JSON parsing (double-encoding)
- Date parsing
- String operations (generate_id, normalization)

**Impact**: ~20-30% speedup

#### 7. Remove Progress Bar Overhead
**Current**: Rich progress bar updates every batch

**Target**: Update every 10 batches or disable entirely

**Changes**:
- `src/etl/progress.py`: Reduce update frequency
- Or disable: `ENABLE_PROGRESS_BAR=false`

**Impact**: ~5-10% speedup

---

### Combined Performance Estimate

| Optimization | Expected Speedup | Cumulative Speed |
|--------------|------------------|------------------|
| Baseline     | 1x               | 105 learners/s   |
| 8 workers    | 8x               | 840 learners/s   |
| Larger batches | 2x             | 1,680 learners/s |
| Remove validation | 1.3x        | 2,184 learners/s |
| Connection pooling | 1.1x      | 2,402 learners/s |
| Optimized writes | 1.3x        | 3,123 learners/s |
| Profile opts | 1.2x            | 3,747 learners/s |
| Less logging | 1.1x            | 4,122 learners/s |

**Target**: 3,000-4,000 learners/second
**Total Time**: 1,597,198 / 3,500 = **~8 minutes** 🚀

---

## Implementation Plan

### Phase 1: Date-Based Temporal Logic (30 minutes)
1. Add `_is_current_by_date()` helper to `Transformer`
2. Update `_process_employment()` to use date logic
3. Update docstrings (remove "actual" language)
4. Run tests
5. Commit changes

### Phase 2: Quick Wins (15 minutes)
1. Increase `ETL_MAX_WORKERS` to 8
2. Increase `ETL_CHUNK_SIZE` to 50,000
3. Increase `ETL_BATCH_SIZE` to 5,000
4. Disable progress bar: `ENABLE_PROGRESS_BAR=false`
5. Clear database

### Phase 3: Test Run (10 minutes)
1. Run ETL on 100K rows
2. Measure speed
3. Validate data quality
4. Adjust settings if needed

### Phase 4: Full Run (8-15 minutes)
1. Run full ETL on 1.6M rows
2. Monitor progress
3. Validate results

### Phase 5: Advanced Optimizations (Optional, if needed)
1. Profile with py-spy
2. Optimize hot paths
3. Implement APOC procedures if bottleneck is Neo4j writes

---

## Risk Assessment

### Low Risk ✅
- Increasing workers (fully parallel, no shared state)
- Larger batch sizes (tested patterns)
- Disabling progress bar (cosmetic)

### Medium Risk ⚠️
- Date-based logic (need to validate against CSV ground truth)
- Removing validation (may miss data quality issues)

### High Risk ❌
- None identified

### Mitigation
- Test on 100K subset first
- Keep validation enabled for first run
- Compare results with previous run

---

## Success Criteria

### Data Quality
- ✅ All employment entries preserved (no filtering)
- ✅ Current employment count based on dates
- ✅ Professional status derivation correct
- ✅ Same number of total WORKS_FOR relationships

### Performance
- ✅ Processing speed ≥ 1,000 learners/second
- ✅ Total ETL time ≤ 30 minutes
- ✅ Memory usage stable (no leaks)

### Code Quality
- ✅ No "actual"/"enhanced" naming
- ✅ All tests passing
- ✅ Clean documentation

---

## Rollback Plan

If issues arise:
1. Stop ETL: `pkill -f "uv run python src/cli.py run"`
2. Revert changes: `git checkout HEAD -- src/`
3. Clear database: `uv run python src/cli.py clear-data --yes`
4. Return to previous working state

---

## Next Steps

Once approved:
1. Implement Phase 1 (date logic)
2. Implement Phase 2 (performance quick wins)
3. Run Phase 3 (test on 100K)
4. Review results
5. Run Phase 4 (full ETL)

**Estimated Total Time**: 1-2 hours implementation + 10-15 minutes ETL

---

**Status**: ✅ APPROVED
**Date**: 2025-11-24
**Target Completion**: Same day
