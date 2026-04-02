"""Todo CRUD router - endpoints for managing todo items."""
from datetime import datetime, timezone

import sqlite3

from typing import List

from fastapi import APIRouter, Depends, HTTPException, status

from app.database import get_db
from app.models import TodoCreate, TodoUpdate, TodoResponse

router = APIRouter()


@router.get("/todos", response_model=List[TodoResponse])
def list_todos(db: sqlite3.Connection = Depends(get_db)) -> List[TodoResponse]:
    """List all todo items, newest first."""
    rows = db.execute("SELECT * FROM todos ORDER BY created_at DESC").fetchall()
    return [
        TodoResponse(
            id=row["id"],
            title=row["title"],
            completed=bool(row["completed"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
        for row in rows
    ]


@router.get("/todos/{todo_id}", response_model=TodoResponse)
def get_todo(todo_id: int, db: sqlite3.Connection = Depends(get_db)) -> TodoResponse:
    """Get a single todo item by ID. Returns 404 if not found."""
    row = db.execute("SELECT * FROM todos WHERE id = ?", (todo_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Todo not found")
    return TodoResponse(
        id=row["id"],
        title=row["title"],
        completed=bool(row["completed"]),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


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


@router.patch("/todos/{todo_id}", response_model=TodoResponse)
def update_todo(
    todo_id: int, todo: TodoUpdate, db: sqlite3.Connection = Depends(get_db)
) -> TodoResponse:
    """Update a todo item partially. At least one field must be provided."""
    row = db.execute("SELECT * FROM todos WHERE id = ?", (todo_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Todo not found")

    new_title = todo.title if todo.title is not None else row["title"]
    new_completed = todo.completed if todo.completed is not None else bool(row["completed"])
    new_updated_at = datetime.now(timezone.utc).isoformat()

    db.execute(
        "UPDATE todos SET title = ?, completed = ?, updated_at = ? WHERE id = ?",
        (new_title, int(new_completed), new_updated_at, todo_id),
    )
    db.commit()

    updated_row = db.execute("SELECT * FROM todos WHERE id = ?", (todo_id,)).fetchone()
    return TodoResponse(
        id=updated_row["id"],
        title=updated_row["title"],
        completed=bool(updated_row["completed"]),
        created_at=updated_row["created_at"],
        updated_at=updated_row["updated_at"],
    )
