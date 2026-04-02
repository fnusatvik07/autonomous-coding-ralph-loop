"""Tests for DELETE /api/todos/{id} endpoint."""
from fastapi.testclient import TestClient
import pytest


class TestDeleteSuccess:
    """TASK-037: DELETE /api/todos/{id} returns 204 on success."""

    def test_delete_existing_returns_204(self, client: TestClient):
        """Create a todo then DELETE it, expect 204."""
        create_resp = client.post("/api/todos", json={"title": "To be deleted"})
        assert create_resp.status_code == 201
        todo_id = create_resp.json()["id"]

        resp = client.delete(f"/api/todos/{todo_id}")
        assert resp.status_code == 204

    def test_delete_response_body_is_empty(self, client: TestClient):
        """Response body should be empty on 204."""
        create_resp = client.post("/api/todos", json={"title": "Delete me"})
        todo_id = create_resp.json()["id"]

        resp = client.delete(f"/api/todos/{todo_id}")
        assert resp.status_code == 204
        assert resp.content == b""


class TestDeleteNotFound:
    """TASK-038: DELETE /api/todos/{id} returns 404 for non-existent todo."""

    def test_delete_not_found_returns_404(self, client: TestClient):
        """DELETE /api/todos/9999 returns 404."""
        resp = client.delete("/api/todos/9999")
        assert resp.status_code == 404

    def test_delete_not_found_detail_message(self, client: TestClient):
        """Response body contains {"detail": "Todo not found"}."""
        resp = client.delete("/api/todos/9999")
        assert resp.json() == {"detail": "Todo not found"}


class TestDeleteVerifyGone:
    """TASK-039: Deleted todo is no longer retrievable."""

    def test_deleted_todo_is_gone(self, client: TestClient):
        """After DELETE, GET for that ID returns 404."""
        create_resp = client.post("/api/todos", json={"title": "Will vanish"})
        todo_id = create_resp.json()["id"]

        delete_resp = client.delete(f"/api/todos/{todo_id}")
        assert delete_resp.status_code == 204

        get_resp = client.get(f"/api/todos/{todo_id}")
        assert get_resp.status_code == 404

    def test_deleted_todo_not_in_list(self, client: TestClient):
        """After DELETE, the todo should not appear in GET /api/todos."""
        create_resp = client.post("/api/todos", json={"title": "Vanishing item"})
        todo_id = create_resp.json()["id"]

        client.delete(f"/api/todos/{todo_id}")

        list_resp = client.get("/api/todos")
        ids = [t["id"] for t in list_resp.json()]
        assert todo_id not in ids


class TestDeleteLifecycle:
    """TASK-040: Full CRUD lifecycle: create, get, update, delete, verify gone."""

    def test_full_crud_lifecycle(self, client: TestClient):
        """End-to-end: POST → GET → PATCH → DELETE → verify 404."""
        # Step 1: Create
        create_resp = client.post("/api/todos", json={"title": "Lifecycle todo"})
        assert create_resp.status_code == 201
        todo = create_resp.json()
        todo_id = todo["id"]
        assert todo["title"] == "Lifecycle todo"
        assert todo["completed"] is False

        # Step 2: GET - retrieve and verify fields
        get_resp = client.get(f"/api/todos/{todo_id}")
        assert get_resp.status_code == 200
        fetched = get_resp.json()
        assert fetched["id"] == todo_id
        assert fetched["title"] == "Lifecycle todo"
        assert fetched["completed"] is False

        # Step 3: PATCH - update title
        patch_resp = client.patch(
            f"/api/todos/{todo_id}", json={"title": "Updated lifecycle"}
        )
        assert patch_resp.status_code == 200
        updated = patch_resp.json()
        assert updated["title"] == "Updated lifecycle"

        # Step 4: DELETE
        delete_resp = client.delete(f"/api/todos/{todo_id}")
        assert delete_resp.status_code == 204

        # Step 5: Verify gone
        verify_resp = client.get(f"/api/todos/{todo_id}")
        assert verify_resp.status_code == 404
