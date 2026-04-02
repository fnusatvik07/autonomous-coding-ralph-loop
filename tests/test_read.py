"""Tests for GET /api/todos endpoint — empty list and count behavior."""
import time

from fastapi.testclient import TestClient


class TestListTodosCount:
    """TASK-025: GET /api/todos returns correct count of items."""

    def test_multiple_todos_returns_correct_count(self, client):
        """Create 5 todos then GET /api/todos and verify count == 5."""
        for i in range(1, 6):
            resp = client.post("/api/todos", json={"title": f"Todo {i}"})
            assert resp.status_code == 201

        response = client.get("/api/todos")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 5

    def test_count_increases_with_each_create(self, client):
        """Verify count increases as more todos are created."""
        for i in range(1, 4):
            client.post("/api/todos", json={"title": f"Item {i}"})
            response = client.get("/api/todos")
            assert len(response.json()) == i


class TestGetTodoNotFound:
    """TASK-027: GET /api/todos/{id} returns 404 for non-existent todo."""

    def test_not_found_returns_404(self, client):
        """GET /api/todos/9999 returns HTTP 404."""
        response = client.get("/api/todos/9999")
        assert response.status_code == 404

    def test_not_found_returns_detail_message(self, client):
        """GET /api/todos/9999 returns {"detail": "Todo not found"}."""
        response = client.get("/api/todos/9999")
        assert response.json() == {"detail": "Todo not found"}


class TestListTodosEmpty:
    """TASK-023: GET /api/todos returns empty list when no todos exist."""

    def test_empty_database_returns_200(self, client):
        """GET /api/todos with no data returns HTTP 200."""
        response = client.get("/api/todos")
        assert response.status_code == 200

    def test_empty_database_returns_empty_list(self, client):
        """GET /api/todos with no data returns an empty JSON array []."""
        response = client.get("/api/todos")
        assert response.json() == []


class TestListTodosDefaultOrder:
    """TASK-024: GET /api/todos returns newest first by default."""

    def test_default_order_newest_first(self, client: TestClient):
        """Create 3 todos and verify default order is newest first."""
        for title in ["First", "Second", "Third"]:
            client.post("/api/todos", json={"title": title})
            time.sleep(0.01)
        response = client.get("/api/todos")
        titles = [t["title"] for t in response.json()]
        assert titles == ["Third", "Second", "First"]


class TestGetTodoById:
    """TASK-026: GET /api/todos/{id} returns a single todo."""

    def test_get_by_id_returns_200(self, client: TestClient):
        create_resp = client.post("/api/todos", json={"title": "Find me"})
        todo_id = create_resp.json()["id"]
        response = client.get(f"/api/todos/{todo_id}")
        assert response.status_code == 200

    def test_get_by_id_returns_correct_todo(self, client: TestClient):
        create_resp = client.post("/api/todos", json={"title": "Find me"})
        todo_id = create_resp.json()["id"]
        response = client.get(f"/api/todos/{todo_id}")
        data = response.json()
        assert data["id"] == todo_id
        assert data["title"] == "Find me"
        assert data["completed"] is False

    def test_get_by_id_has_timestamps(self, client: TestClient):
        create_resp = client.post("/api/todos", json={"title": "Timestamps"})
        todo_id = create_resp.json()["id"]
        response = client.get(f"/api/todos/{todo_id}")
        data = response.json()
        assert "created_at" in data
        assert "updated_at" in data


class TestGetTodoInvalidId:
    """TASK-028: GET /api/todos/{id} with invalid id format."""

    def test_string_id_returns_422(self, client: TestClient):
        response = client.get("/api/todos/abc")
        assert response.status_code == 422

    def test_float_id_returns_422(self, client: TestClient):
        response = client.get("/api/todos/1.5")
        assert response.status_code == 422
