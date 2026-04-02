"""Pydantic models for the Todo API request/response validation."""
from pydantic import BaseModel, Field, field_validator, model_validator


class TodoCreate(BaseModel):
    """Schema for creating a new todo item."""

    title: str = Field(..., min_length=1, max_length=200)
    completed: bool = False

    @field_validator("title")
    @classmethod
    def strip_and_validate_title(cls, v: str) -> str:
        """Strip whitespace from title and reject whitespace-only strings."""
        stripped = v.strip()
        if not stripped:
            raise ValueError("Title cannot be empty or whitespace-only")
        return stripped


class TodoUpdate(BaseModel):
    """Schema for updating an existing todo item."""

    title: str | None = Field(None, min_length=1, max_length=200)
    completed: bool | None = None

    @field_validator("title")
    @classmethod
    def strip_and_validate_title(cls, v: str | None) -> str | None:
        """Strip whitespace from title and reject whitespace-only strings."""
        if v is None:
            return v
        stripped = v.strip()
        if not stripped:
            raise ValueError("Title cannot be empty or whitespace-only")
        return stripped

    @model_validator(mode="after")
    def check_at_least_one_field(self) -> "TodoUpdate":
        """Ensure at least one field is provided."""
        if self.title is None and self.completed is None:
            raise ValueError("At least one field must be provided")
        return self


class TodoResponse(BaseModel):
    """Schema for todo item responses."""

    id: int
    title: str
    completed: bool
    created_at: str
    updated_at: str
