"""Tests for Pydantic models (TodoCreate, TodoUpdate, TodoResponse)."""
import pytest
from pydantic import ValidationError

from app.models import TodoCreate, TodoUpdate, TodoResponse


class TestTodoCreate:
    """Tests for TodoCreate model."""

    def test_model_exists(self):
        """TodoCreate model exists in app/models.py."""
        assert TodoCreate is not None

    def test_valid_title(self):
        """Valid title creates a TodoCreate instance."""
        t = TodoCreate(title="Test")
        assert t.title == "Test"

    def test_title_is_required(self):
        """Title field is required."""
        with pytest.raises(ValidationError):
            TodoCreate()

    def test_title_is_str_type(self):
        """Title must be a string."""
        t = TodoCreate(title="hello")
        assert isinstance(t.title, str)

    def test_title_min_length(self):
        """Title with min_length=1 rejects empty string."""
        with pytest.raises(ValidationError):
            TodoCreate(title="")

    def test_title_max_length(self):
        """Title with max_length=200 rejects long strings."""
        with pytest.raises(ValidationError):
            TodoCreate(title="x" * 201)

    def test_title_exactly_200_chars(self):
        """Title of exactly 200 characters is accepted."""
        t = TodoCreate(title="x" * 200)
        assert len(t.title) == 200

    def test_completed_defaults_false(self):
        """Completed field defaults to False."""
        t = TodoCreate(title="Test")
        assert t.completed is False

    def test_completed_can_be_set_true(self):
        """Completed can be explicitly set to True."""
        t = TodoCreate(title="Test", completed=True)
        assert t.completed is True

    def test_title_strips_whitespace(self):
        """Title whitespace is stripped."""
        t = TodoCreate(title="  hello  ")
        assert t.title == "hello"

    def test_whitespace_only_title_rejected(self):
        """Whitespace-only title raises ValidationError."""
        with pytest.raises(ValidationError):
            TodoCreate(title="   ")

    def test_title_rejects_non_string(self):
        """Non-string types for title raise ValidationError or get coerced."""
        # Pydantic v2 may coerce some types; integers should fail min_length after coercion
        # But lists/dicts should fail
        with pytest.raises(ValidationError):
            TodoCreate(title=["not", "a", "string"])


class TestTodoUpdate:
    """Tests for TodoUpdate model."""

    def test_model_exists(self):
        """TodoUpdate model exists in app/models.py."""
        assert TodoUpdate is not None

    def test_update_title_only(self):
        """Can update with title only."""
        t = TodoUpdate(title="Updated")
        assert t.title == "Updated"
        assert t.completed is None

    def test_update_completed_only(self):
        """Can update with completed only."""
        t = TodoUpdate(completed=True)
        assert t.completed is True
        assert t.title is None

    def test_both_fields_optional(self):
        """Both fields are individually optional."""
        t = TodoUpdate(title="New", completed=True)
        assert t.title == "New"
        assert t.completed is True

    def test_empty_body_raises_validation_error(self):
        """Empty body {} raises ValidationError with specific message."""
        with pytest.raises(ValidationError, match="At least one field must be provided"):
            TodoUpdate()

    def test_title_strips_whitespace(self):
        """Title whitespace is stripped in updates."""
        t = TodoUpdate(title="  updated  ")
        assert t.title == "updated"

    def test_whitespace_only_title_rejected(self):
        """Whitespace-only title in update raises ValidationError."""
        with pytest.raises(ValidationError):
            TodoUpdate(title="   ")

    def test_title_min_length(self):
        """Update title with empty string raises ValidationError."""
        with pytest.raises(ValidationError):
            TodoUpdate(title="")

    def test_title_max_length(self):
        """Update title exceeding 200 chars raises ValidationError."""
        with pytest.raises(ValidationError):
            TodoUpdate(title="x" * 201)


class TestTodoResponse:
    """Tests for TodoResponse model."""

    def test_model_exists(self):
        """TodoResponse model exists in app/models.py."""
        assert TodoResponse is not None

    def test_all_fields_present(self):
        """TodoResponse has all 5 required fields."""
        t = TodoResponse(
            id=1,
            title="Test",
            completed=False,
            created_at="2026-01-01T00:00:00Z",
            updated_at="2026-01-01T00:00:00Z",
        )
        assert t.id == 1
        assert t.title == "Test"
        assert t.completed is False
        assert t.created_at == "2026-01-01T00:00:00Z"
        assert t.updated_at == "2026-01-01T00:00:00Z"

    def test_id_is_int(self):
        """id field is int type."""
        t = TodoResponse(
            id=42, title="X", completed=True,
            created_at="2026-01-01T00:00:00Z",
            updated_at="2026-01-01T00:00:00Z",
        )
        assert isinstance(t.id, int)

    def test_title_is_str(self):
        """title field is str type."""
        t = TodoResponse(
            id=1, title="Hello", completed=False,
            created_at="2026-01-01T00:00:00Z",
            updated_at="2026-01-01T00:00:00Z",
        )
        assert isinstance(t.title, str)

    def test_completed_is_bool(self):
        """completed field is bool type."""
        t = TodoResponse(
            id=1, title="X", completed=True,
            created_at="2026-01-01T00:00:00Z",
            updated_at="2026-01-01T00:00:00Z",
        )
        assert isinstance(t.completed, bool)

    def test_timestamps_are_str(self):
        """created_at and updated_at are str type."""
        t = TodoResponse(
            id=1, title="X", completed=False,
            created_at="2026-01-01T00:00:00Z",
            updated_at="2026-01-01T00:00:00Z",
        )
        assert isinstance(t.created_at, str)
        assert isinstance(t.updated_at, str)

    def test_missing_field_raises_error(self):
        """Missing required fields raise ValidationError."""
        with pytest.raises(ValidationError):
            TodoResponse(id=1, title="X")  # missing completed, timestamps
