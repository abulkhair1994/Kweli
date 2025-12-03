"""Pre-built analytics tools for common queries."""

from typing import Any

from langchain_core.tools import tool

# Note: These tools will be bound to a Neo4j executor at runtime
# For now, they return the Cypher query strings


@tool
def get_top_countries_by_learners(limit: int = 10) -> dict[str, Any]:
    """
    Get the top countries by learner count.

    Uses the HYBRID approach: filters by country code property,
    then joins with Country nodes for metadata.

    Args:
        limit: Number of top countries to return (default: 10, max: 100)

    Returns:
        Dict with Cypher query and parameters
    """
    limit = min(limit, 100)  # Cap at 100

    query = """
    MATCH (l:Learner)
    WHERE l.countryOfResidenceCode IS NOT NULL
    WITH l.countryOfResidenceCode as countryCode, count(l) as learnerCount
    MATCH (c:Country {code: countryCode})
    RETURN c.name as country, c.code as countryCode, learnerCount
    ORDER BY learnerCount DESC
    LIMIT $limit
    """

    return {
        "query": query,
        "params": {"limit": limit},
        "description": f"Top {limit} countries by learner count",
    }


@tool
def get_program_completion_rates(program_name: str | None = None, limit: int = 20) -> dict[str, Any]:
    """
    Get program completion rates.

    Args:
        program_name: Optional program name filter
        limit: Number of programs to return (default: 20, max: 100)

    Returns:
        Dict with Cypher query and parameters
    """
    limit = min(limit, 100)

    if program_name:
        query = """
        MATCH (p:Program {name: $program_name})<-[e:ENROLLED_IN]-(l:Learner)
        WITH p.name as program,
             count(l) as totalEnrolled,
             sum(CASE WHEN e.enrollmentStatus IN ['Graduated', 'Completed'] THEN 1 ELSE 0 END) as completed,
             sum(CASE WHEN e.enrollmentStatus = 'Dropped Out' THEN 1 ELSE 0 END) as droppedOut
        RETURN program, totalEnrolled, completed, droppedOut,
               round(100.0 * completed / totalEnrolled, 2) as completionRate,
               round(100.0 * droppedOut / totalEnrolled, 2) as dropoutRate
        """
        params = {"program_name": program_name}
    else:
        query = """
        MATCH (p:Program)<-[e:ENROLLED_IN]-(l:Learner)
        WITH p.name as program,
             count(l) as totalEnrolled,
             sum(CASE WHEN e.enrollmentStatus IN ['Graduated', 'Completed'] THEN 1 ELSE 0 END) as completed,
             sum(CASE WHEN e.enrollmentStatus = 'Dropped Out' THEN 1 ELSE 0 END) as droppedOut
        RETURN program, totalEnrolled, completed, droppedOut,
               round(100.0 * completed / totalEnrolled, 2) as completionRate,
               round(100.0 * droppedOut / totalEnrolled, 2) as dropoutRate
        ORDER BY completionRate DESC
        LIMIT $limit
        """
        params = {"limit": limit}

    return {
        "query": query,
        "params": params,
        "description": f"Program completion rates{' for ' + program_name if program_name else ''}",
    }


@tool
def get_employment_rate_by_program(program_name: str | None = None, limit: int = 20) -> dict[str, Any]:
    """
    Get employment rate by program.

    Args:
        program_name: Optional program name filter
        limit: Number of programs to return (default: 20, max: 100)

    Returns:
        Dict with Cypher query and parameters
    """
    limit = min(limit, 100)

    if program_name:
        query = """
        MATCH (p:Program {name: $program_name})<-[:ENROLLED_IN]-(l:Learner)
        WITH p.name as program, count(DISTINCT l) as totalLearners
        MATCH (p2:Program {name: program})<-[:ENROLLED_IN]-(l2:Learner)-[:WORKS_FOR]->(c:Company)
        WITH program, totalLearners, count(DISTINCT l2) as employedLearners
        RETURN program, totalLearners, employedLearners,
               round(100.0 * employedLearners / totalLearners, 2) as employmentRate
        """
        params = {"program_name": program_name}
    else:
        query = """
        MATCH (p:Program)<-[:ENROLLED_IN]-(l:Learner)
        WITH p.name as program, count(DISTINCT l) as totalLearners
        MATCH (p2:Program {name: program})<-[:ENROLLED_IN]-(l2:Learner)-[:WORKS_FOR]->(c:Company)
        WITH program, totalLearners, count(DISTINCT l2) as employedLearners
        WHERE totalLearners > 100
        RETURN program, totalLearners, employedLearners,
               round(100.0 * employedLearners / totalLearners, 2) as employmentRate
        ORDER BY employmentRate DESC
        LIMIT $limit
        """
        params = {"limit": limit}

    return {
        "query": query,
        "params": params,
        "description": f"Employment rate{' for ' + program_name if program_name else ' by program'}",
    }


@tool
def get_top_skills(category: str | None = None, limit: int = 20) -> dict[str, Any]:
    """
    Get the top skills by learner count.

    Args:
        category: Optional skill category filter
        limit: Number of skills to return (default: 20, max: 100)

    Returns:
        Dict with Cypher query and parameters
    """
    limit = min(limit, 100)

    if category:
        query = """
        MATCH (s:Skill {category: $category})<-[:HAS_SKILL]-(l:Learner)
        RETURN s.name as skill, s.category as category, count(l) as learnerCount
        ORDER BY learnerCount DESC
        LIMIT $limit
        """
        params = {"category": category, "limit": limit}
    else:
        query = """
        MATCH (s:Skill)<-[:HAS_SKILL]-(l:Learner)
        RETURN s.name as skill, s.category as category, count(l) as learnerCount
        ORDER BY learnerCount DESC
        LIMIT $limit
        """
        params = {"limit": limit}

    return {
        "query": query,
        "params": params,
        "description": f"Top {limit} skills{' in ' + category if category else ''}",
    }


@tool
def get_learner_journey(email_hash: str) -> dict[str, Any]:
    """
    Get the complete journey for a specific learner.

    Args:
        email_hash: Hashed email of the learner

    Returns:
        Dict with Cypher query and parameters
    """
    query = """
    MATCH (l:Learner {hashedEmail: $email_hash})
    OPTIONAL MATCH (l)-[:HAS_SKILL]->(s:Skill)
    OPTIONAL MATCH (l)-[e:ENROLLED_IN]->(p:Program)
    OPTIONAL MATCH (l)-[w:WORKS_FOR]->(c:Company)
    OPTIONAL MATCH (country:Country {code: l.countryOfResidenceCode})
    OPTIONAL MATCH (city:City {id: l.cityOfResidenceId})
    RETURN l.fullName as name,
           l.gender as gender,
           l.educationLevel as educationLevel,
           country.name as countryOfResidence,
           city.name as cityOfResidence,
           l.currentLearningState as learningState,
           l.currentProfessionalStatus as professionalStatus,
           collect(DISTINCT s.name) as skills,
           collect(DISTINCT {
               program: p.name,
               status: e.enrollmentStatus,
               completionRate: e.completionRate,
               lmsScore: e.lmsOverallScore
           }) as programs,
           collect(DISTINCT {
               company: c.name,
               position: w.position,
               isCurrent: w.isCurrent,
               startDate: w.startDate
           }) as employment
    LIMIT 1
    """

    return {
        "query": query,
        "params": {"email_hash": email_hash},
        "description": f"Complete journey for learner {email_hash}",
    }


@tool
def get_skills_for_employed_learners(
    country_code: str | None = None,
    limit: int = 20,
) -> dict[str, Any]:
    """
    Get the top skills among employed learners.

    Args:
        country_code: Optional country filter (e.g., "EG", "NG")
        limit: Number of skills to return (default: 20, max: 100)

    Returns:
        Dict with Cypher query and parameters
    """
    limit = min(limit, 100)

    if country_code:
        query = """
        MATCH (l:Learner)-[:WORKS_FOR]->(c:Company)
        WHERE l.countryOfResidenceCode = $country_code
        MATCH (l)-[:HAS_SKILL]->(s:Skill)
        RETURN s.name as skill, count(DISTINCT l) as employedLearnersWithSkill
        ORDER BY employedLearnersWithSkill DESC
        LIMIT $limit
        """
        params = {"country_code": country_code, "limit": limit}
    else:
        query = """
        MATCH (l:Learner)-[:WORKS_FOR]->(c:Company)
        MATCH (l)-[:HAS_SKILL]->(s:Skill)
        RETURN s.name as skill, count(DISTINCT l) as employedLearnersWithSkill
        ORDER BY employedLearnersWithSkill DESC
        LIMIT $limit
        """
        params = {"limit": limit}

    return {
        "query": query,
        "params": params,
        "description": f"Top {limit} skills for employed learners"
        f"{' in ' + country_code if country_code else ''}",
    }


@tool
def get_geographic_distribution(
    metric: str = "learners",
    limit: int = 20,
) -> dict[str, Any]:
    """
    Get geographic distribution of learners or other metrics.

    Args:
        metric: What to measure ("learners", "programs", "companies")
        limit: Number of countries to return (default: 20, max: 100)

    Returns:
        Dict with Cypher query and parameters
    """
    limit = min(limit, 100)

    if metric == "learners":
        query = """
        MATCH (l:Learner)
        WHERE l.countryOfResidenceCode IS NOT NULL
        WITH l.countryOfResidenceCode as code, count(l) as count
        MATCH (c:Country {code: code})
        RETURN c.name as country, c.code as countryCode, count as learnerCount
        ORDER BY count DESC
        LIMIT $limit
        """
    elif metric == "programs":
        query = """
        MATCH (l:Learner)-[:ENROLLED_IN]->(p:Program)
        WHERE l.countryOfResidenceCode IS NOT NULL
        WITH l.countryOfResidenceCode as code, count(DISTINCT p) as count
        MATCH (c:Country {code: code})
        RETURN c.name as country, c.code as countryCode, count as programCount
        ORDER BY count DESC
        LIMIT $limit
        """
    elif metric == "companies":
        query = """
        MATCH (l:Learner)-[:WORKS_FOR]->(co:Company)
        WHERE l.countryOfResidenceCode IS NOT NULL
        WITH l.countryOfResidenceCode as code, count(DISTINCT co) as count
        MATCH (c:Country {code: code})
        RETURN c.name as country, c.code as countryCode, count as companyCount
        ORDER BY count DESC
        LIMIT $limit
        """
    else:
        query = """
        MATCH (l:Learner)
        WHERE l.countryOfResidenceCode IS NOT NULL
        WITH l.countryOfResidenceCode as code, count(l) as count
        MATCH (c:Country {code: code})
        RETURN c.name as country, c.code as countryCode, count
        ORDER BY count DESC
        LIMIT $limit
        """

    return {
        "query": query,
        "params": {"limit": limit},
        "description": f"Geographic distribution of {metric}",
    }


@tool
def get_time_to_employment_stats(program_name: str | None = None) -> dict[str, Any]:
    """
    Get statistics on time from graduation to employment.

    Args:
        program_name: Optional program name filter

    Returns:
        Dict with Cypher query and parameters
    """
    if program_name:
        query = """
        MATCH (l:Learner)-[e:ENROLLED_IN]->(p:Program {name: $program_name})
        MATCH (l)-[w:WORKS_FOR]->(c:Company)
        WHERE e.graduationDate IS NOT NULL
          AND w.startDate IS NOT NULL
          AND w.startDate >= e.graduationDate
        WITH duration.between(e.graduationDate, w.startDate).days as daysToEmployment
        RETURN $program_name as program,
               count(daysToEmployment) as sampleSize,
               round(avg(daysToEmployment), 0) as avgDays,
               round(percentileCont(daysToEmployment, 0.5), 0) as medianDays,
               min(daysToEmployment) as minDays,
               max(daysToEmployment) as maxDays
        """
        params = {"program_name": program_name}
    else:
        query = """
        MATCH (l:Learner)-[e:ENROLLED_IN]->(p:Program)
        MATCH (l)-[w:WORKS_FOR]->(c:Company)
        WHERE e.graduationDate IS NOT NULL
          AND w.startDate IS NOT NULL
          AND w.startDate >= e.graduationDate
        WITH p.name as program, duration.between(e.graduationDate, w.startDate).days as daysToEmployment
        WITH program, collect(daysToEmployment) as days
        WHERE size(days) > 10
        RETURN program,
               size(days) as sampleSize,
               round(avg([d IN days | toFloat(d)]), 0) as avgDays,
               round(percentileCont([d IN days | toFloat(d)], 0.5), 0) as medianDays
        ORDER BY avgDays ASC
        LIMIT 20
        """
        params = {}

    return {
        "query": query,
        "params": params,
        "description": f"Time to employment stats{' for ' + program_name if program_name else ''}",
    }
