"""
ETL Pipeline orchestrator.

Coordinates the full Extract-Transform-Load process from CSV to Neo4j.
"""

from pathlib import Path
from typing import Any

from structlog.types import FilteringBoundLogger

from kweli.etl.neo4j_ops.connection import Neo4jConnection
from kweli.etl.pipeline.batch_accumulator import BatchAccumulator
from kweli.etl.pipeline.checkpoint import Checkpoint
from kweli.etl.pipeline.extractor import Extractor
from kweli.etl.pipeline.loader import Loader
from kweli.etl.pipeline.progress import ProgressTracker
from kweli.etl.pipeline.transformer import Transformer
from kweli.etl.utils.logger import get_logger
from kweli.etl.validators.data_quality import DataQualityChecker, QualityMetrics


class ETLPipeline:
    """Orchestrate the ETL pipeline."""

    def __init__(
        self,
        csv_path: Path | str,
        connection: Neo4jConnection,
        chunk_size: int = 10000,
        batch_size: int = 1000,
        checkpoint_interval: int = 5000,
        enable_progress_bar: bool = True,
        resume_from_checkpoint: bool = False,
        logger: FilteringBoundLogger | None = None,
    ) -> None:
        """
        Initialize ETL pipeline.

        Args:
            csv_path: Path to CSV file
            connection: Neo4j connection
            chunk_size: Rows per chunk for CSV reading
            batch_size: Batch size for Neo4j operations
            checkpoint_interval: Save checkpoint every N rows
            enable_progress_bar: Show rich progress bar
            resume_from_checkpoint: Resume from last checkpoint
            logger: Optional logger instance
        """
        self.csv_path = Path(csv_path)
        self.connection = connection
        self.chunk_size = chunk_size
        self.batch_size = batch_size
        self.checkpoint_interval = checkpoint_interval
        self.enable_progress_bar = enable_progress_bar
        self.resume_from_checkpoint = resume_from_checkpoint
        self.logger = logger or get_logger(__name__)

        # Initialize components
        self.extractor = Extractor(csv_path, chunk_size, logger)
        self.transformer = Transformer(logger)
        self.loader = Loader(connection, logger)
        self.validator = DataQualityChecker(logger=logger)
        self.checkpoint = Checkpoint(logger=logger)
        self.accumulator = BatchAccumulator(batch_size=batch_size)

        # Metrics tracking
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
        self.rows_processed = 0
        self.start_row = 0

        # Progress tracker (initialized later with total rows)
        self.progress: ProgressTracker | None = None

    def run(self) -> dict[str, Any]:
        """
        Run the complete ETL pipeline.

        Returns:
            Dictionary of final metrics
        """
        try:
            # Get total rows
            total_rows = self.extractor.get_total_rows()
            self.logger.info("Starting ETL pipeline", total_rows=total_rows)

            # Handle resume from checkpoint
            if self.resume_from_checkpoint:
                checkpoint_data = self.checkpoint.load()
                if checkpoint_data:
                    self.start_row = checkpoint_data.get("last_processed_row", 0)
                    self.nodes_created = checkpoint_data.get("nodes_created", self.nodes_created)
                    self.logger.info("Resuming from checkpoint", start_row=self.start_row)

            # Initialize progress tracker
            remaining_rows = total_rows - self.start_row
            self.progress = ProgressTracker(
                total_rows=remaining_rows,
                enable_progress_bar=self.enable_progress_bar,
                log_interval=1000,
                logger=self.logger,
            )

            # Process data in chunks
            self._process_chunks()

            # Finalize
            progress_metrics = self.progress.finish() if self.progress else {}
            quality_metrics = self.validator.metrics

            # Save final checkpoint
            self.checkpoint.save(
                last_processed_row=self.rows_processed,
                total_rows=total_rows,
                nodes_created=self.nodes_created,
                errors=quality_metrics.invalid_records,
                status="completed",
            )

            # Return final metrics
            return self._build_final_metrics(progress_metrics, quality_metrics)

        except Exception as e:
            self.logger.error("ETL pipeline failed", error=str(e))
            # Save error checkpoint
            self.checkpoint.save(
                last_processed_row=self.rows_processed,
                total_rows=total_rows,
                nodes_created=self.nodes_created,
                status="failed",
            )
            raise

    def _process_chunks(self) -> None:
        """Process CSV data in chunks."""
        for chunk_df in self.extractor.extract_chunks():
            # Convert chunk to list of dicts
            rows = chunk_df.to_dicts()

            # Skip rows if resuming
            if self.start_row > 0:
                rows_to_skip = min(len(rows), self.start_row - self.rows_processed)
                rows = rows[rows_to_skip:]
                self.rows_processed += rows_to_skip
                if not rows:
                    continue

            # Process each row
            for row in rows:
                self._process_row(row)
                self.rows_processed += 1

                # Flush batch when full
                if self.accumulator.is_full():
                    self._flush_batch()

                # Save checkpoint periodically
                if self.rows_processed % self.checkpoint_interval == 0:
                    self._flush_batch()  # Flush before checkpoint
                    self._save_checkpoint()

            # Flush any remaining entities in this chunk
            if not self.accumulator.is_empty():
                self._flush_batch()

    def _process_row(self, row: dict[str, Any]) -> None:
        """
        Process a single CSV row.

        Args:
            row: CSV row as dictionary
        """
        try:
            # Transform row to graph entities
            entities = self.transformer.transform_row(row)

            # Add entities to batch accumulator
            if entities.learner:
                self.accumulator.add(
                    learner=entities.learner,
                    countries=entities.countries,
                    cities=entities.cities,
                    skills=entities.skills,
                    programs=entities.programs,
                    companies=entities.companies,
                    learning_states=entities.learning_states,
                    professional_statuses=entities.professional_statuses,
                    learning_entries=entities.learning_details_entries,
                    employment_entries=entities.employment_details_entries,
                )

                # Update metrics (approximate - de-duplication happens at flush)
                self._update_metrics(entities)

            # Update progress
            if self.progress:
                self.progress.update(success=True)

        except Exception as e:
            self.logger.warning(
                "Failed to process row",
                sand_id=row.get("sand_id"),
                error=str(e),
            )
            if self.progress:
                self.progress.update(success=False)

    def _update_metrics(self, entities) -> None:
        """Update node creation metrics."""
        if entities.learner:
            self.nodes_created["learners"] += 1

        self.nodes_created["countries"] += len(entities.countries)
        self.nodes_created["cities"] += len(entities.cities)
        self.nodes_created["skills"] += len(entities.skills)
        self.nodes_created["programs"] += len(entities.programs)
        self.nodes_created["companies"] += len(entities.companies)
        self.nodes_created["learning_states"] += len(entities.learning_states)
        self.nodes_created["professional_statuses"] += len(entities.professional_statuses)

    def _flush_batch(self) -> None:
        """Flush accumulated batch to Neo4j."""
        if self.accumulator.is_empty():
            return

        try:
            batch_data = self.accumulator.get_batch()
            batch_stats = self.accumulator.get_stats()

            self.logger.info("Flushing batch to Neo4j", **batch_stats)

            # Load batch to Neo4j
            self.loader.load_batch(batch_data)

            # Clear accumulator for next batch
            self.accumulator.clear()

        except Exception as e:
            self.logger.error("Failed to flush batch", error=str(e))
            raise

    def _save_checkpoint(self) -> None:
        """Save current progress to checkpoint."""
        self.checkpoint.save(
            last_processed_row=self.rows_processed,
            total_rows=self.extractor.get_total_rows(),
            nodes_created=self.nodes_created,
            errors=self.validator.metrics.invalid_records,
            status="in_progress",
        )

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
        }


__all__ = ["ETLPipeline"]
