# Education Details Field Analysis

**Date:** December 1, 2025
**Dataset:** `impact_learners_profile-1759316791571.csv`
**Field Analyzed:** `education_details`

---

## Executive Summary

The `education_details` field contains JSON arrays with formal education history for learners. Only **6.29%** of learners (100,446 out of 1,597,198) have populated education details, while 93.71% have empty arrays. The data covers **28,595 unique institutions** across primarily African countries, with Nigerian and Kenyan universities being the most represented.

---

## Coverage Statistics

| Metric | Value | Percentage |
|--------|-------|------------|
| Total rows in dataset | 1,597,198 | 100.00% |
| Empty education_details (`"[]"`) | 1,496,752 | 93.71% |
| **With education data** | **100,446** | **6.29%** |
| Total education entries | 125,868 | - |
| Avg entries per learner | 1.25 | - |

### `has_education_details` Flag Accuracy

| Flag Value | Actual Data | Count |
|------------|-------------|-------|
| 0 | Empty `"[]"` | 1,496,752 |
| 1 | Has data | 100,446 |

**Finding:** The `has_education_details` flag is **100% accurate** - it perfectly matches whether actual data exists.

---

## JSON Schema

Each education entry contains 7 fields:

```json
{
  "index": "1",
  "institution_name": "University of Ghana",
  "start_date": "2016-09-01",
  "end_date": "2020-07-01",
  "field_of_study": "Business and Economics...",
  "level_of_study": "Bachelor's degree",
  "graduated": "1"
}
```

| Field | Type | Nullable | Description |
|-------|------|----------|-------------|
| `index` | string | No | Entry sequence number (1-based) |
| `institution_name` | string | No | Name of educational institution |
| `start_date` | string | No | Format: YYYY-MM-DD |
| `end_date` | string | No | Format: YYYY-MM-DD |
| `field_of_study` | string | No | Academic discipline |
| `level_of_study` | string | No | Degree level |
| `graduated` | string | No | "0" or "1" |

---

## Number of Education Entries Per Learner

| Entries | Learners | Percentage |
|---------|----------|------------|
| 1 | 80,372 | 80.02% |
| 2 | 15,949 | 15.88% |
| 3 | 3,251 | 3.24% |
| 4 | 655 | 0.65% |
| 5 | 149 | 0.15% |
| 6+ | 70 | 0.07% |
| **Max** | **11** | - |

**Finding:** Most learners (80%) report only one education entry. About 20% have pursued multiple degrees.

---

## Field Analysis: `institution_name`

### Top 20 Institutions

| Rank | Institution | Count | % of Entries |
|------|-------------|-------|--------------|
| 1 | University of Ghana | 2,934 | 2.33% |
| 2 | University of Lagos | 2,905 | 2.31% |
| 3 | Kwame Nkrumah University of Science and Technology | 2,585 | 2.05% |
| 4 | University of Ilorin | 1,941 | 1.54% |
| 5 | University of Benin | 1,902 | 1.51% |
| 6 | University of Ibadan | 1,686 | 1.34% |
| 7 | University of Nairobi | 1,658 | 1.32% |
| 8 | Kenyatta University | 1,387 | 1.10% |
| 9 | University of Cape Coast | 1,344 | 1.07% |
| 10 | Jomo Kenyatta University of Agriculture and Technology | 1,304 | 1.04% |
| 11 | Nnamdi Azikiwe University | 1,114 | 0.89% |
| 12 | National Open University of Nigeria | 1,097 | 0.87% |
| 13 | Obafemi Awolowo University Ile-Ife | 1,097 | 0.87% |
| 14 | University of Nigeria | 981 | 0.78% |
| 15 | ALX | 950 | 0.75% |
| 16 | Lagos State University | 908 | 0.72% |
| 17 | Cairo University | 904 | 0.72% |
| 18 | Addis Ababa University | 866 | 0.69% |
| 19 | University of Uyo | 856 | 0.68% |
| 20 | Ahmadu Bello University | 804 | 0.64% |

**Total Unique Institutions:** 28,595

### Institutions by Detected Country

| Country | Count | Percentage |
|---------|-------|------------|
| Other/Unknown | 73,761 | 58.60% |
| Nigeria | 27,316 | 21.70% |
| Kenya | 7,928 | 6.30% |
| Ghana | 6,833 | 5.43% |
| Egypt | 3,278 | 2.60% |
| Ethiopia | 2,010 | 1.60% |
| South Africa | 1,640 | 1.30% |
| Rwanda | 1,534 | 1.22% |
| Uganda | 1,153 | 0.92% |
| Morocco | 291 | 0.23% |
| Tanzania | 124 | 0.10% |

### Special Institution Types

| Type | Count | Percentage |
|------|-------|------------|
| ALX (program provider) | 2,393 | 1.90% |
| Polytechnic | 4,591 | 3.65% |
| Secondary/High School | 2,143 | 1.70% |
| Udacity | 172 | 0.14% |
| Google certifications | 127 | 0.10% |
| Coursera | 115 | 0.09% |
| Online/Distance | 70 | 0.06% |
| Udemy | 43 | 0.03% |

---

## Field Analysis: `level_of_study`

| Level | Count | Percentage |
|-------|-------|------------|
| Bachelor's degree | 62,567 | 49.71% |
| n/a | 17,929 | 14.24% |
| College/University | 10,862 | 8.63% |
| Some college / No degree | 8,704 | 6.92% |
| High school diploma | 7,489 | 5.95% |
| Master's degree | 7,353 | 5.84% |
| Associate's degree | 4,366 | 3.47% |
| Postgraduate diploma | 3,392 | 2.69% |
| Graduate School | 1,991 | 1.58% |
| High School | 734 | 0.58% |
| Doctorate degree | 363 | 0.29% |
| Vocational School | 113 | 0.09% |
| Elementary/Junior High School | 5 | 0.00% |

**Finding:** Nearly half (49.71%) of education entries are Bachelor's degrees. The `n/a` category (14.24%) represents entries where level was not specified.

### Graduation Rate by Level

| Level | Graduated | Not Graduated | Rate |
|-------|-----------|---------------|------|
| Bachelor's degree | 48,962 | 13,605 | 78.3% |
| **n/a** | **0** | **17,929** | **0.0%** |
| College/University | 100 | 10,762 | 0.9% |
| Some college / No degree | 6,395 | 2,309 | 73.5% |
| High school diploma | 6,669 | 820 | 89.1% |
| Master's degree | 5,753 | 1,600 | 78.2% |
| Associate's degree | 3,821 | 545 | 87.5% |
| Postgraduate diploma | 3,205 | 187 | 94.5% |
| Graduate School | 5 | 1,986 | 0.3% |
| Doctorate degree | 306 | 57 | 84.3% |

**Key Insight:** The `n/a` level has **0% graduation rate** - all 17,929 entries are marked `graduated=0`. These likely represent ongoing education or entries without proper level classification.

---

## Field Analysis: `field_of_study`

| Field of Study | Count | Percentage |
|----------------|-------|------------|
| Business and Economics | 20,567 | 16.34% |
| Other | 17,132 | 13.61% |
| Information Technology / Computer Science | 13,051 | 10.37% |
| Engineering | 9,458 | 7.51% |
| Sciences (Biology, Chemistry, Physics) | 6,376 | 5.07% |
| Education | 6,267 | 4.98% |
| Business | 5,322 | 4.23% |
| Medical, Pharmacy & Dental Sciences | 4,356 | 3.46% |
| Social Science | 3,309 | 2.63% |
| Software Engineering | 3,167 | 2.52% |
| Agriculture & Natural Resources | 2,688 | 2.14% |
| Mathematics | 2,501 | 1.99% |
| Journalism & Media | 2,229 | 1.77% |
| Health | 1,915 | 1.52% |
| Law | 1,802 | 1.43% |
| Arts | 1,668 | 1.33% |
| *... 26 more categories* | - | - |

**Total Unique Fields:** 43

---

## Field Analysis: Date Fields

### `start_date`

| Metric | Value |
|--------|-------|
| Valid dates | 125,420 (99.64%) |
| Invalid (1970-01-01) | 448 (0.36%) |
| Year range | 1970 - 2025 |

**Top Start Years:**

| Year | Count | Percentage |
|------|-------|------------|
| 2018 | 11,350 | 9.05% |
| 2019 | 10,900 | 8.69% |
| 2017 | 10,598 | 8.45% |
| 2016 | 10,178 | 8.12% |
| 2015 | 9,622 | 7.67% |
| 2021 | 8,583 | 6.84% |
| 2022 | 8,278 | 6.60% |
| 2014 | 8,175 | 6.52% |
| 2020 | 7,206 | 5.75% |

### `end_date`

| Metric | Value |
|--------|-------|
| Valid dates | 101,577 (80.70%) |
| **Invalid (1970-01-01)** | **24,284 (19.29%)** |
| Year range | 1970 - 2030 |

**Top End Years:**

| Year | Count | Percentage |
|------|-------|------------|
| 2022 | 13,299 | 13.09% |
| 2021 | 12,386 | 12.19% |
| 2023 | 11,898 | 11.71% |
| 2019 | 9,720 | 9.57% |
| 2018 | 8,175 | 8.05% |
| 2024 | 6,664 | 6.56% |

**Key Finding:** 19.29% of entries have `end_date = 1970-01-01`, which is the system's sentinel value for "unknown" or "ongoing" education.

---

## Duration Analysis

For entries with valid start and end dates:

| Metric | Value |
|--------|-------|
| Entries analyzed | 101,247 |
| Average duration | **3.78 years** |
| Min duration | -1.00 years (data error) |
| Max duration | 14.92 years |

### Duration Distribution

| Duration | Count | Percentage |
|----------|-------|------------|
| < 0 (invalid) | 52 | 0.05% |
| < 1 year | 7,534 | 7.44% |
| 1-2 years | 8,467 | 8.36% |
| 2-3 years | 12,169 | 12.02% |
| **3-4 years** | **23,480** | **23.19%** |
| **4-5 years** | **31,303** | **30.92%** |
| 5-6 years | 12,144 | 11.99% |
| 6+ years | 6,098 | 6.02% |

**Finding:** Most education entries span 3-5 years (54.11%), consistent with typical undergraduate program lengths in African universities.

---

## Field Analysis: `graduated`

| Value | Count | Percentage | Meaning |
|-------|-------|------------|---------|
| "1" | 75,227 | 59.77% | Graduated |
| "0" | 50,641 | 40.23% | Not graduated |

**Note:** The `graduated` field is a string ("0" or "1"), not a boolean.

---

## Multi-Education Patterns

### Learners with Multiple Entries

| Category | Count |
|----------|-------|
| Learners with 1 education entry | 80,372 |
| **Learners with 2+ entries** | **20,074** |

### Common Education Progressions

| Progression | Count | Description |
|-------------|-------|-------------|
| Bachelor's → Master's | 2,949 | Standard postgraduate path |
| High school → Bachelor's | 1,218 | Complete education history |
| Bachelor's → Some college | 1,126 | May indicate certification courses |
| Bachelor's → Bachelor's | 892 | Double degree or transfer |
| College/University → Bachelor's | 761 | Progression to degree |
| n/a → n/a | 711 | Incomplete data |
| n/a → Bachelor's | 698 | Partial history |
| Bachelor's → Postgraduate diploma | 654 | Professional certification |
| Associate's → Bachelor's | 480 | Standard progression |

---

## Data Quality Issues

| Issue | Count | Percentage | Severity |
|-------|-------|------------|----------|
| `graduated=0` but has end_date (past) | 46,468 | 36.92% | **Medium** |
| Invalid end_date (1970-01-01) | 24,284 | 19.29% | Low |
| `level_of_study = n/a` | 17,929 | 14.24% | Low |
| Duration < 6 months | 3,837 | 3.05% | Low |
| Duration > 8 years | 859 | 0.68% | Low |
| Future end_date | 590 | 0.47% | Low |
| Invalid start_date (1970-01-01) | 448 | 0.36% | Low |
| End date before start date | 221 | 0.18% | **High** |
| `field_of_study = n/a` | 103 | 0.08% | Low |

### Analysis of `n/a` Level Entries

The 17,929 entries with `level_of_study = n/a`:
- **100% have `graduated=0`**
- Come from major universities (University of Lagos, OAU, University of Ilorin)
- Have valid field_of_study values
- Likely represent **currently enrolled** students or **incomplete entries**

Top institutions with `n/a` level:
1. University of Lagos (685)
2. Obafemi Awolowo University (430)
3. University of Ilorin (410)
4. University of Ibadan (367)
5. University of Benin (347)

---

## Comparison with Standalone Columns

The dataset has two additional columns that relate to education:
- `education_level_of_study` (standalone column)
- `education_field_of_study` (standalone column)

### For Rows WITH education_details

| Column | Top Value | Count |
|--------|-----------|-------|
| education_level_of_study | Bachelor's degree or equivalent | 37,904 |
| education_level_of_study | Bachelor'S Degree | 17,207 |
| education_field_of_study | Other | 13,260 |
| education_field_of_study | Business and Economics | 13,119 |

### For Rows WITHOUT education_details (empty `[]`)

| Column | Top Value | Count |
|--------|-----------|-------|
| education_level_of_study | Bachelor's degree or equivalent | 405,152 |
| education_level_of_study | Currently enrolled at university/college | 166,846 |
| education_field_of_study | Other | 174,406 |
| education_field_of_study | Business and Economics | 151,714 |

**Finding:** The standalone columns contain data even when `education_details` is empty, suggesting these columns come from a different data source (possibly profile/registration data vs. detailed education history).

---

## Recommendations for ETL

### 1. Data Cleaning

```python
# Handle sentinel values
if end_date == "1970-01-01":
    end_date = None  # Ongoing or unknown

if start_date == "1970-01-01":
    start_date = None  # Unknown start
```

### 2. Node Creation

Create `Education` nodes for each entry in `education_details`:

```cypher
CREATE (e:Education {
    institution_name: $institution_name,
    level_of_study: $level_of_study,
    field_of_study: $field_of_study,
    start_date: date($start_date),
    end_date: date($end_date),
    graduated: toBoolean($graduated = "1")
})
```

### 3. Institution Normalization

Consider creating separate `Institution` nodes to normalize the 28,595 unique institutions:

```cypher
MERGE (i:Institution {name: $institution_name})
SET i.country = $detected_country
```

### 4. Relationship

```cypher
MATCH (l:Learner {hashed_email: $hashed_email})
MATCH (e:Education {...})
CREATE (l)-[:HAS_EDUCATION {index: $index}]->(e)
```

---

## Summary Statistics

| Metric | Value |
|--------|-------|
| Learners with education data | 100,446 (6.29%) |
| Total education entries | 125,868 |
| Average entries per learner | 1.25 |
| Unique institutions | 28,595 |
| Unique fields of study | 43 |
| Unique levels of study | 13 |
| Overall graduation rate | 59.77% |
| Average education duration | 3.78 years |
| Most common level | Bachelor's degree (49.71%) |
| Most common field | Business and Economics (16.34%) |
| Top country (by institution) | Nigeria (21.70%) |

---

**Analysis completed:** December 1, 2025
