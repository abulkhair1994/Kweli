"""
CLI for Impact Learners Knowledge Graph ETL.

Provides commands for running ETL, managing checkpoints, and viewing stats.
Supports both CSV and MySQL data sources.
"""

from __future__ import annotations

import os
from pathlib import Path

import click
import yaml
from dotenv import load_dotenv

# Load .env file from project root (handles running from any directory)
# cli.py is at kweli/etl/cli.py, so .parent.parent.parent gets to project root
_project_root = Path(__file__).parent.parent.parent
_env_file = _project_root / ".env"
if _env_file.exists():
    load_dotenv(_env_file, override=True)
else:
    load_dotenv(override=True)  # Fallback to current directory

from kweli.etl.neo4j_ops.connection import Neo4jConnection
from kweli.etl.neo4j_ops.indexes import setup_indexes
from kweli.etl.pipeline.checkpoint import Checkpoint
from kweli.etl.pipeline.extractor import Extractor
from kweli.etl.pipeline.pipeline import ETLPipeline
from kweli.etl.pipeline.two_phase_pipeline import TwoPhaseETLPipeline
from kweli.etl.utils.logger import get_logger


@click.group()
def cli():
    """Impact Learners Knowledge Graph ETL CLI."""
    pass


@cli.command()
@click.option(
    "--source",
    type=click.Choice(["csv", "mysql", "parquet"], case_sensitive=False),
    default=None,
    help="Data source type (overrides config file)",
)
@click.option(
    "--csv-path",
    type=click.Path(exists=True, path_type=Path),
    default=None,
    help="Path to CSV file (required if source=csv)",
)
@click.option(
    "--parquet-path",
    type=click.Path(exists=True, path_type=Path),
    default=None,
    help="Path to Parquet file (required if source=parquet)",
)
@click.option(
    "--dry-run/--no-dry-run",
    default=False,
    help="Validate connections without running ETL",
)
@click.option(
    "--config",
    type=click.Path(exists=True, path_type=Path),
    default=Path("config/settings.yaml"),
    help="Path to config file",
)
@click.option(
    "--mode",
    type=click.Choice(["sequential", "parallel"], case_sensitive=False),
    default="parallel",
    help="ETL pipeline mode (sequential or parallel)",
)
@click.option(
    "--resume/--no-resume",
    default=False,
    help="Resume from last checkpoint",
)
@click.option(
    "--max-rows",
    type=int,
    default=None,
    help="Maximum rows to process (for testing)",
)
@click.option(
    "--progress/--no-progress",
    default=True,
    help="Show progress bar",
)
def run(
    source: str | None,
    csv_path: Path | None,
    parquet_path: Path | None,
    dry_run: bool,
    config: Path,
    mode: str,
    resume: bool,
    max_rows: int | None,
    progress: bool,
):
    """
    Run the ETL pipeline.

    Examples:

        # Run with Parquet source (recommended - fastest, no timeouts)
        uv run python -m kweli.etl.cli run --source parquet --parquet-path data/raw/learners.parquet

        # Run with MySQL source (may timeout for large tables)
        uv run python -m kweli.etl.cli run --source mysql

        # Dry run to validate connections
        uv run python -m kweli.etl.cli run --source mysql --dry-run

        # Run with CSV source
        uv run python -m kweli.etl.cli run --source csv --csv-path data/raw/file.csv

        # Resume interrupted run
        uv run python -m kweli.etl.cli run --source mysql --resume

        # Test with limited rows
        uv run python -m kweli.etl.cli run --source mysql --max-rows 1000
    """
    logger = get_logger(__name__)

    try:
        # Load config
        with open(config) as f:
            cfg = yaml.safe_load(f)

        etl_cfg = cfg.get("etl", {})
        neo4j_cfg = cfg.get("neo4j", {})
        data_source_cfg = cfg.get("data_source", {})

        # Determine source type
        source_type = source or data_source_cfg.get("type", "csv")

        # Build source configuration
        if source_type == "mysql":
            # Load MySQL config from settings + environment
            mysql_cfg = data_source_cfg.get("mysql", {})

            # Override with environment variables (for secrets)
            mysql_cfg["host"] = os.getenv("MYSQL_HOST", mysql_cfg.get("host", ""))
            mysql_cfg["port"] = int(os.getenv("MYSQL_PORT", mysql_cfg.get("port", 3306)))
            mysql_cfg["database"] = os.getenv(
                "MYSQL_DATABASE", mysql_cfg.get("database", "")
            )
            mysql_cfg["table"] = os.getenv(
                "MYSQL_TABLE", mysql_cfg.get("table", "impact_learners_profile")
            )
            mysql_cfg["user"] = os.getenv("MYSQL_USER", mysql_cfg.get("user", ""))
            mysql_cfg["password"] = os.getenv("MYSQL_PASSWORD", "")

            if not mysql_cfg["password"]:
                raise click.ClickException(
                    "MYSQL_PASSWORD environment variable is required for MySQL source"
                )

            click.echo(
                f"Source: MySQL ({mysql_cfg['host']}/{mysql_cfg['database']}.{mysql_cfg['table']})"
            )
        elif source_type == "parquet":
            # Parquet source - default to data/raw/learners.parquet
            parquet_path = parquet_path or Path(
                data_source_cfg.get("parquet", {}).get(
                    "path", "data/raw/learners.parquet"
                )
            )
            if not parquet_path.exists():
                raise click.ClickException(
                    f"Parquet file not found: {parquet_path}\n"
                    "Run 'export-parquet' first to create it from MySQL."
                )

            click.echo(f"Source: Parquet ({parquet_path})")
        else:
            # CSV source
            csv_path = csv_path or Path(
                data_source_cfg.get("csv", {}).get(
                    "path", "data/raw/impact_learners_profile-1759316791571.csv"
                )
            )
            if not csv_path.exists():
                raise click.ClickException(f"CSV file not found: {csv_path}")

            click.echo(f"Source: CSV ({csv_path})")

        # Build Neo4j configuration (with environment variable overrides)
        neo4j_uri = os.getenv("NEO4J_URI", neo4j_cfg.get("uri", "bolt://localhost:7687"))
        neo4j_user = os.getenv("NEO4J_USER", neo4j_cfg.get("user", "neo4j"))
        neo4j_password = os.getenv("NEO4J_PASSWORD", neo4j_cfg.get("password", ""))

        if not neo4j_password:
            raise click.ClickException(
                "NEO4J_PASSWORD environment variable is required"
            )

        # Detect if this is Aura
        is_aura = "databases.neo4j.io" in neo4j_uri
        click.echo(f"Target: Neo4j ({neo4j_uri}){' [Aura]' if is_aura else ''}")

        # Dry run mode - just validate connections
        if dry_run:
            click.echo("\n--- Dry Run Mode ---")

            # Test MySQL connection
            if source_type == "mysql":
                click.echo("\nTesting MySQL connection...")
                try:
                    from kweli.etl.transformers.mysql_reader import MySQLStreamReader

                    reader = MySQLStreamReader(
                        host=mysql_cfg["host"],
                        database=mysql_cfg["database"],
                        table=mysql_cfg["table"],
                        user=mysql_cfg["user"],
                        password=mysql_cfg["password"],
                        port=mysql_cfg.get("port", 3306),
                        use_ssl=mysql_cfg.get("use_ssl", True),
                    )
                    if not reader.test_connection():
                        raise click.ClickException("MySQL connection test failed")

                    total_rows = reader.get_total_rows()
                    columns = reader.get_columns()
                    sample = reader.read_sample(5)
                    click.echo(f"  Connected to {mysql_cfg['host']}")
                    click.echo(f"  Table: {mysql_cfg['table']}")
                    click.echo(f"  Total rows: {total_rows:,}")
                    click.echo(f"  Columns: {len(columns)}")
                    click.echo(f"  Sample rows retrieved: {len(sample)}")
                except Exception as e:
                    raise click.ClickException(f"MySQL connection failed: {e}") from e
            else:
                click.echo(f"\nCSV file exists: {csv_path}")
                extractor = Extractor.from_csv(csv_path)
                total_rows = extractor.get_total_rows()
                click.echo(f"  Total rows: {total_rows:,}")

            # Test Neo4j connection
            click.echo("\nTesting Neo4j connection...")
            try:
                conn = Neo4jConnection(
                    uri=neo4j_uri,
                    user=neo4j_user,
                    password=neo4j_password,
                    max_retries=neo4j_cfg.get("max_retries", 3),
                    retry_delay=neo4j_cfg.get("retry_delay", 1.0),
                )
                conn.connect()
                if not conn.health_check():
                    raise click.ClickException("Neo4j health check failed")
                node_count = conn.get_node_count()
                click.echo(f"  Connected to {neo4j_uri}")
                click.echo(f"  Is Aura: {conn.is_aura}")
                click.echo(f"  Encrypted: {conn.encrypted}")
                click.echo(f"  Current nodes: {node_count:,}")
                conn.close()
            except Exception as e:
                raise click.ClickException(f"Neo4j connection failed: {e}") from e

            click.echo("\n All connections validated successfully!")
            return

        # Connect to Neo4j
        click.echo(f"\nConnecting to Neo4j at {neo4j_uri}...")
        connection = Neo4jConnection(
            uri=neo4j_uri,
            user=neo4j_user,
            password=neo4j_password,
            max_connection_pool_size=neo4j_cfg.get("max_connection_pool_size", 30),
            connection_timeout=neo4j_cfg.get("connection_timeout", 30),
            max_transaction_retry_time=neo4j_cfg.get("max_transaction_retry_time", 60),
            max_retries=neo4j_cfg.get("max_retries", 3),
            retry_delay=neo4j_cfg.get("retry_delay", 1.0),
        )

        with connection:
            # Health check
            if not connection.health_check():
                click.echo("Neo4j health check failed", err=True)
                raise click.Abort()

            click.echo("Neo4j connection successful")

            # Setup indexes
            click.echo("Setting up indexes and constraints...")
            setup_indexes(connection)
            click.echo("Indexes ready")

            # Create extractor based on source type
            chunk_size = data_source_cfg.get(
                "chunk_size", etl_cfg.get("chunk_size", 10000)
            )

            if source_type == "mysql":
                extractor = Extractor.from_mysql(mysql_cfg, chunk_size=chunk_size)
            elif source_type == "parquet":
                extractor = Extractor.from_parquet(parquet_path, chunk_size=chunk_size)
            else:
                extractor = Extractor.from_csv(csv_path, chunk_size=chunk_size)

            # Run pipeline
            click.echo(f"\nStarting ETL pipeline ({mode} mode)")
            if resume:
                click.echo("Resume mode: ON")
            if max_rows:
                click.echo(f"Max rows: {max_rows:,}")

            if mode == "parallel":
                pipeline = TwoPhaseETLPipeline(
                    csv_path=csv_path if source_type == "csv" else None,
                    connection=connection,
                    chunk_size=chunk_size,
                    batch_size=etl_cfg.get("batch_size", 1000),
                    num_workers=etl_cfg.get("num_workers", 4),
                    checkpoint_interval=etl_cfg.get("checkpoint_interval", 5000),
                    enable_progress_bar=progress,
                    logger=logger,
                    # Pass the extractor for MySQL and Parquet modes
                    extractor=extractor if source_type in ("mysql", "parquet") else None,
                )
            else:  # sequential
                pipeline = ETLPipeline(
                    csv_path=csv_path if source_type == "csv" else None,
                    connection=connection,
                    chunk_size=chunk_size,
                    batch_size=etl_cfg.get("batch_size", 1000),
                    checkpoint_interval=etl_cfg.get("checkpoint_interval", 5000),
                    enable_progress_bar=progress,
                    resume_from_checkpoint=resume,
                    logger=logger,
                    # Pass the extractor for MySQL and Parquet modes
                    extractor=extractor if source_type in ("mysql", "parquet") else None,
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

    except click.ClickException:
        raise
    except Exception as e:
        click.echo(f"ETL failed: {e}", err=True)
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
    click.echo("Checkpoint cleared")


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
    neo4j_uri = os.getenv("NEO4J_URI", neo4j_cfg.get("uri", "bolt://localhost:7687"))
    neo4j_user = os.getenv("NEO4J_USER", neo4j_cfg.get("user", "neo4j"))
    neo4j_password = os.getenv("NEO4J_PASSWORD", neo4j_cfg.get("password", "password"))

    click.echo(f"Testing connection to {neo4j_uri}...")

    try:
        connection = Neo4jConnection(
            uri=neo4j_uri,
            user=neo4j_user,
            password=neo4j_password,
        )

        with connection:
            if connection.health_check():
                click.echo("Connection successful")
                click.echo("Neo4j server is healthy")
                click.echo(f"Is Aura: {connection.is_aura}")
                click.echo(f"Encrypted: {connection.encrypted}")
            else:
                click.echo("Health check failed", err=True)

    except Exception as e:
        click.echo(f"Connection failed: {e}", err=True)
        raise click.Abort() from e


@cli.command()
@click.option(
    "--source",
    type=click.Choice(["csv", "mysql"], case_sensitive=False),
    default=None,
    help="Data source type",
)
@click.option(
    "--csv-path",
    type=click.Path(exists=True, path_type=Path),
    default=None,
    help="Path to CSV file",
)
@click.option(
    "--config",
    type=click.Path(exists=True, path_type=Path),
    default=Path("config/settings.yaml"),
    help="Path to config file",
)
def test_source(source: str | None, csv_path: Path | None, config: Path):
    """Test data source connection."""
    with open(config) as f:
        cfg = yaml.safe_load(f)

    data_source_cfg = cfg.get("data_source", {})
    source_type = source or data_source_cfg.get("type", "csv")

    if source_type == "mysql":
        mysql_cfg = data_source_cfg.get("mysql", {})
        mysql_cfg["host"] = os.getenv("MYSQL_HOST", mysql_cfg.get("host", ""))
        mysql_cfg["database"] = os.getenv("MYSQL_DATABASE", mysql_cfg.get("database", ""))
        mysql_cfg["table"] = os.getenv(
            "MYSQL_TABLE", mysql_cfg.get("table", "impact_learners_profile")
        )
        mysql_cfg["user"] = os.getenv("MYSQL_USER", mysql_cfg.get("user", ""))
        mysql_cfg["password"] = os.getenv("MYSQL_PASSWORD", "")

        if not mysql_cfg["password"]:
            raise click.ClickException("MYSQL_PASSWORD environment variable is required")

        click.echo(f"Testing MySQL connection to {mysql_cfg['host']}...")

        try:
            from kweli.etl.transformers.mysql_reader import MySQLStreamReader

            reader = MySQLStreamReader(
                host=mysql_cfg["host"],
                database=mysql_cfg["database"],
                table=mysql_cfg["table"],
                user=mysql_cfg["user"],
                password=mysql_cfg["password"],
                port=mysql_cfg.get("port", 3306),
                use_ssl=mysql_cfg.get("use_ssl", True),
            )

            if reader.test_connection():
                click.echo("Connection successful")
                click.echo(f"Database: {mysql_cfg['database']}")
                click.echo(f"Table: {mysql_cfg['table']}")
                click.echo(f"Total rows: {reader.get_total_rows():,}")
                click.echo(f"Columns: {len(reader.get_columns())}")
            else:
                click.echo("Connection test failed", err=True)
                raise click.Abort()

        except Exception as e:
            click.echo(f"MySQL connection failed: {e}", err=True)
            raise click.Abort() from e

    else:
        csv_file = csv_path or Path(
            data_source_cfg.get("csv", {}).get(
                "path", "data/raw/impact_learners_profile-1759316791571.csv"
            )
        )

        if not csv_file.exists():
            raise click.ClickException(f"CSV file not found: {csv_file}")

        click.echo(f"Testing CSV file: {csv_file}")

        try:
            extractor = Extractor.from_csv(csv_file)
            click.echo("CSV file accessible")
            click.echo(f"Total rows: {extractor.get_total_rows():,}")
            click.echo(f"Columns: {len(extractor.get_columns())}")
        except Exception as e:
            click.echo(f"CSV read failed: {e}", err=True)
            raise click.Abort() from e


@cli.command()
@click.option(
    "--config",
    type=click.Path(exists=True, path_type=Path),
    default=Path("config/settings.yaml"),
    help="Path to config file",
)
@click.confirmation_option(
    prompt="This will delete ALL data in Neo4j. Are you sure?"
)
def clear_database(config: Path):
    """Clear all nodes and relationships from Neo4j database."""
    logger = get_logger(__name__)

    with open(config) as f:
        cfg = yaml.safe_load(f)

    neo4j_cfg = cfg.get("neo4j", {})
    neo4j_uri = os.getenv("NEO4J_URI", neo4j_cfg.get("uri", "bolt://localhost:7687"))
    neo4j_user = os.getenv("NEO4J_USER", neo4j_cfg.get("user", "neo4j"))
    neo4j_password = os.getenv("NEO4J_PASSWORD", neo4j_cfg.get("password", "password"))

    try:
        connection = Neo4jConnection(
            uri=neo4j_uri,
            user=neo4j_user,
            password=neo4j_password,
        )

        with connection:
            if not connection.health_check():
                click.echo("Neo4j health check failed", err=True)
                raise click.Abort()

            click.echo("Clearing database...")

            # Count nodes before deletion
            node_count = connection.get_node_count()
            click.echo(f"Found {node_count:,} nodes")

            # Delete all relationships first (in batches)
            click.echo("Deleting all relationships...")
            batch_size = 10000
            deleted_rels = 0
            while True:
                rel_query = f"""
                    MATCH ()-[r]->()
                    WITH r LIMIT {batch_size}
                    DELETE r
                    RETURN count(r) as deleted
                """
                result = connection.execute_query(rel_query)
                count = result[0]["deleted"] if result else 0
                deleted_rels += count
                if count == 0:
                    break
                click.echo(f"  Deleted {deleted_rels:,} relationships...")

            # Delete all nodes (in batches)
            click.echo("Deleting all nodes...")
            deleted_nodes = 0
            while True:
                node_query = f"""
                    MATCH (n)
                    WITH n LIMIT {batch_size}
                    DELETE n
                    RETURN count(n) as deleted
                """
                result = connection.execute_query(node_query)
                count = result[0]["deleted"] if result else 0
                deleted_nodes += count
                if count == 0:
                    break
                click.echo(f"  Deleted {deleted_nodes:,} nodes...")

            # Verify deletion
            remaining = connection.get_node_count()

            if remaining == 0:
                click.echo("Database cleared successfully")
                logger.info("Database cleared", nodes_deleted=node_count)
            else:
                click.echo(f"{remaining} nodes remaining", err=True)

    except Exception as e:
        click.echo(f"Failed to clear database: {e}", err=True)
        raise click.Abort() from e


@cli.command("export-parquet")
@click.option(
    "--output",
    type=click.Path(path_type=Path),
    default=Path("data/raw/learners.parquet"),
    help="Output Parquet file path",
)
@click.option(
    "--config",
    type=click.Path(exists=True, path_type=Path),
    default=Path("config/settings.yaml"),
    help="Path to config file",
)
@click.option(
    "--chunk-size",
    type=int,
    default=50000,
    help="Rows per chunk during export",
)
def export_parquet(output: Path, config: Path, chunk_size: int):
    """
    Export MySQL table to Parquet file.

    This creates a local Parquet file from the MySQL table, which can then
    be used for ETL without risk of MySQL connection timeouts.

    Examples:

        # Export to default location
        uv run python -m kweli.etl.cli export-parquet

        # Export to custom path
        uv run python -m kweli.etl.cli export-parquet --output data/exports/learners.parquet

        # Then run ETL from Parquet
        uv run python -m kweli.etl.cli run --source parquet
    """
    logger = get_logger(__name__)

    try:
        # Load config
        with open(config) as f:
            cfg = yaml.safe_load(f)

        data_source_cfg = cfg.get("data_source", {})
        mysql_cfg = data_source_cfg.get("mysql", {})

        # Override with environment variables
        mysql_cfg["host"] = os.getenv("MYSQL_HOST", mysql_cfg.get("host", ""))
        mysql_cfg["port"] = int(os.getenv("MYSQL_PORT", mysql_cfg.get("port", 3306)))
        mysql_cfg["database"] = os.getenv("MYSQL_DATABASE", mysql_cfg.get("database", ""))
        mysql_cfg["table"] = os.getenv(
            "MYSQL_TABLE", mysql_cfg.get("table", "impact_learners_profile")
        )
        mysql_cfg["user"] = os.getenv("MYSQL_USER", mysql_cfg.get("user", ""))
        mysql_cfg["password"] = os.getenv("MYSQL_PASSWORD", "")

        if not mysql_cfg["password"]:
            raise click.ClickException(
                "MYSQL_PASSWORD environment variable is required"
            )

        click.echo(f"Source: MySQL ({mysql_cfg['host']}/{mysql_cfg['database']}.{mysql_cfg['table']})")
        click.echo(f"Output: {output}")
        click.echo(f"Chunk size: {chunk_size:,}")
        click.echo()

        # Create output directory if needed
        output.parent.mkdir(parents=True, exist_ok=True)

        # Run export
        from kweli.etl.transformers.mysql_to_parquet import MySQLToParquetExporter

        exporter = MySQLToParquetExporter(
            host=mysql_cfg["host"],
            database=mysql_cfg["database"],
            table=mysql_cfg["table"],
            user=mysql_cfg["user"],
            password=mysql_cfg["password"],
            port=mysql_cfg.get("port", 3306),
            use_ssl=mysql_cfg.get("use_ssl", True),
            chunk_size=chunk_size,
            logger=logger,
        )

        stats = exporter.export(output)

        # Display results
        click.echo()
        click.echo("=" * 60)
        click.echo("EXPORT COMPLETED SUCCESSFULLY")
        click.echo("=" * 60)
        click.echo(f"Rows exported: {stats['rows_exported']:,}")
        click.echo(f"Elapsed time: {stats['elapsed_seconds']:.2f} seconds")
        click.echo(f"Rate: {stats['rate_rows_per_sec']:.1f} rows/sec")
        click.echo(f"File size: {stats['file_size_mb']:.2f} MB")
        click.echo(f"Compression: {stats['compression']}")
        click.echo(f"\nOutput file: {stats['output_file']}")
        click.echo()
        click.echo("Next step: Run ETL from Parquet file:")
        click.echo(f"  uv run python -m kweli.etl.cli run --source parquet --parquet-path {output}")

    except click.ClickException:
        raise
    except Exception as e:
        click.echo(f"Export failed: {e}", err=True)
        logger.error("Parquet export failed", error=str(e))
        raise click.Abort() from e


if __name__ == "__main__":
    cli()
