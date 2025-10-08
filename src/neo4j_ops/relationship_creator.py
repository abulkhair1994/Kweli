"""
Relationship creator for Neo4j.

Creates relationships between nodes with properties.
"""

from structlog.types import FilteringBoundLogger

from models.relationships import (
    EnrolledInRelationship,
    HasSkillRelationship,
    WorksForRelationship,
)
from neo4j_ops.connection import Neo4jConnection
from utils.logger import get_logger


class RelationshipCreator:
    """Create relationships in Neo4j."""

    def __init__(
        self,
        connection: Neo4jConnection,
        logger: FilteringBoundLogger | None = None,
    ) -> None:
        """
        Initialize relationship creator.

        Args:
            connection: Neo4j connection instance
            logger: Optional logger instance
        """
        self.connection = connection
        self.logger = logger or get_logger(__name__)

    def create_has_skill(
        self,
        learner_sand_id: str,
        skill_id: str,
        relationship: HasSkillRelationship,
    ) -> None:
        """
        Create HAS_SKILL relationship.

        Args:
            learner_sand_id: Learner sandId
            skill_id: Skill id
            relationship: HasSkillRelationship instance
        """
        query = """
        MATCH (l:Learner {sandId: $learner_sand_id})
        MATCH (s:Skill {id: $skill_id})
        MERGE (l)-[r:HAS_SKILL]->(s)
        SET r.proficiencyLevel = $proficiency_level,
            r.source = $source,
            r.acquiredDate = CASE WHEN $acquired_date IS NOT NULL
                THEN date($acquired_date) ELSE null END,
            r.lastUpdated = datetime($last_updated)
        """

        params = {
            "learner_sand_id": learner_sand_id,
            "skill_id": skill_id,
            "proficiency_level": relationship.proficiency_level,
            "source": relationship.source,
            "acquired_date": (
                str(relationship.acquired_date) if relationship.acquired_date else None
            ),
            "last_updated": relationship.last_updated.isoformat(),
        }

        self.connection.execute_write(query, params)

    def create_enrolled_in(
        self,
        learner_sand_id: str,
        program_id: str,
        relationship: EnrolledInRelationship,
    ) -> None:
        """
        Create ENROLLED_IN relationship.

        Args:
            learner_sand_id: Learner sandId
            program_id: Program id
            relationship: EnrolledInRelationship instance
        """
        query = """
        MATCH (l:Learner {sandId: $learner_sand_id})
        MATCH (p:Program {id: $program_id})
        MERGE (l)-[r:ENROLLED_IN]->(p)
        SET r.index = $index,
            r.cohortCode = $cohort_code,
            r.enrollmentStatus = $enrollment_status,
            r.startDate = date($start_date),
            r.endDate = CASE WHEN $end_date IS NOT NULL THEN date($end_date) ELSE null END,
            r.graduationDate = CASE WHEN $graduation_date IS NOT NULL
                THEN date($graduation_date) ELSE null END,
            r.lmsOverallScore = $lms_overall_score,
            r.completionRate = $completion_rate,
            r.numberOfAssignments = $number_of_assignments,
            r.numberOfSubmissions = $number_of_submissions,
            r.numberOfAssignmentsPassed = $number_of_assignments_passed,
            r.assignmentCompletionRate = $assignment_completion_rate,
            r.numberOfMilestones = $number_of_milestones,
            r.numberOfMilestonesSubmitted = $number_of_milestones_submitted,
            r.numberOfMilestonesPassed = $number_of_milestones_passed,
            r.milestoneCompletionRate = $milestone_completion_rate,
            r.numberOfTests = $number_of_tests,
            r.numberOfTestsSubmitted = $number_of_tests_submitted,
            r.numberOfTestsPassed = $number_of_tests_passed,
            r.testCompletionRate = $test_completion_rate,
            r.isCompleted = $is_completed,
            r.isDropped = $is_dropped,
            r.duration = $duration
        """

        params = {
            "learner_sand_id": learner_sand_id,
            "program_id": program_id,
            "index": relationship.index,
            "cohort_code": relationship.cohort_code,
            "enrollment_status": relationship.enrollment_status,
            "start_date": str(relationship.start_date),
            "end_date": str(relationship.end_date) if relationship.end_date else None,
            "graduation_date": (
                str(relationship.graduation_date) if relationship.graduation_date else None
            ),
            "lms_overall_score": relationship.lms_overall_score,
            "completion_rate": relationship.completion_rate,
            "number_of_assignments": relationship.number_of_assignments,
            "number_of_submissions": relationship.number_of_submissions,
            "number_of_assignments_passed": relationship.number_of_assignments_passed,
            "assignment_completion_rate": relationship.assignment_completion_rate,
            "number_of_milestones": relationship.number_of_milestones,
            "number_of_milestones_submitted": relationship.number_of_milestones_submitted,
            "number_of_milestones_passed": relationship.number_of_milestones_passed,
            "milestone_completion_rate": relationship.milestone_completion_rate,
            "number_of_tests": relationship.number_of_tests,
            "number_of_tests_submitted": relationship.number_of_tests_submitted,
            "number_of_tests_passed": relationship.number_of_tests_passed,
            "test_completion_rate": relationship.test_completion_rate,
            "is_completed": relationship.is_completed,
            "is_dropped": relationship.is_dropped,
            "duration": relationship.duration,
        }

        self.connection.execute_write(query, params)

    def create_works_for(
        self,
        learner_sand_id: str,
        company_id: str,
        relationship: WorksForRelationship,
    ) -> None:
        """
        Create WORKS_FOR relationship.

        Args:
            learner_sand_id: Learner sandId
            company_id: Company id
            relationship: WorksForRelationship instance
        """
        query = """
        MATCH (l:Learner {sandId: $learner_sand_id})
        MATCH (c:Company {id: $company_id})
        MERGE (l)-[r:WORKS_FOR]->(c)
        SET r.position = $position,
            r.department = $department,
            r.employmentType = $employment_type,
            r.startDate = CASE WHEN $start_date IS NOT NULL
                THEN date($start_date) ELSE null END,
            r.endDate = CASE WHEN $end_date IS NOT NULL
                THEN date($end_date) ELSE null END,
            r.isCurrent = $is_current,
            r.salaryRange = $salary_range,
            r.source = $source,
            r.duration = $duration
        """

        params = {
            "learner_sand_id": learner_sand_id,
            "company_id": company_id,
            "position": relationship.position,
            "department": relationship.department,
            "employment_type": relationship.employment_type,
            "start_date": str(relationship.start_date) if relationship.start_date else None,
            "end_date": str(relationship.end_date) if relationship.end_date else None,
            "is_current": relationship.is_current,
            "salary_range": relationship.salary_range,
            "source": relationship.source,
            "duration": relationship.duration,
        }

        self.connection.execute_write(query, params)

    def link_learner_to_learning_state(
        self,
        learner_sand_id: str,
        learning_state_id: str,
    ) -> None:
        """
        Link Learner to LearningState (temporal).

        Args:
            learner_sand_id: Learner sandId
            learning_state_id: LearningState internal id
        """
        query = """
        MATCH (l:Learner {sandId: $learner_sand_id})
        MATCH (ls:LearningState) WHERE id(ls) = $learning_state_id
        CREATE (l)-[:IN_LEARNING_STATE {transitionDate: datetime()}]->(ls)
        """

        params = {
            "learner_sand_id": learner_sand_id,
            "learning_state_id": learning_state_id,
        }

        self.connection.execute_write(query, params)

    def link_learner_to_professional_status(
        self,
        learner_sand_id: str,
        professional_status_id: str,
    ) -> None:
        """
        Link Learner to ProfessionalStatus (temporal).

        Args:
            learner_sand_id: Learner sandId
            professional_status_id: ProfessionalStatus internal id
        """
        query = """
        MATCH (l:Learner {sandId: $learner_sand_id})
        MATCH (ps:ProfessionalStatus) WHERE id(ps) = $professional_status_id
        CREATE (l)-[:HAS_PROFESSIONAL_STATUS {transitionDate: datetime()}]->(ps)
        """

        params = {
            "learner_sand_id": learner_sand_id,
            "professional_status_id": professional_status_id,
        }

        self.connection.execute_write(query, params)


__all__ = ["RelationshipCreator"]
