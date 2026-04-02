"""Tests for FEAT-002: Database Layer (TASK-004, TASK-005)."""
import os
import sqlite3
import tempfile

from app.database import init_db, get_db


# TASK-004: SQLite database initialization creates todos table
class TestInitDb:
    def test_database_module_exists(self):
        """Step 1: app/database.py exists with init_db() function."""
        assert os.path.isfile("app/database.py")
        assert callable(init_db)

    def test_init_db_creates_todos_table(self):
        """Step 2: init_db() creates todos table with correct schema."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        try:
            init_db(db_path)
            conn = sqlite3.connect(db_path)
            cursor = conn.execute("PRAGMA table_info(todos)")
            columns = {row[1]: row for row in cursor.fetchall()}
            conn.close()

            # Check all required columns exist
            assert "id" in columns
            assert "title" in columns
            assert "completed" in columns
            assert "created_at" in columns
            assert "updated_at" in columns

            # Check column types
            assert columns["id"][2] == "INTEGER"
            assert columns["title"][2] == "TEXT"
            assert columns["completed"][2] == "INTEGER"
            assert columns["created_at"][2] == "TEXT"
            assert columns["updated_at"][2] == "TEXT"

            # Check NOT NULL constraints (pk=1 means primary key for id)
            assert columns["id"][5] == 1  # primary key
            assert columns["title"][3] == 1  # NOT NULL
            assert columns["completed"][3] == 1  # NOT NULL
            assert columns["created_at"][3] == 1  # NOT NULL
            assert columns["updated_at"][3] == 1  # NOT NULL

            # Check defaults
            assert columns["completed"][4] == "0"  # DEFAULT 0
        finally:
            os.unlink(db_path)

    def test_init_db_is_idempotent(self):
        """Step 3: Uses CREATE TABLE IF NOT EXISTS (idempotent)."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        try:
            # Call init_db twice - should not raise
            init_db(db_path)
            init_db(db_path)

            # Verify table still exists and is correct
            conn = sqlite3.connect(db_path)
            cursor = conn.execute("PRAGMA table_info(todos)")
            columns = cursor.fetchall()
            conn.close()
            assert len(columns) == 5
        finally:
            os.unlink(db_path)

    def test_init_db_uses_autoincrement(self):
        """id column uses AUTOINCREMENT."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        try:
            init_db(db_path)
            conn = sqlite3.connect(db_path)
            cursor = conn.execute(
                "SELECT sql FROM sqlite_master WHERE type='table' AND name='todos'"
            )
            create_sql = cursor.fetchone()[0].upper()
            conn.close()
            assert "AUTOINCREMENT" in create_sql
        finally:
            os.unlink(db_path)

    def test_init_db_respects_database_url_env(self):
        """Uses DATABASE_URL env var with default 'todos.db'."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        try:
            old_env = os.environ.get("DATABASE_URL")
            os.environ["DATABASE_URL"] = db_path
            # Re-import to pick up new env var
            import importlib
            import app.database
            importlib.reload(app.database)
            app.database.init_db()

            conn = sqlite3.connect(db_path)
            cursor = conn.execute("PRAGMA table_info(todos)")
            columns = cursor.fetchall()
            conn.close()
            assert len(columns) == 5
        finally:
            # Restore env
            if old_env is not None:
                os.environ["DATABASE_URL"] = old_env
            elif "DATABASE_URL" in os.environ:
                del os.environ["DATABASE_URL"]
            import importlib
            import app.database
            importlib.reload(app.database)
            os.unlink(db_path)


# TASK-005: get_db dependency yields connection with Row factory
class TestGetDb:
    def test_get_db_is_generator(self):
        """Step 1: get_db() is a generator function suitable for FastAPI Depends()."""
        import inspect
        assert inspect.isgeneratorfunction(get_db)

    def test_get_db_yields_connection_with_row_factory(self):
        """Step 2: Connection uses sqlite3.Row as row_factory."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        try:
            init_db(db_path)
            gen = get_db(db_path)
            conn = next(gen)
            assert conn.row_factory is sqlite3.Row
            # Clean up generator
            try:
                next(gen)
            except StopIteration:
                pass
        finally:
            os.unlink(db_path)

    def test_get_db_connection_is_closed_after_use(self):
        """Step 3: Connection is properly closed after the request completes."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        try:
            init_db(db_path)
            gen = get_db(db_path)
            conn = next(gen)
            # Connection should be open
            assert isinstance(conn, sqlite3.Connection)
            # Exhaust generator to trigger cleanup
            try:
                next(gen)
            except StopIteration:
                pass
            # After generator is exhausted, connection should be closed
            # Trying to use a closed connection raises ProgrammingError
            import pytest
            with pytest.raises(Exception):
                conn.execute("SELECT 1")
        finally:
            os.unlink(db_path)

    def test_get_db_row_factory_returns_dict_like_rows(self):
        """Rows from the connection can be accessed by column name."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        try:
            init_db(db_path)
            gen = get_db(db_path)
            conn = next(gen)
            conn.execute(
                "INSERT INTO todos (title, completed, created_at, updated_at) "
                "VALUES (?, ?, ?, ?)",
                ("Test", 0, "2024-01-01T00:00:00", "2024-01-01T00:00:00"),
            )
            row = conn.execute("SELECT * FROM todos").fetchone()
            # sqlite3.Row allows dict-like access
            assert row["title"] == "Test"
            assert row["completed"] == 0
            assert row["id"] == 1
            try:
                next(gen)
            except StopIteration:
                pass
        finally:
            os.unlink(db_path)
