# MySQL Streaming ETL - Status Report

**Date:** 2025-12-09
**Status:** Failed (MySQL connection timeout during Phase 2)

## Summary

The ETL was run with the new streaming mode to address the O(N²) OFFSET pagination problem. **Phase 1 completed successfully**, but **Phase 2 failed** due to MySQL connection timeout while writing to Neo4j.

## The Problem We Solved

### Original Issue
The MySQL table `impact_learners_profile` has **NO INDEXES** and **NO PRIMARY KEY**. The original OFFSET-based pagination had O(N²) complexity:

```
At 500k rows: 80 rows/sec (each query 11-17 seconds)
At 1M rows: Would be ~40 rows/sec
Total estimated time: 10+ hours
```

### Solution Implemented
Added **streaming mode** using unbuffered cursor with `fetchmany()`:
- Single table scan with O(N) complexity
- Achieved **540-650 rows/sec** consistently
- Read all 1.617M rows in **~49 minutes** (vs 10+ hours with OFFSET)

## ETL Run Results

| Metric | Value |
|--------|-------|
| Total Rows | 1,617,360 |
| Phase 1 Duration | ~49 minutes |
| Phase 1 Read Rate | ~546 rows/sec |
| Phase 1 Status | **Completed** |
| Phase 2 Status | **Failed** |
| Error | `2013: Lost connection to MySQL server during query` |

### Phase 1 Completed Successfully
Extracted shared entities and loaded to Neo4j:
- Countries: ~208
- Cities: ~4,493
- Companies: ~462,162
- Programs: ~127
- Skills: ~3,334

### Phase 2 Failed
The MySQL streaming connection was kept open during Phase 2 (writing learners to Neo4j). Due to:
1. Cloud latency to Neo4j Aura
2. SSL connection retries (transient errors)
3. Slow Neo4j batch writes

The MySQL connection became idle too long and the server closed it.

## Do We Need to Start From Beginning?

### Short Answer: **Yes, but with a quick fix**

### Why?
1. **No checkpoint file was saved** - The checkpoints directory is empty
2. **Phase 1 data is in Neo4j** - Shared entities (countries, cities, companies, etc.) were created
3. **Phase 2 was incomplete** - Some learners may have been created, but not all

### The Fix
The streaming connection only needs to stay open during **Phase 1 (reading)**. During Phase 2, we're only writing to Neo4j - we don't need MySQL anymore.

**Solution: Close MySQL connection after Phase 1 completes.**

This requires a small change to `two_phase_pipeline.py`.

## Files Modified for Streaming Mode

1. **`kweli/etl/transformers/mysql_reader.py`**
   - Added `read_mode` parameter ("streaming" or "offset")
   - Added `_read_chunks_streaming()` method using unbuffered cursor
   - Key line: `cursor = conn.cursor(buffered=False)`

2. **`kweli/etl/transformers/data_source.py`**
   - Passes `read_mode` to MySQLStreamReader

3. **`config/settings.yaml`**
   - Added `read_mode: "streaming"` setting
   - Added `read_timeout: 3600` (1 hour)

## Next Steps

### Option 1: Quick Fix (Recommended)
1. Modify `two_phase_pipeline.py` to close MySQL connection after Phase 1
2. Clear Neo4j database
3. Re-run ETL

### Option 2: Add Connection Keepalive
1. Add periodic MySQL ping during Phase 2 to keep connection alive
2. More complex, not recommended

### Option 3: Increase MySQL Timeout
1. Requires access to RDS parameter group
2. Not always possible

## Performance Comparison

| Mode | Rate at 500k rows | Total Time (1.6M rows) |
|------|-------------------|------------------------|
| OFFSET | 80 rows/sec | ~10+ hours |
| STREAMING | 540-650 rows/sec | ~49 minutes |

**Streaming is 5-8x faster** for tables without indexes.

## Commands to Re-Run

```bash
# 1. Clear Neo4j (run in Cypher)
# MATCH (n) DETACH DELETE n

# 2. Run ETL with MySQL source
source .env && uv run python -m kweli.etl.cli run --source mysql
```

## Technical Details

### Why Streaming Works
- MySQL unbuffered cursor streams rows one-by-one from server
- `fetchmany(chunk_size)` reads in batches without loading entire result set
- Single SELECT query, single table scan
- No repeated OFFSET queries that require scanning preceding rows

### Why OFFSET is Slow
Without indexes, MySQL must:
1. Scan from row 0 to OFFSET for every query
2. Query for rows 500,000-510,000 scans 500k rows first
3. O(N²) total operations for N rows

### Connection Timeout Issue
- MySQL default `wait_timeout` is typically 8 hours
- But our streaming connection may have different server-side limits
- AWS RDS may have additional timeout settings
- Solution: Don't keep connection open when not actively reading
