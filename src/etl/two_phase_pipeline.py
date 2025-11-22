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

from etl.checkpoint import Checkpoint
from etl.extractor import Extractor
from etl.loader import Loader
from etl.progress import ProgressTracker
from etl.transformer import Transformer
from models.nodes import CityNode, CompanyNode, CountryNode, ProgramNode, SkillNode
from neo4j_ops.connection import Neo4jConnection
from utils.logger import get_logger
from validators.data_quality import DataQualityChecker, QualityMetrics


class TwoPhaseETLPipeline:
    """
    Two-phase ETL pipeline for deadlock-free parallel processing.

    Phase 1: Scan CSV and create all shared entities sequentially
    Phase 2: Process learners in parallel (no conflicts)
    """

    def __init__(
        self,
        csv_path: Path | str,
        connection: Neo4jConnection,
        chunk_size: int = 10000,
        batch_size: int = 1000,
        num_workers: int = 4,
        checkpoint_interval: int = 5000,
        enable_progress_bar: bool = True,
        logger: FilteringBoundLogger | None = None,
    ) -> None:
        """Initialize two-phase ETL pipeline."""
        self.csv_path = Path(csv_path)
        self.connection = connection
        self.chunk_size = chunk_size
        self.batch_size = batch_size
        self.num_workers = num_workers
        self.checkpoint_interval = checkpoint_interval
        self.enable_progress_bar = enable_progress_bar
        self.logger = logger or get_logger(__name__)

        # Initialize components
        self.extractor = Extractor(csv_path, chunk_size, logger)
        self.transformer = Transformer(logger)
        self.validator = DataQualityChecker(logger=logger)
        self.checkpoint = Checkpoint(logger=logger)
        self.loader = Loader(connection, logger)

        # Phase 1: Shared entity collections (de-duplicated)
        self.shared_entities = {
            "countries": {},  # {code: CountryNode}
            "cities": {},     # {id: CityNode}
            "skills": {},     # {id: SkillNode}
            "programs": {},   # {id: ProgramNode}
            "companies": {},  # {id: CompanyNode}
        }

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
            "learning_states": 0,
            "professional_statuses": 0,
        }

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

            # PHASE 2: Process learners in parallel
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
        """Phase 1: Scan CSV and extract all unique shared entities."""
        self.logger.info("Scanning CSV to extract shared entities...")

        progress = ProgressTracker(
            total_rows=total_rows,
            enable_progress_bar=self.enable_progress_bar,
            log_interval=10000,
            logger=self.logger,
        )

        rows_scanned = 0
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

                    rows_scanned += 1
                    progress.update(success=True)

                except Exception as e:
                    self.logger.warning("Failed to extract from row", error=str(e))
                    progress.update(success=False)

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
        )

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

    def _phase2_process_learners_parallel(self, total_rows: int) -> None:
        """Phase 2: Process learners in parallel (shared entities already exist)."""
        progress = ProgressTracker(
            total_rows=total_rows,
            enable_progress_bar=self.enable_progress_bar,
            log_interval=1000,
            logger=self.logger,
        )

        # Batch accumulator for learners
        learner_batch = []
        batch_lock = Lock()

        with ThreadPoolExecutor(max_workers=self.num_workers) as executor:
            futures = []

            for chunk_df in self.extractor.extract_chunks():
                rows = chunk_df.to_dicts()

                for row in rows:
                    try:
                        entities = self.transformer.transform_row(row)

                        if entities.learner:
                            with batch_lock:
                                learner_batch.append(entities)

                                # Flush batch when full
                                if len(learner_batch) >= self.batch_size:
                                    batch_to_process = learner_batch.copy()
                                    learner_batch.clear()

                                    # Submit to worker pool
                                    future = executor.submit(
                                        self._process_learner_batch,
                                        batch_to_process
                                    )
                                    futures.append(future)

                            with self._metrics_lock:
                                self.rows_processed += 1
                                self.nodes_created["learners"] += 1

                        progress.update(success=True)

                    except Exception as e:
                        self.logger.warning("Failed to process row", error=str(e))
                        progress.update(success=False)

            # Flush remaining batch
            if learner_batch:
                future = executor.submit(self._process_learner_batch, learner_batch)
                futures.append(future)

            # Wait for all batches to complete
            for future in as_completed(futures):
                try:
                    future.result()
                except Exception as e:
                    self.logger.error("Batch processing failed", error=str(e))
                    raise

        progress.finish()

    def _process_learner_batch(self, entities_batch: list) -> None:
        """Process a batch of learners (runs in worker thread)."""
        # Extract learners and temporal states
        learners = []
        learning_states = []
        professional_statuses = []
        learning_entries = []
        employment_entries = []
        skill_associations = []

        for entities in entities_batch:
            if entities.learner:
                learners.append(entities.learner)
                learning_states.extend(entities.learning_states)
                professional_statuses.extend(entities.professional_statuses)

                # Collect relationship data
                sand_id = entities.learner.sand_id
                if sand_id:
                    learning_entries.extend([(sand_id, e) for e in entities.learning_details_entries])
                    employment_entries.extend([(sand_id, e) for e in entities.employment_details_entries])
                    skill_associations.extend([(sand_id, s.id) for s in entities.skills])

        # Create learners
        if learners:
            learner_records = [self.loader._learner_to_dict(learner) for learner in learners]
            self.loader.batch_ops.batch_create_nodes("Learner", learner_records, "hashedEmail")

        # Create temporal states
        if learning_states:
            state_records = [
                {"state": s.state, "startDate": s.start_date, "endDate": s.end_date,
                 "isCurrent": s.is_current, "reason": s.reason}
                for s in learning_states
            ]
            self.loader.batch_ops.batch_execute("""
                UNWIND $records AS record
                MERGE (s:LearningState {state: record.state, startDate: record.startDate})
                SET s.endDate = record.endDate, s.isCurrent = record.isCurrent, s.reason = record.reason
            """, state_records)

        if professional_statuses:
            status_records = [
                {"status": s.status, "startDate": s.start_date, "endDate": s.end_date,
                 "isCurrent": s.is_current, "details": s.details}
                for s in professional_statuses
            ]
            self.loader.batch_ops.batch_execute("""
                UNWIND $records AS record
                MERGE (ps:ProfessionalStatus {status: record.status, startDate: record.startDate})
                SET ps.endDate = record.endDate, ps.isCurrent = record.isCurrent, ps.details = record.details
            """, status_records)

        # Create relationships
        if skill_associations:
            skill_rels = [
                {"from_id": sand_id, "to_id": skill_id, "properties": {}}
                for sand_id, skill_id in skill_associations
            ]
            self.loader.batch_ops.batch_create_relationships(
                "HAS_SKILL", "Learner", "sandId", "Skill", "id", skill_rels
            )

        if learning_entries:
            self.loader._batch_create_enrollment_relationships_from_list(learning_entries)

        if employment_entries:
            self.loader._batch_create_employment_relationships_from_list(employment_entries)

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
