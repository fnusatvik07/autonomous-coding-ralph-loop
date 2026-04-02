"""Tests for POST /api/todos endpoint."""
from datetime import datetime

from fastapi.testclient import TestClient


class TestCreateTodoTitleOnly:
    """TASK-015: POST /api/todos creates todo with title only."""

    def test_title_only_returns_201(self, client: TestClient):
        response = client.post("/api/todos", json={"title": "Buy milk"})
        assert response.status_code == 201

    def test_title_only_response_has_id(self, client: TestClient):
        response = client.post("/api/todos", json={"title": "Buy milk"})
        data = response.json()
        assert "id" in data
        assert isinstance(data["id"], int)

    def test_title_only_response_has_title(self, client: TestClient):
        response = client.post("/api/todos", json={"title": "Buy milk"})
        data = response.json()
        assert data["title"] == "Buy milk"

    def test_title_only_completed_defaults_false(self, client: TestClient):
        response = client.post("/api/todos", json={"title": "Buy milk"})
        data = response.json()
        assert data["completed"] is False

    def test_title_only_has_created_at(self, client: TestClient):
        response = client.post("/api/todos", json={"title": "Buy milk"})
        data = response.json()
        assert "created_at" in data
        # Verify it's a valid ISO 8601 timestamp
        datetime.fromisoformat(data["created_at"])

    def test_title_only_has_updated_at(self, client: TestClient):
        response = client.post("/api/todos", json={"title": "Buy milk"})
        data = response.json()
        assert "updated_at" in data
        # Verify it's a valid ISO 8601 timestamp
        datetime.fromisoformat(data["updated_at"])


class TestCreateTodoMissingTitle:
    """TASK-017: POST /api/todos rejects missing title."""

    def test_missing_title_empty_body_returns_422(self, client: TestClient):
        response = client.post("/api/todos", json={})
        assert response.status_code == 422

    def test_missing_title_completed_only_returns_422(self, client: TestClient):
        response = client.post("/api/todos", json={"completed": True})
        assert response.status_code == 422


class TestCreateTodoEmptyTitle:
    """TASK-018: POST /api/todos rejects empty string title."""

    def test_empty_string_title_returns_422(self, client: TestClient):
        response = client.post("/api/todos", json={"title": ""})
        assert response.status_code == 422

    def test_empty_string_title_error_references_title(self, client: TestClient):
        response = client.post("/api/todos", json={"title": ""})
        data = response.json()
        assert "detail" in data
        # Verify error references title in validation errors
        errors = data["detail"]
        assert any("title" in str(err).lower() for err in errors)

    def test_whitespace_only_title_returns_422(self, client: TestClient):
        response = client.post("/api/todos", json={"title": "   "})
        assert response.status_code == 422

    def test_whitespace_only_title_error_references_title(self, client: TestClient):
        response = client.post("/api/todos", json={"title": "   "})
        data = response.json()
        assert "detail" in data
        errors = data["detail"]
        assert any("title" in str(err).lower() for err in errors)


class TestCreateTodoCompletedWrongType:
    """TASK-021: POST /api/todos rejects wrong type for completed."""

    def test_completed_string_wrong_type_returns_422(self, client: TestClient):
        response = client.post("/api/todos", json={"title": "Test", "completed": "yes"})
        assert response.status_code == 422

    def test_completed_int_wrong_type_returns_422(self, client: TestClient):
        response = client.post("/api/todos", json={"title": "Test", "completed": 42})
        assert response.status_code == 422

    def test_completed_string_wrong_type_error_references_completed(self, client: TestClient):
        response = client.post("/api/todos", json={"title": "Test", "completed": "yes"})
        data = response.json()
        assert "detail" in data
        errors = data["detail"]
        assert any("completed" in str(err).lower() for err in errors)

    def test_completed_int_wrong_type_error_references_completed(self, client: TestClient):
        response = client.post("/api/todos", json={"title": "Test", "completed": 42})
        data = response.json()
        assert "detail" in data
        errors = data["detail"]
        assert any("completed" in str(err).lower() for err in errors)


class TestCreateTodoTitleLength:
    """TASK-020: POST /api/todos enforces title length boundaries."""

    def test_title_exactly_200_chars_returns_201(self, client: TestClient):
        title = "a" * 200
        response = client.post("/api/todos", json={"title": title})
        assert response.status_code == 201

    def test_title_exactly_200_chars_in_response(self, client: TestClient):
        title = "a" * 200
        response = client.post("/api/todos", json={"title": title})
        data = response.json()
        assert len(data["title"]) == 200

    def test_title_201_chars_returns_422(self, client: TestClient):
        title = "a" * 201
        response = client.post("/api/todos", json={"title": title})
        assert response.status_code == 422
