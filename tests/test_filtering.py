"""Tests for filtering, sorting, and pagination of todos."""
import time

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client_with_data(client: TestClient):
    """Client with 3 seeded todos: 2 incomplete, 1 completed."""
    client.post("/api/todos", json={"title": "Incomplete One"})
    client.post("/api/todos", json={"title": "Incomplete Two"})
    client.post("/api/todos", json={"title": "Completed One", "completed": True})
    return client


class TestFilterCompletedTrue:
    """TASK-041: Filter by completed=true returns only completed todos."""

    def test_completed_true_returns_200(self, client_with_data: TestClient):
        resp = client_with_data.get("/api/todos", params={"completed": "true"})
        assert resp.status_code == 200

    def test_completed_true_returns_only_completed(self, client_with_data: TestClient):
        resp = client_with_data.get("/api/todos", params={"completed": "true"})
        todos = resp.json()
        assert len(todos) == 1
        assert todos[0]["title"] == "Completed One"
        assert todos[0]["completed"] is True


class TestFilterCompletedFalse:
    """TASK-042: Filter by completed=false returns only incomplete todos."""

    def test_completed_false_returns_200(self, client_with_data: TestClient):
        resp = client_with_data.get("/api/todos", params={"completed": "false"})
        assert resp.status_code == 200

    def test_completed_false_returns_only_incomplete(self, client_with_data: TestClient):
        resp = client_with_data.get("/api/todos", params={"completed": "false"})
        todos = resp.json()
        assert len(todos) == 2
        assert all(t["completed"] is False for t in todos)


class TestSearch:
    """TASK-043: Search by case-insensitive substring match on title."""

    def test_search_returns_200(self, client: TestClient):
        client.post("/api/todos", json={"title": "Buy Milk"})
        client.post("/api/todos", json={"title": "Buy Bread"})
        client.post("/api/todos", json={"title": "Walk Dog"})
        resp = client.get("/api/todos", params={"search": "buy"})
        assert resp.status_code == 200

    def test_search_case_insensitive(self, client: TestClient):
        client.post("/api/todos", json={"title": "Buy Milk"})
        client.post("/api/todos", json={"title": "Buy Bread"})
        client.post("/api/todos", json={"title": "Walk Dog"})
        resp = client.get("/api/todos", params={"search": "buy"})
        todos = resp.json()
        assert len(todos) == 2
        titles = {t["title"] for t in todos}
        assert titles == {"Buy Milk", "Buy Bread"}

    def test_search_no_match(self, client: TestClient):
        client.post("/api/todos", json={"title": "Buy Milk"})
        resp = client.get("/api/todos", params={"search": "zzz"})
        assert resp.json() == []


class TestPagination:
    """TASK-044: Pagination with skip and limit."""

    def test_skip_0_limit_3(self, client: TestClient):
        for i in range(10):
            client.post("/api/todos", json={"title": f"Todo {i}"})
        resp = client.get("/api/todos", params={"skip": 0, "limit": 3})
        assert resp.status_code == 200
        assert len(resp.json()) == 3

    def test_skip_3_limit_3(self, client: TestClient):
        for i in range(10):
            client.post("/api/todos", json={"title": f"Todo {i}"})
        resp1 = client.get("/api/todos", params={"skip": 0, "limit": 3})
        resp2 = client.get("/api/todos", params={"skip": 3, "limit": 3})
        ids1 = {t["id"] for t in resp1.json()}
        ids2 = {t["id"] for t in resp2.json()}
        assert len(resp2.json()) == 3
        assert ids1.isdisjoint(ids2)

    def test_skip_beyond_count(self, client: TestClient):
        client.post("/api/todos", json={"title": "Only one"})
        resp = client.get("/api/todos", params={"skip": 100, "limit": 10})
        assert resp.json() == []


class TestSortTitleAsc:
    """TASK-045: Sort by title ascending."""

    def test_sort_title_asc_returns_200(self, client: TestClient):
        for title in ["Cherry", "Apple", "Banana"]:
            client.post("/api/todos", json={"title": title})
        resp = client.get("/api/todos", params={"sort": "title", "order": "asc"})
        assert resp.status_code == 200

    def test_sort_title_asc_order(self, client: TestClient):
        for title in ["Cherry", "Apple", "Banana"]:
            client.post("/api/todos", json={"title": title})
        resp = client.get("/api/todos", params={"sort": "title", "order": "asc"})
        titles = [t["title"] for t in resp.json()]
        assert titles == ["Apple", "Banana", "Cherry"]


class TestDefaultSort:
    """TASK-046: Default sort is created_at descending (newest first)."""

    def test_default_sort_newest_first(self, client: TestClient):
        titles = ["First", "Second", "Third"]
        for title in titles:
            client.post("/api/todos", json={"title": title})
            time.sleep(0.01)  # ensure distinct timestamps
        resp = client.get("/api/todos")
        result_titles = [t["title"] for t in resp.json()]
        assert result_titles == ["Third", "Second", "First"]


class TestInvalidQueryParams:
    """TASK-047: Query parameter validation rejects invalid values."""

    def test_limit_zero_returns_422(self, client: TestClient):
        resp = client.get("/api/todos", params={"limit": 0})
        assert resp.status_code == 422

    def test_limit_101_returns_422(self, client: TestClient):
        resp = client.get("/api/todos", params={"limit": 101})
        assert resp.status_code == 422

    def test_skip_negative_returns_422(self, client: TestClient):
        resp = client.get("/api/todos", params={"skip": -1})
        assert resp.status_code == 422

    def test_limit_boundary_1_ok(self, client: TestClient):
        resp = client.get("/api/todos", params={"limit": 1})
        assert resp.status_code == 200

    def test_limit_boundary_100_ok(self, client: TestClient):
        resp = client.get("/api/todos", params={"limit": 100})
        assert resp.status_code == 200

    def test_sort_invalid_returns_422(self, client: TestClient):
        resp = client.get("/api/todos", params={"sort": "invalid"})
        assert resp.status_code == 422

    def test_order_invalid_returns_422(self, client: TestClient):
        resp = client.get("/api/todos", params={"order": "invalid"})
        assert resp.status_code == 422


class TestDefaultPagination:
    """TASK-048: Default pagination: limit=20, skip=0."""

    def test_default_limit_returns_20(self, client: TestClient):
        for i in range(25):
            client.post("/api/todos", json={"title": f"Todo {i}"})
        resp = client.get("/api/todos")
        assert resp.status_code == 200
        assert len(resp.json()) == 20
