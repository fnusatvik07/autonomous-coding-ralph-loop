"""Tests for FEAT-001: Project Infrastructure & Database Layer."""

import os
import sqlite3
import tempfile

import pytest


# --- TASK-001: pyproject.toml ---

def test_pyproject_toml_exists():
    """Step 1: pyproject.toml exists in project root."""
    assert os.path.exists("pyproject.toml")


def test_dependencies_include_fastapi_and_uvicorn():
    """Step 2: dependencies include fastapi>=0.115 and uvicorn>=0.30."""
    content = open("pyproject.toml").read()
    assert "fastapi>=0.115" in content
    assert "uvicorn>=0.30" in content


def test_dev_dependencies_include_httpx_and_pytest():
    """Step 3: dev dependencies include httpx>=0.27 and pytest>=8.0."""
    content = open("pyproject.toml").read()
    assert "httpx>=0.27" in content
    assert "pytest>=8.0" in content


def test_pytest_testpaths_configured():
    """Step 5: pytest.ini_options sets testpaths to ['tests']."""
    content = open("pyproject.toml").read()
    assert "testpaths" in content
    assert '"tests"' in content or "'tests'" in content


def test_all_deps_importable():
    """All key dependencies can be imported."""
    import fastapi
    import uvicorn
    import httpx
    import pytest as _pytest


# --- TASK-002: Directory structure ---

def test_app_init_exists():
    """Step 1: app/__init__.py exists."""
    assert os.path.exists("app/__init__.py")


def test_app_routers_init_exists():
    """Step 2: app/routers/__init__.py exists."""
    assert os.path.exists("app/routers/__init__.py")


def test_tests_init_exists():
    """Step 3: tests/__init__.py exists."""
    assert os.path.exists("tests/__init__.py")


def test_app_importable():
    """The app package can be imported."""
    import app


# --- TASK-003: Database module ---

def test_database_module_exists():
    """Step 1: app/database.py exists with init_db() function."""
    assert os.path.exists("app/database.py")
    from app.database import init_db
    assert callable(init_db)


def test_init_db_creates_todos_table():
    """Step 2: init_db() creates the todos table with correct columns."""
    from app.database import init_db

    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    try:
        init_db(db_path)
        conn = sqlite3.connect(db_path)
        cursor = conn.execute("PRAGMA table_info(todos)")
        columns = {row[1]: row[2] for row in cursor.fetchall()}
        conn.close()

        assert "id" in columns
        assert "title" in columns
        assert "completed" in columns
        assert "created_at" in columns
        assert "updated_at" in columns

        # Verify types
        assert columns["id"] == "INTEGER"
        assert columns["title"] == "TEXT"
        assert columns["completed"] == "INTEGER"
        assert columns["created_at"] == "TEXT"
        assert columns["updated_at"] == "TEXT"
    finally:
        os.unlink(db_path)


def test_init_db_idempotent():
    """init_db() can be called multiple times without error."""
    from app.database import init_db

    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    try:
        init_db(db_path)
        init_db(db_path)  # Should not raise
    finally:
        os.unlink(db_path)


def test_get_db_yields_connection_with_row_factory():
    """Step 3: get_db() yields a sqlite3.Connection with row_factory=sqlite3.Row."""
    from app.database import get_db, init_db

    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    try:
        init_db(db_path)
        gen = get_db(db_path)
        conn = next(gen)

        assert isinstance(conn, sqlite3.Connection)
        assert conn.row_factory is sqlite3.Row

        # Verify we can query
        conn.execute(
            "INSERT INTO todos (title, completed, created_at, updated_at) VALUES (?, ?, ?, ?)",
            ("Test", 0, "2024-01-01T00:00:00Z", "2024-01-01T00:00:00Z"),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM todos WHERE id = 1").fetchone()
        assert row["title"] == "Test"

        # Close the generator
        try:
            next(gen)
        except StopIteration:
            pass
    finally:
        os.unlink(db_path)
