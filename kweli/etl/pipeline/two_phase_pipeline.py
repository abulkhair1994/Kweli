"""
Two-Phase ETL Pipeline - Deadlock-free parallel processing.

Phase 1: Sequential creation of shared entities (countries, cities, skills, programs, companies)
Phase 2: Parallel creation of learners + relationships

This eliminates deadlocks by ensuring shared entities exist before parallel processing.
"""

from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from threading import Lock
from typing import Any

from structlog.types import FilteringBoundLogger

from kweli.etl.models.nodes import (
    CityNode,
    CompanyNode,
    CountryNode,
    LearningStateNode,
    ProfessionalStatusNode,
    ProgramNode,
    SkillNode,
)
from kweli.etl.neo4j_ops.connection import Neo4jConnection
from kweli.etl.pipeline.checkpoint import Checkpoint
from kweli.etl.pipeline.extractor import Extractor
from kweli.etl.pipeline.loader import Loader
from kweli.etl.pipeline.progress import ProgressTracker
from kweli.etl.pipeline.transformer import Transformer
from kweli.etl.utils.logger import get_logger
from kweli.etl.validators.data_quality import DataQualityChecker, QualityMetrics


class TwoPhaseETLPipeline:
    """
    Two-phase ETL pipeline for deadlock-free parallel processing.

    Phase 1: Scan CSV and create all shared entities sequentially
    Phase 2: Process learners in parallel (no conflicts)
    """

    def __init__(
        self,
        csv_path: Path | str | None = None,
        connection: Neo4jConnection = None,
        chunk_size: int = 10000,
        batch_size: int = 1000,
        num_workers: int = 4,
        checkpoint_interval: int = 5000,
        enable_progress_bar: bool = True,
        logger: FilteringBoundLogger | None = None,
        extractor: Extractor | None = None,
    ) -> None:
        """Initialize two-phase ETL pipeline."""
        self.csv_path = Path(csv_path) if csv_path else None
        self.connection = connection
        self.chunk_size = chunk_size
        self.batch_size = batch_size
        self.num_workers = num_workers
        self.checkpoint_interval = checkpoint_interval
        self.enable_progress_bar = enable_progress_bar
        self.logger = logger or get_logger(__name__)

        # Initialize components - use provided extractor or create from CSV path
        if extractor is not None:
            self.extractor = extractor
        elif csv_path is not None:
            self.extractor = Extractor(source_type="csv", csv_path=csv_path, chunk_size=chunk_size, logger=logger)
        else:
            raise ValueError("Either csv_path or extractor must be provided")
        self.transformer = Transformer(logger)
        self.validator = DataQualityChecker(logger=logger)
        self.checkpoint = Checkpoint(logger=logger)
        self.loader = Loader(connection, batch_size=batch_size, logger=logger)

        # Log configuration for debugging
        self.logger.info(
            "TwoPhaseETLPipeline initialized",
            chunk_size=chunk_size,
            batch_size=batch_size,
            num_workers=num_workers,
        )

        # Phase 1: Shared entity collections (de-duplicated)
        self.shared_entities = {
            "countries": {},  # {code: CountryNode}
            "cities": {},     # {id: CityNode}
            "skills": {},     # {id: SkillNode}
            "programs": {},   # {id: ProgramNode}
            "companies": {},  # {id: CompanyNode}
            "learning_states": {},  # {(state, start_date): LearningStateNode}
            "professional_statuses": {},  # {(status, start_date): ProfessionalStatusNode}
        }

        # Phase 1: Store ALL transformed entities for reuse in Phase 2
        # This avoids re-reading from MySQL (which causes timeout issues with streaming)
        self._transformed_entities_batches: list = []

        # Metrics
        self._metrics_lock = Lock()
        self.rows_processed = 0
        self.nodes_created: dict[str, int] = {
            "learners": 0,
            "countries": 0,
            "cities": 0,
            "skills": 0,
            "programs": 0,
            "companies": 0,
            "learning_states": 0,  # Created in Phase 1 (shared entities)
            "professional_statuses": 0,  # Created in Phase 1 (shared entities)
        }

        # Store learner-to-state associations for relationship creation in Phase 2
        # {hashed_email: [(state, start_date), ...]}
        self._learner_learning_states: dict[str, list[tuple]] = {}
        self._learner_professional_statuses: dict[str, list[tuple]] = {}

    def run(self) -> dict[str, Any]:
        """Run the two-phase ETL pipeline."""
        try:
            total_rows = self.extractor.get_total_rows()
            self.logger.info(
                "Starting two-phase ETL pipeline",
                total_rows=total_rows,
                num_workers=self.num_workers,
            )

            # PHASE 1: Extract and create shared entities sequentially
            self.logger.info("=" * 60)
            self.logger.info("PHASE 1: Extracting shared entities")
            self.logger.info("=" * 60)
            self._phase1_extract_shared_entities(total_rows)

            # Close data source connection after Phase 1 to prevent timeout
            # This is critical for MySQL streaming mode where the connection
            # would otherwise stay open during Phase 2's slow Neo4j writes
            self._close_data_source()

            # PHASE 2: Process learners in parallel (using stored entities)
            self.logger.info("=" * 60)
            self.logger.info("PHASE 2: Processing learners in parallel")
            self.logger.info("=" * 60)
            self._phase2_process_learners_parallel(total_rows)

            # Build final metrics
            progress_metrics = {"elapsed_seconds": 0, "average_rate": 0}
            quality_metrics = self.validator.metrics

            return self._build_final_metrics(progress_metrics, quality_metrics)

        except Exception as e:
            self.logger.error("Two-phase ETL pipeline failed", error=str(e))
            raise

    def _phase1_extract_shared_entities(self, total_rows: int) -> None:
        """Phase 1: Scan data source and extract all unique shared entities.

        Also stores ALL transformed entities for reuse in Phase 2.
        This avoids re-reading from the data source, which is critical for MySQL
        streaming mode where keeping the connection open during Phase 2's Neo4j
        writes would cause timeout errors.
        """
        self.logger.info("Scanning data source to extract shared entities...")
        self.logger.info("(Also storing all entities for Phase 2 - single pass optimization)")

        progress = ProgressTracker(
            total_rows=total_rows,
            enable_progress_bar=self.enable_progress_bar,
            log_interval=10000,
            logger=self.logger,
        )

        rows_scanned = 0
        current_batch = []

        for chunk_df in self.extractor.extract_chunks():
            rows = chunk_df.to_dicts()

            for row in rows:
                try:
                    entities = self.transformer.transform_row(row)

                    # Collect unique shared entities
                    for country in entities.countries:
                        if country.code not in self.shared_entities["countries"]:
                            self.shared_entities["countries"][country.code] = country

                    for city in entities.cities:
                        if city.id not in self.shared_entities["cities"]:
                            self.shared_entities["cities"][city.id] = city

                    for skill in entities.skills:
                        if skill.id not in self.shared_entities["skills"]:
                            self.shared_entities["skills"][skill.id] = skill

                    for program in entities.programs:
                        if program.id not in self.shared_entities["programs"]:
                            self.shared_entities["programs"][program.id] = program

                    for company in entities.companies:
                        if company.id not in self.shared_entities["companies"]:
                            self.shared_entities["companies"][company.id] = company

                    # Collect unique learning states (shared entities)
                    # Skip states with null start_date (Neo4j MERGE requires non-null key)
                    for ls in entities.learning_states:
                        if ls.start_date is None:
                            continue  # Skip null start_date - can't use as MERGE key
                        # Key: (state_value, start_date) - must match MERGE key in Neo4j
                        state_value = ls.state.value if hasattr(ls.state, 'value') else str(ls.state)
                        key = (state_value, ls.start_date)
                        if key not in self.shared_entities["learning_states"]:
                            self.shared_entities["learning_states"][key] = ls

                    # Collect unique professional statuses (shared entities)
                    # Skip statuses with null start_date (Neo4j MERGE requires non-null key)
                    for ps in entities.professional_statuses:
                        if ps.start_date is None:
                            continue  # Skip null start_date - can't use as MERGE key
                        status_value = ps.status.value if hasattr(ps.status, 'value') else str(ps.status)
                        key = (status_value, ps.start_date)
                        if key not in self.shared_entities["professional_statuses"]:
                            self.shared_entities["professional_statuses"][key] = ps

                    # Store learner-to-state associations for Phase 2 relationship creation
                    # Only store associations with non-null start_dates (must match shared entities)
                    if entities.learner and entities.learner.hashed_email:
                        hashed_email = entities.learner.hashed_email

                        # Learning state associations (skip null start_dates)
                        if entities.learning_states:
                            valid_states = [
                                (ls.state.value if hasattr(ls.state, 'value') else str(ls.state),
                                 ls.start_date, ls.end_date, ls.is_current)
                                for ls in entities.learning_states
                                if ls.start_date is not None
                            ]
                            if valid_states:
                                self._learner_learning_states[hashed_email] = valid_states

                        # Professional status associations (skip null start_dates)
                        if entities.professional_statuses:
                            valid_statuses = [
                                (ps.status.value if hasattr(ps.status, 'value') else str(ps.status),
                                 ps.start_date, ps.end_date, ps.is_current)
                                for ps in entities.professional_statuses
                                if ps.start_date is not None
                            ]
                            if valid_statuses:
                                self._learner_professional_statuses[hashed_email] = valid_statuses

                    # Store transformed entities for Phase 2 (single pass optimization)
                    if entities.learner:
                        current_batch.append(entities)
                        if len(current_batch) >= self.batch_size:
                            self._transformed_entities_batches.append(current_batch)
                            current_batch = []

                    rows_scanned += 1
                    progress.update(success=True)

                except Exception as e:
                    self.logger.warning("Failed to extract from row", error=str(e))
                    progress.update(success=False)

        # Store remaining batch
        if current_batch:
            self._transformed_entities_batches.append(current_batch)

        progress.finish()

        # Create shared entities in batches (sequential, no conflicts)
        self.logger.info("Creating shared entities sequentially...")
        self._create_shared_entities_batched()

        self.logger.info(
            "Phase 1 complete",
            countries=len(self.shared_entities["countries"]),
            cities=len(self.shared_entities["cities"]),
            skills=len(self.shared_entities["skills"]),
            programs=len(self.shared_entities["programs"]),
            companies=len(self.shared_entities["companies"]),
            learning_states=len(self.shared_entities["learning_states"]),
            professional_statuses=len(self.shared_entities["professional_statuses"]),
            stored_batches=len(self._transformed_entities_batches),
            total_learners_stored=sum(len(b) for b in self._transformed_entities_batches),
        )

    def _close_data_source(self) -> None:
        """Close the data source connection after Phase 1.

        This is critical for MySQL streaming mode to prevent connection timeout
        during Phase 2's slow Neo4j writes. The MySQL connection would otherwise
        sit idle and get terminated by the server.
        """
        if hasattr(self.extractor, "reader") and hasattr(self.extractor.reader, "close"):
            self.logger.info("Closing data source connection (MySQL streaming fix)")
            self.extractor.reader.close()
        else:
            self.logger.debug("Data source does not require explicit close")

    def _create_shared_entities_batched(self) -> None:
        """Create all shared entities in batches sequentially."""
        # Create countries
        if self.shared_entities["countries"]:
            countries_list = list(self.shared_entities["countries"].values())
            for i in range(0, len(countries_list), self.batch_size):
                batch = countries_list[i:i + self.batch_size]
                self._create_country_batch(batch)
            self.nodes_created["countries"] = len(countries_list)

        # Create cities
        if self.shared_entities["cities"]:
            cities_list = list(self.shared_entities["cities"].values())
            for i in range(0, len(cities_list), self.batch_size):
                batch = cities_list[i:i + self.batch_size]
                self._create_city_batch(batch)
            self.nodes_created["cities"] = len(cities_list)

        # Create skills
        if self.shared_entities["skills"]:
            skills_list = list(self.shared_entities["skills"].values())
            for i in range(0, len(skills_list), self.batch_size):
                batch = skills_list[i:i + self.batch_size]
                self._create_skill_batch(batch)
            self.nodes_created["skills"] = len(skills_list)

        # Create programs
        if self.shared_entities["programs"]:
            programs_list = list(self.shared_entities["programs"].values())
            for i in range(0, len(programs_list), self.batch_size):
                batch = programs_list[i:i + self.batch_size]
                self._create_program_batch(batch)
            self.nodes_created["programs"] = len(programs_list)

        # Create companies
        if self.shared_entities["companies"]:
            companies_list = list(self.shared_entities["companies"].values())
            for i in range(0, len(companies_list), self.batch_size):
                batch = companies_list[i:i + self.batch_size]
                self._create_company_batch(batch)
            self.nodes_created["companies"] = len(companies_list)

        # Create learning states (NEW - shared entities)
        if self.shared_entities["learning_states"]:
            states_list = list(self.shared_entities["learning_states"].values())
            for i in range(0, len(states_list), self.batch_size):
                batch = states_list[i:i + self.batch_size]
                self._create_learning_state_batch(batch)
            self.nodes_created["learning_states"] = len(states_list)
            self.logger.info("Created learning state nodes", count=len(states_list))

        # Create professional statuses (NEW - shared entities)
        if self.shared_entities["professional_statuses"]:
            statuses_list = list(self.shared_entities["professional_statuses"].values())
            for i in range(0, len(statuses_list), self.batch_size):
                batch = statuses_list[i:i + self.batch_size]
                self._create_professional_status_batch(batch)
            self.nodes_created["professional_statuses"] = len(statuses_list)
            self.logger.info("Created professional status nodes", count=len(statuses_list))

    def _create_country_batch(self, countries: list[CountryNode]) -> None:
        """Create a batch of country nodes."""
        records = [
            {"code": c.code, "name": c.name, "latitude": c.latitude, "longitude": c.longitude}
            for c in countries
        ]
        self.loader.batch_ops.batch_create_nodes("Country", records, "code")

    def _create_city_batch(self, cities: list[CityNode]) -> None:
        """Create a batch of city nodes."""
        records = [
            {"id": c.id, "name": c.name, "countryCode": c.country_code,
             "latitude": c.latitude, "longitude": c.longitude}
            for c in cities
        ]
        self.loader.batch_ops.batch_create_nodes("City", records, "id")

    def _create_skill_batch(self, skills: list[SkillNode]) -> None:
        """Create a batch of skill nodes."""
        records = [
            {"id": s.id, "name": s.name, "category": s.category}
            for s in skills
        ]
        self.loader.batch_ops.batch_create_nodes("Skill", records, "id")

    def _create_program_batch(self, programs: list[ProgramNode]) -> None:
        """Create a batch of program nodes."""
        records = [
            {"id": p.id, "name": p.name, "cohortCode": p.cohort_code, "provider": p.provider}
            for p in programs
        ]
        self.loader.batch_ops.batch_create_nodes("Program", records, "id")

    def _create_company_batch(self, companies: list[CompanyNode]) -> None:
        """Create a batch of company nodes."""
        records = [
            {"id": c.id, "name": c.name, "industry": c.industry, "countryCode": c.country_code}
            for c in companies
        ]
        self.loader.batch_ops.batch_create_nodes("Company", records, "id")

    def _create_learning_state_batch(self, states: list[LearningStateNode]) -> None:
        """Create a batch of learning state nodes (shared entities)."""
        records = [
            {
                "state": s.state.value if hasattr(s.state, 'value') else str(s.state),
                "startDate": s.start_date,
                "endDate": s.end_date,
                "isCurrent": s.is_current,
                "reason": s.reason,
            }
            for s in states
        ]
        # Use batch_execute with MERGE on (state, startDate) composite key
        self.loader.batch_ops.batch_execute("""
            UNWIND $records AS record
            MERGE (s:LearningState {state: record.state, startDate: record.startDate})
            SET s.endDate = record.endDate, s.isCurrent = record.isCurrent, s.reason = record.reason
        """, records)

    def _create_professional_status_batch(self, statuses: list[ProfessionalStatusNode]) -> None:
        """Create a batch of professional status nodes (shared entities)."""
        records = [
            {
                "status": s.status.value if hasattr(s.status, 'value') else str(s.status),
                "startDate": s.start_date,
                "endDate": s.end_date,
                "isCurrent": s.is_current,
                "details": s.details,
            }
            for s in statuses
        ]
        # Use batch_execute with MERGE on (status, startDate) composite key
        self.loader.batch_ops.batch_execute("""
            UNWIND $records AS record
            MERGE (ps:ProfessionalStatus {status: record.status, startDate: record.startDate})
            SET ps.endDate = record.endDate, ps.isCurrent = record.isCurrent, ps.details = record.details
        """, records)

    def _phase2_process_learners_parallel(self, _total_rows: int) -> None:
        """Phase 2: Process learners in parallel using stored entities from Phase 1.

        Instead of re-reading from the data source (which would require keeping
        the MySQL connection open), we use the entities stored during Phase 1.
        This prevents MySQL streaming timeout issues.
        """
        total_learners = sum(len(b) for b in self._transformed_entities_batches)
        self.logger.info(
            "Starting Phase 2: Parallel learner processing (using stored entities)",
            num_workers=self.num_workers,
            batch_size=self.batch_size,
            total_batches=len(self._transformed_entities_batches),
            total_learners=total_learners,
        )

        progress = ProgressTracker(
            total_rows=total_learners,
            enable_progress_bar=self.enable_progress_bar,
            log_interval=1000,
            logger=self.logger,
        )

        with ThreadPoolExecutor(max_workers=self.num_workers) as executor:
            self.logger.info("ThreadPoolExecutor started", max_workers=self.num_workers)
            futures = []

            # Process pre-batched entities from Phase 1
            for batch_idx, entities_batch in enumerate(self._transformed_entities_batches):
                # Submit batch to worker pool
                future = executor.submit(
                    self._process_learner_batch,
                    entities_batch
                )
                futures.append(future)

                # Update metrics
                with self._metrics_lock:
                    self.rows_processed += len(entities_batch)
                    self.nodes_created["learners"] += len(entities_batch)

                # Update progress for each entity in the batch
                for _ in entities_batch:
                    progress.update(success=True)

                # Log batch submission progress
                if (batch_idx + 1) % 100 == 0:
                    self.logger.debug(
                        "Submitted batches to thread pool",
                        batches_submitted=batch_idx + 1,
                        total_batches=len(self._transformed_entities_batches),
                    )

            # Wait for all batches to complete
            completed = 0
            for future in as_completed(futures):
                try:
                    future.result()
                    completed += 1
                    if completed % 100 == 0:
                        self.logger.debug(
                            "Batch processing progress",
                            batches_completed=completed,
                            total_batches=len(futures),
                        )
                except Exception as e:
                    self.logger.error("Batch processing failed", error=str(e))
                    raise

        progress.finish()

        # Clear stored entities to free memory
        self._transformed_entities_batches.clear()
        self.logger.info("Cleared stored entities from memory")

    def _process_learner_batch(self, entities_batch: list) -> None:
        """Process a batch of learners (runs in worker thread).

        NOTE: Temporal state NODES (LearningState, ProfessionalStatus) are created
        in Phase 1 as shared entities. This method only creates Learner nodes and
        all RELATIONSHIPS (including temporal state relationships).
        """
        # Extract learners and relationship data
        learners = []
        learning_entries = []
        employment_entries = []
        skill_associations = []
        learning_state_rels = []  # For HAS_LEARNING_STATE relationships
        professional_status_rels = []  # For HAS_PROFESSIONAL_STATUS relationships

        for entities in entities_batch:
            if entities.learner:
                learners.append(entities.learner)

                # Collect relationship data
                hashed_email = entities.learner.hashed_email
                if hashed_email:
                    learning_entries.extend([(hashed_email, e) for e in entities.learning_details_entries])
                    employment_entries.extend([(hashed_email, e) for e in entities.employment_details_entries])
                    skill_associations.extend([(hashed_email, s.id) for s in entities.skills])

                    # Collect temporal state relationship data from stored associations
                    if hashed_email in self._learner_learning_states:
                        for state, start_date, end_date, is_current in self._learner_learning_states[hashed_email]:
                            learning_state_rels.append({
                                "learner_id": hashed_email,
                                "state": state,
                                "start_date": start_date,
                                "end_date": end_date,
                                "is_current": is_current,
                            })

                    if hashed_email in self._learner_professional_statuses:
                        for status, start_date, end_date, is_current in self._learner_professional_statuses[hashed_email]:
                            professional_status_rels.append({
                                "learner_id": hashed_email,
                                "status": status,
                                "start_date": start_date,
                                "end_date": end_date,
                                "is_current": is_current,
                            })

        # Create learner nodes
        if learners:
            learner_records = [self.loader._learner_to_dict(learner) for learner in learners]
            self.loader.batch_ops.batch_create_nodes("Learner", learner_records, "hashedEmail")

        # Create skill relationships
        if skill_associations:
            skill_rels = [
                {"from_id": hashed_email, "to_id": skill_id, "properties": {}}
                for hashed_email, skill_id in skill_associations
            ]
            self.loader.batch_ops.batch_create_relationships(
                "HAS_SKILL", "Learner", "hashedEmail", "Skill", "id", skill_rels
            )

        # Create enrollment relationships
        if learning_entries:
            self.loader._batch_create_enrollment_relationships_from_list(learning_entries)

        # Create employment relationships
        if employment_entries:
            self.loader._batch_create_employment_relationships_from_list(employment_entries)

        # Create temporal state relationships (nodes already exist from Phase 1)
        if learning_state_rels:
            self.loader.batch_ops.batch_execute("""
                UNWIND $records AS record
                MATCH (l:Learner {hashedEmail: record.learner_id})
                MATCH (s:LearningState {state: record.state, startDate: record.start_date})
                MERGE (l)-[r:HAS_LEARNING_STATE]->(s)
                SET r.validFrom = record.start_date, r.validTo = record.end_date, r.isCurrent = record.is_current
            """, learning_state_rels)

        if professional_status_rels:
            self.loader.batch_ops.batch_execute("""
                UNWIND $records AS record
                MATCH (l:Learner {hashedEmail: record.learner_id})
                MATCH (ps:ProfessionalStatus {status: record.status, startDate: record.start_date})
                MERGE (l)-[r:HAS_PROFESSIONAL_STATUS]->(ps)
                SET r.validFrom = record.start_date, r.validTo = record.end_date, r.isCurrent = record.is_current
            """, professional_status_rels)

    def _build_final_metrics(
        self,
        progress_metrics: dict[str, Any],
        quality_metrics: QualityMetrics,
    ) -> dict[str, Any]:
        """Build final metrics report."""
        return {
            "status": "completed",
            "rows_processed": self.rows_processed,
            "processing_rate": progress_metrics.get("average_rate", 0),
            "elapsed_seconds": progress_metrics.get("elapsed_seconds", 0),
            "nodes_created": self.nodes_created,
            "total_nodes": sum(self.nodes_created.values()),
            "quality_metrics": {
                "valid_records": quality_metrics.valid_records,
                "invalid_records": quality_metrics.invalid_records,
                "error_rate": quality_metrics.error_rate,
                "errors_by_type": quality_metrics.errors_by_type,
            },
            "parallelism": {
                "num_workers": self.num_workers,
                "pipeline_type": "two-phase (deadlock-free)",
            },
        }


__all__ = ["TwoPhaseETLPipeline"]
