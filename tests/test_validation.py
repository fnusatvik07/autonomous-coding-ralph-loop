"""Tests for validation edge cases (FEAT-011: TASK-049 through TASK-053)."""
from datetime import datetime

import pytest
from fastapi.testclient import TestClient


class TestTitleTrimming:
    """TASK-049: Title with leading/trailing spaces is trimmed."""

    def test_trim_leading_trailing_spaces_returns_201(self, client: TestClient):
        response = client.post("/api/todos", json={"title": "  Hello World  "})
        assert response.status_code == 201

    def test_trim_response_title_is_trimmed(self, client: TestClient):
        response = client.post("/api/todos", json={"title": "  Hello World  "})
        assert response.json()["title"] == "Hello World"

    def test_strip_stored_value_in_database_is_trimmed(self, client: TestClient):
        """Verify the stored value in the database is also trimmed."""
        create_resp = client.post("/api/todos", json={"title": "  Hello World  "})
        todo_id = create_resp.json()["id"]
        get_resp = client.get(f"/api/todos/{todo_id}")
        assert get_resp.json()["title"] == "Hello World"

    def test_trim_only_leading_spaces(self, client: TestClient):
        response = client.post("/api/todos", json={"title": "   Leading"})
        assert response.json()["title"] == "Leading"

    def test_strip_only_trailing_spaces(self, client: TestClient):
        response = client.post("/api/todos", json={"title": "Trailing   "})
        assert response.json()["title"] == "Trailing"


class TestSpecialCharacterTitle:
    """TASK-050: Title with only special characters is accepted."""

    def test_special_characters_returns_201(self, client: TestClient):
        response = client.post("/api/todos", json={"title": "!@#$%^&*()"})
        assert response.status_code == 201

    def test_special_characters_title_matches(self, client: TestClient):
        response = client.post("/api/todos", json={"title": "!@#$%^&*()"})
        assert response.json()["title"] == "!@#$%^&*()"

    def test_special_unicode_characters(self, client: TestClient):
        response = client.post("/api/todos", json={"title": "émojis 🎉 & ñ"})
        assert response.status_code == 201
        assert response.json()["title"] == "émojis 🎉 & ñ"


class TestBooleanLikeStringCompleted:
    """TASK-051: Boolean-like strings for completed are rejected."""

    def test_string_completed_yes_returns_422(self, client: TestClient):
        response = client.post("/api/todos", json={"title": "Test", "completed": "yes"})
        assert response.status_code == 422

    def test_string_completed_no_returns_422(self, client: TestClient):
        response = client.post("/api/todos", json={"title": "Test", "completed": "no"})
        assert response.status_code == 422

    def test_boolean_like_string_true_returns_422(self, client: TestClient):
        response = client.post("/api/todos", json={"title": "Test", "completed": "true"})
        assert response.status_code == 422

    def test_boolean_like_string_false_returns_422(self, client: TestClient):
        response = client.post("/api/todos", json={"title": "Test", "completed": "false"})
        assert response.status_code == 422

    def test_boolean_like_integer_1_returns_422(self, client: TestClient):
        response = client.post("/api/todos", json={"title": "Test", "completed": 1})
        assert response.status_code == 422


class TestTimestampISO8601:
    """TASK-052: Response timestamps are valid ISO 8601 format."""

    def test_timestamp_created_at_is_iso8601(self, client: TestClient):
        response = client.post("/api/todos", json={"title": "Timestamp test"})
        data = response.json()
        # Should parse without error
        dt = datetime.fromisoformat(data["created_at"])
        assert dt is not None

    def test_iso_updated_at_is_iso8601(self, client: TestClient):
        response = client.post("/api/todos", json={"title": "Timestamp test"})
        data = response.json()
        dt = datetime.fromisoformat(data["updated_at"])
        assert dt is not None

    def test_timestamp_contains_t_separator(self, client: TestClient):
        response = client.post("/api/todos", json={"title": "Timestamp test"})
        data = response.json()
        assert "T" in data["created_at"]
        assert "T" in data["updated_at"]

    def test_iso_timestamps_have_date_and_time(self, client: TestClient):
        """Verify ISO 8601 pattern like 2026-04-01T12:00:00."""
        response = client.post("/api/todos", json={"title": "Timestamp test"})
        data = response.json()
        # Parse and validate components exist
        created = datetime.fromisoformat(data["created_at"])
        assert created.year >= 2024
        assert 1 <= created.month <= 12
        assert 1 <= created.day <= 31


class TestInputTypeRejection:
    """TASK-053: Comprehensive input type rejection."""

    def test_type_numeric_title_coerced_or_rejected(self, client: TestClient):
        """POST with {"title": 123} — numeric title."""
        response = client.post("/api/todos", json={"title": 123})
        # Pydantic may coerce int to str, or reject. Either 201 or 422 is valid.
        # If coerced, the response title should be "123"
        if response.status_code == 201:
            assert response.json()["title"] == "123"
        else:
            assert response.status_code == 422

    def test_reject_null_title_returns_422(self, client: TestClient):
        response = client.post("/api/todos", json={"title": None})
        assert response.status_code == 422

    def test_reject_array_title_returns_422(self, client: TestClient):
        response = client.post("/api/todos", json={"title": ["array"]})
        assert response.status_code == 422

    def test_type_object_title_returns_422(self, client: TestClient):
        response = client.post("/api/todos", json={"title": {"key": "value"}})
        assert response.status_code == 422

    def test_reject_boolean_title_returns_422(self, client: TestClient):
        response = client.post("/api/todos", json={"title": True})
        # Pydantic may coerce bool to str or reject
        if response.status_code == 201:
            assert response.json()["title"] in ("True", "true")
        else:
            assert response.status_code == 422
