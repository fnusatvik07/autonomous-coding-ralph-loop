"""Tests for TASK-014: Test client fixture with in-memory database."""
import sqlite3

import pytest
from fastapi.testclient import TestClient


class TestConfTestFixtureExists:
    """Verify that conftest.py exists and fixtures are importable."""

    def test_conftest_module_exists(self):
        """tests/conftest.py exists."""
        import importlib
        import tests.conftest
        assert tests.conftest is not None

    def test_test_db_fixture_defined(self):
        """test_db fixture is defined in conftest."""
        from tests.conftest import test_db
        assert callable(test_db)

    def test_memory_db_fixture_defined(self):
        """memory_db fixture is defined in conftest."""
        from tests.conftest import memory_db
        assert callable(memory_db)

    def test_client_fixture_defined(self):
        """client fixture is defined in conftest."""
        from tests.conftest import client
        assert callable(client)

    def test_client_with_memory_db_fixture_defined(self):
        """client_with_memory_db fixture is defined in conftest."""
        from tests.conftest import client_with_memory_db
        assert callable(client_with_memory_db)


class TestTestDbFixture:
    """Test the test_db fixture creates an isolated temp database."""

    def test_test_db_returns_path(self, test_db):
        """test_db yields a database file path string."""
        assert isinstance(test_db, str)
        assert test_db.endswith(".db")

    def test_test_db_has_todos_table(self, test_db):
        """test_db creates the todos table."""
        conn = sqlite3.connect(test_db)
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='todos'"
        )
        tables = cursor.fetchall()
        conn.close()
        assert len(tables) == 1
        assert tables[0][0] == "todos"

    def test_test_db_is_empty(self, test_db):
        """test_db starts with an empty todos table."""
        conn = sqlite3.connect(test_db)
        cursor = conn.execute("SELECT COUNT(*) FROM todos")
        count = cursor.fetchone()[0]
        conn.close()
        assert count == 0

    def test_test_db_is_isolated(self, test_db):
        """Each test_db invocation creates a fresh database."""
        conn = sqlite3.connect(test_db)
        conn.execute(
            "INSERT INTO todos (title, completed, created_at, updated_at) "
            "VALUES ('test', 0, '2024-01-01', '2024-01-01')"
        )
        conn.commit()
        cursor = conn.execute("SELECT COUNT(*) FROM todos")
        count = cursor.fetchone()[0]
        conn.close()
        assert count == 1  # Data was inserted in this test only


class TestMemoryDbFixture:
    """Test the memory_db fixture provides an in-memory SQLite connection."""

    def test_memory_db_is_connection(self, memory_db):
        """memory_db yields a sqlite3.Connection."""
        assert isinstance(memory_db, sqlite3.Connection)

    def test_memory_db_has_row_factory(self, memory_db):
        """memory_db connection has row_factory set to sqlite3.Row."""
        assert memory_db.row_factory == sqlite3.Row

    def test_memory_db_has_todos_table(self, memory_db):
        """memory_db creates the todos table."""
        cursor = memory_db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='todos'"
        )
        tables = cursor.fetchall()
        assert len(tables) == 1
        assert tables[0]["name"] == "todos"

    def test_memory_db_is_empty(self, memory_db):
        """memory_db starts with an empty todos table."""
        cursor = memory_db.execute("SELECT COUNT(*) as cnt FROM todos")
        row = cursor.fetchone()
        assert row["cnt"] == 0

    def test_memory_db_supports_inserts(self, memory_db):
        """memory_db supports inserting and querying data."""
        memory_db.execute(
            "INSERT INTO todos (title, completed, created_at, updated_at) "
            "VALUES ('Buy milk', 0, '2024-01-01T00:00:00', '2024-01-01T00:00:00')"
        )
        memory_db.commit()
        cursor = memory_db.execute("SELECT * FROM todos WHERE title='Buy milk'")
        row = cursor.fetchone()
        assert row is not None
        assert row["title"] == "Buy milk"
        assert row["completed"] == 0

    def test_memory_db_schema_has_correct_columns(self, memory_db):
        """memory_db todos table has all expected columns."""
        cursor = memory_db.execute("PRAGMA table_info(todos)")
        columns = {row["name"] for row in cursor.fetchall()}
        expected = {"id", "title", "completed", "created_at", "updated_at"}
        assert columns == expected


class TestClientFixture:
    """Test the client fixture provides a working TestClient."""

    def test_client_is_test_client(self, client):
        """client fixture yields a TestClient instance."""
        assert isinstance(client, TestClient)

    def test_client_health_check(self, client):
        """client can hit the health check endpoint."""
        response = client.get("/")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}

    def test_client_docs_accessible(self, client):
        """client can access Swagger docs."""
        response = client.get("/docs")
        assert response.status_code == 200
