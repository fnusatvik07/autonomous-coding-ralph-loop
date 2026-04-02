"""Tests for PATCH /api/todos/{id} — update todo endpoint."""
import time

import pytest
from fastapi.testclient import TestClient


def _create_todo(client: TestClient, title: str = "Test Todo", completed: bool = False) -> dict:
    """Helper to create a todo and return its response JSON."""
    resp = client.post("/api/todos", json={"title": title, "completed": completed})
    assert resp.status_code == 201
    return resp.json()


class TestUpdateTitleOnly:
    """TASK-029: PATCH with title only updates title, leaves completed unchanged."""

    def test_title_only_returns_200(self, client: TestClient):
        todo = _create_todo(client, title="Original", completed=False)
        resp = client.patch(f"/api/todos/{todo['id']}", json={"title": "Updated"})
        assert resp.status_code == 200

    def test_title_only_response_has_new_title(self, client: TestClient):
        todo = _create_todo(client, title="Original", completed=False)
        resp = client.patch(f"/api/todos/{todo['id']}", json={"title": "Updated"})
        data = resp.json()
        assert data["title"] == "Updated"

    def test_title_only_completed_unchanged(self, client: TestClient):
        todo = _create_todo(client, title="Original", completed=False)
        resp = client.patch(f"/api/todos/{todo['id']}", json={"title": "Updated"})
        data = resp.json()
        assert data["completed"] is False

    def test_title_only_completed_true_unchanged(self, client: TestClient):
        todo = _create_todo(client, title="Original", completed=True)
        resp = client.patch(f"/api/todos/{todo['id']}", json={"title": "Updated"})
        data = resp.json()
        assert data["completed"] is True


class TestUpdateCompletedOnly:
    """TASK-030: PATCH with completed only updates completed, leaves title unchanged."""

    def test_completed_only_returns_200(self, client: TestClient):
        todo = _create_todo(client, title="Keep This")
        resp = client.patch(f"/api/todos/{todo['id']}", json={"completed": True})
        assert resp.status_code == 200

    def test_completed_only_sets_true(self, client: TestClient):
        todo = _create_todo(client, title="Keep This")
        resp = client.patch(f"/api/todos/{todo['id']}", json={"completed": True})
        data = resp.json()
        assert data["completed"] is True

    def test_completed_only_title_unchanged(self, client: TestClient):
        todo = _create_todo(client, title="Keep This")
        resp = client.patch(f"/api/todos/{todo['id']}", json={"completed": True})
        data = resp.json()
        assert data["title"] == "Keep This"

    def test_completed_toggle_back_to_false(self, client: TestClient):
        todo = _create_todo(client, title="Toggle", completed=True)
        resp = client.patch(f"/api/todos/{todo['id']}", json={"completed": False})
        data = resp.json()
        assert data["completed"] is False


class TestUpdateBothFields:
    """TASK-031: PATCH with both title and completed updates both."""

    def test_both_returns_200(self, client: TestClient):
        todo = _create_todo(client, title="Old")
        resp = client.patch(
            f"/api/todos/{todo['id']}", json={"title": "New", "completed": True}
        )
        assert resp.status_code == 200

    def test_both_title_updated(self, client: TestClient):
        todo = _create_todo(client, title="Old")
        resp = client.patch(
            f"/api/todos/{todo['id']}", json={"title": "New", "completed": True}
        )
        data = resp.json()
        assert data["title"] == "New"

    def test_both_completed_updated(self, client: TestClient):
        todo = _create_todo(client, title="Old")
        resp = client.patch(
            f"/api/todos/{todo['id']}", json={"title": "New", "completed": True}
        )
        data = resp.json()
        assert data["completed"] is True


class TestUpdateNotFound:
    """TASK-032: PATCH on non-existent todo returns 404."""

    def test_not_found_returns_404(self, client: TestClient):
        resp = client.patch("/api/todos/9999", json={"title": "X"})
        assert resp.status_code == 404

    def test_not_found_detail_message(self, client: TestClient):
        resp = client.patch("/api/todos/9999", json={"title": "X"})
        assert resp.json() == {"detail": "Todo not found"}


class TestUpdateEmptyBody:
    """TASK-033: PATCH with empty body {} returns 422."""

    def test_empty_body_returns_422(self, client: TestClient):
        todo = _create_todo(client)
        resp = client.patch(f"/api/todos/{todo['id']}", json={})
        assert resp.status_code == 422

    def test_empty_body_error_message(self, client: TestClient):
        todo = _create_todo(client)
        resp = client.patch(f"/api/todos/{todo['id']}", json={})
        body = resp.json()
        # Pydantic model_validator raises ValueError with this message
        assert "At least one field must be provided" in str(body)


class TestUpdateWhitespaceTitle:
    """TASK-034: PATCH with whitespace-only title returns 422."""

    def test_whitespace_title_returns_422(self, client: TestClient):
        todo = _create_todo(client)
        resp = client.patch(f"/api/todos/{todo['id']}", json={"title": "   "})
        assert resp.status_code == 422

    def test_empty_string_title_returns_422(self, client: TestClient):
        todo = _create_todo(client)
        resp = client.patch(f"/api/todos/{todo['id']}", json={"title": ""})
        assert resp.status_code == 422


class TestUpdateLongTitle:
    """TASK-035: PATCH with title exceeding 200 chars returns 422."""

    def test_long_title_201_chars_returns_422(self, client: TestClient):
        todo = _create_todo(client)
        resp = client.patch(f"/api/todos/{todo['id']}", json={"title": "a" * 201})
        assert resp.status_code == 422

    def test_title_exactly_200_chars_returns_200(self, client: TestClient):
        todo = _create_todo(client)
        resp = client.patch(f"/api/todos/{todo['id']}", json={"title": "a" * 200})
        assert resp.status_code == 200


class TestUpdateTimestamp:
    """TASK-036: PATCH refreshes updated_at but not created_at."""

    def test_updated_at_changes(self, client: TestClient):
        todo = _create_todo(client)
        original_updated_at = todo["updated_at"]
        # Small delay to ensure timestamp differs
        time.sleep(0.05)
        resp = client.patch(f"/api/todos/{todo['id']}", json={"title": "Changed"})
        data = resp.json()
        assert data["updated_at"] != original_updated_at

    def test_created_at_unchanged(self, client: TestClient):
        todo = _create_todo(client)
        original_created_at = todo["created_at"]
        time.sleep(0.05)
        resp = client.patch(f"/api/todos/{todo['id']}", json={"title": "Changed"})
        data = resp.json()
        assert data["created_at"] == original_created_at

    def test_updated_at_is_newer(self, client: TestClient):
        todo = _create_todo(client)
        original_updated_at = todo["updated_at"]
        time.sleep(0.05)
        resp = client.patch(f"/api/todos/{todo['id']}", json={"completed": True})
        data = resp.json()
        assert data["updated_at"] > original_updated_at
