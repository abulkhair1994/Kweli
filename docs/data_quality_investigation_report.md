# Data Quality Investigation Report: Professional Status Discrepancy

**Date**: 2025-01-20
**Investigator**: Claude Code Analysis
**Case ID**: DQ-2025-001
**Status**: ✅ RESOLVED - Root cause identified

---

## Executive Summary

Investigation of learner `c52d2f6690479174f5cc44b364e8c7f3` revealed a **systematic data quality issue** affecting **183,118 learners (11.5%)** in the database. These learners are marked as "Unemployed" despite having current employment relationships.

**Root Cause**: ETL pipeline derives `currentProfessionalStatus` from CSV flag fields (`is_wage_employed`, `is_a_freelancer`, `is_running_a_venture`) which are **outdated/incorrect**, rather than from the actual `employment_details` JSON field which contains accurate, up-to-date employment data.

**Business Impact**:
- Incorrect analytics and reporting on employment outcomes
- Misleading success metrics for Impact programs
- Potential misallocation of resources for job placement assistance

**Recommendation**: **HIGH PRIORITY** - Update ETL logic to derive professional status from `employment_details` instead of unreliable flag fields, then re-run ETL to correct the database.

---

## Case Details

### Learner Profile (Sample Case)

| Field | Value |
|-------|-------|
| **Hashed Email** | `25d05927de503e5990e9d5bb6f799dd3` |
| **Full Name** | `c52d2f6690479174f5cc44b364e8c7f3` ⚠️ (hash, not actual name) |
| **Gender** | Male |
| **Country** | Nigeria (NG) |
| **Education** | Bachelor's degree or equivalent |
| **Learning State** | Graduate ✅ |
| **Professional Status** | Unemployed ❌ (incorrect) |

### The Discrepancy

```
📊 Professional Status: "Unemployed"
💼 Current Employment: 2 jobs marked as current
   1. Principal Data Scientist at gomoney (Started: 2022-04-01)
   2. Principal Data Scientist at Sterling Bank Plc (Started: 2022-04-01)

❌ CONTRADICTION: Cannot be unemployed with 2 current jobs!
```

---

## Investigation Findings

### 1. Raw CSV Data Analysis

**File**: `data/raw/impact_learners_profile-1759316791571.csv`
**Learner Record**: `hashed_email = 25d05927de503e5990e9d5bb6f799dd3`

#### CSV Fields (Source of Truth):

```yaml
Status Fields (UNRELIABLE):
  current_professional_status: null (None)
  is_wage_employed: 0
  is_a_freelancer: 0
  is_running_a_venture: 0

Employment Data (RELIABLE):
  employment_details: 14 records (JSON array)
  Current jobs in employment_details: 2
    - Job 12: gomoney, is_current: "1", end_date: "9999-12-31"
    - Job 13: Sterling Bank Plc, is_current: "1", end_date: "9999-12-31"
```

#### Complete Employment History (from CSV):

| # | Organization | Title | Start Date | End Date | is_current |
|---|-------------|-------|------------|----------|------------|
| 1 | Hadejia General Hospital | Data Analyst | 2014-06-01 | 2014-11-30 | 0 |
| 2 | Metropolitan International School | Educator | 2016-02-01 | 2016-10-31 | 0 |
| 3 | Imaad schools | Educator | 2017-02-01 | 2017-09-30 | 0 |
| 4 | Compovine | Research Analyst | 2018-01-01 | 2018-08-31 | 0 |
| 5 | Edubridge Consultants | Digital Strategist | 2018-08-01 | 2020-08-31 | 0 |
| 6 | UNITeS CISCO Networking Academy | Project Manager | 2019-03-01 | 2021-02-28 | 0 |
| 7 | Dataville Research LLC | International Development Intern | 2020-02-01 | 2020-04-30 | 0 |
| 8 | Hamoye.com | Data Scientist | 2020-07-01 | 2020-12-31 | 0 |
| 9 | Omdena | Lead ML Engineer | 2020-12-01 | 2022-12-31 | 0 |
| 10 | London Academy Business School | Head Of IT | 2021-02-01 | 2021-07-31 | 0 |
| 11 | AFEX | Head, ML & Analytics | 2021-07-01 | 2022-06-30 | 0 |
| **12** | **gomoney** | **Principal Data Scientist** | **2022-04-01** | **9999-12-31** | **1** ✅ |
| **13** | **Sterling Bank Plc** | **Principal Data Scientist** | **2022-04-01** | **9999-12-31** | **1** ✅ |
| 14 | FITC Nigeria | Head - Technology | 2022-05-01 | 2023-05-31 | 0 |

**Key Observations**:
- Jobs 12 & 13 have `is_current: "1"` (string "1", not integer)
- End date `9999-12-31` is a sentinel value meaning "no end date" (still employed)
- **All flag fields are 0**, contradicting the actual employment data
- This learner has held 14 different positions over 8+ years, showing career progression

---

### 2. Neo4j Data Analysis

**Query**: `MATCH (l:Learner {hashedEmail: "25d05927de503e5990e9d5bb6f799dd3"})`

#### Neo4j Node Properties:

```yaml
Learner Node:
  hashedEmail: "25d05927de503e5990e9d5bb6f799dd3"
  fullName: "c52d2f6690479174f5cc44b364e8c7f3" ⚠️ (hash from CSV)
  sandId: null
  currentProfessionalStatus: "Unemployed" ❌ (derived from flags)
  currentLearningState: "Graduate" ✅
  gender: "male"
  countryOfResidenceCode: "NG"
  educationLevel: "Bachelor's degree or equivalent"

Employment Relationships:
  Total WORKS_FOR relationships: 14
  Current jobs (isCurrent: true): 2
    - Sterling Bank Plc (source: employment_details)
    - gomoney (source: employment_details)
  Past jobs (isCurrent: false): 12
```

**Critical Finding**: The ETL correctly parsed and loaded all 14 employment records from `employment_details` JSON, including correctly setting `isCurrent: true` for the 2 current jobs. However, it **separately and incorrectly** derived `currentProfessionalStatus: "Unemployed"` from the unreliable flag fields.

---

### 3. ETL Pipeline Analysis

**Location**: `src/transformers/state_deriver.py` and `src/etl/transformer.py`

#### Current ETL Logic (FLAWED):

```python
def derive_professional_status(learner_data: dict) -> str:
    """
    Derive professional status from flag fields.

    Problem: These flags are outdated and don't reflect current employment!
    """
    if learner_data.get('is_wage_employed') == 1:
        return 'Wage Employed'
    elif learner_data.get('is_a_freelancer') == 1:
        return 'Freelancer'
    elif learner_data.get('is_running_a_venture') == 1:
        return 'Entrepreneur'
    else:
        return 'Unemployed'  # ❌ Default when all flags are 0
```

#### How Employment Relationships Are Created (CORRECT):

```python
def parse_employment_details(employment_json: str) -> List[WorksForRelationship]:
    """
    Parse employment_details JSON and create relationships.

    This part works correctly - it accurately identifies current jobs!
    """
    jobs = json.loads(employment_json)
    relationships = []

    for job in jobs:
        is_current = job.get('is_current') == '1'  # String comparison

        relationships.append(WorksForRelationship(
            company_name=job.get('organization_name'),
            position=job.get('job_title'),
            start_date=job.get('start_date'),
            end_date=job.get('end_date'),
            is_current=is_current,  # ✅ Correctly set
            source='employment_details'
        ))

    return relationships
```

**The Contradiction**: The ETL has TWO separate code paths:

1. **Status Derivation** (uses flags) → **WRONG** → Sets `currentProfessionalStatus = "Unemployed"`
2. **Relationship Creation** (uses JSON) → **CORRECT** → Creates 2 current WORKS_FOR relationships

These operate independently and produce contradictory results!

---

## Root Cause Analysis

### The Problem

The CSV data has **two sources of employment information**:

1. **Flag Fields** (snapshot fields - OUTDATED):
   - `is_wage_employed`
   - `is_a_freelancer`
   - `is_running_a_venture`
   - `current_professional_status`

2. **JSON Field** (detailed records - CURRENT):
   - `employment_details` (array of job records with dates and `is_current` flags)

### Why Flags Are Wrong

The flags appear to be **denormalized snapshot fields** from an earlier date that were never updated. Evidence:

- Learner has 2 jobs starting 2022-04-01 (nearly 3 years ago)
- Flags still show 0 (unemployed)
- `employment_details` JSON contains up-to-date, detailed records

**Hypothesis**: The source system maintains `employment_details` as the **primary record** (updated when jobs change), while flag fields are **derived views** that became stale over time. The source system likely stopped updating these flags at some point.

### Why This Wasn't Caught

1. **No cross-validation** between flag-derived status and employment relationships
2. **No data quality checks** in ETL to detect this inconsistency
3. **Separate code paths** for status vs. relationships prevented detection

---

## Scope Analysis

### Database-Wide Impact

**Query Results** (Analysis Date: 2025-01-20):

```sql
Total Learners: 1,597,167
Affected Learners: 183,118 (11.5% ❌)
Current Jobs (among affected): 244,138
Average Jobs per Affected Learner: 1.3
```

**Professional Status Distribution**:

| Status | Count | Percentage | Notes |
|--------|-------|------------|-------|
| Unemployed | 1,534,191 | 96.1% | ⚠️ 11.9% have current jobs |
| Wage Employed | 52,941 | 3.3% | Likely correct |
| Entrepreneur | 10,035 | 0.6% | Likely correct |

**Critical Finding**: Of the 1.53M learners marked "Unemployed", **183,118 (11.9%)** actually have current employment relationships in the database!

### Query to Identify Affected Learners

```cypher
// Find all learners marked unemployed but with current jobs
MATCH (l:Learner)-[w:WORKS_FOR]->(c:Company)
WHERE w.isCurrent = true
  AND l.currentProfessionalStatus = 'Unemployed'
RETURN l.hashedEmail, l.fullName, count(w) as current_jobs, collect(c.name) as companies
ORDER BY current_jobs DESC
```

---

## Additional Data Quality Issues Found

### 1. Full Name is Hash Value

**Issue**: Many learners have `fullName` set to what appears to be a hash value (e.g., `c52d2f6690479174f5cc44b364e8c7f3`) instead of an actual name.

**Source**: CSV field `full_name` contains hash values for some learners.

**Impact**:
- Cannot display user-friendly names in reports/dashboards
- May indicate privacy/anonymization applied inconsistently

**Sample Query**:
```cypher
MATCH (l:Learner)
WHERE l.fullName =~ '[0-9a-f]{32}'  // 32-char hex string (MD5 pattern)
RETURN count(l) as learners_with_hash_names
```

### 2. Duplicate Current Jobs on Same Date

**Issue**: Some learners have multiple "current" jobs starting on the exact same date.

**Example**: Our sample learner has 2 "Principal Data Scientist" roles both starting 2022-04-01:
- gomoney
- Sterling Bank Plc

**Possible Causes**:
- Legitimate (consulting/part-time work)
- Data entry error
- Job change where old job wasn't marked as ended

**Recommendation**: Add validation to flag potential duplicates for review.

---

## Recommendations

### Immediate Actions (HIGH PRIORITY)

#### 1. Fix ETL Logic

**File to Modify**: `src/transformers/state_deriver.py`

**Current Code (WRONG)**:
```python
def derive_professional_status(learner_data: dict) -> str:
    if learner_data.get('is_wage_employed') == 1:
        return 'Wage Employed'
    # ... rest of flag-based logic
```

**Proposed Code (CORRECT)**:
```python
def derive_professional_status(
    learner_data: dict,
    employment_details: List[dict]
) -> str:
    """
    Derive professional status from actual employment records.

    Priority:
    1. Check employment_details for current jobs
    2. Fall back to flags only if no employment_details exist
    """
    # Parse employment details
    if employment_details:
        current_jobs = [job for job in employment_details
                       if job.get('is_current') == '1']

        if len(current_jobs) >= 2:
            return 'Multiple'
        elif len(current_jobs) == 1:
            # Determine type from employment details
            # Could enhance by checking job_title keywords
            return 'Wage Employed'  # Default assumption

    # Fallback to flags (for learners without employment_details)
    if learner_data.get('is_running_a_venture') == 1:
        return 'Entrepreneur'
    elif learner_data.get('is_a_freelancer') == 1:
        return 'Freelancer'
    elif learner_data.get('is_wage_employed') == 1:
        return 'Wage Employed'
    else:
        return 'Unemployed'
```

#### 2. Add Data Quality Validation

**New File**: `src/validators/employment_validator.py`

```python
def validate_employment_consistency(
    learner: Learner,
    employment_relationships: List[WorksForRelationship]
) -> List[str]:
    """
    Validate consistency between professional status and employment.

    Returns list of warnings.
    """
    warnings = []

    current_jobs = [e for e in employment_relationships if e.is_current]

    # Check 1: Unemployed but has current jobs
    if learner.current_professional_status == 'Unemployed' and current_jobs:
        warnings.append(
            f"Status is 'Unemployed' but has {len(current_jobs)} current job(s)"
        )

    # Check 2: Employed but no current jobs
    if learner.current_professional_status in ['Wage Employed', 'Freelancer', 'Multiple']:
        if not current_jobs:
            warnings.append(
                f"Status is '{learner.current_professional_status}' but has no current jobs"
            )

    # Check 3: Multiple current jobs on same date
    if len(current_jobs) > 1:
        start_dates = [e.start_date for e in current_jobs]
        if len(set(start_dates)) < len(start_dates):
            warnings.append(
                f"Multiple current jobs with same start date - possible duplicate"
            )

    return warnings
```

#### 3. Re-run ETL Pipeline

After fixing the logic:

```bash
# 1. Clear existing data
uv run python src/cli.py clear-database --confirm

# 2. Re-run ETL with corrected logic
uv run python src/cli.py run

# 3. Generate data quality report
uv run python src/cli.py validate-data-quality --output data/reports/dq_report.json
```

### Medium-Term Actions

1. **Add Monitoring**:
   - Create scheduled query to detect status/employment mismatches
   - Alert when inconsistency rate exceeds threshold (e.g., >5%)

2. **Update Documentation**:
   - Document that `employment_details` is source of truth
   - Mark flag fields as deprecated/unreliable

3. **Enhance Notebook**:
   - Add data quality checks section
   - Show before/after comparison of status derivation

### Long-Term Actions

1. **Upstream Fix**:
   - Contact data source team
   - Request either:
     - Stop providing unreliable flag fields, OR
     - Fix flag field calculation to match `employment_details`

2. **Full Name Issue**:
   - Investigate why some names are hashes
   - Determine if this is intentional anonymization
   - If yes, update reports to handle anonymized names

---

## Verification Plan

After implementing fixes, verify with these queries:

### Query 1: Check for Remaining Inconsistencies

```cypher
MATCH (l:Learner)-[w:WORKS_FOR]->(c:Company)
WHERE w.isCurrent = true
  AND l.currentProfessionalStatus = 'Unemployed'
RETURN count(DISTINCT l) as remaining_issues
// Expected: 0
```

### Query 2: Verify Status Distribution

```cypher
MATCH (l:Learner)
RETURN l.currentProfessionalStatus as status,
       count(l) as count,
       round(count(l) * 100.0 / 1597167, 2) as percentage
ORDER BY count DESC
```

**Expected Results** (after fix):
- Unemployed: ~1.35M (84-85%) - reduced from 96.1%
- Wage Employed: ~230K (14-15%) - increased from 3.3%
- Multiple: ~5-10K (0.3-0.6%) - new category
- Entrepreneur: ~10K (0.6%) - unchanged

### Query 3: Sample Verification

```cypher
// Re-check our original case study learner
MATCH (l:Learner {hashedEmail: "25d05927de503e5990e9d5bb6f799dd3"})
MATCH (l)-[w:WORKS_FOR]->(c:Company)
WHERE w.isCurrent = true
RETURN l.currentProfessionalStatus, count(w) as current_jobs
// Expected: "Multiple" or "Wage Employed", current_jobs = 2
```

---

## Conclusion

This investigation revealed a **systematic ETL bug** affecting 11.5% of learners (183K+). The root cause is the ETL pipeline's reliance on outdated flag fields instead of the accurate `employment_details` JSON data.

**Impact**:
- 🔴 **High**: Incorrect reporting on employment outcomes
- 🔴 **High**: Misleading program success metrics
- 🟡 **Medium**: Resource misallocation (job assistance for already-employed learners)

**Resolution Path**:
1. ✅ Root cause identified
2. 🔄 ETL logic fix designed (see recommendations)
3. ⏳ Implementation pending
4. ⏳ Validation pending
5. ⏳ Re-run ETL pending

**Estimated Fix Time**: 2-4 hours (code changes + testing + re-ETL)

**Estimated Business Value**: Accurate employment metrics will provide true picture of Impact's program effectiveness and enable better resource allocation.

---

## Appendix A: Test Cases

After implementing fixes, run these tests:

### Test 1: Status Derivation Logic

```python
def test_derive_professional_status_from_employment():
    # Case 1: Has current job
    learner_data = {'is_wage_employed': 0}  # Flag says unemployed
    employment_details = [
        {'is_current': '1', 'organization_name': 'Company A'}
    ]

    status = derive_professional_status(learner_data, employment_details)
    assert status == 'Wage Employed', "Should derive from employment, not flags"

    # Case 2: Multiple current jobs
    employment_details = [
        {'is_current': '1', 'organization_name': 'Company A'},
        {'is_current': '1', 'organization_name': 'Company B'}
    ]

    status = derive_professional_status(learner_data, employment_details)
    assert status == 'Multiple', "Should detect multiple current jobs"

    # Case 3: No employment details - fallback to flags
    status = derive_professional_status({'is_wage_employed': 1}, [])
    assert status == 'Wage Employed', "Should use flags when no employment_details"
```

### Test 2: Consistency Validation

```python
def test_employment_consistency_validation():
    learner = Learner(current_professional_status='Unemployed')
    current_jobs = [
        WorksForRelationship(company_name='Test', is_current=True)
    ]

    warnings = validate_employment_consistency(learner, current_jobs)
    assert len(warnings) > 0, "Should warn about unemployed with current jobs"
    assert 'Unemployed' in warnings[0]
    assert 'current job' in warnings[0].lower()
```

---

## Appendix B: Additional Queries for Analysis

### Find Learners with Most Current Jobs

```cypher
MATCH (l:Learner)-[w:WORKS_FOR]->(c:Company)
WHERE w.isCurrent = true
WITH l, count(w) as job_count, collect(c.name) as companies
WHERE job_count > 1
RETURN l.fullName, l.currentProfessionalStatus, job_count, companies
ORDER BY job_count DESC
LIMIT 20
```

### Employment Rate by Learning State

```cypher
MATCH (l:Learner)
OPTIONAL MATCH (l)-[w:WORKS_FOR]->(c:Company)
WHERE w.isCurrent = true
WITH l.currentLearningState as state,
     count(DISTINCT l) as total_learners,
     count(DISTINCT CASE WHEN w IS NOT NULL THEN l END) as employed_learners
RETURN state,
       total_learners,
       employed_learners,
       round(employed_learners * 100.0 / total_learners, 2) as employment_rate
ORDER BY total_learners DESC
```

### Identify Hash Names

```cypher
MATCH (l:Learner)
WHERE l.fullName =~ '[0-9a-f]{32}'
RETURN count(l) as hash_name_count,
       count(l) * 100.0 / 1597167 as percentage
```

---

**Report Generated**: 2025-01-20
**Next Review Date**: After ETL fix implementation
**Owner**: Data Engineering Team
**Stakeholders**: Analytics Team, Product Team, Executive Leadership
