"""Database initialization and connection management for the Todo API."""
import os
import sqlite3
from typing import Generator

DATABASE_URL = os.environ.get("DATABASE_URL", "todos.db")


def init_db(db_path: str | None = None) -> None:
    """Initialize the database by creating the todos table if it doesn't exist.

    Args:
        db_path: Optional path to the SQLite database file.
                 Defaults to DATABASE_URL env var or 'todos.db'.
    """
    path = db_path or DATABASE_URL
    conn = sqlite3.connect(path)
    try:
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
    finally:
        conn.close()


def get_db(db_path: str | None = None) -> Generator[sqlite3.Connection, None, None]:
    """Yield a database connection with Row factory, closing it after use.

    This is a generator function suitable for use with FastAPI's Depends().

    Args:
        db_path: Optional path to the SQLite database file.
                 Defaults to DATABASE_URL env var or 'todos.db'.

    Yields:
        sqlite3.Connection with row_factory set to sqlite3.Row.
    """
    path = db_path or DATABASE_URL
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()
