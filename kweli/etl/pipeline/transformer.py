"""
ETL Transformer.

Transforms CSV rows into graph entities (nodes and relationships).
"""

from typing import Any

from structlog.types import FilteringBoundLogger

from kweli.etl.models.nodes import (
    CityNode,
    CompanyNode,
    CountryNode,
    LearnerNode,
    LearningStateNode,
    ProfessionalStatusNode,
    ProgramNode,
    SkillNode,
)
from kweli.etl.transformers.date_converter import DateConverter
from kweli.etl.transformers.field_mapper import FieldMapper
from kweli.etl.transformers.geo_normalizer import GeoNormalizer
from kweli.etl.transformers.json_parser import JSONParser
from kweli.etl.transformers.skills_parser import SkillsParser
from kweli.etl.transformers.state_deriver import StateDeriver
from kweli.etl.utils.helpers import generate_id
from kweli.etl.utils.logger import get_logger


class GraphEntities:
    """Container for graph entities extracted from a learner record."""

    def __init__(self) -> None:
        """Initialize graph entities container."""
        self.learner: LearnerNode | None = None
        self.countries: list[CountryNode] = []
        self.cities: list[CityNode] = []
        self.skills: list[SkillNode] = []
        self.programs: list[ProgramNode] = []
        self.companies: list[CompanyNode] = []
        self.learning_states: list[LearningStateNode] = []
        self.professional_statuses: list[ProfessionalStatusNode] = []

        # Store raw entry data for relationship creation
        self.learning_details_entries: list[Any] = []
        self.employment_details_entries: list[Any] = []

        # Cache current job count and placement info for performance
        self.current_job_count: int = 0
        self.has_placement: bool = False
        self.placement_is_venture: bool = False


class Transformer:
    """Transform CSV data to graph entities."""

    def __init__(self, logger: FilteringBoundLogger | None = None) -> None:
        """Initialize transformer."""
        self.logger = logger or get_logger(__name__)

        # Initialize all transformers
        self.field_mapper = FieldMapper(logger)
        self.geo_normalizer = GeoNormalizer(logger=logger)
        self.skills_parser = SkillsParser(logger=logger)
        self.state_deriver = StateDeriver(logger=logger)
        self.date_converter = DateConverter(logger=logger)
        self.json_parser = JSONParser(logger)

    def _is_current_by_date(self, end_date: str | None) -> bool:
        """
        Determine if employment is current based on end_date.

        Logic:
        - No end_date (None, '', 'null') → Current
        - end_date = '9999-12-31' (sentinel) → Current
        - end_date >= snapshot_date → Current
        - end_date < snapshot_date → Past

        Args:
            end_date: End date string from CSV

        Returns:
            True if employment is current
        """
        from datetime import datetime

        # No end date means ongoing
        if not end_date or end_date.strip() in ["", "null", "None"]:
            return True

        # Sentinel value for ongoing
        if end_date == "9999-12-31":
            return True

        # Compare with snapshot date
        try:
            end = datetime.strptime(end_date, "%Y-%m-%d").date()
            # Use state_deriver's snapshot_date
            return end >= self.state_deriver.snapshot_date
        except (ValueError, AttributeError):
            # If can't parse, assume current (preserve data)
            return True

    def transform_row(self, row: dict[str, Any]) -> GraphEntities:
        """
        Transform a CSV row into graph entities.

        Args:
            row: CSV row as dictionary

        Returns:
            GraphEntities containing all nodes and relationships
        """
        entities = GraphEntities()

        try:
            # Map basic fields
            learner_dict = self.field_mapper.map_csv_row_to_dict(row)
            raw_fields = self.field_mapper.extract_raw_fields(row)

            # Process geographic data (HYBRID approach)
            self._process_geography(learner_dict, raw_fields, entities)

            # Process employment FIRST (parse employment_details to get current job info)
            # This must happen before _derive_states() so we can use accurate employment data
            self._process_employment(raw_fields, entities)

            # Process placement details (to determine employment type)
            self._process_placement(raw_fields, entities)

            # Derive states (now has access to employment and placement data)
            self._derive_states(learner_dict, raw_fields, entities)

            # Create learner node (hashedEmail is primary key, sandId can be null)
            entities.learner = LearnerNode(**learner_dict)

            # Process skills
            self._process_skills(raw_fields, entities)

            # Process learning details (programs & enrollments)
            self._process_learning_details(raw_fields, entities)

        except Exception as e:
            self.logger.error(
                "Failed to transform row",
                sand_id=row.get("sand_id"),
                error=str(e),
            )
            raise

        return entities

    def _process_geography(
        self,
        learner_dict: dict[str, Any],
        raw_fields: dict[str, Any],
        entities: GraphEntities,
    ) -> None:
        """Process geographic data (countries and cities)."""
        # Country of residence
        if raw_fields.get("country_of_residence"):
            country_node = self.geo_normalizer.create_country_node(
                raw_fields["country_of_residence"],
                raw_fields.get("country_of_residence_latitude"),
                raw_fields.get("country_of_residence_longitude"),
            )
            if country_node:
                entities.countries.append(country_node)
                learner_dict["country_of_residence_code"] = country_node.code

        # Country of origin
        if raw_fields.get("country_of_origin"):
            country_node = self.geo_normalizer.create_country_node(
                raw_fields["country_of_origin"]
            )
            if country_node:
                if country_node not in entities.countries:
                    entities.countries.append(country_node)
                learner_dict["country_of_origin_code"] = country_node.code

        # City of residence
        if raw_fields.get("city_of_residence") and learner_dict.get(
            "country_of_residence_code"
        ):
            city_node = self.geo_normalizer.create_city_node(
                raw_fields["city_of_residence"],
                learner_dict["country_of_residence_code"],
                raw_fields.get("city_of_residence_latitude"),
                raw_fields.get("city_of_residence_longitude"),
            )
            if city_node:
                entities.cities.append(city_node)
                learner_dict["city_of_residence_id"] = city_node.id

    def _derive_states(
        self,
        learner_dict: dict[str, Any],
        raw_fields: dict[str, Any],
        entities: GraphEntities,
    ) -> None:
        """Derive learning and professional states."""
        # Derive current learning state from flags (for learner's current_learning_state property)
        learning_state = self.state_deriver.derive_learning_state(
            raw_fields.get("is_active_learner"),
            raw_fields.get("is_graduate_learner"),
            raw_fields.get("is_a_dropped_out"),
        )
        learner_dict["current_learning_state"] = learning_state

        # Build FULL learning state history from learning_details
        learning_details_str = raw_fields.get("learning_details")
        if learning_details_str:
            # Parse learning_details to build temporal history
            learning_details_entries = self.json_parser.parse_learning_details(learning_details_str)
            learning_state_history = self.state_deriver.derive_learning_state_history(
                learning_details_entries,
                fallback_state=learning_state,  # Use derived state as fallback
            )
            entities.learning_states.extend(learning_state_history)
        else:
            # No learning_details, create single snapshot state
            learning_state_node = self.state_deriver.create_learning_state_node(learning_state)
            entities.learning_states.append(learning_state_node)

        # Derive current professional status (with current job count and placement info)
        prof_status = self.state_deriver.derive_professional_status(
            raw_fields.get("is_running_a_venture"),
            raw_fields.get("is_a_freelancer"),
            raw_fields.get("is_wage_employed"),
            current_job_count=entities.current_job_count,
            has_placement=entities.has_placement,
            placement_is_venture=entities.placement_is_venture,
        )
        learner_dict["current_professional_status"] = prof_status

        # Build FULL professional status history from employment_details
        employment_details_str = raw_fields.get("employment_details")
        if employment_details_str:
            # Parse employment_details to build temporal history
            employment_details_entries = self.json_parser.parse_employment_details(employment_details_str)

            # Prepare current status flags for history builder
            current_status_flags = {
                "is_wage": bool(raw_fields.get("is_wage_employed")),
                "is_venture": bool(raw_fields.get("is_running_a_venture")),
                "is_freelancer": bool(raw_fields.get("is_a_freelancer")),
            }

            prof_status_history = self.state_deriver.derive_professional_status_history(
                employment_details_entries,
                current_status_flags=current_status_flags,
                placement_is_venture=entities.placement_is_venture,
                fallback_status=prof_status,  # Use derived status as fallback
            )
            entities.professional_statuses.extend(prof_status_history)
        else:
            # No employment_details, create single snapshot status
            prof_status_node = self.state_deriver.create_professional_status_node(prof_status)
            entities.professional_statuses.append(prof_status_node)

    def _process_skills(
        self,
        raw_fields: dict[str, Any],
        entities: GraphEntities,
    ) -> None:
        """Process skills from skills_list."""
        skills_str = raw_fields.get("skills_list")
        if skills_str:
            skills = self.skills_parser.parse_skills(skills_str)
            entities.skills.extend(skills)

    def _process_learning_details(
        self,
        raw_fields: dict[str, Any],
        entities: GraphEntities,
    ) -> None:
        """Process learning_details JSON (programs)."""
        learning_details_str = raw_fields.get("learning_details")
        if learning_details_str:
            entries = self.json_parser.parse_learning_details(learning_details_str)

            for entry in entries:
                # Create Program node
                program = ProgramNode(
                    id=entry.cohort_code,
                    name=entry.program_name,
                    cohort_code=entry.cohort_code,
                    provider="ALX",  # Default provider
                )
                if program not in entities.programs:
                    entities.programs.append(program)

                # Store entry for relationship creation
                entities.learning_details_entries.append(entry)

    def _process_employment(
        self,
        raw_fields: dict[str, Any],
        entities: GraphEntities,
    ) -> None:
        """Process employment_details JSON (companies)."""
        employment_str = raw_fields.get("employment_details")
        if employment_str:
            entries = self.json_parser.parse_employment_details(employment_str)

            for entry in entries:
                # Determine current status based on end_date (temporal logic)
                is_current_employment = self._is_current_by_date(entry.end_date)

                # Count current jobs for performance optimization
                if is_current_employment:
                    entities.current_job_count += 1

                # Create Company node
                company_id = generate_id(entry.organization_name)
                company = CompanyNode(
                    id=company_id,
                    name=entry.organization_name,
                    country_code=None,  # Could parse from entry.country
                )

                # Avoid duplicates
                if not any(c.id == company.id for c in entities.companies):
                    entities.companies.append(company)

                # Store entry for relationship creation
                entities.employment_details_entries.append(entry)

    def _process_placement(
        self,
        raw_fields: dict[str, Any],
        entities: GraphEntities,
    ) -> None:
        """Process placement_details JSON to determine placement type."""
        placement_str = raw_fields.get("placement_details")
        if placement_str:
            # Parse placement_details (can be wage employment or venture)
            placement = self.json_parser.parse_placement_details(placement_str, is_venture=False)
            if not placement:
                # Try parsing as venture
                placement = self.json_parser.parse_placement_details(placement_str, is_venture=True)

            if placement:
                entities.has_placement = True
                # Check if it's a venture (has business_name) or wage employment
                entities.placement_is_venture = hasattr(placement, "business_name")


__all__ = ["Transformer", "GraphEntities"]
