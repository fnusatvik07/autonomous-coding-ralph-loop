"""Database module for SQLite connection management."""

import os
import sqlite3
from typing import Generator

DATABASE_URL = os.environ.get("DATABASE_URL", "todos.db")


def init_db(db_path: str = DATABASE_URL) -> None:
    """Create the todos table if it doesn't exist."""
    conn = sqlite3.connect(db_path)
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS todos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                completed INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        conn.commit()
    finally:
        conn.close()


def get_db(db_path: str = DATABASE_URL) -> Generator[sqlite3.Connection, None, None]:
    """FastAPI dependency that yields a sqlite3.Connection per request.

    Sets row_factory to sqlite3.Row for dict-like access.
    """
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()
