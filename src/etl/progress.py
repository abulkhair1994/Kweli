"""
ETL Progress tracker.

Tracks and displays progress with metrics.
"""

from datetime import datetime
from typing import Any

from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TaskID,
    TextColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
)
from structlog.types import FilteringBoundLogger

from utils.logger import get_logger


class ProgressTracker:
    """Track ETL progress with metrics."""

    def __init__(
        self,
        total_rows: int,
        enable_progress_bar: bool = True,
        log_interval: int = 1000,
        logger: FilteringBoundLogger | None = None,
    ) -> None:
        """
        Initialize progress tracker.

        Args:
            total_rows: Total number of rows to process
            enable_progress_bar: Show rich progress bar
            log_interval: Log progress every N rows
            logger: Optional logger instance
        """
        self.total_rows = total_rows
        self.enable_progress_bar = enable_progress_bar
        self.log_interval = log_interval
        self.logger = logger or get_logger(__name__)

        # Metrics
        self.rows_processed = 0
        self.rows_succeeded = 0
        self.rows_failed = 0
        self.start_time = datetime.utcnow()
        self.last_log_time = self.start_time

        # Progress bar
        self.progress: Progress | None = None
        self.task_id: TaskID | None = None

        if enable_progress_bar:
            self._init_progress_bar()

    def _init_progress_bar(self) -> None:
        """Initialize rich progress bar."""
        self.progress = Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            MofNCompleteColumn(),
            TextColumn("•"),
            TimeElapsedColumn(),
            TextColumn("•"),
            TimeRemainingColumn(),
            TextColumn("• {task.fields[rate]:.0f} rows/sec"),
        )

        self.progress.start()
        self.task_id = self.progress.add_task(
            "Processing learner records",
            total=self.total_rows,
            rate=0.0,
        )

    def update(self, success: bool = True) -> None:
        """
        Update progress.

        Args:
            success: Whether the row was processed successfully
        """
        self.rows_processed += 1

        if success:
            self.rows_succeeded += 1
        else:
            self.rows_failed += 1

        # Update progress bar
        if self.progress and self.task_id is not None:
            rate = self._calculate_rate()
            self.progress.update(self.task_id, advance=1, rate=rate)

        # Log progress
        if self.rows_processed % self.log_interval == 0:
            self._log_progress()

    def _calculate_rate(self) -> float:
        """Calculate processing rate (rows/sec)."""
        elapsed = (datetime.utcnow() - self.start_time).total_seconds()
        if elapsed > 0:
            return self.rows_processed / elapsed
        return 0.0

    def _log_progress(self) -> None:
        """Log progress metrics."""
        elapsed = datetime.utcnow() - self.start_time
        rate = self._calculate_rate()
        progress_pct = (self.rows_processed / self.total_rows) * 100 if self.total_rows > 0 else 0

        self.logger.info(
            "ETL progress",
            processed=self.rows_processed,
            total=self.total_rows,
            progress_percent=round(progress_pct, 2),
            succeeded=self.rows_succeeded,
            failed=self.rows_failed,
            rate=round(rate, 2),
            elapsed=str(elapsed).split(".")[0],  # Remove microseconds
        )

        self.last_log_time = datetime.utcnow()

    def finish(self) -> dict[str, Any]:
        """
        Finish tracking and return final metrics.

        Returns:
            Dictionary of final metrics
        """
        if self.progress:
            self.progress.stop()

        # Final log
        self._log_progress()

        elapsed = datetime.utcnow() - self.start_time
        rate = self._calculate_rate()

        metrics = {
            "total_rows": self.total_rows,
            "rows_processed": self.rows_processed,
            "rows_succeeded": self.rows_succeeded,
            "rows_failed": self.rows_failed,
            "success_rate": round(
                (self.rows_succeeded / self.rows_processed) * 100, 2
            )
            if self.rows_processed > 0
            else 0,
            "error_rate": round((self.rows_failed / self.rows_processed) * 100, 2)
            if self.rows_processed > 0
            else 0,
            "elapsed_seconds": elapsed.total_seconds(),
            "average_rate": round(rate, 2),
        }

        self.logger.info("ETL completed", **metrics)

        return metrics


__all__ = ["ProgressTracker"]
