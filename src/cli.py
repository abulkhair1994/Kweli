"""
CLI for Impact Learners Knowledge Graph ETL.

Provides commands for running ETL, managing checkpoints, and viewing stats.
"""

from pathlib import Path

import click
import yaml

from etl.checkpoint import Checkpoint
from etl.two_phase_pipeline import TwoPhaseETLPipeline
from neo4j_ops.connection import Neo4jConnection
from neo4j_ops.indexes import setup_indexes
from utils.logger import get_logger


@click.group()
def cli():
    """Impact Learners Knowledge Graph ETL CLI."""
    pass


@cli.command()
@click.option(
    "--csv-path",
    type=click.Path(exists=True, path_type=Path),
    default=Path("data/raw/impact_learners_profile-1759316791571.csv"),
    help="Path to CSV file",
)
@click.option(
    "--config",
    type=click.Path(exists=True, path_type=Path),
    default=Path("config/settings.yaml"),
    help="Path to config file",
)
@click.option(
    "--resume/--no-resume",
    default=False,
    help="Resume from last checkpoint",
)
@click.option(
    "--progress/--no-progress",
    default=True,
    help="Show progress bar",
)
def run(csv_path: Path, config: Path, resume: bool, progress: bool):
    """Run the ETL pipeline."""
    logger = get_logger(__name__)

    try:
        # Load config
        with open(config) as f:
            cfg = yaml.safe_load(f)

        etl_cfg = cfg.get("etl", {})
        neo4j_cfg = cfg.get("neo4j", {})

        # Connect to Neo4j
        click.echo(f"Connecting to Neo4j at {neo4j_cfg.get('uri')}...")
        connection = Neo4jConnection(
            uri=neo4j_cfg.get("uri", "bolt://localhost:7687"),
            user=neo4j_cfg.get("user", "neo4j"),
            password=neo4j_cfg.get("password", "password"),
        )

        with connection:
            # Health check
            if not connection.health_check():
                click.echo("❌ Neo4j health check failed", err=True)
                raise click.Abort()

            click.echo("✓ Neo4j connection successful")

            # Setup indexes
            click.echo("Setting up indexes and constraints...")
            setup_indexes(connection)
            click.echo("✓ Indexes ready")

            # Run pipeline
            click.echo(f"\nStarting ETL pipeline for {csv_path}")
            if resume:
                click.echo("Resume mode: ON")

            pipeline = TwoPhaseETLPipeline(
                csv_path=csv_path,
                connection=connection,
                chunk_size=etl_cfg.get("chunk_size", 10000),
                batch_size=etl_cfg.get("batch_size", 1000),
                num_workers=etl_cfg.get("num_workers", 4),  # Read from config (default: 4)
                checkpoint_interval=etl_cfg.get("checkpoint_interval", 5000),
                enable_progress_bar=progress,
                logger=logger,
            )

            metrics = pipeline.run()

            # Display results
            click.echo("\n" + "=" * 60)
            click.echo("ETL COMPLETED SUCCESSFULLY")
            click.echo("=" * 60)
            click.echo(f"Rows processed: {metrics['rows_processed']:,}")
            click.echo(f"Processing rate: {metrics['processing_rate']:.2f} rows/sec")
            click.echo(f"Elapsed time: {metrics['elapsed_seconds']:.2f} seconds")
            click.echo(f"\nTotal nodes created: {metrics['total_nodes']:,}")
            click.echo("\nNodes by type:")
            for node_type, count in metrics["nodes_created"].items():
                click.echo(f"  {node_type}: {count:,}")

            quality = metrics["quality_metrics"]
            click.echo("\nQuality metrics:")
            click.echo(f"  Valid records: {quality['valid_records']:,}")
            click.echo(f"  Invalid records: {quality['invalid_records']:,}")
            click.echo(f"  Error rate: {quality['error_rate']:.2%}")

    except Exception as e:
        click.echo(f"❌ ETL failed: {e}", err=True)
        raise click.Abort() from e


@cli.command()
def checkpoint_status():
    """Show current checkpoint status."""
    checkpoint = Checkpoint()
    data = checkpoint.load()

    if not data:
        click.echo("No checkpoint found")
        return

    click.echo("Current Checkpoint:")
    click.echo(f"  Status: {data.get('status')}")
    click.echo(f"  Last row processed: {data.get('last_processed_row'):,}")
    click.echo(f"  Total rows: {data.get('total_rows'):,}")
    click.echo(f"  Progress: {data.get('progress_percent')}%")
    click.echo(f"  Started at: {data.get('started_at')}")
    click.echo(f"  Last checkpoint: {data.get('last_checkpoint_at')}")
    click.echo(f"  Errors: {data.get('errors', 0)}")

    nodes = data.get("nodes_created", {})
    if nodes:
        click.echo("\n  Nodes created:")
        for node_type, count in nodes.items():
            click.echo(f"    {node_type}: {count:,}")


@cli.command()
@click.confirmation_option(prompt="Are you sure you want to clear the checkpoint?")
def checkpoint_clear():
    """Clear the current checkpoint."""
    checkpoint = Checkpoint()
    checkpoint.clear()
    click.echo("✓ Checkpoint cleared")


@cli.command()
@click.option(
    "--config",
    type=click.Path(exists=True, path_type=Path),
    default=Path("config/settings.yaml"),
    help="Path to config file",
)
def test_connection(config: Path):
    """Test Neo4j connection."""
    with open(config) as f:
        cfg = yaml.safe_load(f)

    neo4j_cfg = cfg.get("neo4j", {})

    click.echo(f"Testing connection to {neo4j_cfg.get('uri')}...")

    try:
        connection = Neo4jConnection(
            uri=neo4j_cfg.get("uri", "bolt://localhost:7687"),
            user=neo4j_cfg.get("user", "neo4j"),
            password=neo4j_cfg.get("password", "password"),
        )

        with connection:
            if connection.health_check():
                click.echo("✓ Connection successful")
                click.echo("✓ Neo4j server is healthy")
            else:
                click.echo("❌ Health check failed", err=True)

    except Exception as e:
        click.echo(f"❌ Connection failed: {e}", err=True)
        raise click.Abort() from e


@cli.command()
@click.option(
    "--config",
    type=click.Path(exists=True, path_type=Path),
    default=Path("config/settings.yaml"),
    help="Path to config file",
)
@click.confirmation_option(
    prompt="⚠️  This will delete ALL data in Neo4j. Are you sure?"
)
def clear_database(config: Path):
    """Clear all nodes and relationships from Neo4j database."""
    logger = get_logger(__name__)

    with open(config) as f:
        cfg = yaml.safe_load(f)

    neo4j_cfg = cfg.get("neo4j", {})

    try:
        connection = Neo4jConnection(
            uri=neo4j_cfg.get("uri", "bolt://localhost:7687"),
            user=neo4j_cfg.get("user", "neo4j"),
            password=neo4j_cfg.get("password", "password"),
        )

        with connection:
            if not connection.health_check():
                click.echo("❌ Neo4j health check failed", err=True)
                raise click.Abort()

            click.echo("Clearing database...")

            # Count nodes before deletion
            count_query = "MATCH (n) RETURN count(n) as count"
            result = connection.execute_query(count_query)
            node_count = result[0]["count"] if result else 0

            click.echo(f"Found {node_count:,} nodes")

            # Delete all relationships first (in batches to avoid memory issues)
            click.echo("Deleting all relationships...")
            batch_size = 10000
            deleted_rels = 0
            while True:
                rel_query = f"MATCH ()-[r]->() WITH r LIMIT {batch_size} DELETE r RETURN count(r) as deleted"
                result = connection.execute_query(rel_query)
                count = result[0]["deleted"] if result else 0
                deleted_rels += count
                if count == 0:
                    break
                click.echo(f"  Deleted {deleted_rels:,} relationships...")

            # Delete all nodes (in batches to avoid memory issues)
            click.echo("Deleting all nodes...")
            deleted_nodes = 0
            while True:
                node_query = f"MATCH (n) WITH n LIMIT {batch_size} DELETE n RETURN count(n) as deleted"
                result = connection.execute_query(node_query)
                count = result[0]["deleted"] if result else 0
                deleted_nodes += count
                if count == 0:
                    break
                click.echo(f"  Deleted {deleted_nodes:,} nodes...")

            # Verify deletion
            result = connection.execute_query(count_query)
            remaining = result[0]["count"] if result else 0

            if remaining == 0:
                click.echo("✓ Database cleared successfully")
                logger.info("Database cleared", nodes_deleted=node_count)
            else:
                click.echo(f"⚠️  {remaining} nodes remaining", err=True)

    except Exception as e:
        click.echo(f"❌ Failed to clear database: {e}", err=True)
        raise click.Abort() from e


if __name__ == "__main__":
    cli()
