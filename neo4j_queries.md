# Neo4j Cypher Queries for Impact Learners Knowledge Graph

This document contains tested and working Cypher queries for analyzing learner data, focusing on programs, professional status, and geographic distribution.

**Database URL:** http://localhost:7475
**Data loaded:** 61 learners with 25,330 relationships

---

## Table of Contents
1. [Program Queries](#program-queries)
2. [Professional Status Queries](#professional-status-queries)
3. [Geographic Distribution Queries](#geographic-distribution-queries)

---

## Program Queries

### 1. Programs with Learner Count

Get all programs with the number of enrolled learners.

```cypher
MATCH (p:Program)<-[:ENROLLED_IN]-(l:Learner)
RETURN p.name as program,
       p.cohortCode as cohort,
       count(l) as learner_count
ORDER BY learner_count DESC
```

**Returns:** 21 results
**Sample output:** Virtual Assistant (VA-C10) with 9 learners

---

### 2. Program Enrollment by Status

See enrollment distribution across different statuses (Graduated, Dropped Out, etc.).

```cypher
MATCH (l:Learner)-[e:ENROLLED_IN]->(p:Program)
RETURN p.name as program,
       e.enrollmentStatus as status,
       count(*) as count
ORDER BY program, count DESC
```

**Returns:** 13 results
**Sample output:** AI Career Essentials - Graduated: 1 learner

---

### 3. Program Performance Metrics

Analyze program performance with LMS scores, completion rates, and duration.

```cypher
MATCH (l:Learner)-[e:ENROLLED_IN]->(p:Program)
WHERE e.lmsOverallScore IS NOT NULL
RETURN p.name as program,
       p.cohortCode as cohort,
       count(l) as learners,
       avg(e.lmsOverallScore) as avg_lms_score,
       avg(e.completionRate) as avg_completion_rate,
       avg(e.duration) as avg_duration_days
ORDER BY learners DESC
```

**Returns:** 20 results
**Sample output:** Virtual Assistant (VA-C10) - 9 learners, avg LMS score 43.34, avg completion 44.4%

---

### 4. Learners in Specific Program

Find all learners enrolled in a specific program (example: VA-C6).

```cypher
MATCH (l:Learner)-[e:ENROLLED_IN]->(p:Program {cohortCode: 'VA-C6'})
RETURN l.fullName as learner,
       l.sandId as sand_id,
       e.enrollmentStatus as status,
       e.startDate as start_date,
       e.completionRate as completion_rate
ORDER BY e.startDate DESC
LIMIT 10
```

**Returns:** 3 results
**Sample output:** Learner graduated from VA-C6 starting 2024-09-23 with 100% completion

---

### 5. Program Completion and Dropout Rates

Calculate completion and dropout percentages for each program.

```cypher
MATCH (l:Learner)-[e:ENROLLED_IN]->(p:Program)
WITH p,
     sum(CASE WHEN e.isCompleted = true THEN 1 ELSE 0 END) as completed,
     sum(CASE WHEN e.isDropped = true THEN 1 ELSE 0 END) as dropped,
     count(*) as total
RETURN p.name as program,
       p.cohortCode as cohort,
       total,
       completed,
       dropped,
       round(completed * 100.0 / total, 2) as completion_percentage,
       round(dropped * 100.0 / total, 2) as dropout_percentage
ORDER BY total DESC
```

**Returns:** 21 results
**Sample output:** Virtual Assistant (VA-C10) - 44.44% completion, 55.56% dropout

---

## Professional Status Queries

### 6. Professional Status Distribution

Count learners by professional status.

```cypher
MATCH (l:Learner)-[:HAS_PROFESSIONAL_STATUS]->(ps:ProfessionalStatus)
RETURN ps.status as status,
       count(DISTINCT l) as learner_count
ORDER BY learner_count DESC
```

**Returns:** 1 result
**Sample output:** Multiple - 61 learners

---

### 7. Learners by Current Professional Status

Get current professional status for all learners.

```cypher
MATCH (l:Learner)
WHERE l.currentProfessionalStatus IS NOT NULL
RETURN l.currentProfessionalStatus as status,
       count(l) as count
ORDER BY count DESC
```

**Returns:** 1 result
**Sample output:** Multiple - 61 learners

---

### 8. Employed Learners with Company Details

Find learners who are currently employed or have employment history.

```cypher
MATCH (l:Learner)-[w:WORKS_FOR]->(c:Company)
RETURN l.fullName as learner,
       c.name as company,
       w.position as position,
       w.startDate as start_date,
       w.isCurrent as is_current
ORDER BY w.startDate DESC
LIMIT 10
```

**Returns:** 10 results
**Sample output:** Learner working as Intern at P3 Consulting Minna (current position)

---

### 9. Professional Status by Program

Analyze professional status distribution within each program.

```cypher
MATCH (l:Learner)-[:ENROLLED_IN]->(p:Program)
WHERE l.currentProfessionalStatus IS NOT NULL
RETURN p.name as program,
       l.currentProfessionalStatus as professional_status,
       count(l) as count
ORDER BY program, count DESC
```

**Returns:** 6 results
**Sample output:** AI Career Essentials - Multiple status: 3 learners

---

## Geographic Distribution Queries

### 10. Learners by Country

Count learners in each country.

```cypher
MATCH (l:Learner)
WHERE l.countryOfResidenceCode IS NOT NULL
RETURN l.countryOfResidenceCode as country,
       count(l) as learner_count
ORDER BY learner_count DESC
```

**Returns:** 5 results
**Sample output:** Ghana (GH) - 35 learners

---

### 11. Learners by City

Count learners in each city with country information.

```cypher
MATCH (l:Learner)
WHERE l.cityOfResidenceId IS NOT NULL
RETURN l.cityOfResidenceId as city,
       l.countryOfResidenceCode as country,
       count(l) as learner_count
ORDER BY learner_count DESC
```

**Returns:** 17 results
**Sample output:** Accra, Ghana (GH-ACC) - 26 learners

---

### 12. Programs by Country

See which programs are popular in each country.

```cypher
MATCH (l:Learner)-[:ENROLLED_IN]->(p:Program)
WHERE l.countryOfResidenceCode IS NOT NULL
RETURN l.countryOfResidenceCode as country,
       p.name as program,
       count(l) as learner_count
ORDER BY country, learner_count DESC
```

**Returns:** 13 results
**Sample output:** Cameroon (CM) - Virtual Assistant: 1 learner

---

### 13. Professional Status by Country

Analyze professional status distribution across countries.

```cypher
MATCH (l:Learner)
WHERE l.countryOfResidenceCode IS NOT NULL
  AND l.currentProfessionalStatus IS NOT NULL
RETURN l.countryOfResidenceCode as country,
       l.currentProfessionalStatus as status,
       count(l) as count
ORDER BY country, count DESC
```

**Returns:** 5 results
**Sample output:** Cameroon (CM) - Multiple status: 1 learner

---

### 14. Learning State by Country

See learning states (Graduate, Active, Dropped Out) by country.

```cypher
MATCH (l:Learner)
WHERE l.countryOfResidenceCode IS NOT NULL
  AND l.currentLearningState IS NOT NULL
RETURN l.countryOfResidenceCode as country,
       l.currentLearningState as learning_state,
       count(l) as count
ORDER BY country, count DESC
```

**Returns:** 5 results
**Sample output:** Cameroon (CM) - Graduate: 1 learner

---

## Additional Useful Queries

### Find Learner Journey (Skills → Program → Employment)

```cypher
MATCH (l:Learner {sandId: 'YOUR_LEARNER_ID'})
OPTIONAL MATCH (l)-[:HAS_SKILL]->(s:Skill)
OPTIONAL MATCH (l)-[e:ENROLLED_IN]->(p:Program)
OPTIONAL MATCH (l)-[w:WORKS_FOR]->(c:Company)
RETURN l.fullName as learner,
       collect(DISTINCT s.name) as skills,
       collect(DISTINCT {program: p.name, status: e.enrollmentStatus}) as programs,
       collect(DISTINCT {company: c.name, position: w.position}) as employment
```

Replace `'YOUR_LEARNER_ID'` with an actual sandId to see their complete journey.

---

### Top Companies Hiring Impact Learners

```cypher
MATCH (c:Company)<-[:WORKS_FOR]-(l:Learner)
RETURN c.name as company,
       count(DISTINCT l) as learner_count
ORDER BY learner_count DESC
LIMIT 10
```

---

## Notes

- All queries have been tested and return results from the current database
- Property names use camelCase (e.g., `fullName`, `sandId`, `cohortCode`)
- Date properties use Neo4j's `Date` type
- Use Neo4j Browser at http://localhost:7475 to visualize results
- Total data: 61 learners, 1,629 nodes, 25,330 relationships

---

**Generated:** 2025-10-07
**Database Version:** Neo4j (accessed via port 7475)
