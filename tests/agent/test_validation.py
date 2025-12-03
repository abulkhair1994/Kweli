"""Tests for Cypher query validation."""


from kweli.agent.tools.validation import (
    add_limit_clause,
    has_injection_risk,
    has_limit_clause,
    has_write_operations,
    normalize_query,
    validate_cypher_query,
    validate_query_parameters,
)


class TestNormalizeQuery:
    """Tests for normalize_query function."""

    def test_normalize_whitespace(self):
        """Test whitespace normalization."""
        query = "MATCH   (n)    RETURN   n"
        result = normalize_query(query)
        assert result == "MATCH (n) RETURN n"

    def test_remove_comments(self):
        """Test comment removal."""
        query = "MATCH (n) // this is a comment\nRETURN n"
        result = normalize_query(query)
        assert "comment" not in result.lower()

    def test_strip_trailing_whitespace(self):
        """Test trailing whitespace removal."""
        query = "  MATCH (n) RETURN n  \n"
        result = normalize_query(query)
        assert result == "MATCH (n) RETURN n"


class TestHasWriteOperations:
    """Tests for has_write_operations function."""

    def test_detect_create(self):
        """Test detection of CREATE."""
        assert has_write_operations("CREATE (n:Node)")
        assert has_write_operations("create (n:Node)")

    def test_detect_delete(self):
        """Test detection of DELETE."""
        assert has_write_operations("MATCH (n) DELETE n")
        assert has_write_operations("MATCH (n) DETACH DELETE n")

    def test_detect_set(self):
        """Test detection of SET."""
        assert has_write_operations("MATCH (n) SET n.name = 'test'")

    def test_detect_merge(self):
        """Test detection of MERGE."""
        assert has_write_operations("MERGE (n:Node {id: 1})")

    def test_allow_read_operations(self):
        """Test that read operations are allowed."""
        assert not has_write_operations("MATCH (n) RETURN n")
        assert not has_write_operations("MATCH (n) WHERE n.created_at > 0 RETURN n")

    def test_false_positive_created_at(self):
        """Test that property names don't trigger false positives."""
        assert not has_write_operations("MATCH (n) WHERE n.created_at IS NOT NULL RETURN n")


class TestHasLimitClause:
    """Tests for has_limit_clause function."""

    def test_detect_limit(self):
        """Test detection of LIMIT clause."""
        assert has_limit_clause("MATCH (n) RETURN n LIMIT 10")
        assert has_limit_clause("MATCH (n) RETURN n limit 100")

    def test_no_limit(self):
        """Test queries without LIMIT."""
        assert not has_limit_clause("MATCH (n) RETURN n")


class TestAddLimitClause:
    """Tests for add_limit_clause function."""

    def test_add_limit(self):
        """Test adding LIMIT clause."""
        query = "MATCH (n) RETURN n"
        result = add_limit_clause(query, 100)
        assert "LIMIT 100" in result

    def test_strip_semicolon(self):
        """Test that semicolons are stripped before adding LIMIT."""
        query = "MATCH (n) RETURN n;"
        result = add_limit_clause(query, 100)
        assert result == "MATCH (n) RETURN n LIMIT 100"


class TestHasInjectionRisk:
    """Tests for has_injection_risk function."""

    def test_detect_string_concatenation(self):
        """Test detection of string concatenation."""
        assert has_injection_risk("MATCH (n) WHERE n.name = 'test' + 'value'")

    def test_detect_unusual_quotes(self):
        """Test detection of unusual quote patterns."""
        assert has_injection_risk("MATCH (n) WHERE n.name = ''''''")

    def test_allow_safe_queries(self):
        """Test that safe queries are allowed."""
        assert not has_injection_risk("MATCH (n) WHERE n.name = 'test' RETURN n")
        assert not has_injection_risk("MATCH (n) WHERE n.id = $id RETURN n")


class TestValidateCypherQuery:
    """Tests for validate_cypher_query function."""

    def test_empty_query(self):
        """Test validation of empty query."""
        result = validate_cypher_query("")
        assert not result.is_valid
        assert "empty" in result.error_message.lower()

    def test_write_operation_rejected(self):
        """Test that write operations are rejected."""
        result = validate_cypher_query("CREATE (n:Node)")
        assert not result.is_valid
        assert "write" in result.error_message.lower()

    def test_injection_risk_rejected(self):
        """Test that injection risks are rejected."""
        result = validate_cypher_query("MATCH (n) WHERE n.name = 'a' + 'b' RETURN n")
        assert not result.is_valid
        assert "injection" in result.error_message.lower()

    def test_auto_add_limit(self):
        """Test automatic addition of LIMIT clause."""
        result = validate_cypher_query("MATCH (n) RETURN n", auto_add_limit=True)
        assert result.is_valid
        assert result.modified_query is not None
        assert "LIMIT" in result.modified_query

    def test_require_limit_without_auto_add(self):
        """Test that LIMIT is required when auto_add=False."""
        result = validate_cypher_query("MATCH (n) RETURN n", auto_add_limit=False)
        assert not result.is_valid
        assert "limit" in result.error_message.lower()

    def test_valid_query_with_limit(self):
        """Test validation of valid query with LIMIT."""
        result = validate_cypher_query("MATCH (n) RETURN n LIMIT 10")
        assert result.is_valid
        assert result.error_message is None

    def test_valid_query_complex(self):
        """Test validation of complex valid query."""
        query = """
        MATCH (l:Learner)
        WHERE l.countryOfResidenceCode = $code
        WITH l.countryOfResidenceCode as code, count(l) as count
        MATCH (c:Country {code: code})
        RETURN c.name, count
        ORDER BY count DESC
        LIMIT 10
        """
        result = validate_cypher_query(query)
        assert result.is_valid


class TestValidateQueryParameters:
    """Tests for validate_query_parameters function."""

    def test_empty_params(self):
        """Test validation of empty parameters."""
        result = validate_query_parameters({})
        assert result.is_valid

    def test_valid_params(self):
        """Test validation of valid parameters."""
        params = {"code": "EG", "limit": 10, "name": "test"}
        result = validate_query_parameters(params)
        assert result.is_valid

    def test_suspicious_characters(self):
        """Test detection of suspicious characters."""
        params = {"code": "EG; DROP TABLE"}
        result = validate_query_parameters(params)
        assert not result.is_valid
        assert "suspicious" in result.error_message.lower()

    def test_too_long_string(self):
        """Test detection of overly long strings."""
        params = {"code": "A" * 20000}
        result = validate_query_parameters(params)
        assert not result.is_valid
        assert "length" in result.error_message.lower()

    def test_numeric_params(self):
        """Test that numeric params are allowed."""
        params = {"limit": 100, "count": 42}
        result = validate_query_parameters(params)
        assert result.is_valid
