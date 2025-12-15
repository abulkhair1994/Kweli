"""Unit tests for MySQL stream reader and data source factory."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import polars as pl
import pytest

from kweli.etl.transformers.data_source import DataSourceFactory, DataSourceType
from kweli.etl.transformers.mysql_reader import MySQLStreamReader


class TestMySQLStreamReader:
    """Tests for MySQL stream reader."""

    @pytest.fixture
    def mock_pool(self):
        """Create mock connection pool."""
        with patch("mysql.connector.pooling.MySQLConnectionPool") as mock:
            yield mock

    @pytest.fixture
    def mock_connection(self):
        """Create mock database connection."""
        conn = MagicMock()
        cursor = MagicMock()
        conn.cursor.return_value = cursor
        return conn, cursor

    def test_init_validates_required_fields(self, mock_pool, monkeypatch):
        """Test that initialization validates required fields when env vars are empty."""
        # Clear environment variables so fallbacks don't kick in
        monkeypatch.delenv("MYSQL_HOST", raising=False)
        monkeypatch.delenv("MYSQL_DATABASE", raising=False)
        monkeypatch.delenv("MYSQL_USER", raising=False)
        monkeypatch.delenv("MYSQL_PASSWORD", raising=False)

        # Host validation - passing None explicitly (empty string uses "localhost" default)
        with pytest.raises(ValueError, match="MySQL host is required"):
            MySQLStreamReader(
                host=None,
                database="test",
                user="user",
                password="pass",
            )

        with pytest.raises(ValueError, match="MySQL database is required"):
            MySQLStreamReader(
                host="localhost",
                database=None,
                user="user",
                password="pass",
            )

        with pytest.raises(ValueError, match="MySQL user is required"):
            MySQLStreamReader(
                host="localhost",
                database="test",
                user=None,
                password="pass",
            )

        with pytest.raises(ValueError, match="MySQL password is required"):
            MySQLStreamReader(
                host="localhost",
                database="test",
                user="user",
                password=None,
            )

    def test_init_creates_reader_with_defaults(self, mock_pool):
        """Test that initialization sets default values."""
        reader = MySQLStreamReader(
            host="localhost",
            database="test_db",
            table="test_table",
            user="test_user",
            password="test_pass",
        )

        assert reader.host == "localhost"
        assert reader.database == "test_db"
        assert reader.table == "test_table"
        assert reader.port == 3306
        assert reader.chunk_size == 2000  # Small chunks for OFFSET performance
        assert reader.use_ssl is True

    def test_init_accepts_custom_values(self, mock_pool):
        """Test that initialization accepts custom values."""
        reader = MySQLStreamReader(
            host="myhost",
            database="mydb",
            table="mytable",
            user="myuser",
            password="mypass",
            port=3307,
            chunk_size=5000,
            use_ssl=False,
        )

        assert reader.host == "myhost"
        assert reader.database == "mydb"
        assert reader.table == "mytable"
        assert reader.port == 3307
        assert reader.chunk_size == 5000
        assert reader.use_ssl is False

    def test_get_columns_returns_column_names(self, mock_pool, mock_connection):
        """Test that get_columns returns column names from DESCRIBE."""
        conn, cursor = mock_connection
        mock_pool.return_value.get_connection.return_value = conn
        cursor.fetchall.return_value = [
            ("id", "int", "NO", "PRI", None, "auto_increment"),
            ("name", "varchar(255)", "YES", "", None, ""),
            ("email", "text", "YES", "", None, ""),
        ]

        reader = MySQLStreamReader(
            host="localhost",
            database="test_db",
            table="test_table",
            user="test_user",
            password="test_pass",
        )

        columns = reader.get_columns()

        assert columns == ["id", "name", "email"]
        cursor.execute.assert_called_with("DESCRIBE `test_table`")

    def test_get_columns_caches_result(self, mock_pool, mock_connection):
        """Test that columns are cached after first call."""
        conn, cursor = mock_connection
        mock_pool.return_value.get_connection.return_value = conn
        cursor.fetchall.return_value = [("col1", "text", "", "", None, "")]

        reader = MySQLStreamReader(
            host="localhost",
            database="test_db",
            table="test_table",
            user="test_user",
            password="test_pass",
        )

        # Call twice
        reader.get_columns()
        reader.get_columns()

        # Should only query once (first call caches result)
        assert cursor.execute.call_count == 1

    def test_get_total_rows_returns_count(self, mock_pool, mock_connection):
        """Test that get_total_rows returns correct count."""
        conn, cursor = mock_connection
        mock_pool.return_value.get_connection.return_value = conn
        cursor.fetchone.return_value = (1617360,)

        reader = MySQLStreamReader(
            host="localhost",
            database="test_db",
            table="test_table",
            user="test_user",
            password="test_pass",
        )

        total = reader.get_total_rows()

        assert total == 1617360

    def test_get_total_rows_caches_result(self, mock_pool, mock_connection):
        """Test that total rows are cached after first call."""
        conn, cursor = mock_connection
        mock_pool.return_value.get_connection.return_value = conn
        cursor.fetchone.return_value = (100,)

        reader = MySQLStreamReader(
            host="localhost",
            database="test_db",
            table="test_table",
            user="test_user",
            password="test_pass",
        )

        # Call twice
        reader.get_total_rows()
        reader.get_total_rows()

        # Should only query once
        assert cursor.execute.call_count == 1

    def test_read_chunks_yields_dataframes(self, mock_pool, mock_connection):
        """Test that read_chunks yields Polars DataFrames."""
        conn, cursor = mock_connection
        mock_pool.return_value.get_connection.return_value = conn

        # Mock total rows count
        cursor.fetchone.return_value = (2,)
        # Mock data rows
        cursor.fetchall.return_value = [
            {"id": 1, "name": "Test1"},
            {"id": 2, "name": "Test2"},
        ]

        reader = MySQLStreamReader(
            host="localhost",
            database="test_db",
            table="test_table",
            user="test_user",
            password="test_pass",
            chunk_size=10,
        )

        # Skip get_columns call by setting cached value
        reader._columns = ["id", "name"]

        chunks = list(reader.read_chunks())

        assert len(chunks) == 1
        assert isinstance(chunks[0], pl.DataFrame)
        assert len(chunks[0]) == 2

    def test_read_chunks_uses_offset(self, mock_pool, mock_connection):
        """Test that read_chunks starts from specified offset."""
        conn, cursor = mock_connection
        mock_pool.return_value.get_connection.return_value = conn

        # Return 100 rows total, start from offset 50
        cursor.fetchone.return_value = (100,)
        # Return 50 rows so we complete in one chunk
        cursor.fetchall.return_value = [{"id": i} for i in range(50)]

        reader = MySQLStreamReader(
            host="localhost",
            database="test_db",
            table="test_table",
            user="test_user",
            password="test_pass",
            chunk_size=100,
        )
        reader._columns = ["id"]

        list(reader.read_chunks(start_row=50))

        # Check that OFFSET 50 was used in the first SELECT
        calls = cursor.execute.call_args_list
        select_calls = [str(c) for c in calls if "SELECT *" in str(c)]
        assert len(select_calls) > 0
        assert "OFFSET 50" in select_calls[0]

    def test_read_chunks_respects_max_rows(self, mock_pool, mock_connection):
        """Test that read_chunks stops after max_rows."""
        conn, cursor = mock_connection
        mock_pool.return_value.get_connection.return_value = conn

        cursor.fetchone.return_value = (1000,)
        cursor.fetchall.return_value = [{"id": i} for i in range(50)]

        reader = MySQLStreamReader(
            host="localhost",
            database="test_db",
            table="test_table",
            user="test_user",
            password="test_pass",
            chunk_size=100,
        )
        reader._columns = ["id"]

        chunks = list(reader.read_chunks(max_rows=50))

        assert len(chunks) == 1
        assert len(chunks[0]) == 50

    def test_read_sample_returns_dataframe(self, mock_pool, mock_connection):
        """Test that read_sample returns a Polars DataFrame."""
        conn, cursor = mock_connection
        mock_pool.return_value.get_connection.return_value = conn
        cursor.fetchall.return_value = [{"id": 1, "name": "Test"}]

        reader = MySQLStreamReader(
            host="localhost",
            database="test_db",
            table="test_table",
            user="test_user",
            password="test_pass",
        )

        sample = reader.read_sample(n_rows=10)

        assert isinstance(sample, pl.DataFrame)
        cursor.execute.assert_called_with("SELECT * FROM `test_table` LIMIT 10")

    def test_test_connection_returns_true_on_success(self, mock_pool, mock_connection):
        """Test that test_connection returns True when connection works."""
        conn, cursor = mock_connection
        mock_pool.return_value.get_connection.return_value = conn
        cursor.fetchone.return_value = (1,)

        reader = MySQLStreamReader(
            host="localhost",
            database="test_db",
            table="test_table",
            user="test_user",
            password="test_pass",
        )

        assert reader.test_connection() is True

    def test_test_connection_returns_false_on_failure(self, mock_pool):
        """Test that test_connection returns False when connection fails."""
        mock_pool.return_value.get_connection.side_effect = Exception("Connection failed")

        reader = MySQLStreamReader(
            host="localhost",
            database="test_db",
            table="test_table",
            user="test_user",
            password="test_pass",
        )

        assert reader.test_connection() is False


class TestDataSourceFactory:
    """Tests for data source factory."""

    def test_create_csv_reader(self, tmp_path):
        """Test creating CSV reader through factory."""
        # Create a test CSV file
        csv_file = tmp_path / "test.csv"
        csv_file.write_text("id,name\n1,Test\n")

        reader = DataSourceFactory.create(
            source_type=DataSourceType.CSV,
            config={"csv_path": csv_file, "chunk_size": 100},
        )

        assert reader is not None
        assert hasattr(reader, "read_chunks")
        assert hasattr(reader, "get_columns")
        assert hasattr(reader, "get_total_rows")

    def test_create_csv_reader_with_string_type(self, tmp_path):
        """Test creating CSV reader with string type."""
        csv_file = tmp_path / "test.csv"
        csv_file.write_text("id,name\n1,Test\n")

        reader = DataSourceFactory.create(
            source_type="csv",
            config={"csv_path": csv_file},
        )

        assert reader is not None

    def test_create_mysql_reader(self):
        """Test creating MySQL reader through factory."""
        with patch(
            "kweli.etl.transformers.mysql_reader.MySQLStreamReader"
        ) as mock_reader:
            mock_reader.return_value = MagicMock()

            reader = DataSourceFactory.create(
                source_type="mysql",
                config={
                    "mysql": {
                        "host": "localhost",
                        "database": "test",
                        "table": "test_table",
                        "user": "user",
                        "password": "pass",
                    }
                },
            )

            mock_reader.assert_called_once()
            assert reader is not None

    def test_create_raises_for_missing_csv_path(self):
        """Test that factory raises error for missing csv_path."""
        with pytest.raises(ValueError, match="csv_path is required"):
            DataSourceFactory.create(
                source_type=DataSourceType.CSV,
                config={},
            )

    def test_create_raises_for_missing_mysql_config(self):
        """Test that factory raises error for missing MySQL config."""
        with pytest.raises(ValueError, match="Missing required MySQL config"):
            DataSourceFactory.create(
                source_type="mysql",
                config={"mysql": {"host": "localhost"}},
            )

    def test_create_raises_for_unsupported_type(self):
        """Test that factory raises error for unsupported type."""
        with pytest.raises(ValueError, match="Unsupported data source type"):
            DataSourceFactory.create(
                source_type="unsupported",
                config={},
            )

    def test_create_mysql_with_all_options(self):
        """Test creating MySQL reader with all configuration options."""
        with patch(
            "kweli.etl.transformers.mysql_reader.MySQLStreamReader"
        ) as mock_reader:
            mock_reader.return_value = MagicMock()

            DataSourceFactory.create(
                source_type=DataSourceType.MYSQL,
                config={
                    "chunk_size": 5000,
                    "mysql": {
                        "host": "myhost.rds.amazonaws.com",
                        "database": "prod_db",
                        "table": "learners",
                        "user": "admin",
                        "password": "secret",
                        "port": 3307,
                        "use_ssl": True,
                        "connection_timeout": 60,
                        "read_timeout": 300,
                    },
                },
            )

            call_kwargs = mock_reader.call_args[1]
            assert call_kwargs["host"] == "myhost.rds.amazonaws.com"
            assert call_kwargs["database"] == "prod_db"
            assert call_kwargs["table"] == "learners"
            assert call_kwargs["port"] == 3307
            assert call_kwargs["chunk_size"] == 5000
            assert call_kwargs["use_ssl"] is True


class TestMySQLConfig:
    """Tests for MySQLConfig model."""

    def test_from_env_loads_environment_variables(self, monkeypatch):
        """Test that from_env loads from environment variables."""
        from kweli.etl.utils.config import MySQLConfig

        monkeypatch.setenv("MYSQL_HOST", "test-host.rds.amazonaws.com")
        monkeypatch.setenv("MYSQL_PORT", "3307")
        monkeypatch.setenv("MYSQL_DATABASE", "test_db")
        monkeypatch.setenv("MYSQL_TABLE", "test_table")
        monkeypatch.setenv("MYSQL_USER", "test_user")
        monkeypatch.setenv("MYSQL_PASSWORD", "test_pass")
        monkeypatch.setenv("MYSQL_USE_SSL", "false")

        config = MySQLConfig.from_env()

        assert config.host == "test-host.rds.amazonaws.com"
        assert config.port == 3307
        assert config.database == "test_db"
        assert config.table == "test_table"
        assert config.user == "test_user"
        assert config.password == "test_pass"
        assert config.use_ssl is False

    def test_from_env_uses_defaults(self, monkeypatch):
        """Test that from_env uses defaults for missing variables."""
        from kweli.etl.utils.config import MySQLConfig

        # Clear any existing env vars
        for key in [
            "MYSQL_HOST",
            "MYSQL_PORT",
            "MYSQL_DATABASE",
            "MYSQL_TABLE",
            "MYSQL_USER",
            "MYSQL_PASSWORD",
            "MYSQL_USE_SSL",
        ]:
            monkeypatch.delenv(key, raising=False)

        config = MySQLConfig.from_env()

        assert config.host == ""
        assert config.port == 3306
        assert config.table == "impact_learners_profile"
        assert config.use_ssl is True


class TestDataSourceConfig:
    """Tests for DataSourceConfig model."""

    def test_default_values(self):
        """Test that DataSourceConfig has correct defaults."""
        from kweli.etl.utils.config import DataSourceConfig

        config = DataSourceConfig()

        assert config.type == "csv"
        assert config.csv_path is None
        assert config.chunk_size == 10000
        assert config.mysql is not None

    def test_mysql_config_nested(self):
        """Test that MySQL config is properly nested."""
        from kweli.etl.utils.config import DataSourceConfig, MySQLConfig

        config = DataSourceConfig(
            type="mysql",
            mysql=MySQLConfig(
                host="localhost",
                database="test",
                user="user",
                password="pass",
            ),
        )

        assert config.type == "mysql"
        assert config.mysql.host == "localhost"
        assert config.mysql.database == "test"
