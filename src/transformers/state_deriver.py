"""
State deriver for learning and professional status.

Derives temporal state from boolean flags (is_active_learner, is_graduate_learner, etc.)
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
        is_freelancer: int | bool | None,
        is_wage: int | bool | None,
    ) -> ProfessionalStatus:
        """
        Derive professional status from flags.

        Logic:
        - Count how many are 1
        - If > 1 → Multiple
        - If is_venture = 1 → Entrepreneur
        - If is_freelancer = 1 → Freelancer
        - If is_wage = 1 → Wage Employed
        - If all 0 → Unemployed

        Args:
            is_venture: Is running a venture flag
            is_freelancer: Is a freelancer flag
            is_wage: Is wage employed flag

        Returns:
            ProfessionalStatus enum
        """
        # Convert to boolean and count
        is_venture_bool = bool(is_venture) if is_venture else False
        is_freelancer_bool = bool(is_freelancer) if is_freelancer else False
        is_wage_bool = bool(is_wage) if is_wage else False

        active_count = sum([is_venture_bool, is_freelancer_bool, is_wage_bool])

        # Apply logic
        if active_count > 1:
            return ProfessionalStatus.MULTIPLE
        elif is_venture_bool:
            return ProfessionalStatus.ENTREPRENEUR
        elif is_freelancer_bool:
            return ProfessionalStatus.FREELANCER
        elif is_wage_bool:
            return ProfessionalStatus.WAGE_EMPLOYED
        else:
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
