"""
Professional status history builder.

Builds complete temporal professional status history from employment_details array,
creating multiple ProfessionalStatusNode instances to track career progression over time.
"""

from datetime import date, timedelta

from structlog.types import FilteringBoundLogger

from kweli.etl.models.enums import ProfessionalStatus
from kweli.etl.models.nodes import ProfessionalStatusNode
from kweli.etl.models.parsers import EmploymentDetailsEntry
from kweli.etl.transformers.date_converter import DateConverter
from kweli.etl.utils.logger import get_logger


class ProfessionalStatusHistoryBuilder:
    """Build complete professional status history from employment data."""

    def __init__(
        self,
        unemployment_gap_months: int = 1,
        infer_initial_unemployment: bool = True,
        logger: FilteringBoundLogger | None = None,
    ) -> None:
        """
        Initialize professional status history builder.

        Args:
            unemployment_gap_months: Gap in months to consider unemployed
            infer_initial_unemployment: Create unemployed status before first job
            logger: Optional logger instance
        """
        self.unemployment_gap_months = unemployment_gap_months
        self.infer_initial_unemployment = infer_initial_unemployment
        self.logger = logger or get_logger(__name__)
        self.date_converter = DateConverter()

    def build_status_history(
        self,
        employment_details: list[EmploymentDetailsEntry],
        current_status_flags: dict[str, bool] | None = None,
        placement_is_venture: bool = False,
    ) -> list[ProfessionalStatusNode]:
        """
        Build complete professional status history from employment_details.

        Logic:
        1. Sort employment by start date
        2. Create initial "Unemployed" state (if enabled)
        3. For each employment:
           - Create status at start_date (Wage Employed/Entrepreneur/Freelancer)
           - If gap > unemployment_gap_months from previous: create "Unemployed" in between
        4. After last employment ends: create "Unemployed"
        5. Use current_status_flags for final state

        Args:
            employment_details: List of employment details entries
            current_status_flags: Optional dict with is_wage, is_venture, is_freelancer
            placement_is_venture: Whether placement is a venture

        Returns:
            List of ProfessionalStatusNode instances in chronological order
        """
        if not employment_details:
            # No employment history - return empty list or initial unemployed
            if self.infer_initial_unemployment:
                return [self._create_unemployed_node(
                    start_date=None,  # Use snapshot date in caller
                    details="No employment history",
                )]
            return []

        # Parse employment entries with dates
        parsed_jobs = self._parse_employment_dates(employment_details, placement_is_venture)

        if not parsed_jobs:
            # No valid dates found
            if self.infer_initial_unemployment:
                return [self._create_unemployed_node(
                    start_date=None,
                    details="No valid employment dates",
                )]
            return []

        # Sort by start date
        parsed_jobs.sort(key=lambda j: j["start_date"])

        # Build status timeline
        statuses: list[ProfessionalStatusNode] = []

        # Initial unemployed state (before first job)
        if self.infer_initial_unemployment:
            first_job_start = parsed_jobs[0]["start_date"]
            unemployed_start = self._calculate_unemployed_start(first_job_start)

            initial_unemployed = ProfessionalStatusNode(
                status=ProfessionalStatus.UNEMPLOYED,
                start_date=unemployed_start,
                end_date=first_job_start,
                is_current=False,
                details="Before first employment",
            )
            statuses.append(initial_unemployed)

        # Process each employment
        for i, job in enumerate(parsed_jobs):
            # Check for unemployment gap from previous job
            if i > 0:
                prev_job = parsed_jobs[i - 1]
                prev_end = prev_job["end_date"] or date.today()
                current_start = job["start_date"]

                gap_days = (current_start - prev_end).days

                # If gap > threshold, create unemployed period
                gap_threshold_days = self.unemployment_gap_months * 30
                if gap_days > gap_threshold_days:
                    # Close previous status if still open
                    if statuses and statuses[-1].end_date is None:
                        statuses[-1].end_date = prev_end

                    unemployed_gap = ProfessionalStatusNode(
                        status=ProfessionalStatus.UNEMPLOYED,
                        start_date=prev_end,
                        end_date=current_start,
                        is_current=False,
                        details=f"Gap of {gap_days} days between jobs",
                    )
                    statuses.append(unemployed_gap)

            # Create employment status
            employment_status = self._create_employment_status_node(job)
            statuses.append(employment_status)

        # After last job: if it ended and no current employment, create unemployed
        last_job = parsed_jobs[-1]
        if last_job["end_date"] and not last_job["is_current"]:
            # Check if there's a current status from flags
            if current_status_flags:
                current_status = self._derive_current_status_from_flags(
                    current_status_flags,
                    placement_is_venture,
                )
                # Only create unemployed if current status is actually unemployed
                if current_status == ProfessionalStatus.UNEMPLOYED:
                    # Close last employment status
                    if statuses and statuses[-1].end_date is None:
                        statuses[-1].end_date = last_job["end_date"]

                    final_unemployed = ProfessionalStatusNode(
                        status=ProfessionalStatus.UNEMPLOYED,
                        start_date=last_job["end_date"],
                        end_date=None,
                        is_current=True,
                        details="After last employment ended",
                    )
                    statuses.append(final_unemployed)
                else:
                    # Has current employment not in employment_details (e.g., from placement)
                    # Close last employment status
                    if statuses and statuses[-1].end_date is None:
                        statuses[-1].end_date = last_job["end_date"]

                    # Create current status
                    current_node = ProfessionalStatusNode(
                        status=current_status,
                        start_date=last_job["end_date"],
                        end_date=None,
                        is_current=True,
                        details="Current status from placement/flags",
                    )
                    statuses.append(current_node)
            else:
                # No flags, assume unemployed after last job ended
                if statuses and statuses[-1].end_date is None:
                    statuses[-1].end_date = last_job["end_date"]

                final_unemployed = ProfessionalStatusNode(
                    status=ProfessionalStatus.UNEMPLOYED,
                    start_date=last_job["end_date"],
                    end_date=None,
                    is_current=True,
                    details="After last employment ended",
                )
                statuses.append(final_unemployed)

        # Mark the last status as current
        if statuses:
            statuses[-1].is_current = True

        return statuses

    def _parse_employment_dates(
        self,
        employment_details: list[EmploymentDetailsEntry],
        placement_is_venture: bool = False,
    ) -> list[dict]:
        """
        Parse employment dates and create structured job records.

        Args:
            employment_details: List of employment details entries
            placement_is_venture: Whether placement is a venture

        Returns:
            List of parsed job dictionaries with dates
        """
        parsed = []

        for entry in employment_details:
            # Parse start date (required)
            start_date = self.date_converter.convert_date(entry.start_date)
            if not start_date:
                self.logger.warning(
                    "Skipping job with invalid start_date",
                    organization_name=entry.organization_name,
                    start_date=entry.start_date,
                )
                continue

            # Parse end date (optional)
            end_date = self.date_converter.convert_date(entry.end_date)

            # Parse is_current flag
            is_current_str = entry.is_current.strip().lower() if entry.is_current else "0"
            is_current = is_current_str in ("1", "true", "yes")

            # Auto-correct: if end_date exists, is_current should be False
            if end_date and is_current:
                is_current = False

            # Classify employment type
            employment_type = self._classify_employment_type(
                entry.job_title,
                entry.organization_name,
                placement_is_venture,
            )

            parsed.append({
                "organization_name": entry.organization_name,
                "job_title": entry.job_title,
                "start_date": start_date,
                "end_date": end_date,
                "is_current": is_current,
                "employment_type": employment_type,
            })

        return parsed

    def _classify_employment_type(
        self,
        job_title: str,
        organization_name: str,
        placement_is_venture: bool = False,
    ) -> ProfessionalStatus:
        """
        Classify employment type from job details.

        Args:
            job_title: Job title
            organization_name: Organization name
            placement_is_venture: Whether placement is a venture

        Returns:
            ProfessionalStatus enum
        """
        # Check for venture/entrepreneur keywords
        venture_keywords = [
            "founder",
            "co-founder",
            "entrepreneur",
            "ceo",
            "owner",
            "venture",
            "startup",
        ]

        # Check for freelance keywords
        freelance_keywords = [
            "freelance",
            "freelancer",
            "consultant",
            "contractor",
            "self-employed",
        ]

        job_title_lower = job_title.lower() if job_title else ""
        org_name_lower = organization_name.lower() if organization_name else ""

        # Check if it's a venture
        if placement_is_venture or any(kw in job_title_lower or kw in org_name_lower for kw in venture_keywords):
            return ProfessionalStatus.ENTREPRENEUR

        # Check if it's freelance
        if any(kw in job_title_lower or kw in org_name_lower for kw in freelance_keywords):
            return ProfessionalStatus.FREELANCER

        # Default to wage employed
        return ProfessionalStatus.WAGE_EMPLOYED

    def _create_employment_status_node(self, job: dict) -> ProfessionalStatusNode:
        """
        Create ProfessionalStatusNode for an employment period.

        Args:
            job: Parsed job dictionary

        Returns:
            ProfessionalStatusNode
        """
        return ProfessionalStatusNode(
            status=job["employment_type"],
            start_date=job["start_date"],
            end_date=job["end_date"],
            is_current=job["is_current"],
            details=f"{job['job_title']} at {job['organization_name']}",
        )

    def _create_unemployed_node(
        self,
        start_date: date | None = None,
        end_date: date | None = None,
        details: str = "Unemployed",
    ) -> ProfessionalStatusNode:
        """
        Create ProfessionalStatusNode for unemployment period.

        Args:
            start_date: Start date
            end_date: End date
            details: Details about unemployment

        Returns:
            ProfessionalStatusNode
        """
        return ProfessionalStatusNode(
            status=ProfessionalStatus.UNEMPLOYED,
            start_date=start_date or date.today(),
            end_date=end_date,
            is_current=end_date is None,
            details=details,
        )

    def _calculate_unemployed_start(self, first_job_start: date) -> date:
        """
        Calculate when unemployed period should start before first job.

        For simplicity, we'll start 1 year before first job (or at age 18).

        Args:
            first_job_start: Start date of first job

        Returns:
            Unemployed start date
        """
        # Start 1 year before first job as a reasonable default
        # (We don't have birth date to calculate age 18)
        return first_job_start - timedelta(days=365)

    def _derive_current_status_from_flags(
        self,
        flags: dict[str, bool],
        placement_is_venture: bool = False,
    ) -> ProfessionalStatus:
        """
        Derive current professional status from flags.

        Args:
            flags: Dict with is_wage, is_venture, is_freelancer
            placement_is_venture: Whether placement is a venture

        Returns:
            ProfessionalStatus enum
        """
        is_venture = flags.get("is_venture", False)
        is_wage = flags.get("is_wage", False)
        is_freelancer = flags.get("is_freelancer", False)

        # Count current statuses
        status_count = sum([is_venture, is_wage, is_freelancer])

        if status_count >= 2:
            return ProfessionalStatus.MULTIPLE
        elif is_venture or placement_is_venture:
            return ProfessionalStatus.ENTREPRENEUR
        elif is_wage:
            return ProfessionalStatus.WAGE_EMPLOYED
        elif is_freelancer:
            return ProfessionalStatus.FREELANCER
        else:
            return ProfessionalStatus.UNEMPLOYED


__all__ = ["ProfessionalStatusHistoryBuilder"]
