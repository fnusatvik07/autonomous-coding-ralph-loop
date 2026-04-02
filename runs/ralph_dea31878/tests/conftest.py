"""Shared pytest fixtures for the Todo API test suite."""
import os
import sqlite3

import pytest
from fastapi.testclient import TestClient

from app.database import init_db, get_db
from app.main import app


@pytest.fixture()
def test_db(tmp_path):
    """Create a temporary SQLite database initialized with the todos schema.

    Yields the database file path. The database is automatically cleaned up
    after each test by pytest's tmp_path fixture.
    """
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    yield db_path


@pytest.fixture()
def memory_db():
    """Create an in-memory SQLite database with the todos schema.

    Yields a sqlite3.Connection with row_factory set to sqlite3.Row.
    The connection is closed after the test.
    """
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS todos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            completed INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    conn.commit()
    yield conn
    conn.close()


@pytest.fixture()
def client(tmp_path):
    """Create a FastAPI TestClient backed by a temporary database.

    Overrides the get_db dependency so all requests use a fresh,
    isolated SQLite database. The database is initialized with the
    todos schema before the client is yielded.
    """
    db_path = str(tmp_path / "test_client.db")
    os.environ["DATABASE_URL"] = db_path

    try:
        with TestClient(app) as tc:
            yield tc
    finally:
        os.environ.pop("DATABASE_URL", None)


@pytest.fixture()
def client_with_memory_db(memory_db):
    """Create a FastAPI TestClient backed by an in-memory database.

    Overrides the get_db dependency to return the shared in-memory
    connection, ensuring all requests within a test share the same
    database state.
    """
    def override_get_db():
        try:
            yield memory_db
        except Exception:
            pass

    app.dependency_overrides[get_db] = override_get_db

    # We still need a db for lifespan init_db, use tmp
    original_env = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = ":memory:"

    try:
        with TestClient(app) as tc:
            yield tc
    finally:
        app.dependency_overrides.clear()
        if original_env is not None:
            os.environ["DATABASE_URL"] = original_env
        else:
            os.environ.pop("DATABASE_URL", None)
