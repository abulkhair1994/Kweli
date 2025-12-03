"""
Skills parser for converting comma-separated skills into Skill nodes.
"""

from structlog.types import FilteringBoundLogger

from kweli.etl.models.nodes import SkillNode
from kweli.etl.utils.helpers import normalize_skill_name, normalize_string
from kweli.etl.utils.logger import get_logger


class SkillsParser:
    """Parse skills from comma-separated strings."""

    def __init__(
        self,
        delimiter: str = ",",
        max_skills: int = 50,
        logger: FilteringBoundLogger | None = None,
    ) -> None:
        """
        Initialize skills parser.

        Args:
            delimiter: Delimiter for splitting skills
            max_skills: Maximum skills per learner
            logger: Optional logger instance
        """
        self.delimiter = delimiter
        self.max_skills = max_skills
        self.logger = logger or get_logger(__name__)

    def parse_skills(self, skills_str: str | None) -> list[SkillNode]:
        """
        Parse comma-separated skills string into SkillNode objects.

        Args:
            skills_str: Comma-separated skills string

        Returns:
            List of SkillNode objects

        Examples:
            "Python, Data Analysis, SQL" -> [
                SkillNode(id="python", name="Python"),
                SkillNode(id="data_analysis", name="Data Analysis"),
                SkillNode(id="sql", name="SQL"),
            ]
        """
        if not skills_str:
            return []

        # Split and clean
        raw_skills = [s.strip() for s in skills_str.split(self.delimiter)]
        raw_skills = [s for s in raw_skills if s and s.lower() not in ("n/a", "none")]

        # Check max limit
        if len(raw_skills) > self.max_skills:
            self.logger.warning(
                "Too many skills, truncating",
                skills_count=len(raw_skills),
                max_skills=self.max_skills,
            )
            raw_skills = raw_skills[: self.max_skills]

        # Create SkillNode objects
        skills: list[SkillNode] = []
        seen_ids: set[str] = set()

        for skill_name in raw_skills:
            normalized_name = normalize_string(skill_name)
            if not normalized_name:
                continue

            # Create skill ID
            skill_id = normalize_skill_name(normalized_name)

            # Skip duplicates
            if skill_id in seen_ids:
                continue

            seen_ids.add(skill_id)

            # Create SkillNode
            skills.append(
                SkillNode(
                    id=skill_id,
                    name=normalized_name,
                    category=self._categorize_skill(normalized_name),
                )
            )

        return skills

    def _categorize_skill(self, skill_name: str) -> str:
        """
        Categorize skill based on name (simple heuristic).

        Args:
            skill_name: Skill name

        Returns:
            Category string
        """
        skill_lower = skill_name.lower()

        # Technical skills
        technical_keywords = [
            "python",
            "java",
            "javascript",
            "sql",
            "data",
            "machine learning",
            "ai",
            "programming",
            "coding",
            "software",
            "development",
            "web",
            "cloud",
            "database",
        ]
        if any(keyword in skill_lower for keyword in technical_keywords):
            return "Technical"

        # Business skills
        business_keywords = [
            "management",
            "leadership",
            "strategy",
            "finance",
            "accounting",
            "marketing",
            "sales",
            "business",
        ]
        if any(keyword in skill_lower for keyword in business_keywords):
            return "Business"

        # Soft skills
        soft_keywords = [
            "communication",
            "teamwork",
            "problem solving",
            "critical thinking",
            "presentation",
            "collaboration",
        ]
        if any(keyword in skill_lower for keyword in soft_keywords):
            return "Soft Skill"

        # Default
        return "Other"


__all__ = ["SkillsParser"]
