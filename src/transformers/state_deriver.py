"""
State deriver for learning and professional status.

Derives temporal state from boolean flags (is_active_learner, is_graduate_learner, etc.)
and from employment_details JSON (which is more accurate than flags).
"""

from datetime import date

from structlog.types import FilteringBoundLogger

from models.enums import LearningState, ProfessionalStatus
from models.nodes import LearningStateNode, ProfessionalStatusNode
from utils.logger import get_logger


class StateDeriver:
    """Derive learning state and professional status from flags."""

    def __init__(
        self,
        default_snapshot_date: str | date = "2025-10-06",
        logger: FilteringBoundLogger | None = None,
    ) -> None:
        """
        Initialize state deriver.

        Args:
            default_snapshot_date: Default date for state snapshots
            logger: Optional logger instance
        """
        self.logger = logger or get_logger(__name__)

        # Parse snapshot date
        if isinstance(default_snapshot_date, str):
            parts = default_snapshot_date.split("-")
            self.snapshot_date = date(int(parts[0]), int(parts[1]), int(parts[2]))
        else:
            self.snapshot_date = default_snapshot_date

    def derive_learning_state(
        self,
        is_active: int | bool | None,
        is_graduate: int | bool | None,
        is_dropped: int | bool | None,
    ) -> LearningState:
        """
        Derive learning state from flags.

        Logic:
        - If is_graduate = 1 → Graduate
        - Else if is_dropped = 1 → Dropped Out
        - Else if is_active = 1 → Active
        - Else → Inactive

        Args:
            is_active: Is active learner flag
            is_graduate: Is graduate learner flag
            is_dropped: Is dropped out flag

        Returns:
            LearningState enum
        """
        # Convert to boolean
        is_active_bool = bool(is_active) if is_active else False
        is_graduate_bool = bool(is_graduate) if is_graduate else False
        is_dropped_bool = bool(is_dropped) if is_dropped else False

        # Apply logic
        if is_graduate_bool:
            return LearningState.GRADUATE
        elif is_dropped_bool:
            return LearningState.DROPPED_OUT
        elif is_active_bool:
            return LearningState.ACTIVE
        else:
            return LearningState.INACTIVE

    def derive_professional_status(
        self,
        is_venture: int | bool | None,
        is_freelancer: int | bool | None,  # noqa: ARG002
        is_wage: int | bool | None,
        current_job_count: int = 0,
        has_placement: bool = False,
        placement_is_venture: bool = False,
    ) -> ProfessionalStatus:
        """
        Derive professional status from employment_details (source of truth) and placement_details (type classification).

        Priority Logic:
        1. Check current_job_count from employment_details (actual current employment)
           - If >= 2 current jobs → Multiple
           - If 1 current job:
             - Use placement_details to determine type if available
             - If placement is venture → Entrepreneur
             - Otherwise → Wage Employed (default)
        2. Fall back to placement flags for recently placed learners (no employment_details yet)
           - If is_venture = 1 → Entrepreneur
           - If is_wage = 1 → Wage Employed
        3. No current employment → Unemployed

        Note: This uses employment_details as the source of truth (18.5% coverage)
              rather than unreliable flags (4.1% coverage). The flags only track
              official program placements and are not updated when learners self-report
              employment changes.

        Args:
            is_venture: Is running a venture flag (program placement only)
            is_freelancer: Is a freelancer flag (UNUSED in dataset)
            is_wage: Is wage employed flag (program placement only)
            current_job_count: Number of current jobs from employment_details
            has_placement: Whether learner has placement_details
            placement_is_venture: Whether placement is a venture (vs wage employment)

        Returns:
            ProfessionalStatus enum
        """
        # PRIORITY 1: Check actual current employment from employment_details
        # This is the source of truth - captures all employment (self-reported + placements)
        if current_job_count >= 2:
            return ProfessionalStatus.MULTIPLE

        elif current_job_count == 1:
            # Has one current job - determine type from placement if available
            if has_placement and placement_is_venture:
                return ProfessionalStatus.ENTREPRENEUR
            else:
                # Default to wage employed for current jobs
                # (Most jobs are wage employment, ventures are rare)
                return ProfessionalStatus.WAGE_EMPLOYED

        # PRIORITY 2: No current jobs - check placement flags for recently placed learners
        # (These learners may have been placed but haven't updated employment_details yet)
        is_venture_bool = bool(is_venture) if is_venture else False
        is_wage_bool = bool(is_wage) if is_wage else False

        if is_venture_bool:
            return ProfessionalStatus.ENTREPRENEUR
        elif is_wage_bool:
            return ProfessionalStatus.WAGE_EMPLOYED

        # PRIORITY 3: No current employment and no recent placement
        return ProfessionalStatus.UNEMPLOYED

    def create_learning_state_node(
        self,
        state: LearningState,
        start_date: date | None = None,
    ) -> LearningStateNode:
        """
        Create LearningStateNode (for temporal tracking).

        Args:
            state: Learning state
            start_date: When state began (defaults to snapshot date)

        Returns:
            LearningStateNode
        """
        return LearningStateNode(
            state=state,
            start_date=start_date or self.snapshot_date,
            end_date=None,
            is_current=True,
        )

    def create_professional_status_node(
        self,
        status: ProfessionalStatus,
        start_date: date | None = None,
    ) -> ProfessionalStatusNode:
        """
        Create ProfessionalStatusNode (for temporal tracking).

        Args:
            status: Professional status
            start_date: When status began (defaults to snapshot date)

        Returns:
            ProfessionalStatusNode
        """
        return ProfessionalStatusNode(
            status=status,
            start_date=start_date or self.snapshot_date,
            end_date=None,
            is_current=True,
        )


__all__ = ["StateDeriver"]
