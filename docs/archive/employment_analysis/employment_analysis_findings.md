# Employment Analysis: `is_wage_employed` vs `employment_details`

**Analysis Date:** October 5, 2025
**Dataset:** impact_learners_profile-1759316791571.csv
**File Size:** 2.5 GB
**Total Records:** 1,597,198

---

## Executive Summary

Analysis reveals that the employment-related columns are **functioning correctly**. The `has_employment_details` flag accurately reflects whether employment data exists (distinguishing between empty array `"[]"` and actual job records). The relationship between `is_wage_employed` and `employment_details` shows clear patterns indicating that only 3.32% of learners are in traditional wage employment.

---

## ✓ CLARIFICATION: has_employment_details Flag is CORRECT

**The `has_employment_details` flag works as intended:**
- **`has_employment_details=0` correctly indicates `employment_details="[]"` (empty JSON array)**
- **`has_employment_details=1` correctly indicates actual employment records exist**
- **The flag accurately distinguishes between "no employment data" vs "has employment history"**

This flag is **RELIABLE** and can be used for filtering and analysis.

---

## Key Findings

### 1. Overall Distribution

| `is_wage_employed` | Count | Percentage |
|-------------------|-------|------------|
| 0 (Not employed) | 1,544,249 | 96.68% |
| 1 (Wage employed) | 52,949 | 3.32% |

### 2. Empty Employment Details Pattern

- **1,309,213 records (81.97%)** have empty employment details `"[]"` (no employment history)
- **287,985 records (18.03%)** have actual employment data
- Distribution of empty records:
  - 99.33% → `is_wage_employed = 0` ✓ (consistent)
  - 0.67% → `is_wage_employed = 1` (8,747 records - may be recently employed)

**Interpretation:** Empty employment details strongly correlate with not being wage employed, which is logically consistent. Most learners (82%) have no employment history on record.

### 3. Key Patterns Identified

#### Pattern #1: Employment History Does Not Guarantee Wage Employment
Many records have detailed employment histories but are marked as NOT wage employed (84.65% of those with employment data):

- 152 records: "Virtual Assistant at alx_africa" → `is_wage_employed = 0`
- 76 records: Extensive academic career (10 positions at University of Pretoria/ExploreAI) → `is_wage_employed = 0`
- 41 records: CEO positions at multiple companies → `is_wage_employed = 0`
- 45 records: "Software Engineer at alx_africa" → `is_wage_employed = 0`

**Likely explanation:** These individuals may be self-employed, freelancers, or no longer in wage employment despite having past employment history.

#### Pattern #2: Recently Employed Without Historical Records
- 8,747 records (16.52% of wage employed) have `is_wage_employed = 1` but empty `employment_details = "[]"`

**Likely explanation:** These individuals may have recently started wage employment but haven't updated their employment history, or their employment details haven't been synced yet.

### 4. Data Diversity

- **Unique employment_details values:** 273,067
- **No NULL values** in either column (0.00%)

---

## Relationship Analysis

### Expected vs Actual Behavior

| Scenario | `is_wage_employed` Distribution | Interpretation |
|----------|-------------------------------|----------------|
| Empty `employment_details = "[]"` | 99.33% → 0, 0.67% → 1 | ✓ Mostly consistent |
| Has employment history | 84.65% → 0, 15.35% → 1 | ✓ Past employment ≠ current wage employment |
| Wage employed (is_wage_employed=1) | 83.48% have employment data | ✓ Mostly consistent |

---

## Possible Explanations

1. **Self-Employment vs Wage Employment**
   The flag may distinguish between:
   - Wage employed (traditional employment)
   - Self-employed/freelancers/contractors (marked as 0)

2. **Current vs Historical Employment**
   `is_wage_employed` might only reflect **current** employment status, not historical records

3. **Data Maintenance Issues**
   The `is_wage_employed` flag may not be consistently updated when employment details change

4. **Different Data Sources**
   The two fields might be populated from different sources with different update schedules

---

## Recommendations

### Data Understanding
1. **Document Field Definitions**
   - Clearly define "wage employed" vs self-employed vs unemployed
   - Document that `is_wage_employed` likely refers to **current** wage employment status
   - Note that `has_employment_details` correctly distinguishes `"[]"` from actual data

2. **Usage Guidelines**
   - `has_employment_details`: Use to filter for learners with any employment history
   - `is_wage_employed`: Use to identify currently wage-employed learners (only 3.32%)
   - `employment_details`: Use for detailed employment analysis

### Data Quality Improvements
3. **Address Edge Cases**
   - Investigate the 8,747 learners marked as wage employed without employment details
   - Consider prompting these users to update their employment history
   - Review records with extensive employment history but `is_wage_employed=0` to understand employment type

4. **Additional Flags** (Optional Enhancement)
   - Consider adding `employment_type` (wage/self-employed/freelance/student/unemployed)
   - Consider adding `is_currently_employed` (any employment) vs `is_wage_employed` (traditional employment)
   - Consider adding `last_employment_update_date` for data freshness tracking

### Monitoring
5. **Track Key Metrics Over Time**
   - Monitor wage employment rate (currently 3.32%)
   - Track employment history completion rate (currently 18.03%)
   - Alert on significant changes in these ratios

---

## Statistical Summary

| Metric | Value |
|--------|-------|
| Total rows analyzed | 1,597,198 |
| Unique `is_wage_employed` values | 2 (0, 1) |
| Unique `has_employment_details` values | 2 (0, 1) |
| Unique `employment_details` values | 273,067 |
| Records with "[]" employment_details | 1,309,213 (81.97%) |
| NULL values in any field | 0 (0.00%) |

---

## Three-Way Relationship Analysis

### has_employment_details Distribution
| Value | Count | Percentage |
|-------|-------|------------|
| 0 (No details) | 1,309,213 | 81.97% |
| 1 (Has details) | 287,985 | 18.03% |

### Three-Way Combinations
| has_employment_details | is_wage_employed | employment_details | Count | % | Interpretation |
|----------------------|------------------|-------------------|-------|---|--------|
| 0 | 0 | `"[]"` (empty) | 1,300,466 | 81.42% | ✓ No history, not employed |
| 1 | 0 | actual data | 243,783 | 15.26% | ✓ Has history, not currently wage employed |
| 1 | 1 | actual data | 44,202 | 2.77% | ✓ Has history, currently wage employed |
| 0 | 1 | `"[]"` (empty) | 8,747 | 0.55% | ⚠️ Wage employed but no history recorded |

### Key Observations

**When `has_employment_details = 0` (no employment history):**
- 99.33% have `is_wage_employed = 0` (not wage employed) ✓
- 0.67% have `is_wage_employed = 1` (wage employed but no history) ⚠️
- **100% have `employment_details = "[]"` (empty array)** ✓

**When `has_employment_details = 1` (has employment history):**
- 84.65% have `is_wage_employed = 0` (not currently wage employed) ✓
- 15.35% have `is_wage_employed = 1` (currently wage employed) ✓
- **100% have actual employment data** ✓

**When `is_wage_employed = 0` (not wage employed):**
- 84.21% have `has_employment_details = 0` (no history) ✓
- 15.79% have `has_employment_details = 1` (has history but not wage employed) ✓

**When `is_wage_employed = 1` (wage employed):**
- 16.52% have `has_employment_details = 0` (no history recorded yet) ⚠️
- 83.48% have `has_employment_details = 1` (has history) ✓

---

## Sample Cases

### Common Scenarios (All Logically Consistent)
- **No history, not employed:** 1,300,466 records (81.42%) ✓ Most common - learners with no employment history
- **Has history, not wage employed:** 243,783 records (15.26%) ✓ Self-employed, freelancers, or previously employed
- **Has history, wage employed:** 44,202 records (2.77%) ✓ Currently in traditional wage employment
- **No history, wage employed:** 8,747 records (0.55%) ⚠️ Edge case - recently employed, history not updated

---

## Summary of Findings

### What the Data Tells Us

1. **`has_employment_details` is RELIABLE** ✓
   - Accurately distinguishes between `"[]"` (no data) and actual employment records
   - Can be safely used for filtering learners with employment history
   - Works as intended

2. **`is_wage_employed` shows clear patterns:**
   - Only 3.32% of learners are currently in wage employment
   - 96.68% are not wage employed (may include self-employed, unemployed, students, or past employees)
   - When people ARE wage employed, 83.48% have employment history recorded

3. **`employment_details` field:**
   - 81.97% have the empty array value `"[]"` (no employment history)
   - 18.03% have actual employment history data
   - 273,067 unique employment histories recorded

4. **The correlation pattern reveals important insights:**
   - Empty employment details `"[]"` → Almost always not wage employed (99.33%) ✓
   - Has employment data → Still mostly not wage employed (84.65%)
   - **Key insight:** `is_wage_employed` specifically means "**currently** in traditional wage employment" NOT just "has employment history"
   - Having employment history does not mean currently employed (could be past jobs, self-employment, etc.)

### Data Quality Score

| Field | Accuracy | Reliability | Recommendation |
|-------|----------|-------------|----------------|
| `employment_details` | High | ✓ Reliable | Use for detailed employment analysis |
| `is_wage_employed` | High | ✓ Reliable | Use for current wage employment status |
| `has_employment_details` | **High** | ✓ **Reliable** | **Use for filtering by employment history** |

### Edge Case to Monitor

- **8,747 records (0.55%)** are marked as `is_wage_employed=1` but have no employment history (`"[]"`)
- This represents recently employed individuals who haven't updated their profile
- Recommend prompting these users to add employment details

---

*Analysis performed using chunked processing (100,000 rows/chunk) to handle the 2.5 GB dataset efficiently.*
*Three-way relationship analysis completed between `has_employment_details`, `is_wage_employed`, and `employment_details`.*
