"""
Cypher query builder.

Builds parameterized MERGE queries for nodes and relationships.
"""

from typing import Any

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


class CypherBuilder:
    """Build Cypher queries for nodes and relationships."""

    @staticmethod
    def build_merge_learner(learner: LearnerNode) -> tuple[str, dict[str, Any]]:
        """
        Build MERGE query for Learner node.

        Args:
            learner: LearnerNode instance

        Returns:
            Tuple of (query, parameters)
        """
        query = """
        MERGE (l:Learner {hashedEmail: $hashed_email})
        SET l.sandId = $sand_id,
            l.fullName = $full_name,
            l.profilePhotoUrl = $profile_photo_url,
            l.bio = $bio,
            l.gender = $gender,
            l.educationLevel = $education_level,
            l.educationField = $education_field,
            l.countryOfResidenceCode = $country_of_residence_code,
            l.countryOfOriginCode = $country_of_origin_code,
            l.cityOfResidenceId = $city_of_residence_id,
            l.currentLearningState = $current_learning_state,
            l.currentProfessionalStatus = $current_professional_status,
            l.isPlaced = $is_placed,
            l.isFeatured = $is_featured,
            l.isRural = $is_rural,
            l.descriptionOfLivingLocation = $description_of_living_location,
            l.hasDisability = $has_disability,
            l.typeOfDisability = $type_of_disability,
            l.isFromLowIncomeHousehold = $is_from_low_income_household,
            l.snapshotId = $snapshot_id,
            l.updatedAt = datetime()
        RETURN l
        """

        params = {
            "sand_id": learner.sand_id,
            "hashed_email": learner.hashed_email,
            "full_name": learner.full_name,
            "profile_photo_url": learner.profile_photo_url,
            "bio": learner.bio,
            "gender": learner.gender,
            "education_level": learner.education_level,
            "education_field": learner.education_field,
            "country_of_residence_code": learner.country_of_residence_code,
            "country_of_origin_code": learner.country_of_origin_code,
            "city_of_residence_id": learner.city_of_residence_id,
            "current_learning_state": learner.current_learning_state,
            "current_professional_status": learner.current_professional_status,
            "is_placed": learner.is_placed,
            "is_featured": learner.is_featured,
            "is_rural": learner.is_rural,
            "description_of_living_location": learner.description_of_living_location,
            "has_disability": learner.has_disability,
            "type_of_disability": learner.type_of_disability,
            "is_from_low_income_household": learner.is_from_low_income_household,
            "snapshot_id": learner.snapshot_id,
        }

        return query, params

    @staticmethod
    def build_merge_country(country: CountryNode) -> tuple[str, dict[str, Any]]:
        """Build MERGE query for Country node."""
        query = """
        MERGE (c:Country {code: $code})
        SET c.name = $name,
            c.latitude = $latitude,
            c.longitude = $longitude
        RETURN c
        """

        params = {
            "code": country.code,
            "name": country.name,
            "latitude": country.latitude,
            "longitude": country.longitude,
        }

        return query, params

    @staticmethod
    def build_merge_city(city: CityNode) -> tuple[str, dict[str, Any]]:
        """Build MERGE query for City node."""
        query = """
        MERGE (c:City {id: $id})
        SET c.name = $name,
            c.countryCode = $country_code,
            c.latitude = $latitude,
            c.longitude = $longitude
        RETURN c
        """

        params = {
            "id": city.id,
            "name": city.name,
            "country_code": city.country_code,
            "latitude": city.latitude,
            "longitude": city.longitude,
        }

        return query, params

    @staticmethod
    def build_merge_skill(skill: SkillNode) -> tuple[str, dict[str, Any]]:
        """Build MERGE query for Skill node."""
        query = """
        MERGE (s:Skill {id: $id})
        SET s.name = $name,
            s.category = $category
        RETURN s
        """

        params = {
            "id": skill.id,
            "name": skill.name,
            "category": skill.category,
        }

        return query, params

    @staticmethod
    def build_merge_program(program: ProgramNode) -> tuple[str, dict[str, Any]]:
        """Build MERGE query for Program node."""
        query = """
        MERGE (p:Program {id: $id})
        SET p.name = $name,
            p.cohortCode = $cohort_code,
            p.provider = $provider
        RETURN p
        """

        params = {
            "id": program.id,
            "name": program.name,
            "cohort_code": program.cohort_code,
            "provider": program.provider,
        }

        return query, params

    @staticmethod
    def build_merge_company(company: CompanyNode) -> tuple[str, dict[str, Any]]:
        """Build MERGE query for Company node."""
        query = """
        MERGE (c:Company {id: $id})
        SET c.name = $name,
            c.industry = $industry,
            c.countryCode = $country_code
        RETURN c
        """

        params = {
            "id": company.id,
            "name": company.name,
            "industry": company.industry,
            "country_code": company.country_code,
        }

        return query, params

    @staticmethod
    def build_merge_learning_state(state: LearningStateNode) -> tuple[str, dict[str, Any]]:
        """Build MERGE query for LearningState node."""
        query = """
        CREATE (ls:LearningState {
            state: $state,
            startDate: date($start_date),
            endDate: CASE WHEN $end_date IS NOT NULL THEN date($end_date) ELSE null END,
            isCurrent: $is_current,
            reason: $reason
        })
        RETURN ls
        """

        params = {
            "state": state.state,
            "start_date": str(state.start_date),
            "end_date": str(state.end_date) if state.end_date else None,
            "is_current": state.is_current,
            "reason": state.reason,
        }

        return query, params

    @staticmethod
    def build_merge_professional_status(
        status: ProfessionalStatusNode,
    ) -> tuple[str, dict[str, Any]]:
        """Build MERGE query for ProfessionalStatus node."""
        query = """
        CREATE (ps:ProfessionalStatus {
            status: $status,
            startDate: date($start_date),
            endDate: CASE WHEN $end_date IS NOT NULL THEN date($end_date) ELSE null END,
            isCurrent: $is_current,
            details: $details
        })
        RETURN ps
        """

        params = {
            "status": status.status,
            "start_date": str(status.start_date),
            "end_date": str(status.end_date) if status.end_date else None,
            "is_current": status.is_current,
            "details": status.details,
        }

        return query, params


__all__ = ["CypherBuilder"]
