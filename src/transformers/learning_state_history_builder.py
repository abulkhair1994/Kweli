"""
Learning state history builder.

Builds complete temporal learning state history from learning_details array,
creating multiple LearningStateNode instances to track state transitions over time.
"""

from datetime import date

from structlog.types import FilteringBoundLogger

from models.enums import LearningState
from models.nodes import LearningStateNode
from models.parsers import LearningDetailsEntry
from transformers.date_converter import DateConverter
from utils.logger import get_logger


class LearningStateHistoryBuilder:
    """Build complete learning state history from enrollment data."""

    def __init__(
        self,
        inactive_gap_months: int = 6,
        logger: FilteringBoundLogger | None = None,
    ) -> None:
        """
        Initialize learning state history builder.

        Args:
            inactive_gap_months: Gap in months to consider learner inactive
            logger: Optional logger instance
        """
        self.inactive_gap_months = inactive_gap_months
        self.logger = logger or get_logger(__name__)
        self.date_converter = DateConverter()

    def build_state_history(
        self,
        learning_details: list[LearningDetailsEntry],
        current_state_flags: dict[str, bool] | None = None,
    ) -> list[LearningStateNode]:
        """
        Build complete learning state history from learning_details.

        Logic:
        1. Sort programs by start date
        2. For each program:
           - Create "Active" state at program_start_date
           - Create end state (Graduate/Dropped Out) at appropriate date
        3. Between programs (gap > inactive_gap_months): create "Inactive" state
        4. Final state: use current_state_flags if provided

        Args:
            learning_details: List of learning details entries
            current_state_flags: Optional dict with is_active, is_graduate, is_dropped

        Returns:
            List of LearningStateNode instances in chronological order
        """
        if not learning_details:
            # No learning history - return empty list
            # (caller should create single snapshot state)
            return []

        # Convert to parsed entries with dates
        parsed_programs = self._parse_program_dates(learning_details)

        if not parsed_programs:
            # No valid dates found
            return []

        # Sort by start date
        parsed_programs.sort(key=lambda p: p["start_date"])

        # Build state timeline
        states: list[LearningStateNode] = []

        for i, program in enumerate(parsed_programs):
            # Create "Active" state at program start
            active_state = LearningStateNode(
                state=LearningState.ACTIVE,
                start_date=program["start_date"],
                end_date=None,  # Will be updated later
                is_current=False,  # Will be updated for last state
                reason=f"Enrolled in {program['program_name']} ({program['cohort_code']})",
            )

            # Determine end state based on enrollment_status
            end_state_type = self._determine_end_state(program["enrollment_status"])
            end_date = self._determine_end_date(program, end_state_type)

            if end_date:
                # Close the Active state
                active_state.end_date = end_date

                # Create end state (Graduate or Dropped Out)
                if end_state_type in (LearningState.GRADUATE, LearningState.DROPPED_OUT):
                    end_state = LearningStateNode(
                        state=end_state_type,
                        start_date=end_date,
                        end_date=None,  # Will be updated if there's a next program
                        is_current=False,
                        reason=self._get_end_reason(end_state_type, program),
                    )
                    states.extend([active_state, end_state])
                else:
                    # No clear end state, just keep Active
                    states.append(active_state)
            else:
                # Program ongoing, leave end_date as None
                states.append(active_state)

            # Check for gap to next program (create Inactive state)
            if i < len(parsed_programs) - 1:
                next_program = parsed_programs[i + 1]
                gap_days = (next_program["start_date"] - (end_date or program["start_date"])).days

                # If gap > inactive_gap_months, create Inactive state
                gap_threshold_days = self.inactive_gap_months * 30
                if gap_days > gap_threshold_days and end_date:
                    # Close the previous end state
                    if states and states[-1].end_date is None:
                        states[-1].end_date = end_date

                    # Create Inactive state
                    inactive_state = LearningStateNode(
                        state=LearningState.INACTIVE,
                        start_date=end_date,
                        end_date=next_program["start_date"],
                        is_current=False,
                        reason=f"Gap of {gap_days} days between programs",
                    )
                    states.append(inactive_state)

        # Mark the last state as current (if exists)
        if states:
            states[-1].is_current = True
            # If last state has no end_date, it's ongoing
            if states[-1].end_date is None:
                states[-1].end_date = None  # Keep as None for current state

        return states

    def _parse_program_dates(
        self,
        learning_details: list[LearningDetailsEntry],
    ) -> list[dict]:
        """
        Parse program dates and create structured program records.

        Args:
            learning_details: List of learning details entries

        Returns:
            List of parsed program dictionaries with dates
        """
        parsed = []

        for entry in learning_details:
            # Parse start date (required)
            start_date = self.date_converter.convert_date(entry.program_start_date)
            if not start_date:
                self.logger.warning(
                    "Skipping program with invalid start_date",
                    program_name=entry.program_name,
                    start_date=entry.program_start_date,
                )
                continue

            # Parse end dates (optional)
            end_date = self.date_converter.convert_date(entry.program_end_date)
            graduation_date = self.date_converter.convert_date(entry.program_graduation_date)

            parsed.append({
                "program_name": entry.program_name,
                "cohort_code": entry.cohort_code,
                "start_date": start_date,
                "end_date": end_date,
                "graduation_date": graduation_date,
                "enrollment_status": entry.enrollment_status.strip() if entry.enrollment_status else "",
            })

        return parsed

    def _determine_end_state(self, enrollment_status: str) -> LearningState:
        """
        Determine end state from enrollment_status.

        Args:
            enrollment_status: Status string from CSV

        Returns:
            LearningState enum
        """
        status_lower = enrollment_status.lower().strip()

        if "graduate" in status_lower or "completed" in status_lower:
            return LearningState.GRADUATE
        elif "drop" in status_lower or "withdraw" in status_lower:
            return LearningState.DROPPED_OUT
        elif "active" in status_lower or "enrolled" in status_lower:
            return LearningState.ACTIVE
        else:
            # Unknown status, default to ACTIVE
            return LearningState.ACTIVE

    def _determine_end_date(
        self,
        program: dict,
        end_state_type: LearningState,
    ) -> date | None:
        """
        Determine the end date for a program state.

        Args:
            program: Parsed program dictionary
            end_state_type: The end state type

        Returns:
            End date or None if ongoing
        """
        # For graduates, prefer graduation_date over end_date
        if end_state_type == LearningState.GRADUATE and program["graduation_date"]:
            return program["graduation_date"]

        # For dropped out or inactive, use end_date
        if end_state_type == LearningState.DROPPED_OUT and program["end_date"]:
            return program["end_date"]

        # For active programs, check if end_date is in the past
        if program["end_date"]:
            today = date.today()
            if program["end_date"] < today:
                # Program ended in the past
                return program["end_date"]

        # No clear end date, program may be ongoing
        return None

    def _get_end_reason(
        self,
        end_state_type: LearningState,
        program: dict,
    ) -> str:
        """
        Generate reason string for end state.

        Args:
            end_state_type: The end state type
            program: Parsed program dictionary

        Returns:
            Reason string
        """
        if end_state_type == LearningState.GRADUATE:
            return f"Graduated from {program['program_name']} ({program['cohort_code']})"
        elif end_state_type == LearningState.DROPPED_OUT:
            return f"Dropped out of {program['program_name']} ({program['cohort_code']})"
        else:
            return f"Status change in {program['program_name']}"


__all__ = ["LearningStateHistoryBuilder"]
