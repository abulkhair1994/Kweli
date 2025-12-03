# Comprehensive Analysis Report: `learning_details` Field

**Analysis Date:** November 27, 2025
**Dataset:** `impact_learners_profile-1759316791571.csv`
**Total Learners:** 1,597,198

---

## 1. Flag Calculation Logic: VERIFIED CORRECT

The data team's SQL logic for calculating the three learner status flags has been **100% verified** against the actual data:

```sql
max(case when lower(enrollment_status) = 'graduated' then 1 else 0 end)    as is_graduate_learner
max(case when lower(enrollment_status) = 'enrolled' then 1 else 0 end)     as is_active_learner
max(case when lower(enrollment_status) in ('dropped out') then 1 else 0 end) as is_a_dropped_out
```

### Verification Results

| Flag | Match Rate | Matches | Total |
|------|------------|---------|-------|
| `is_graduate_learner` | **100.0000%** | 1,597,198 | 1,597,198 |
| `is_active_learner` | **100.0000%** | 1,597,198 | 1,597,198 |
| `is_a_dropped_out` | **100.0000%** | 1,597,198 | 1,597,198 |

The flags are **mutually exclusive** (only one can be 1 per learner), and the sum of all flags equals the total number of learners.

---

## 2. `learning_details` Structure

Each learner has **exactly 1 program** in their `learning_details` array (100% of learners have `index: "1"` only).

### Sample Structure

```json
{
  "index": "1",
  "program_name": "Virtual Assistant",
  "cohort_code": "VA-C4",
  "program_start_date": "2024-07-01",
  "program_end_date": "2024-09-03",
  "enrollment_status": "Graduated",
  "program_graduation_date": "2024-09-03",
  "lms_overall_score": "93.64",
  "no_of_assignments": "15",
  "no_of_submissions": "15",
  "no_of_assignment_passed": "15",
  "assignment_completion_rate": "100",
  "no_of_milestone": "7",
  "no_of_milestone_submitted": "7",
  "no_of_milestone_passed": "7",
  "milestone_completion_rate": "100",
  "no_of_test": "8",
  "no_of_test_submitted": "8",
  "no_of_test_passed": "8",
  "test_completion_rate": "100",
  "completion_rate": "1"
}
```

### All 21 Fields in `learning_details`

| Field | Valid % | Missing % | Null Indicator (-99/1970) % | Description |
|-------|---------|-----------|----------------------------|-------------|
| `index` | 100% | 0% | 0% | Always "1" |
| `program_name` | 100% | 0% | 0% | 26 unique programs |
| `cohort_code` | 100% | 0% | 0% | 121 unique cohorts |
| `enrollment_status` | 100% | 0% | 0% | **Key field for flags** |
| `program_start_date` | 98.61% | 0% | 1.39% | 80 unique dates |
| `program_end_date` | 98.61% | 0% | 1.39% | 118 unique dates |
| `program_graduation_date` | 16.22% | 0% | 83.78% | Only for graduates |
| `lms_overall_score` | 59.27% | 0% | 40.73% | 0-100 scale |
| `completion_rate` | 59.58% | 0% | 40.42% | Only 0 or 1 |
| `no_of_assignments` | 59.61% | 0% | 40.39% | Assignment count |
| `no_of_submissions` | 59.61% | 0% | 40.39% | Submission count |
| `no_of_assignment_passed` | 49.04% | 0% | 50.96% | Passed count |
| `assignment_completion_rate` | 59.61% | 0% | 40.39% | 0-100% |
| `no_of_milestone` | 59.27% | 0% | 40.73% | Milestone count |
| `no_of_milestone_submitted` | 59.27% | 0% | 40.73% | Submitted count |
| `no_of_milestone_passed` | 59.27% | 0% | 40.73% | Passed count |
| `milestone_completion_rate` | 59.58% | 0% | 40.42% | 0-100% |
| `no_of_test` | 59.27% | 0% | 40.73% | Test count |
| `no_of_test_submitted` | 59.27% | 0% | 40.73% | Submitted count |
| `no_of_test_passed` | 59.27% | 0% | 40.73% | Passed count |
| `test_completion_rate` | 59.58% | 0% | 40.42% | 0-100% |

---

## 3. `enrollment_status` Values (The Flag Source)

| Status | Count | Percentage | Case Sensitivity Note |
|--------|-------|------------|----------------------|
| `"Dropped Out"` | 1,240,293 | 77.65% | Capital O |
| `"Graduated"` | 259,153 | 16.23% | |
| `"Enrolled"` | 97,551 | 6.11% | |
| `"Dropped out"` | 201 | 0.01% | **Lowercase o** |

### Important: Case Sensitivity

There are **TWO spellings** of "Dropped Out" in the data:
- `"Dropped Out"` (1,240,293 records) - capital O
- `"Dropped out"` (201 records) - lowercase o

The SQL correctly uses `lower()` to handle both variants, ensuring all 1,240,494 dropped out learners are captured.

---

## 4. Flag Cross-Tabulation

| enrollment_status | is_grad=1 | is_grad=0 | is_active=1 | is_active=0 | is_dropped=1 | is_dropped=0 |
|-------------------|-----------|-----------|-------------|-------------|--------------|--------------|
| dropped out | 0 | 1,240,494 | 0 | 1,240,494 | **1,240,494** | 0 |
| enrolled | 0 | 97,551 | **97,551** | 0 | 0 | 97,551 |
| graduated | **259,153** | 0 | 0 | 259,153 | 0 | 259,153 |

**Perfect 1:1 mapping confirmed!**

### Flag Distribution Summary

| Flag | Count | Percentage |
|------|-------|------------|
| `is_graduate_learner = 1` | 259,153 | 16.23% |
| `is_active_learner = 1` | 97,551 | 6.11% |
| `is_a_dropped_out = 1` | 1,240,494 | 77.67% |
| **Total** | **1,597,198** | **100%** |

### Mutual Exclusivity Check

| Combination | Count |
|-------------|-------|
| Graduate AND Active | 0 |
| Graduate AND Dropped | 0 |
| Active AND Dropped | 0 |
| All three flags = 1 | 0 |
| All flags = 0 | 0 |

**Flags are perfectly mutually exclusive.**

---

## 5. Program Distribution

### Top 10 Programs

| Program | Count | Percentage |
|---------|-------|------------|
| Software Engineering | 467,697 | 29.28% |
| ALX AiCE - AI Career Essentials | 449,135 | 28.12% |
| Virtual Assistant | 323,220 | 20.24% |
| ALX Foundations | 194,584 | 12.18% |
| Financial Analyst | 46,133 | 2.89% |
| ALX Pathways | 38,113 | 2.39% |
| AI Career Essentials | 21,118 | 1.32% |
| Founder Academy | 19,413 | 1.22% |
| Udacity | 15,429 | 0.97% |
| ALX AI Starter Kit | 6,166 | 0.39% |

### All 26 Unique Programs

1. Software Engineering
2. ALX AiCE - AI Career Essentials
3. Virtual Assistant
4. ALX Foundations
5. Financial Analyst
6. ALX Pathways
7. AI Career Essentials
8. Founder Academy
9. Udacity
10. ALX AI Starter Kit
11. Freelancer Academy - 2-week
12. Founder Academy - 4-week
13. Data Analytics
14. Data Scientist
15. Introduction to Software Engineering
16. Back-End Web Development
17. Young Entrepreneurs Program
18. Front-End Web Development
19. Data Engineering
20. AWS Cloud Practitioner
21. Salesforce Administrator
22. AI for Developers I
23. AWS Solutions Architect
24. n/a
25. Salesforce Associate
26. Front End ProDev

---

## 6. Top 20 Cohorts

| Cohort Code | Count | Percentage |
|-------------|-------|------------|
| AiCE-C3 | 143,842 | 9.01% |
| AiCE-C4 | 102,290 | 6.40% |
| AiCE-C2 | 91,106 | 5.70% |
| VA-C6 | 83,803 | 5.25% |
| SE-C13 | 73,902 | 4.63% |
| SE-C12 | 71,920 | 4.50% |
| VA-C5 | 50,817 | 3.18% |
| SE-C9 | 46,680 | 2.92% |
| VA-C4 | 40,186 | 2.52% |
| FOUNDATIONS-C10 | 38,830 | 2.43% |
| SE-C16 | 34,220 | 2.14% |
| SE-C11 | 33,435 | 2.09% |
| FOUNDATIONS-C9 | 32,779 | 2.05% |
| SE-C17 | 29,129 | 1.82% |
| AiCE-C7 | 27,410 | 1.72% |
| FOUNDATIONS-C1 | 25,658 | 1.61% |
| AiCE-C5 | 25,142 | 1.57% |
| SE-C8 | 23,781 | 1.49% |
| VA-C2 | 23,220 | 1.45% |
| SE-C18 | 22,713 | 1.42% |

**Total unique cohorts: 121**

---

## 7. Data Quality Findings

### Temporal Consistency Issues

| Issue | Count | Severity |
|-------|-------|----------|
| End date before start date | 1 | Low |
| Graduation date before program start | 29 | Low |
| Graduation date after program end | 21,123 | Medium |
| Graduated but missing graduation date | 349 | Low |
| Not graduated but has graduation date | 228 | Low |

### `completion_rate` by Enrollment Status

| Status | completion=1 | completion=0 | completion=-99 |
|--------|--------------|--------------|----------------|
| **Graduated** | 182,650 (70.5%) | 11,205 (4.3%) | 65,298 (25.2%) |
| Enrolled | 2,230 (2.3%) | 95,320 (97.7%) | 1 (0.0%) |
| Dropped Out | 5,604 (0.5%) | 654,558 (52.8%) | 580,332 (46.8%) |

**Key Insight:** `completion_rate = 1` strongly correlates with `Graduated` status (70.5% of graduates have completion=1).

### Score Patterns

| Pattern | Count |
|---------|-------|
| Perfect score (lms_overall_score = 100) | 2,927 |
| Zero score (lms_overall_score = 0) | 628,167 |
| All LMS fields = -99 (no data) | 645,036 |

---

## 8. Special Values Explained

| Value | Meaning | Where Used |
|-------|---------|------------|
| `-99` | Missing/NULL data | All numeric LMS fields |
| `1970-01-01` | Invalid/missing date | Date fields |
| `0` | Zero/not completed | Scores, counts |
| `1` | Completed | `completion_rate` only |

### Why `-99` is Used

The value `-99` serves as a sentinel/placeholder for missing numeric data. This is common in data warehousing when:
- The source system didn't capture the data
- The learner didn't interact with the LMS
- The program doesn't track that metric

### Why `1970-01-01` is Used

The Unix epoch date `1970-01-01` indicates:
- Missing or invalid date values
- Dates that couldn't be parsed from source systems
- Placeholder for NULL dates in systems that don't support NULL

---

## 9. Summary

### Flag Calculation Logic: CONFIRMED

The three flags (`is_graduate_learner`, `is_active_learner`, `is_a_dropped_out`) are derived directly from the `enrollment_status` field inside `learning_details` using case-insensitive matching:

```
enrollment_status = 'Graduated'                    → is_graduate_learner = 1
enrollment_status = 'Enrolled'                     → is_active_learner = 1
enrollment_status = 'Dropped Out' OR 'Dropped out' → is_a_dropped_out = 1
```

### Key Statistics

- **Total Learners:** 1,597,198
- **Graduates:** 259,153 (16.23%)
- **Active/Enrolled:** 97,551 (6.11%)
- **Dropped Out:** 1,240,494 (77.67%)
- **Programs per Learner:** Exactly 1
- **Unique Programs:** 26
- **Unique Cohorts:** 121

### Data Completeness

- **Core fields** (program_name, cohort_code, enrollment_status): 100% complete
- **Date fields** (start/end): ~98.6% complete
- **LMS metrics**: ~59% complete (40% have -99 placeholder)
- **Graduation date**: Only populated for graduates (~16%)

---

## Appendix: Field Value Distributions

### `completion_rate` Values

| Value | Count | Percentage |
|-------|-------|------------|
| 0 | 761,083 | 47.65% |
| 1 | 190,484 | 11.93% |
| -99 | 645,631 | 40.42% |

### `lms_overall_score` Distribution

- Range: 0 to 100
- Unique values: 9,499
- Most common: 0 (39.33%), followed by scores in the 96-99 range for graduates
- Missing (-99): 40.73%
