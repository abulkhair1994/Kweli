// Neo4j Initialization Script
// Creates constraints and indexes for Impact Learners Knowledge Graph

// ============================================================================
// CONSTRAINTS (Uniqueness + Existence)
// ============================================================================

// Learner constraints
CREATE CONSTRAINT learner_sand_id IF NOT EXISTS
FOR (l:Learner) REQUIRE l.sandId IS UNIQUE;

CREATE CONSTRAINT learner_hashed_email IF NOT EXISTS
FOR (l:Learner) REQUIRE l.hashedEmail IS UNIQUE;

// Country constraint
CREATE CONSTRAINT country_code IF NOT EXISTS
FOR (c:Country) REQUIRE c.code IS UNIQUE;

// City constraint
CREATE CONSTRAINT city_id IF NOT EXISTS
FOR (c:City) REQUIRE c.id IS UNIQUE;

// Skill constraint
CREATE CONSTRAINT skill_id IF NOT EXISTS
FOR (s:Skill) REQUIRE s.id IS UNIQUE;

// Program constraint
CREATE CONSTRAINT program_id IF NOT EXISTS
FOR (p:Program) REQUIRE p.id IS UNIQUE;

// Company constraint
CREATE CONSTRAINT company_id IF NOT EXISTS
FOR (c:Company) REQUIRE c.id IS UNIQUE;

// ============================================================================
// INDEXES (Performance)
// ============================================================================

// Learner indexes (for HYBRID property lookups)
CREATE INDEX learner_country IF NOT EXISTS
FOR (l:Learner) ON (l.countryOfResidenceCode);

CREATE INDEX learner_city IF NOT EXISTS
FOR (l:Learner) ON (l.cityOfResidenceId);

CREATE INDEX learner_learning_state IF NOT EXISTS
FOR (l:Learner) ON (l.currentLearningState);

CREATE INDEX learner_professional_status IF NOT EXISTS
FOR (l:Learner) ON (l.currentProfessionalStatus);

// Country index
CREATE INDEX country_name IF NOT EXISTS
FOR (c:Country) ON (c.name);

// City indexes
CREATE INDEX city_name IF NOT EXISTS
FOR (c:City) ON (c.name);

CREATE INDEX city_country IF NOT EXISTS
FOR (c:City) ON (c.countryCode);

// Skill indexes
CREATE INDEX skill_name IF NOT EXISTS
FOR (s:Skill) ON (s.name);

CREATE INDEX skill_category IF NOT EXISTS
FOR (s:Skill) ON (s.category);

// Program indexes
CREATE INDEX program_cohort IF NOT EXISTS
FOR (p:Program) ON (p.cohortCode);

CREATE INDEX program_name IF NOT EXISTS
FOR (p:Program) ON (p.name);

// Company indexes
CREATE INDEX company_name IF NOT EXISTS
FOR (c:Company) ON (c.name);

CREATE INDEX company_country IF NOT EXISTS
FOR (c:Company) ON (c.countryCode);

// LearningState indexes
CREATE INDEX learning_state_state IF NOT EXISTS
FOR (ls:LearningState) ON (ls.state);

CREATE INDEX learning_state_current IF NOT EXISTS
FOR (ls:LearningState) ON (ls.isCurrent);

// ProfessionalStatus indexes
CREATE INDEX prof_status_status IF NOT EXISTS
FOR (ps:ProfessionalStatus) ON (ps.status);

CREATE INDEX prof_status_current IF NOT EXISTS
FOR (ps:ProfessionalStatus) ON (ps.isCurrent);

// ============================================================================
// COMPLETION MESSAGE
// ============================================================================

RETURN "Constraints and indexes created successfully" AS message;
