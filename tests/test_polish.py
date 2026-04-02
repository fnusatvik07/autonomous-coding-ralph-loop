"""Tests for FEAT-013: Polish & Final Verification.

TASK-061: App starts successfully with uvicorn
TASK-062: All error responses use consistent JSON format
TASK-063: Database file configurable via DATABASE_URL env var
TASK-064: End-to-end API workflow with all endpoints
"""
import os
import sqlite3

import pytest
from fastapi.testclient import TestClient

from app.main import app


# --- TASK-061: App starts successfully with uvicorn ---


class TestAppStartsSuccessfully:
    """TASK-061: Verify the app can be started and responds to requests."""

    def test_app_importable_and_starts(self, client: TestClient):
        """uvicorn app.main:app starts without errors (simulated via TestClient)."""
        # If TestClient instantiation succeeds, the app starts without errors
        response = client.get("/")
        assert response.status_code == 200

    def test_health_check_returns_status_ok(self, client: TestClient):
        """GET / returns {"status": "ok"}."""
        response = client.get("/")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}

    def test_swagger_docs_accessible(self, client: TestClient):
        """GET /docs returns Swagger UI."""
        response = client.get("/docs")
        assert response.status_code == 200
        assert "swagger" in response.text.lower()

    def test_openapi_json_accessible(self, client: TestClient):
        """GET /openapi.json returns the API schema."""
        response = client.get("/openapi.json")
        assert response.status_code == 200
        data = response.json()
        assert "paths" in data
        assert "openapi" in data


# --- TASK-062: All error responses use consistent JSON format ---


class TestConsistentErrorResponses:
    """TASK-062: All error responses use {"detail": ...} JSON format."""

    def test_404_has_detail_field(self, client: TestClient):
        """404 responses have {"detail": "Todo not found"}."""
        response = client.get("/api/todos/999999")
        assert response.status_code == 404
        data = response.json()
        assert "detail" in data
        assert data["detail"] == "Todo not found"

    def test_404_content_type_json(self, client: TestClient):
        """404 responses have Content-Type: application/json."""
        response = client.get("/api/todos/999999")
        assert response.status_code == 404
        assert "application/json" in response.headers["content-type"]

    def test_422_has_detail_field(self, client: TestClient):
        """422 responses have FastAPI's standard validation error body with 'detail'."""
        response = client.post("/api/todos", json={})
        assert response.status_code == 422
        data = response.json()
        assert "detail" in data

    def test_422_content_type_json(self, client: TestClient):
        """422 responses have Content-Type: application/json."""
        response = client.post("/api/todos", json={})
        assert response.status_code == 422
        assert "application/json" in response.headers["content-type"]

    def test_422_detail_is_list(self, client: TestClient):
        """422 validation errors have detail as a list of error objects."""
        response = client.post("/api/todos", json={})
        assert response.status_code == 422
        data = response.json()
        assert isinstance(data["detail"], list)
        assert len(data["detail"]) > 0

    def test_500_has_detail_field(self, client: TestClient):
        """500 responses have {"detail": "Internal server error"}."""
        with TestClient(app, raise_server_exceptions=False) as error_client:
            # Use the existing test-error-route added in test_app.py
            # or test via the global exception handler behavior
            # We'll add a temporary route
            @app.get("/test-polish-error")
            async def raise_error():
                raise RuntimeError("Intentional test error")

            response = error_client.get("/test-polish-error")
            assert response.status_code == 500
            data = response.json()
            assert "detail" in data
            assert data["detail"] == "Internal server error"

    def test_500_content_type_json(self, client: TestClient):
        """500 responses have Content-Type: application/json."""
        with TestClient(app, raise_server_exceptions=False) as error_client:
            response = error_client.get("/test-polish-error")
            assert response.status_code == 500
            assert "application/json" in response.headers["content-type"]


# --- TASK-063: Database file configurable via DATABASE_URL env var ---


class TestDatabaseConfiguration:
    """TASK-063: Database file path configurable via DATABASE_URL."""

    def test_default_database_is_todos_db(self):
        """Default database file is todos.db when DATABASE_URL is not set."""
        from app.database import _get_database_url, DEFAULT_DATABASE_URL
        # Temporarily clear DATABASE_URL
        old = os.environ.pop("DATABASE_URL", None)
        try:
            assert _get_database_url() == "todos.db"
            assert DEFAULT_DATABASE_URL == "todos.db"
        finally:
            if old is not None:
                os.environ["DATABASE_URL"] = old

    def test_database_url_env_changes_path(self, tmp_path):
        """Setting DATABASE_URL env var changes the database file path."""
        custom_path = str(tmp_path / "custom.db")
        old = os.environ.get("DATABASE_URL")
        os.environ["DATABASE_URL"] = custom_path
        try:
            from app.database import _get_database_url
            assert _get_database_url() == custom_path
        finally:
            if old is not None:
                os.environ["DATABASE_URL"] = old
            else:
                os.environ.pop("DATABASE_URL", None)

    def test_custom_database_url_creates_db(self, tmp_path):
        """Setting DATABASE_URL creates the database at the custom path."""
        custom_path = str(tmp_path / "custom_init.db")
        old = os.environ.get("DATABASE_URL")
        os.environ["DATABASE_URL"] = custom_path
        try:
            from app.database import init_db
            init_db()
            # Verify the database was created
            assert os.path.exists(custom_path)
            conn = sqlite3.connect(custom_path)
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='todos'"
            )
            tables = cursor.fetchall()
            conn.close()
            assert len(tables) == 1
        finally:
            if old is not None:
                os.environ["DATABASE_URL"] = old
            else:
                os.environ.pop("DATABASE_URL", None)


# --- TASK-064: End-to-end API workflow with all endpoints ---


class TestEndToEndWorkflow:
    """TASK-064: Comprehensive end-to-end test exercising all API endpoints."""

    def test_health_check_ok(self, client: TestClient):
        """Step 1: GET / returns health check OK."""
        response = client.get("/")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"

    def test_empty_list_initially(self, client: TestClient):
        """Step 2: GET /api/todos returns empty list."""
        response = client.get("/api/todos")
        assert response.status_code == 200
        assert response.json() == []

    def test_create_three_todos(self, client: TestClient):
        """Step 3: POST /api/todos creates 3 todos with different titles."""
        titles = ["Buy groceries", "Walk the dog", "Write tests"]
        created_ids = []

        for title in titles:
            response = client.post("/api/todos", json={"title": title})
            assert response.status_code == 201
            data = response.json()
            assert data["title"] == title
            assert data["completed"] is False
            assert "id" in data
            created_ids.append(data["id"])

        # All IDs should be unique
        assert len(set(created_ids)) == 3

    def test_full_crud_lifecycle(self, client: TestClient):
        """Full CRUD lifecycle: create, read, update, delete."""
        # Create
        create_resp = client.post("/api/todos", json={"title": "Lifecycle test"})
        assert create_resp.status_code == 201
        todo_id = create_resp.json()["id"]

        # Read single
        get_resp = client.get(f"/api/todos/{todo_id}")
        assert get_resp.status_code == 200
        assert get_resp.json()["title"] == "Lifecycle test"

        # Read list
        list_resp = client.get("/api/todos")
        assert list_resp.status_code == 200
        assert len(list_resp.json()) >= 1

        # Update
        update_resp = client.patch(
            f"/api/todos/{todo_id}",
            json={"title": "Updated title", "completed": True},
        )
        assert update_resp.status_code == 200
        assert update_resp.json()["title"] == "Updated title"
        assert update_resp.json()["completed"] is True

        # Verify update
        verify_resp = client.get(f"/api/todos/{todo_id}")
        assert verify_resp.status_code == 200
        assert verify_resp.json()["title"] == "Updated title"
        assert verify_resp.json()["completed"] is True

        # Delete
        delete_resp = client.delete(f"/api/todos/{todo_id}")
        assert delete_resp.status_code == 204

        # Verify deleted
        gone_resp = client.get(f"/api/todos/{todo_id}")
        assert gone_resp.status_code == 404

    def test_filtering_and_pagination_workflow(self, client: TestClient):
        """End-to-end test of filtering and pagination."""
        # Create some todos
        client.post("/api/todos", json={"title": "Alpha task"})
        client.post("/api/todos", json={"title": "Beta task"})
        resp = client.post("/api/todos", json={"title": "Alpha complete", "completed": True})
        # Mark as completed via update
        todo_id = resp.json()["id"]
        client.patch(f"/api/todos/{todo_id}", json={"completed": True})

        # Filter by completed
        completed_resp = client.get("/api/todos?completed=true")
        assert completed_resp.status_code == 200
        for todo in completed_resp.json():
            assert todo["completed"] is True

        # Search
        search_resp = client.get("/api/todos?search=Alpha")
        assert search_resp.status_code == 200
        assert len(search_resp.json()) >= 1
        for todo in search_resp.json():
            assert "Alpha" in todo["title"]

        # Pagination
        page_resp = client.get("/api/todos?limit=1&skip=0")
        assert page_resp.status_code == 200
        assert len(page_resp.json()) <= 1
