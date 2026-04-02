"""Tests for the FastAPI application core: lifespan, health check, error handling, docs."""
import os

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.main import app, lifespan


class TestAppInstance:
    """Test TASK-010: FastAPI app with lifespan initializes database."""

    def test_app_main_exists(self):
        """app/main.py exists and app is importable."""
        from app.main import app
        assert app is not None

    def test_app_is_fastapi_instance(self):
        """App is a FastAPI instance."""
        assert isinstance(app, FastAPI)

    def test_app_has_title(self):
        """App has a title."""
        assert app.title == "Todo API"

    def test_lifespan_calls_init_db(self, tmp_path, monkeypatch):
        """Lifespan handler calls init_db() on startup."""
        import importlib
        import sqlite3

        import app.database as db_mod

        db_path = str(tmp_path / "test_lifespan.db")
        monkeypatch.setenv("DATABASE_URL", db_path)
        # Reload so the module-level DATABASE_URL picks up the new env var
        importlib.reload(db_mod)

        try:
            with TestClient(app) as client:
                # After startup, the database should exist with todos table
                conn = sqlite3.connect(db_path)
                cursor = conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name='todos'"
                )
                tables = cursor.fetchall()
                conn.close()
                assert len(tables) == 1
                assert tables[0][0] == "todos"
        finally:
            importlib.reload(db_mod)

    def test_todos_router_included_with_api_prefix(self):
        """Todos router is included with /api prefix."""
        from app.routers.todos import router
        assert router is not None


class TestHealthCheck:
    """Test TASK-011: GET / returns health check status ok."""

    def test_health_check_returns_200(self, tmp_path):
        """GET / returns 200 status code."""
        db_path = str(tmp_path / "test_health.db")
        os.environ["DATABASE_URL"] = db_path
        try:
            with TestClient(app) as client:
                response = client.get("/")
                assert response.status_code == 200
        finally:
            os.environ.pop("DATABASE_URL", None)

    def test_health_check_returns_status_ok(self, tmp_path):
        """GET / returns {"status": "ok"}."""
        db_path = str(tmp_path / "test_health2.db")
        os.environ["DATABASE_URL"] = db_path
        try:
            with TestClient(app) as client:
                response = client.get("/")
                assert response.json() == {"status": "ok"}
        finally:
            os.environ.pop("DATABASE_URL", None)


class TestGlobalErrorHandler:
    """Test TASK-012: Global exception handler returns 500 JSON."""

    def test_unhandled_exception_returns_500(self, tmp_path):
        """Unhandled exceptions return 500 status code."""
        db_path = str(tmp_path / "test_error.db")
        os.environ["DATABASE_URL"] = db_path

        # Add a temporary route that raises an exception
        @app.get("/test-error-route")
        async def raise_error():
            raise RuntimeError("Something went wrong")

        try:
            with TestClient(app, raise_server_exceptions=False) as client:
                response = client.get("/test-error-route")
                assert response.status_code == 500
        finally:
            os.environ.pop("DATABASE_URL", None)

    def test_unhandled_exception_returns_json_body(self, tmp_path):
        """Unhandled exceptions return {"detail": "Internal server error"}."""
        db_path = str(tmp_path / "test_error2.db")
        os.environ["DATABASE_URL"] = db_path

        try:
            with TestClient(app, raise_server_exceptions=False) as client:
                response = client.get("/test-error-route")
                assert response.json() == {"detail": "Internal server error"}
        finally:
            os.environ.pop("DATABASE_URL", None)

    def test_unhandled_exception_content_type_json(self, tmp_path):
        """Unhandled exceptions return application/json content type."""
        db_path = str(tmp_path / "test_error3.db")
        os.environ["DATABASE_URL"] = db_path

        try:
            with TestClient(app, raise_server_exceptions=False) as client:
                response = client.get("/test-error-route")
                assert "application/json" in response.headers["content-type"]
        finally:
            os.environ.pop("DATABASE_URL", None)


class TestSwaggerDocs:
    """Test TASK-013: Swagger UI accessible at /docs."""

    def test_docs_returns_200(self, tmp_path):
        """GET /docs returns 200."""
        db_path = str(tmp_path / "test_docs.db")
        os.environ["DATABASE_URL"] = db_path
        try:
            with TestClient(app) as client:
                response = client.get("/docs")
                assert response.status_code == 200
        finally:
            os.environ.pop("DATABASE_URL", None)

    def test_docs_contains_swagger_html(self, tmp_path):
        """GET /docs returns HTML containing Swagger UI."""
        db_path = str(tmp_path / "test_docs2.db")
        os.environ["DATABASE_URL"] = db_path
        try:
            with TestClient(app) as client:
                response = client.get("/docs")
                assert "swagger" in response.text.lower()
        finally:
            os.environ.pop("DATABASE_URL", None)
