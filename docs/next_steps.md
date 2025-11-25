# Next Steps: Missing Features & Future Enhancements

## 1. Temporal State Tracking (SCD Type 2) - NOT IMPLEMENTED ⚠️

### Current Status
**The ETL does NOT implement temporal state tracking.** The notebook queries for this feature will fail with warnings.

### What's Missing

#### A. Learning State History
**Current Implementation:**
```python
# In transformer.py (line 209)
learner_dict["current_learning_state"] = learning_state  # Just a property
```

**Current Graph Model:**
```cypher
(:Learner {
    hashedEmail: "abc123",
    currentLearningState: "Graduate"  // Single snapshot value
})
```

**Missing Implementation:**
```cypher
// Multiple temporal relationships tracking state changes over time
(:Learner {hashedEmail: "abc123"})
    -[HAS_LEARNING_STATE {validFrom: "2024-01-01", validTo: "2024-06-30", isCurrent: false}]->
    (:LearningState {state: "Active"})

(:Learner {hashedEmail: "abc123"})
    -[HAS_LEARNING_STATE {validFrom: "2024-07-01", validTo: null, isCurrent: true}]->
    (:LearningState {state: "Graduate"})
```

#### B. Professional Status History
**Current Implementation:**
```python
# In transformer.py (line 224)
learner_dict["current_professional_status"] = prof_status  # Just a property
```

**Current Graph Model:**
```cypher
(:Learner {
    hashedEmail: "abc123",
    currentProfessionalStatus: "Wage Employed"  // Single snapshot value
})
```

**Missing Implementation:**
```cypher
// Multiple temporal relationships tracking employment status over time
(:Learner {hashedEmail: "abc123"})
    -[HAS_PROFESSIONAL_STATUS {validFrom: "2023-01-01", validTo: "2024-05-31", isCurrent: false}]->
    (:ProfessionalStatus {status: "Unemployed"})

(:Learner {hashedEmail: "abc123"})
    -[HAS_PROFESSIONAL_STATUS {validFrom: "2024-06-01", validTo: null, isCurrent: true}]->
    (:ProfessionalStatus {status: "Wage Employed"})
```

---

## Why This Feature is Missing

### Data Limitation
**The CSV only contains SNAPSHOT data (current state), not HISTORICAL data.**

Example CSV columns:
```csv
sand_id,hashed_email,is_active_learner,is_graduate_learner,is_wage_employed
12345,abc123,0,1,1
```

This tells us:
- ✅ Current state: Graduate
- ✅ Current employment: Wage Employed
- ❌ When they became a graduate (no date)
- ❌ Previous states (Active → Dropped Out → Re-enrolled → Graduate)
- ❌ When employment status changed (no history)

### What Would Be Needed

To implement temporal state tracking, you would need:

1. **Historical State Data** in CSV or separate table:
```csv
sand_id,state_type,state_value,transition_date
12345,learning_state,Active,2024-01-01
12345,learning_state,Dropped Out,2024-03-15
12345,learning_state,Active,2024-09-01
12345,learning_state,Graduate,2024-12-20
12345,professional_status,Unemployed,2024-01-01
12345,professional_status,Wage Employed,2024-06-15
```

2. **Or** periodic snapshots:
```csv
snapshot_date,sand_id,learning_state,professional_status
2024-01-01,12345,Active,Unemployed
2024-06-01,12345,Active,Wage Employed
2024-12-01,12345,Graduate,Wage Employed
```

---

## Implementation Guide (If Data Becomes Available)

### Step 1: Update Data Models

**File:** `src/models/relationships.py`

Add temporal properties to state relationships:

```python
@dataclass
class HasLearningStateRelationship(BaseRelationship):
    """Temporal relationship tracking learning state changes."""

    rel_type: str = "HAS_LEARNING_STATE"
    from_label: str = "Learner"
    to_label: str = "LearningState"

    # Temporal tracking (SCD Type 2)
    valid_from: date  # When this state started
    valid_to: date | None = None  # When this state ended (null = current)
    is_current: bool = False  # Quick filter for current state
    transition_reason: str | None = None  # Why state changed (dropout reason, etc.)

@dataclass
class HasProfessionalStatusRelationship(BaseRelationship):
    """Temporal relationship tracking professional status changes."""

    rel_type: str = "HAS_PROFESSIONAL_STATUS"
    from_label: str = "Learner"
    to_label: str = "ProfessionalStatus"

    # Temporal tracking (SCD Type 2)
    valid_from: date
    valid_to: date | None = None
    is_current: bool = False
    transition_type: str | None = None  # "promotion", "job_change", "unemployed", etc.
```

### Step 2: Update Transformer

**File:** `src/etl/transformer.py`

Replace property-based state storage with relationship creation:

```python
def _derive_states(
    self,
    learner_dict: dict[str, Any],
    raw_fields: dict[str, Any],
    entities: GraphEntities,
) -> None:
    """Derive learning and professional states WITH TEMPORAL TRACKING."""

    # Parse state history from CSV (if available)
    state_history = self._parse_state_history(raw_fields)

    for state_entry in state_history:
        # Create learning state node
        learning_state_node = self.state_deriver.create_learning_state_node(
            state_entry["state"]
        )
        entities.learning_states.append(learning_state_node)

        # Create TEMPORAL RELATIONSHIP
        relationship = HasLearningStateRelationship(
            from_id=learner_dict["hashed_email"],
            to_id=learning_state_node.state,
            valid_from=state_entry["start_date"],
            valid_to=state_entry["end_date"],
            is_current=(state_entry["end_date"] is None),
            transition_reason=state_entry.get("reason")
        )
        entities.learning_state_relationships.append(relationship)

    # Keep property for quick access (denormalized)
    learner_dict["current_learning_state"] = state_history[-1]["state"]
```

### Step 3: Update Loader

**File:** `src/neo4j/relationship_creator.py`

Add methods to create temporal state relationships:

```python
def create_learning_state_relationships(
    self,
    relationships: list[HasLearningStateRelationship]
) -> None:
    """Create temporal learning state relationships."""

    cypher = """
    UNWIND $relationships AS rel
    MATCH (learner:Learner {hashedEmail: rel.from_id})
    MATCH (state:LearningState {state: rel.to_id})
    MERGE (learner)-[r:HAS_LEARNING_STATE {
        validFrom: rel.valid_from
    }]->(state)
    SET r.validTo = rel.valid_to,
        r.isCurrent = rel.is_current,
        r.transitionReason = rel.transition_reason
    """

    self._execute_batch(cypher, relationships)
```

### Step 4: Update Cypher Queries

**Notebook queries would then work:**

```cypher
// Find learners who dropped out then graduated
MATCH (l:Learner)-[r1:HAS_LEARNING_STATE]->(s1:LearningState {state: "Dropped Out"})
MATCH (l)-[r2:HAS_LEARNING_STATE]->(s2:LearningState {state: "Graduate"})
WHERE r2.validFrom > r1.validFrom
RETURN l.fullName,
       r1.validFrom as dropout_date,
       r2.validFrom as graduate_date,
       duration.between(r1.validFrom, r2.validFrom).months as months_away
ORDER BY months_away
```

```cypher
// Average time from graduation to employment
MATCH (l:Learner)-[r1:HAS_LEARNING_STATE]->(s1:LearningState {state: "Graduate"})
MATCH (l)-[r2:HAS_PROFESSIONAL_STATUS]->(s2:ProfessionalStatus)
WHERE s2.status IN ["Wage Employed", "Freelancer"]
  AND r2.validFrom > r1.validFrom
WITH duration.between(r1.validFrom, r2.validFrom).months as months_to_employment
RETURN avg(months_to_employment) as avg_months
```

---

## Business Value of Temporal Tracking

If implemented, this would enable:

### 1. Dropout Risk Analysis
- Identify patterns before dropout (enrollment gaps, low scores, etc.)
- Build predictive models: "Learners with X pattern are 80% likely to drop out"

### 2. Re-engagement Success Metrics
- How many dropped-out learners re-engage?
- What's the average time between dropout and re-enrollment?
- What predicts successful re-engagement?

### 3. Time-to-Employment Analytics
- Average time from graduation to first job
- Compare by program, country, skill set
- Identify "fast track" vs "slow track" patterns

### 4. Career Progression Tracking
- Unemployed → Employed → Multiple Jobs → Freelancer
- Average salary progression over time
- Identify successful career paths

### 5. Program Effectiveness Over Time
- Do graduates stay employed after 6 months? 1 year?
- Which programs have the best long-term outcomes?

---

## Alternative: Pseudo-Temporal Tracking

### If Historical Data is Unavailable

You can implement **limited temporal tracking** using employment/program dates:

#### Employment Timeline
```cypher
// Infer state changes from employment start/end dates
MATCH (l:Learner)-[w:WORKS_FOR]->(c:Company)
WITH l, w
ORDER BY w.startDate
WITH l, collect({
    company: c.name,
    start: w.startDate,
    end: w.endDate,
    status: CASE WHEN w.isCurrent THEN "Employed" ELSE "Past Employment" END
}) as employment_timeline
RETURN l.fullName, employment_timeline
```

#### Learning Timeline
```cypher
// Infer from program enrollment dates
MATCH (l:Learner)-[e:ENROLLED_IN]->(p:Program)
WITH l, e, p
ORDER BY e.startDate
WITH l, collect({
    program: p.name,
    start: e.startDate,
    graduation: e.graduationDate,
    status: e.enrollmentStatus
}) as learning_timeline
RETURN l.fullName, learning_timeline
```

This provides **partial temporal tracking** but lacks:
- State transitions unrelated to programs/employment
- Unemployment periods
- Dropout → Re-engagement patterns

---

## Priority Recommendation

### High Priority ⭐⭐⭐
1. **Document this limitation** in README and notebook ✅ (doing now)
2. **Request historical data** from data provider
3. **Build pseudo-temporal queries** using employment/program dates

### Medium Priority ⭐⭐
4. **Implement SCD Type 2 model** if historical data becomes available
5. **Create data quality report** identifying learners with state inconsistencies

### Low Priority ⭐
6. **Build predictive models** once temporal data exists
7. **LLM-powered timeline generation** (infer missing transitions)

---

## Summary

**Current State:**
- ❌ No temporal state tracking
- ❌ No state history in database
- ❌ Notebook queries fail with warnings
- ✅ Current state stored as properties (snapshot only)

**To Implement:**
1. Obtain historical state data or periodic snapshots
2. Update data models with temporal relationships
3. Modify ETL to create state history relationships
4. Update notebook queries to use temporal patterns

**Estimated Effort:**
- If data available: 2-3 days (models + ETL + testing)
- If data unavailable: Cannot implement (requires new data source)

**Business Impact:**
- High value if implemented (dropout prediction, employment analytics)
- Currently blocked by data availability

---

**Last Updated:** 2024-11-24
**Status:** Feature documented, awaiting data availability
