# Discrepancy Between SQL (DuckDB) and Neo4j Query Results

## Overview

When comparing learner counts by country between DuckDB (raw CSV) and Neo4j (knowledge graph), small discrepancies exist due to differences in query logic.

## Observed Discrepancy

| Country | Neo4j (Kweli) | DuckDB | Difference |
|---------|---------------|--------|------------|
| Nigeria | 552,534 | 552,542 | -8 |
| Kenya | 185,436 | 185,443 | -7 |
| Egypt | 174,772 | 174,773 | -1 |
| Ghana | 142,874 | 142,880 | -6 |
| Morocco | 134,048 | 134,015 | **+33** |

## Root Cause

### The Neo4j Query Uses an INNER JOIN

**Neo4j (Kweli) Query:**
```cypher
MATCH (l:Learner)
WHERE l.countryOfResidenceCode IS NOT NULL
WITH l.countryOfResidenceCode as countryCode, count(l) as learnerCount
MATCH (c:Country {code: countryCode})  -- INNER JOIN: excludes learners if Country node doesn't exist
RETURN c.name as country, c.code as countryCode, learnerCount
ORDER BY learnerCount DESC
```

**DuckDB Query:**
```sql
SELECT
    country_of_residence AS country,
    COUNT(*) AS total_learners,
    ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 2) AS percentage
FROM learners
WHERE country_of_residence IS NOT NULL
  AND country_of_residence NOT IN ('n/a', '')
GROUP BY country_of_residence
ORDER BY total_learners DESC
-- NO JOIN: counts all learners directly
```

### Key Difference

The `MATCH (c:Country {code: countryCode})` line in Neo4j is an **INNER JOIN**. If a learner's country code doesn't have a matching `Country` node in the database, that learner is excluded from the count.

DuckDB counts directly from the raw data without requiring a reference table match.

## Why Morocco Shows +33 in Neo4j (Opposite Direction)

Different fields are used:
- **Neo4j**: Uses `countryOfResidenceCode` (e.g., "MA")
- **DuckDB**: Uses `country_of_residence` (e.g., "Morocco")

33 learners have `countryOfResidenceCode = "MA"` but their `country_of_residence` field is NULL, empty, or has a different spelling. Neo4j counts them (because they have the code), DuckDB doesn't (because the name field is missing/different).

## The Fix (If Needed)

To make Neo4j match DuckDB exactly, remove the Country node join:

```cypher
-- Option 1: No join (matches DuckDB behavior)
MATCH (l:Learner)
WHERE l.countryOfResidenceCode IS NOT NULL
RETURN l.countryOfResidenceCode as countryCode, count(l) as learnerCount
ORDER BY learnerCount DESC

-- Option 2: Use OPTIONAL MATCH to include learners without Country nodes
MATCH (l:Learner)
WHERE l.countryOfResidenceCode IS NOT NULL
WITH l.countryOfResidenceCode as countryCode, count(l) as learnerCount
OPTIONAL MATCH (c:Country {code: countryCode})
RETURN COALESCE(c.name, countryCode) as country, countryCode, learnerCount
ORDER BY learnerCount DESC
```

## Impact Assessment

- **Discrepancy magnitude**: ~0.005% of total learners
- **Affected queries**: Any query that joins Learner with Country/City nodes
- **Data integrity**: Both results are correct for their respective query logic

## Recommendation

The current Neo4j approach (INNER JOIN) is intentional - it ensures we only report on countries that exist in our reference data. The small discrepancy is acceptable and represents learners with:
1. Invalid/unknown country codes
2. Country codes not yet added to the Country node table
3. Data entry inconsistencies between code and name fields

If exact parity with raw CSV is required, use `OPTIONAL MATCH` instead of `MATCH` for reference table lookups.

---

## Discrepancy #2: Program Matching Differences

### Observed Discrepancy

| Query | Kweli (Neo4j) | DuckDB (BROAD) | DuckDB (SPECIFIC) |
|-------|---------------|----------------|-------------------|
| Data Analytics in Egypt | 149 | 359 | 149 |
| Data Analytics in Morocco | 227 | 504 | 227 |

### Root Cause

**Different matching approaches:**

| System | Pattern | Matches |
|--------|---------|---------|
| **Kweli (Neo4j)** | `toLower(p.name) CONTAINS 'data analytics'` | Only "Data Analytics" |
| **DuckDB (BROAD)** | `LIKE '%data%'` | Data Analytics, Data Scientist, Data Engineering |
| **DuckDB (SPECIFIC)** | `LIKE '%data analytics%'` | Only "Data Analytics" |

### Programs Matched by `LIKE '%data%'` (BROAD)

```sql
-- In Egypt:
program_name        | learners
--------------------|----------
Data Analytics      | 149
Data Scientist      | 160
Data Engineering    | 50
```

### The Fix

DuckDB notebook now supports both modes:

```sql
-- SPECIFIC (matches Kweli): 149 learners
WHERE LOWER(json_extract_string(learning_details, '$[0].program_name')) LIKE '%data analytics%'

-- BROAD (all data programs): 359 learners
WHERE LOWER(json_extract_string(learning_details, '$[0].program_name')) LIKE '%data%'
```

### Recommendation

- Use **SPECIFIC** matching when comparing with Kweli results
- Use **BROAD** matching for comprehensive analysis of all data-related programs
- The DuckDB notebook now shows both results for transparency
