# Impact Learners Data Analysis & Neo4j Schema

This repository contains data analysis and Neo4j graph database schema design for the Impact Learners platform.

## 📂 Repository Structure

```
.
├── docs/                          # Analysis documentation
│   ├── employment_analysis_findings.md    # Employment data analysis
│   └── has_flags_analysis.md             # has_* flags analysis
├── model/                         # Neo4j schema design
│   └── ModelIdea.md              # Complete Pydantic models & graph schema
├── draft/                         # Draft files and column mappings
│   └── column_names.txt          # Column descriptions and keep/drop decisions
└── README.md                     # This file
```

## 📊 Data Analysis

### Employment Analysis
Comprehensive analysis of 1.6M learner records examining relationships between:
- `is_wage_employed` (3.32% of learners)
- `has_employment_details` (18.03% have employment history)
- `employment_details` (actual employment data)

**Key Finding:** Only 3.32% of learners are currently in wage employment, though 18% have employment history. The difference represents self-employed, freelancers, or previously employed individuals.

See [docs/employment_analysis_findings.md](docs/employment_analysis_findings.md)

### has_* Flags Analysis
Analysis of all 8 `has_*` boolean flags in the dataset:

| Flag | Reliability | Accuracy |
|------|-------------|----------|
| `has_profile_profile_photo` | ✓✓ Highly Reliable | 100% |
| `has_data` | ✓ Reliable | 95.12% |
| `has_employment_details` | ✓ Reliable | ~100%* |
| `has_education_details` | ✓ Reliable | ~100%* |
| `has_social_economic_data` | ✗ Unreliable | 43.83% |

*When accounting for `"[]"` as empty JSON arrays

See [docs/has_flags_analysis.md](docs/has_flags_analysis.md)

## 🗂️ Neo4j Graph Schema

Complete graph database schema design using Pydantic models with:
- **8 Node Types:** Learner, Country, City, Skill, Program, Company, LearningState, ProfessionalStatus
- **7 Relationship Types:** HAS_SKILL, ENROLLED_IN, WORKS_FOR, RUNS_VENTURE, IN_LEARNING_STATE, HAS_PROFESSIONAL_STATUS, IN_COUNTRY
- **Temporal State Tracking:** SCD Type 2 pattern for tracking learning and professional status changes over time
- **HYBRID Geographic Approach:** Avoids supernodes by using property references for countries/cities

See [model/ModelIdea.md](model/ModelIdea.md)

## 🎯 Key Features

### Temporal State Tracking (SCD Type 2)
Innovative approach to track state transitions over time:
- **Learning States:** Active → Dropped Out → Graduate
- **Professional Status:** Unemployed → Wage Employed → Entrepreneur

### Dual Schema Employment Handling
Properly handles two different `placement_details` schemas:
- **Wage/Freelance:** employment_type, salary_range, job_title
- **Venture:** jobs_created, capital_secured, female_opportunities

### Rich Relationship Properties
Relationships carry detailed metrics:
- `ENROLLED_IN`: 20+ properties (scores, completion rates, assignment metrics)
- `WORKS_FOR`: employment history, salary range, duration
- `RUNS_VENTURE`: impact metrics (jobs created, capital secured)

## 📈 Expected Graph Scale

Based on 1.6M learner dataset:
- **Nodes:** ~5-6M total
- **Relationships:** ~10-12M total
- **Learners:** 1,597,198
- **Companies:** ~50K-100K
- **Programs:** ~50-100
- **Skills:** ~500-1,000

## 🚀 Getting Started

### Prerequisites
- Neo4j 4.x or 5.x (for implementing the graph schema)
- Python 3.8+ with pandas, pydantic (for ETL development)

## 📝 Notes

- CSV data files are excluded from git (see `.gitignore`)
- All analysis performed on 2.5GB dataset with 1.6M records
- Chunked processing used to manage memory (100K rows per chunk)

## 🔗 SQL to Neo4j Mapping

Complete mapping documentation available in [model/ModelIdea.md](model/ModelIdea.md) including:
- Column-by-column transformation logic
- ETL helper functions
- Validation functions
- Example transformations

## 📊 Data Quality Insights

- `has_data` flag: 95% accurate, indicates demographic data presence
- `has_employment_details`: Reliable indicator of employment history
- `has_social_economic_data`: Unreliable (44% accuracy), do not use
- Empty JSON arrays (`"[]"`) are stored as data, not NULL

## 🏗️ Architecture Decisions

1. **HYBRID Geographic Approach:** Store country/city codes as properties to avoid supernodes
2. **Temporal Nodes:** Separate nodes for state tracking enable time-series analysis
3. **Rich Relationships:** Store metrics on relationships, not separate nodes
4. **Flexible Employment:** Different relationship types for wage vs venture employment

---

**Dataset:** impact_learners_profile-1759316791571.csv (1,597,198 records)
**Analysis Date:** October 2025
