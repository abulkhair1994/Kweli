"""
ETL Checkpoint system.

Saves and loads ETL progress for resume capability.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from structlog.types import FilteringBoundLogger

from utils.logger import get_logger


class Checkpoint:
    """Manage ETL checkpoints."""

    def __init__(
        self,
        checkpoint_dir: Path | str = "data/checkpoints",
        logger: FilteringBoundLogger | None = None,
    ) -> None:
        """
        Initialize checkpoint manager.

        Args:
            checkpoint_dir: Directory for checkpoint files
            logger: Optional logger instance
        """
        self.checkpoint_dir = Path(checkpoint_dir)
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)
        self.logger = logger or get_logger(__name__)

        self.checkpoint_file = self.checkpoint_dir / "etl_latest.json"

    def save(
        self,
        last_processed_row: int,
        total_rows: int,
        nodes_created: dict[str, int],
        errors: int = 0,
        status: str = "in_progress",
    ) -> None:
        """
        Save checkpoint.

        Args:
            last_processed_row: Last row that was processed
            total_rows: Total rows in dataset
            nodes_created: Count of nodes created by type
            errors: Number of errors encountered
            status: Current status
        """
        checkpoint_data = {
            "last_processed_row": last_processed_row,
            "total_rows": total_rows,
            "started_at": self._get_start_time(),
            "last_checkpoint_at": datetime.utcnow().isoformat(),
            "nodes_created": nodes_created,
            "errors": errors,
            "status": status,
            "progress_percent": round((last_processed_row / total_rows) * 100, 2)
            if total_rows > 0
            else 0,
        }

        with open(self.checkpoint_file, "w") as f:
            json.dump(checkpoint_data, f, indent=2)

        self.logger.debug(
            "Saved checkpoint",
            row=last_processed_row,
            progress=f"{checkpoint_data['progress_percent']}%",
        )

    def load(self) -> dict[str, Any] | None:
        """
        Load latest checkpoint.

        Returns:
            Checkpoint data or None if no checkpoint exists
        """
        if not self.checkpoint_file.exists():
            self.logger.info("No checkpoint found")
            return None

        with open(self.checkpoint_file) as f:
            data = json.load(f)

        self.logger.info(
            "Loaded checkpoint",
            last_row=data.get("last_processed_row"),
            status=data.get("status"),
        )

        return data

    def clear(self) -> None:
        """Clear checkpoint file."""
        if self.checkpoint_file.exists():
            self.checkpoint_file.unlink()
            self.logger.info("Cleared checkpoint")

    def _get_start_time(self) -> str:
        """Get start time from existing checkpoint or create new."""
        existing = self.load()
        if existing and "started_at" in existing:
            return existing["started_at"]
        return datetime.utcnow().isoformat()


__all__ = ["Checkpoint"]
