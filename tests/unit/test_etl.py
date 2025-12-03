"""
Unit tests for ETL components.

Tests for BatchAccumulator and other ETL utilities.
"""

from datetime import date

from kweli.etl.models.enums import LearningState, ProfessionalStatus
from kweli.etl.models.nodes import (
    CityNode,
    CompanyNode,
    CountryNode,
    LearnerNode,
    LearningStateNode,
    ProfessionalStatusNode,
    ProgramNode,
    SkillNode,
)
from kweli.etl.models.parsers import EmploymentDetailsEntry, LearningDetailsEntry
from kweli.etl.pipeline.batch_accumulator import BatchAccumulator, BatchData


class TestBatchData:
    """Test BatchData container."""

    def test_init(self):
        """Test initialization."""
        batch = BatchData()
        assert isinstance(batch.countries, dict)
        assert isinstance(batch.cities, dict)
        assert isinstance(batch.skills, dict)
        assert isinstance(batch.programs, dict)
        assert isinstance(batch.companies, dict)
        assert isinstance(batch.learners, list)
        assert isinstance(batch.learning_states, list)
        assert isinstance(batch.professional_statuses, list)

    def test_count_entities_empty(self):
        """Test entity count when empty."""
        batch = BatchData()
        assert batch.count_entities() == 0

    def test_count_entities_with_data(self):
        """Test entity count with data."""
        batch = BatchData()
        batch.learners.append(
            LearnerNode(sand_id="test1", hashed_email="hash1", full_name="Test User")
        )
        batch.countries["EG"] = CountryNode(code="EG", name="Egypt")
        batch.cities["EG-CAI"] = CityNode(
            id="EG-CAI", name="Cairo", country_code="EG"
        )
        batch.skills["python"] = SkillNode(id="python", name="Python")
        batch.programs["prog1"] = ProgramNode(
            id="prog1", name="Test Program", cohort_code="prog1"
        )
        batch.companies["comp1"] = CompanyNode(id="comp1", name="Test Company")
        batch.learning_states.append(
            LearningStateNode(state=LearningState.ACTIVE, start_date=date.today())
        )
        batch.professional_statuses.append(
            ProfessionalStatusNode(
                status=ProfessionalStatus.UNEMPLOYED, start_date=date.today()
            )
        )

        assert batch.count_entities() == 8


class TestBatchAccumulator:
    """Test BatchAccumulator."""

    def test_init(self):
        """Test initialization."""
        acc = BatchAccumulator(batch_size=100)
        assert acc.batch_size == 100
        assert acc.is_empty()
        assert not acc.is_full()

    def test_add_single_learner(self):
        """Test adding a single learner."""
        acc = BatchAccumulator(batch_size=10)

        learner = LearnerNode(sand_id="test1", hashed_email="hash1", full_name="Test User")
        country = CountryNode(code="EG", name="Egypt")
        city = CityNode(id="EG-CAI", name="Cairo", country_code="EG")
        skill = SkillNode(id="python", name="Python")
        program = ProgramNode(id="prog1", name="Test Program", cohort_code="prog1")
        company = CompanyNode(id="comp1", name="Test Company")
        learning_state = LearningStateNode(
            state=LearningState.ACTIVE, start_date=date.today()
        )
        prof_status = ProfessionalStatusNode(
            status=ProfessionalStatus.UNEMPLOYED, start_date=date.today()
        )

        acc.add(
            learner=learner,
            countries=[country],
            cities=[city],
            skills=[skill],
            programs=[program],
            companies=[company],
            learning_states=[learning_state],
            professional_statuses=[prof_status],
            learning_entries=[],
            employment_entries=[],
        )

        assert not acc.is_empty()
        assert not acc.is_full()

        batch = acc.get_batch()
        assert len(batch.learners) == 1
        assert len(batch.countries) == 1
        assert len(batch.cities) == 1
        assert len(batch.skills) == 1
        assert len(batch.programs) == 1
        assert len(batch.companies) == 1

    def test_deduplication_countries(self):
        """Test that duplicate countries are de-duplicated."""
        acc = BatchAccumulator(batch_size=10)

        learner1 = LearnerNode(sand_id="test1", hashed_email="hash1", full_name="User 1")
        learner2 = LearnerNode(sand_id="test2", hashed_email="hash2", full_name="User 2")

        country_eg = CountryNode(code="EG", name="Egypt")

        # Add two learners with same country
        acc.add(
            learner=learner1,
            countries=[country_eg],
            cities=[],
            skills=[],
            programs=[],
            companies=[],
            learning_states=[],
            professional_statuses=[],
            learning_entries=[],
            employment_entries=[],
        )
        acc.add(
            learner=learner2,
            countries=[country_eg],
            cities=[],
            skills=[],
            programs=[],
            companies=[],
            learning_states=[],
            professional_statuses=[],
            learning_entries=[],
            employment_entries=[],
        )

        batch = acc.get_batch()
        assert len(batch.learners) == 2
        assert len(batch.countries) == 1  # De-duplicated
        assert "EG" in batch.countries

    def test_deduplication_skills(self):
        """Test that duplicate skills are de-duplicated."""
        acc = BatchAccumulator(batch_size=10)

        learner1 = LearnerNode(sand_id="test1", hashed_email="hash1", full_name="User 1")
        learner2 = LearnerNode(sand_id="test2", hashed_email="hash2", full_name="User 2")

        skill_python = SkillNode(id="python", name="Python")

        # Add two learners with same skill
        for learner in [learner1, learner2]:
            acc.add(
                learner=learner,
                countries=[],
                cities=[],
                skills=[skill_python],
                programs=[],
                companies=[],
                learning_states=[],
                professional_statuses=[],
                learning_entries=[],
                employment_entries=[],
            )

        batch = acc.get_batch()
        assert len(batch.learners) == 2
        assert len(batch.skills) == 1  # De-duplicated
        assert "python" in batch.skills

    def test_no_deduplication_learners(self):
        """Test that learners are NOT de-duplicated."""
        acc = BatchAccumulator(batch_size=10)

        learner1 = LearnerNode(sand_id="test1", hashed_email="hash1", full_name="User 1")
        learner2 = LearnerNode(sand_id="test1", hashed_email="hash1", full_name="User 1")  # Same sand_id

        for learner in [learner1, learner2]:
            acc.add(
                learner=learner,
                countries=[],
                cities=[],
                skills=[],
                programs=[],
                companies=[],
                learning_states=[],
                professional_statuses=[],
                learning_entries=[],
                employment_entries=[],
            )

        batch = acc.get_batch()
        assert len(batch.learners) == 2  # Both kept (shouldn't happen, but handled)

    def test_batch_full(self):
        """Test batch full detection."""
        acc = BatchAccumulator(batch_size=3)

        for i in range(3):
            learner = LearnerNode(sand_id=f"test{i}", hashed_email=f"hash{i}", full_name=f"User {i}")
            acc.add(
                learner=learner,
                countries=[],
                cities=[],
                skills=[],
                programs=[],
                companies=[],
                learning_states=[],
                professional_statuses=[],
                learning_entries=[],
                employment_entries=[],
            )

        assert acc.is_full()

    def test_clear_batch(self):
        """Test clearing batch."""
        acc = BatchAccumulator(batch_size=10)

        learner = LearnerNode(sand_id="test1", hashed_email="hash1", full_name="User 1")
        acc.add(
            learner=learner,
            countries=[],
            cities=[],
            skills=[],
            programs=[],
            companies=[],
            learning_states=[],
            professional_statuses=[],
            learning_entries=[],
            employment_entries=[],
        )

        assert not acc.is_empty()
        acc.clear()
        assert acc.is_empty()

    def test_get_stats(self):
        """Test statistics reporting."""
        acc = BatchAccumulator(batch_size=10)

        learner = LearnerNode(sand_id="test1", hashed_email="hash1", full_name="User 1")
        country = CountryNode(code="EG", name="Egypt")
        skill1 = SkillNode(id="python", name="Python")
        skill2 = SkillNode(id="javascript", name="JavaScript")

        acc.add(
            learner=learner,
            countries=[country],
            cities=[],
            skills=[skill1, skill2],
            programs=[],
            companies=[],
            learning_states=[],
            professional_statuses=[],
            learning_entries=[],
            employment_entries=[],
        )

        stats = acc.get_stats()
        assert stats["learners"] == 1
        assert stats["countries"] == 1
        assert stats["skills"] == 2

    def test_relationship_entries(self):
        """Test storing relationship entries."""
        acc = BatchAccumulator(batch_size=10)

        learner = LearnerNode(sand_id="test1", hashed_email="hash1", full_name="User 1")

        learning_entry = LearningDetailsEntry(
            index="1",
            program_name="Test Program",
            cohort_code="COHORT1",
            program_start_date="2024-01-01",
            program_end_date="2024-12-31",
            enrollment_status="active",
            program_graduation_date="",
            lms_overall_score="85",
            no_of_assignments="10",
            no_of_submissions="10",
            no_of_assignment_passed="9",
            assignment_completion_rate="0.90",
            no_of_milestone="5",
            no_of_milestone_submitted="5",
            no_of_milestone_passed="5",
            milestone_completion_rate="1.00",
            no_of_test="3",
            no_of_test_submitted="3",
            no_of_test_passed="3",
            test_completion_rate="1.00",
            completion_rate="0.95",
        )
        employment_entry = EmploymentDetailsEntry(
            index="1",
            organization_name="Test Company",
            start_date="2024-01-01",
            end_date="",
            country="Egypt",
            job_title="Software Engineer",
            is_current="1",
            duration_in_years="1.0",
        )

        acc.add(
            learner=learner,
            countries=[],
            cities=[],
            skills=[],
            programs=[],
            companies=[],
            learning_states=[],
            professional_statuses=[],
            learning_entries=[learning_entry],
            employment_entries=[employment_entry],
        )

        batch = acc.get_batch()
        assert len(batch.learning_entries) == 1
        assert len(batch.employment_entries) == 1
        assert batch.learning_entries[0][0] == "hash1"  # hashed_email
        assert batch.employment_entries[0][0] == "hash1"  # hashed_email

    def test_multiple_batches(self):
        """Test handling multiple batches."""
        acc = BatchAccumulator(batch_size=2)

        # First batch
        for i in range(2):
            learner = LearnerNode(sand_id=f"test{i}", hashed_email=f"hash{i}", full_name=f"User {i}")
            acc.add(
                learner=learner,
                countries=[],
                cities=[],
                skills=[],
                programs=[],
                companies=[],
                learning_states=[],
                professional_statuses=[],
                learning_entries=[],
                employment_entries=[],
            )

        assert acc.is_full()
        batch1 = acc.get_batch()
        assert len(batch1.learners) == 2

        # Clear and start second batch
        acc.clear()
        assert acc.is_empty()

        for i in range(2, 4):
            learner = LearnerNode(sand_id=f"test{i}", hashed_email=f"hash{i}", full_name=f"User {i}")
            acc.add(
                learner=learner,
                countries=[],
                cities=[],
                skills=[],
                programs=[],
                companies=[],
                learning_states=[],
                professional_statuses=[],
                learning_entries=[],
                employment_entries=[],
            )

        batch2 = acc.get_batch()
        assert len(batch2.learners) == 2
        # Verify batches are independent
        assert batch1.learners[0].sand_id != batch2.learners[0].sand_id
