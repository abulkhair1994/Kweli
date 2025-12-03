"""
State deriver for learning and professional status.

Derives temporal state from boolean flags (is_active_learner, is_graduate_learner, etc.)
and from employment_details JSON (which is more accurate than flags).

Also builds complete temporal histories from learning_details and employment_details arrays.
"""

from datetime import date

from structlog.types import FilteringBoundLogger

from kweli.etl.models.enums import LearningState, ProfessionalStatus
from kweli.etl.models.nodes import LearningStateNode, ProfessionalStatusNode
from kweli.etl.models.parsers import EmploymentDetailsEntry, LearningDetailsEntry
from kweli.etl.transformers.learning_state_history_builder import LearningStateHistoryBuilder
from kweli.etl.transformers.professional_status_history_builder import (
    ProfessionalStatusHistoryBuilder,
)
from kweli.etl.utils.logger import get_logger


class StateDeriver:
    """Derive learning state and professional status from flags."""

    def __init__(
        self,
        default_snapshot_date: str | date = "2025-10-06",
        inactive_gap_months: int = 6,
        unemployment_gap_months: int = 1,
        infer_initial_unemployment: bool = True,
        logger: FilteringBoundLogger | None = None,
    ) -> None:
        """
        Initialize state deriver.

        Args:
            default_snapshot_date: Default date for state snapshots
            inactive_gap_months: Gap in months to consider learner inactive
            unemployment_gap_months: Gap in months to consider unemployed
            infer_initial_unemployment: Create unemployed status before first job
            logger: Optional logger instance
        """
        self.logger = logger or get_logger(__name__)
        self.inactive_gap_months = inactive_gap_months
        self.unemployment_gap_months = unemployment_gap_months
        self.infer_initial_unemployment = infer_initial_unemployment

        # Parse snapshot date
        if isinstance(default_snapshot_date, str):
            parts = default_snapshot_date.split("-")
            self.snapshot_date = date(int(parts[0]), int(parts[1]), int(parts[2]))
        else:
            self.snapshot_date = default_snapshot_date

        # Initialize history builders
        self.learning_state_history_builder = LearningStateHistoryBuilder(
            inactive_gap_months=inactive_gap_months,
            logger=self.logger,
        )
        self.professional_status_history_builder = ProfessionalStatusHistoryBuilder(
            unemployment_gap_months=unemployment_gap_months,
            infer_initial_unemployment=infer_initial_unemployment,
            logger=self.logger,
        )

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

    def derive_learning_state_history(
        self,
        learning_details: list[LearningDetailsEntry],
        fallback_state: LearningState | None = None,
    ) -> list[LearningStateNode]:
        """
        Derive complete learning state history from learning_details array.

        This builds multiple LearningStateNode instances representing the full
        temporal timeline of state transitions.

        Args:
            learning_details: List of learning details entries
            fallback_state: State to use if no history can be built

        Returns:
            List of LearningStateNode instances in chronological order
        """
        # Build history from learning_details
        history = self.learning_state_history_builder.build_state_history(learning_details)

        # If no history could be built and we have a fallback state, create snapshot
        if not history and fallback_state:
            history = [self.create_learning_state_node(fallback_state)]

        return history

    def derive_professional_status_history(
        self,
        employment_details: list[EmploymentDetailsEntry],
        current_status_flags: dict[str, bool] | None = None,
        placement_is_venture: bool = False,
        fallback_status: ProfessionalStatus | None = None,
    ) -> list[ProfessionalStatusNode]:
        """
        Derive complete professional status history from employment_details array.

        This builds multiple ProfessionalStatusNode instances representing the full
        career progression timeline.

        Args:
            employment_details: List of employment details entries
            current_status_flags: Optional dict with is_wage, is_venture, is_freelancer
            placement_is_venture: Whether placement is a venture
            fallback_status: Status to use if no history can be built

        Returns:
            List of ProfessionalStatusNode instances in chronological order
        """
        # Build history from employment_details
        history = self.professional_status_history_builder.build_status_history(
            employment_details,
            current_status_flags=current_status_flags,
            placement_is_venture=placement_is_venture,
        )

        # If no history could be built and we have a fallback status, create snapshot
        if not history and fallback_status:
            history = [self.create_professional_status_node(fallback_status)]

        return history


__all__ = ["StateDeriver"]
