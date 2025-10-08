"""
Main ETL execution script.

Run the complete ETL pipeline from CSV to Neo4j.
"""

import sys
from pathlib import Path

import yaml

from etl.pipeline import ETLPipeline
from neo4j_ops.connection import Neo4jConnection
from neo4j_ops.indexes import setup_indexes
from utils.logger import get_logger


def load_config(config_path: Path = Path("config/settings.yaml")) -> dict:
    """Load configuration from YAML file."""
    with open(config_path) as f:
        return yaml.safe_load(f)


def main() -> int:
    """Run ETL pipeline."""
    logger = get_logger(__name__)

    try:
        # Load configuration
        config = load_config()
        etl_config = config.get("etl", {})
        neo4j_config = config.get("neo4j", {})

        # CSV path
        csv_path = Path("data/raw/impact_learners_profile-1759316791571.csv")
        if not csv_path.exists():
            logger.error("CSV file not found", path=str(csv_path))
            return 1

        # Connect to Neo4j
        logger.info("Connecting to Neo4j", uri=neo4j_config.get("uri"))
        connection = Neo4jConnection(
            uri=neo4j_config.get("uri", "bolt://localhost:7687"),
            user=neo4j_config.get("user", "neo4j"),
            password=neo4j_config.get("password", "password"),
        )

        with connection:
            # Health check
            if not connection.health_check():
                logger.error("Neo4j health check failed")
                return 1

            logger.info("Neo4j connection successful")

            # Setup indexes (idempotent)
            logger.info("Setting up Neo4j indexes and constraints")
            setup_indexes(connection)

            # Create pipeline
            pipeline = ETLPipeline(
                csv_path=csv_path,
                connection=connection,
                chunk_size=etl_config.get("chunk_size", 10000),
                batch_size=etl_config.get("batch_size", 1000),
                checkpoint_interval=etl_config.get("checkpoint_interval", 5000),
                enable_progress_bar=True,
                resume_from_checkpoint=etl_config.get("resume_from_checkpoint", False),
                logger=logger,
            )

            # Run pipeline
            logger.info("Starting ETL pipeline")
            metrics = pipeline.run()

            # Log final metrics
            logger.info(
                "ETL pipeline completed successfully",
                **metrics,
            )

            return 0

    except KeyboardInterrupt:
        logger.warning("ETL pipeline interrupted by user")
        return 130

    except Exception as e:
        logger.error("ETL pipeline failed", error=str(e), exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
