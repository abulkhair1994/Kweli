# Learner Identity & Multi-Program Enrollment Analysis

**Date:** November 30, 2025
**Dataset:** `impact_learners_profile-1759316791571.csv`
**Purpose:** Clarification request for Engineering Team

---

## Executive Summary

During ETL development, we discovered a critical data modeling question: **How should we uniquely identify a "learner" across multiple program enrollments?**

The current data structure uses `hashed_email` as the row identifier, but analysis reveals that **the same person enrolling in multiple programs appears as separate rows with different `hashed_email` values**.

---

## Key Findings

### 1. Data Structure Overview

| Metric | Value | Notes |
|--------|-------|-------|
| Total Rows | 1,597,198 | Each row = 1 enrollment record |
| Unique `hashed_email` | 1,597,167 | ~1:1 with rows (31 duplicates) |
| Unique `full_name` (hashed) | 1,341,109 | 256K fewer than rows |
| Unique `sand_id` (excl. n/a) | 199,208 | Only 12.5% of rows have this |
| Rows with `sand_id = "n/a"` | 1,397,980 | **87.5% missing** |

### 2. Enrollment Status per Identifier

| Identifier | Enrollment Status Behavior |
|------------|---------------------------|
| `hashed_email` | **Always unique per enrollment** - each row has exactly 1 program with 1 status |
| `full_name` | **Can have multiple statuses** - same person may be "Graduated" in Program A and "Dropped Out" in Program B |
| `sand_id` | When present, appears to be unique per enrollment (no multi-program observed) |

### 3. Multi-Program Learners (Using `full_name` as Person Identifier)

| Category | Count | Percentage |
|----------|-------|------------|
| Single-program learners | 1,239,792 | 92.4% |
| **Multi-program learners** | **101,317** | **7.6%** |

**Breakdown of multi-program learners:**
- Same `full_name`, **different `hashed_email`** for each enrollment: **101,317 (100%)**
- Same `full_name`, same `hashed_email`: **0 (0%)**

### 4. Status Combinations for Multi-Program Learners

| Status Combination | Count | Description |
|-------------------|-------|-------------|
| Dropped Out (all programs) | 46,558 | Person dropped out of multiple programs |
| Dropped Out + Graduated | 33,114 | Person graduated from some, dropped from others |
| Dropped Out + Enrolled | 10,611 | Currently active in some, dropped from others |
| Graduated (all programs) | 4,731 | Person graduated from multiple programs |
| Dropped Out + Enrolled + Graduated | 4,431 | Mixed status across 3+ programs |
| Enrolled + Graduated | 1,564 | Active and graduated programs |
| Enrolled (all programs) | 304 | Active in multiple programs |

### 5. Concurrent Enrollment (Overlapping Dates)

| Metric | Value |
|--------|-------|
| Learners with concurrent enrollment | **31,478** |
| Percentage of all learners | **2.3%** |

**Example:**
```
Learner X (same full_name, different hashed_email):

  Row 1: hashed_email_A
    Program: Udacity
    Period: 2022-04-01 to 2022-08-26
    Status: Graduated

  Row 2: hashed_email_B
    Program: Financial Analyst
    Period: 2022-05-01 to 2022-07-29
    Status: Dropped Out

Timeline:
  Apr 2022 ──── Started Udacity
  May 2022 ──── Started Financial Analyst (CONCURRENT)
  Jul 2022 ──── Ended Financial Analyst (Dropped Out)
  Aug 2022 ──── Ended Udacity (Graduated)
```

---

## The Problem

### Current Data Model Interpretation

If we use `hashed_email` as the learner identifier:
- **1,597,167 unique learners**
- Each enrollment treated as a separate person
- Cannot track learner journeys across programs
- Cannot identify re-enrollment patterns

### Alternative Interpretation (Using `full_name`)

If we use `full_name` as the learner identifier:
- **1,341,109 unique learners**
- 101,317 learners have multiple program enrollments
- Can track complete learner journeys
- **BUT:** Same name ≠ always same person (potential false positives)

### Risk of Using `full_name`

We observed cases where the same `full_name` hash has:
- Different countries of residence
- Different genders (male vs female)

This suggests either:
1. **Hash collisions** (unlikely for MD5)
2. **Common names** hashing to same value
3. **Different people** with identical names

---

## Questions for Engineering Team

### Q1: What is the intended unique identifier for a LEARNER (person)?

- Is `hashed_email` meant to uniquely identify a person?
- Why does the same person use different email addresses for different program enrollments?
- Is there a canonical "person_id" or "user_id" that links all enrollments for the same individual?

### Q2: Why is `sand_id` missing for 87.5% of records?

- What is `sand_id` and when is it populated?
- Can `sand_id` be used as the person identifier when available?
- Is there a plan to backfill `sand_id` for historical records?

### Q3: Is `full_name` reliable for linking enrollments?

- Is `full_name` hashed from the exact same source for all enrollments?
- Should we assume same `full_name` hash = same person?
- How do we handle potential false positives (different people, same name)?

### Q4: What is the expected data model for multi-program learners?

**Option A: One row per enrollment (current structure)**
```
Row 1: email_A → Program 1 → learning_details: [1 entry]
Row 2: email_B → Program 2 → learning_details: [1 entry]
```

**Option B: One row per person with all enrollments**
```
Row 1: person_id → learning_details: [Program 1, Program 2, ...]
```

Which model is correct? If Option A, how should we link enrollments to the same person?

### Q5: How should we calculate "unique learner count"?

For reporting purposes:
- Count of unique `hashed_email`? (1,597,167)
- Count of unique `full_name`? (1,341,109)
- Something else?

---

## Impact on Analytics

| Use Case | Impact if Identity is Wrong |
|----------|----------------------------|
| Unique learner counts | Overcounted by ~256K (19%) |
| Re-enrollment analysis | Cannot identify re-enrollments |
| Learner journey tracking | Fragmented across rows |
| Program completion rates | May count same person multiple times |
| Dropout → Re-enrollment patterns | Invisible |
| Graduate → New program patterns | Invisible |

---

## Recommendation

Until clarified, we propose:

1. **Primary identifier:** Use `hashed_email` (1 row = 1 enrollment = 1 learner node in graph)
2. **Secondary linking:** Create a `PossibleSamePerson` relationship using `full_name` matching
3. **Flag multi-enrollment:** Add property `has_other_enrollments: true` when same `full_name` appears multiple times

This allows us to:
- Maintain data integrity (no false merges)
- Enable future analysis once identity is clarified
- Support both interpretations in queries

---

## Appendix: Data Samples

### Sample Multi-Program Learner (Same `full_name`, Different `hashed_email`)

```
full_name: 4704cc30cb8863356526... (hashed)

Enrollment 1:
  hashed_email: abc123...
  program: ALX Foundations
  status: Graduated
  period: 2023-05-01 to 2023-08-27

Enrollment 2:
  hashed_email: def456...
  program: Software Engineering
  status: Dropped Out
  period: 2023-09-11 to 2024-04-05

Enrollment 3:
  hashed_email: ghi789...
  program: ALX AiCE - AI Career Essentials
  status: Enrolled
  period: 2024-09-16 to 2024-12-03
```

### Status Flag Verification

The `is_graduate_learner`, `is_active_learner`, and `is_a_dropped_out` flags are:
- **Correct per row** (derived from `enrollment_status` in that row's `learning_details`)
- **Not aggregated across programs** (a person could be "Graduate" in one row and "Dropped Out" in another)

---

**Please confirm the correct approach for learner identity resolution.**
