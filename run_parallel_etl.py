#!/usr/bin/env python3
"""
Run parallel ETL pipeline with optimizations.

This script:
1. Clears the Neo4j database
2. Sets up indexes and constraints
3. Runs the parallel ETL pipeline
"""

import sys
from pathlib import Path

from etl.two_phase_pipeline import TwoPhaseETLPipeline
from neo4j_ops.connection import Neo4jConnection
from neo4j_ops.indexes import IndexManager
from utils.config import get_settings
from utils.logger import get_logger

# Setup logger
logger = get_logger(__name__)


def main():
    """Run the parallel ETL pipeline."""
    # Load configuration
    settings = get_settings("config/settings.yaml")

    # CSV file path
    csv_path = Path("data/raw/impact_learners_profile-1759316791571.csv")
    if not csv_path.exists():
        logger.error("CSV file not found", path=str(csv_path))
        sys.exit(1)

    logger.info("Starting parallel ETL pipeline", csv_path=str(csv_path))

    # Connect to Neo4j
    connection = Neo4jConnection(
        uri=settings.neo4j.uri if hasattr(settings.neo4j, 'uri') else "bolt://localhost:7688",
        user="neo4j",
        password="password123",
        max_connection_pool_size=settings.neo4j.max_connection_pool_size,
    )

    try:
        connection.connect()
        logger.info("Connected to Neo4j", uri=connection.uri)

        # Step 1: Clear database
        logger.info("=" * 60)
        logger.info("STEP 1: Clearing Neo4j database")
        logger.info("=" * 60)
        connection.clear_database()
        logger.info("✅ Database cleared")

        # Step 2: Setup indexes and constraints
        logger.info("=" * 60)
        logger.info("STEP 2: Setting up indexes and constraints")
        logger.info("=" * 60)
        index_manager = IndexManager(connection)
        index_manager.create_all_constraints_and_indexes()
        logger.info("✅ Indexes and constraints created")

        # Step 3: Run parallel ETL pipeline
        logger.info("=" * 60)
        logger.info("STEP 3: Running parallel ETL pipeline")
        logger.info("=" * 60)

        # Get ETL config
        num_workers = settings.etl.max_workers
        chunk_size = settings.etl.chunk_size
        batch_size = settings.etl.batch_size

        logger.info(
            "Pipeline configuration",
            num_workers=num_workers,
            chunk_size=chunk_size,
            batch_size=batch_size,
        )

        pipeline = TwoPhaseETLPipeline(
            csv_path=csv_path,
            connection=connection,
            chunk_size=chunk_size,
            batch_size=batch_size,
            num_workers=num_workers,
            checkpoint_interval=settings.etl.checkpoint_interval,
            enable_progress_bar=settings.etl.enable_progress_bar,
        )

        # Run pipeline
        metrics = pipeline.run()

        # Step 4: Display results
        logger.info("=" * 60)
        logger.info("PIPELINE COMPLETE!")
        logger.info("=" * 60)
        logger.info("Final metrics", **metrics)

        # Calculate and display performance
        if metrics.get("processing_rate") and metrics.get("elapsed_seconds"):
            logger.info(
                "Performance summary",
                processing_rate=f"{metrics['processing_rate']:.0f} rows/sec",
                total_time=f"{metrics['elapsed_seconds'] / 60:.1f} minutes",
                speedup_vs_baseline=f"{metrics['processing_rate'] / 2250:.1f}x",
            )

        logger.info("✅ ETL pipeline completed successfully!")

    except KeyboardInterrupt:
        logger.warning("Pipeline interrupted by user")
        sys.exit(130)
    except Exception as e:
        logger.error("Pipeline failed", error=str(e), exc_info=True)
        sys.exit(1)
    finally:
        connection.close()
        logger.info("Neo4j connection closed")


if __name__ == "__main__":
    main()
