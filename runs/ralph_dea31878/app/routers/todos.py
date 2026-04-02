"""Todo CRUD router - endpoints for managing todo items."""
from datetime import datetime, timezone

import sqlite3

from fastapi import APIRouter, Depends, status

from app.database import get_db
from app.models import TodoCreate, TodoResponse

router = APIRouter()


@router.post("/todos", response_model=TodoResponse, status_code=status.HTTP_201_CREATED)
def create_todo(todo: TodoCreate, db: sqlite3.Connection = Depends(get_db)) -> TodoResponse:
    """Create a new todo item.

    Accepts a JSON body with title (required) and completed (optional, default false).
    Returns the created todo with auto-generated id, created_at, and updated_at.
    """
    now = datetime.now(timezone.utc).isoformat()
    cursor = db.execute(
        "INSERT INTO todos (title, completed, created_at, updated_at) VALUES (?, ?, ?, ?)",
        (todo.title, int(todo.completed), now, now),
    )
    db.commit()
    todo_id = cursor.lastrowid

    row = db.execute("SELECT * FROM todos WHERE id = ?", (todo_id,)).fetchone()
    return TodoResponse(
        id=row["id"],
        title=row["title"],
        completed=bool(row["completed"]),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )
