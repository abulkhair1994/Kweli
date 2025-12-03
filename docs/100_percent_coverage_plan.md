# Plan: Achieve 100% Test Coverage for Temporal History Builders

**Date**: November 26, 2025
**Status**: NOT IMPLEMENTED - Plan Only
**Current Coverage**: Learning State (95%), Professional Status (87%)
**Target Coverage**: 100% for both builders

---

## Analysis Summary

### Current Coverage Status

**Learning State History Builder**: 95% coverage
- **Missing 4 lines**: 112, 206, 239, 261
- **File**: `src/transformers/learning_state_history_builder.py`

**Professional Status History Builder**: 87% coverage
- **Missing 10 lines**: 86, 150-160, 165, 179, 233, 386, 388, 391-394
- **File**: `src/transformers/professional_status_history_builder.py`

---

## CSV Data Analysis (10,000 Rows Sampled)

### Key Findings from Real Data

#### Learning State Data
| Enrollment Status | Count | Percentage |
|------------------|-------|------------|
| Dropped Out | 498 | 49.8% |
| Graduated | 452 | 45.2% |
| Enrolled | 50 | 5.0% |
| **Other** | **0** | **0.0%** |

**Insights**:
- Only 3 enrollment status values exist in production data
- Line 206 (unknown status) is **UNREACHABLE** with real data
- Must use **synthetic data** for unknown status testing

#### Professional Status Data
| Flag | Count | Percentage |
|------|-------|------------|
| is_wage_employed=1 | 916 | 9.16% |
| is_running_venture=1 | 119 | 1.19% |
| is_a_freelancer=1 | **0** | **0.00%** |
| Multiple flags | **0** | **0.00%** |

**Insights**:
- Freelancer flag **NEVER SET** (0 in 10,000 rows)
- Multiple employment flags **NEVER CO-OCCUR**
- Lines 386, 391-394 require **synthetic data** for testing

#### Date Sentinel Values
- **1970-01-01**: Invalid date marker → converted to NULL by DateConverter
- **9999-12-31**: Ongoing/current job marker → converted to NULL by DateConverter

---

## Test Cases to Add (10 Total)

### Learning State History Builder (4 New Tests)

#### Test 1: Unknown Enrollment Status (Line 206)
**Coverage Target**: Line 206 - Default to ACTIVE for unknown status

```python
def test_unknown_enrollment_status_defaults_to_active():
    """Test that unknown enrollment status defaults to ACTIVE state."""
    builder = LearningStateHistoryBuilder()
    entries = [
        LearningDetailsEntry(
            index="0",
            program_name="Test Program",
            cohort_code="TEST-2024",
            program_start_date="2024-01-01",
            program_end_date="2024-06-30",
            enrollment_status="Suspended",  # Unknown status (not in real data)
            program_graduation_date="",
            lms_overall_score="75",
            no_of_assignments="10",
            no_of_submissions="8",
            no_of_assignment_passed="7",
            assignment_completion_rate="80",
            no_of_milestone="5",
            no_of_milestone_submitted="4",
            no_of_milestone_passed="3",
            milestone_completion_rate="80",
            no_of_test="3",
            no_of_test_submitted="2",
            no_of_test_passed="2",
            test_completion_rate="67",
            completion_rate="75",
        )
    ]

    history = builder.build_state_history(entries)

    # Should create Active state (default for unknown status)
    assert len(history) == 2  # Active + end state
    assert history[0].state == LearningState.ACTIVE
    assert "Suspended" not in str(history[0].state)
```

**Data Source**: SYNTHETIC (impossible with real data)
**Expected**: State defaults to ACTIVE when status is unknown

---

#### Test 2: Program with No End Date (Line 239)
**Coverage Target**: Line 239 - Return None for ongoing programs

```python
def test_program_ongoing_no_end_date():
    """Test program with no end date (ongoing/current program)."""
    builder = LearningStateHistoryBuilder()
    entries = [
        LearningDetailsEntry(
            index="0",
            program_name="ALX Pathways",
            cohort_code="PATHWAYS-C3",
            program_start_date="2024-09-01",
            program_end_date="",  # No end date - ongoing
            enrollment_status="Enrolled",
            program_graduation_date="",
            lms_overall_score="0",
            no_of_assignments="10",
            no_of_submissions="5",
            no_of_assignment_passed="4",
            assignment_completion_rate="50",
            no_of_milestone="5",
            no_of_milestone_submitted="2",
            no_of_milestone_passed="1",
            milestone_completion_rate="40",
            no_of_test="3",
            no_of_test_submitted="1",
            no_of_test_passed="0",
            test_completion_rate="33",
            completion_rate="40",
        )
    ]

    history = builder.build_state_history(entries)

    # Should create Active state with no end_date (ongoing)
    assert len(history) == 1
    assert history[0].state == LearningState.ACTIVE
    assert history[0].end_date is None  # Line 239 returns None
    assert history[0].is_current is True
```

**Data Source**: REAL-LIKE (1.1% have sentinel dates)
**Expected**: end_date is None for ongoing programs

---

#### Test 3: Enrolled Status Transition (Line 261)
**Coverage Target**: Line 261 - Generic end reason for non-Graduate/Dropped-Out

```python
def test_enrolled_to_enrolled_transition():
    """Test transition between two Enrolled programs."""
    builder = LearningStateHistoryBuilder()
    entries = [
        LearningDetailsEntry(
            index="0",
            program_name="ALX Pathways",
            cohort_code="PATHWAYS-C1",
            program_start_date="2023-01-01",
            program_end_date="2023-06-30",
            enrollment_status="Enrolled",
            program_graduation_date="",
            lms_overall_score="65",
            no_of_assignments="10",
            no_of_submissions="7",
            no_of_assignment_passed="6",
            assignment_completion_rate="70",
            no_of_milestone="5",
            no_of_milestone_submitted="3",
            no_of_milestone_passed="2",
            milestone_completion_rate="60",
            no_of_test="3",
            no_of_test_submitted="2",
            no_of_test_passed="1",
            test_completion_rate="67",
            completion_rate="65",
        ),
        LearningDetailsEntry(
            index="1",
            program_name="ALX Foundations",
            cohort_code="FOUNDATIONS-C2",
            program_start_date="2023-07-01",
            program_end_date="2023-12-31",
            enrollment_status="Enrolled",
            program_graduation_date="",
            lms_overall_score="70",
            no_of_assignments="10",
            no_of_submissions="8",
            no_of_assignment_passed="7",
            assignment_completion_rate="80",
            no_of_milestone="5",
            no_of_milestone_submitted="4",
            no_of_milestone_passed="3",
            milestone_completion_rate="80",
            no_of_test="3",
            no_of_test_submitted="2",
            no_of_test_passed="2",
            test_completion_rate="67",
            completion_rate="70",
        ),
    ]

    history = builder.build_state_history(entries)

    # Should create Active states for both programs
    assert len(history) == 2
    assert all(state.state == LearningState.ACTIVE for state in history)
    # First program should use line 261 for end reason (generic)
    assert "Status change" in history[0].reason or "Enrolled" in history[0].reason
```

**Data Source**: REAL (5% of programs are Enrolled)
**Expected**: Generic end reason used for Enrolled transitions

---

#### Test 4: All Programs Invalid Dates (Line 112)
**Coverage Target**: Line 112 - Early return when all dates invalid

```python
def test_all_programs_invalid_dates():
    """Test when all programs have invalid sentinel dates."""
    builder = LearningStateHistoryBuilder()
    entries = [
        LearningDetailsEntry(
            index="0",
            program_name="Bad Program 1",
            cohort_code="BAD-1",
            program_start_date="1970-01-01",  # Sentinel - converted to NULL
            program_end_date="1970-01-01",
            enrollment_status="Dropped Out",
            program_graduation_date="1970-01-01",
            lms_overall_score="0",
            no_of_assignments="0",
            no_of_submissions="0",
            no_of_assignment_passed="0",
            assignment_completion_rate="0",
            no_of_milestone="0",
            no_of_milestone_submitted="0",
            no_of_milestone_passed="0",
            milestone_completion_rate="0",
            no_of_test="0",
            no_of_test_submitted="0",
            no_of_test_passed="0",
            test_completion_rate="0",
            completion_rate="0",
        ),
        LearningDetailsEntry(
            index="1",
            program_name="Bad Program 2",
            cohort_code="BAD-2",
            program_start_date="invalid-date",  # Invalid
            program_end_date="2024-12-31",
            enrollment_status="Enrolled",
            program_graduation_date="",
            lms_overall_score="0",
            no_of_assignments="0",
            no_of_submissions="0",
            no_of_assignment_passed="0",
            assignment_completion_rate="0",
            no_of_milestone="0",
            no_of_milestone_submitted="0",
            no_of_milestone_passed="0",
            milestone_completion_rate="0",
            no_of_test="0",
            no_of_test_submitted="0",
            no_of_test_passed="0",
            test_completion_rate="0",
            completion_rate="0",
        ),
    ]

    history = builder.build_state_history(entries)

    # No valid dates found - should return empty list
    assert history == []  # Line 112 returns empty
```

**Data Source**: REAL (1.1% have sentinel dates)
**Expected**: Returns empty list when all dates invalid

---

### Professional Status History Builder (6 New Tests)

#### Test 5: All Jobs Invalid Dates (Line 86)
**Coverage Target**: Line 86 - Return unemployed when no valid employment dates

```python
def test_all_jobs_invalid_dates():
    """Test when all employment entries have invalid dates."""
    builder = ProfessionalStatusHistoryBuilder(infer_initial_unemployment=False)
    entries = [
        EmploymentDetailsEntry(
            index="0",
            organization_name="Bad Company",
            start_date="1970-01-01",  # Sentinel - converted to NULL
            end_date="2024-12-31",
            country="Egypt",
            job_title="Engineer",
            is_current="0",
            duration_in_years="1.0",
        ),
        EmploymentDetailsEntry(
            index="1",
            organization_name="Another Bad Company",
            start_date="invalid-date",  # Invalid
            end_date="2024-06-30",
            country="Kenya",
            job_title="Developer",
            is_current="0",
            duration_in_years="0.5",
        ),
    ]

    history = builder.build_status_history(entries)

    # No valid dates - should return empty list (line 86)
    assert history == []
```

**Data Source**: REAL-LIKE (1970-01-01 is common sentinel)
**Expected**: Returns empty list when no valid dates

---

#### Test 6: Job Ended + Current Employment Flags (Lines 150-160)
**Coverage Target**: Lines 150-160 - Handle job ended but flags show employed

```python
def test_job_ended_but_flags_show_employed():
    """Test job ended but current flags indicate new employment (via placement)."""
    builder = ProfessionalStatusHistoryBuilder()
    entries = [
        EmploymentDetailsEntry(
            index="0",
            organization_name="Old Company",
            start_date="2023-01-01",
            end_date="2023-12-31",  # Job actually ended
            country="Egypt",
            job_title="Software Engineer",
            is_current="0",
            duration_in_years="1.0",
        )
    ]

    # Flags show currently employed (new job via placement, not in employment_details yet)
    current_status_flags = {
        "is_wage": True,
        "is_venture": False,
        "is_freelancer": False,
    }

    history = builder.build_status_history(
        entries,
        current_status_flags=current_status_flags,
    )

    # Should create: Unemployed → Wage(Old) → Wage(New from flags)
    assert len(history) == 3
    assert history[0].status == ProfessionalStatus.UNEMPLOYED
    assert history[1].status == ProfessionalStatus.WAGE_EMPLOYED
    assert history[1].end_date == date(2023, 12, 31)  # Old job closed (line 150-151)
    assert history[2].status == ProfessionalStatus.WAGE_EMPLOYED
    assert history[2].is_current is True
    assert "placement/flags" in history[2].details  # Line 160
```

**Data Source**: REALISTIC (placement creates new jobs not yet in employment_details)
**Expected**: Creates unemployed gap, then new employment from flags

---

#### Test 7: Job Ended + No Current Flags (Line 179)
**Coverage Target**: Line 179 - Close last job when no flags provided

```python
def test_job_ended_no_current_flags():
    """Test job ended with no current status flags provided."""
    builder = ProfessionalStatusHistoryBuilder()
    entries = [
        EmploymentDetailsEntry(
            index="0",
            organization_name="Past Company",
            start_date="2022-06-01",
            end_date="2023-05-31",
            country="Nigeria",
            job_title="Data Analyst",
            is_current="0",
            duration_in_years="1.0",
        )
    ]

    # No current flags provided
    history = builder.build_status_history(
        entries,
        current_status_flags=None,  # No flags
    )

    # Should create: Unemployed → Wage → Unemployed
    assert len(history) == 3
    assert history[0].status == ProfessionalStatus.UNEMPLOYED
    assert history[1].status == ProfessionalStatus.WAGE_EMPLOYED
    assert history[1].end_date == date(2023, 5, 31)  # Line 179 closes last job
    assert history[2].status == ProfessionalStatus.UNEMPLOYED
    assert history[2].is_current is True
```

**Data Source**: REALISTIC (learners without current employment)
**Expected**: Closes last job, creates final unemployed status

---

#### Test 8: Auto-Correct is_current Flag (Line 233)
**Coverage Target**: Line 233 - Auto-correct is_current when end_date exists

```python
def test_job_with_end_date_auto_corrects_is_current():
    """Test that jobs with end_date have is_current auto-corrected to False."""
    builder = ProfessionalStatusHistoryBuilder()
    entries = [
        EmploymentDetailsEntry(
            index="0",
            organization_name="Company",
            start_date="2023-01-01",
            end_date="2023-12-31",  # Real end date (not sentinel)
            country="Egypt",
            job_title="Engineer",
            is_current="1",  # WRONG! Should be 0
            duration_in_years="1.0",
        )
    ]

    history = builder.build_status_history(entries)

    # is_current should be auto-corrected to False (line 233)
    assert len(history) >= 2
    employment_status = history[1]  # Skip initial unemployed
    assert employment_status.status == ProfessionalStatus.WAGE_EMPLOYED
    assert employment_status.is_current is False  # Auto-corrected
    assert employment_status.end_date == date(2023, 12, 31)
```

**Data Source**: REALISTIC (data quality issue in CSV)
**Expected**: Auto-corrects is_current to False when end_date exists

---

#### Test 9: Multiple Employment Flags (Line 386)
**Coverage Target**: Line 386 - Return MULTIPLE when 2+ flags set

```python
def test_multiple_employment_flags():
    """Test multiple employment flags set simultaneously (MULTIPLE status)."""
    builder = ProfessionalStatusHistoryBuilder()
    entries = [
        EmploymentDetailsEntry(
            index="0",
            organization_name="Multi Company",
            start_date="2023-01-01",
            end_date="2023-12-31",
            country="Kenya",
            job_title="Multi-role",
            is_current="0",
            duration_in_years="1.0",
        )
    ]

    # SYNTHETIC: Multiple flags set (never happens in real data)
    current_status_flags = {
        "is_wage": True,
        "is_venture": True,
        "is_freelancer": False,
    }

    history = builder.build_status_history(
        entries,
        current_status_flags=current_status_flags,
    )

    # Last status should be MULTIPLE (line 386)
    assert history[-1].status == ProfessionalStatus.MULTIPLE
    assert history[-1].is_current is True
```

**Data Source**: SYNTHETIC (never occurs in real data - 0 in 10,000 rows)
**Expected**: Returns MULTIPLE when 2+ flags are True

---

#### Test 10: Freelancer Flag (Line 391)
**Coverage Target**: Line 391 - Return FREELANCER when flag set

```python
def test_freelancer_flag_from_current_status():
    """Test freelancer status from current flags (never in real data)."""
    builder = ProfessionalStatusHistoryBuilder()
    entries = []  # No employment history

    # SYNTHETIC: Freelancer flag set (NEVER happens in real data - 0 in 10,000 rows)
    current_status_flags = {
        "is_wage": False,
        "is_venture": False,
        "is_freelancer": True,
    }

    history = builder.build_status_history(
        entries,
        current_status_flags=current_status_flags,
    )

    # Should return freelancer status (line 391)
    assert len(history) == 1
    assert history[0].status == ProfessionalStatus.FREELANCER  # Line 391
    assert history[0].is_current is True
```

**Data Source**: SYNTHETIC (impossible with real data - flag never set)
**Expected**: Returns FREELANCER when flag is True

---

## Implementation Steps

### Step 1: Add Tests to test_transformers.py
1. Add 4 tests to `TestLearningStateHistoryBuilder` class
2. Add 6 tests to `TestProfessionalStatusHistoryBuilder` class
3. Total: ~350 lines of test code

### Step 2: Verify Coverage
```bash
# Test learning state builder
uv run pytest tests/unit/test_transformers.py::TestLearningStateHistoryBuilder -v \
  --cov=src/transformers/learning_state_history_builder.py --cov-report=term-missing

# Test professional status builder
uv run pytest tests/unit/test_transformers.py::TestProfessionalStatusHistoryBuilder -v \
  --cov=src/transformers/professional_status_history_builder.py --cov-report=term-missing
```

### Step 3: Run All Tests
```bash
uv run pytest tests/unit/test_transformers.py -v
```

### Step 4: Code Quality
```bash
uv run ruff check --fix
```

---

## Expected Outcome

| Metric | Before | After |
|--------|--------|-------|
| Learning State Coverage | 95% | **100%** |
| Professional Status Coverage | 87% | **100%** |
| Total Tests | 18 | **28** |
| Lines Covered | All main paths | **All paths** |
| Test Lines Added | 0 | **~350** |

---

## Data-Driven Insights

### Tests Using Real Data Patterns
- Test 2: Ongoing programs (1.1% in real data)
- Test 3: Enrolled transitions (5% in real data)
- Test 4: Sentinel dates (1.1% in real data)
- Test 6: Job ended + flags (realistic placement scenario)
- Test 7: Job ended + no flags (realistic unemployment)
- Test 8: Data quality issue (is_current mismatch)

### Tests Using Synthetic Data (Impossible Scenarios)
- Test 1: Unknown enrollment status (0% in real data)
- Test 9: Multiple employment flags (0% in real data)
- Test 10: Freelancer flag (0% in real data - NEVER SET)

---

## Notes

1. **Synthetic Data Justification**: Some code paths are defensive and never execute with real data but are important for robustness
2. **Coverage vs. Value**: Tests 9 and 10 cover code that may never execute in production but validate defensive programming
3. **Real Data Analysis**: Based on 10,000 row sample from 1.7M row CSV
4. **Sentinel Values**: 1970-01-01 and 9999-12-31 are automatically converted to NULL by DateConverter

---

## Status: PLAN ONLY - NOT IMPLEMENTED

This document serves as a comprehensive plan for achieving 100% test coverage. Implementation should be done when needed.

**To implement**: Copy test cases from this document to `tests/unit/test_transformers.py`
