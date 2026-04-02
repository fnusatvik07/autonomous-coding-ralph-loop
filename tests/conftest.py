"""Shared fixtures for Ralph Loop tests."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Callable

import pytest

from ralph.config import Config
from ralph.models import AgentResult, PRD, Feature, Task, TaskStatus
from ralph.providers.base import BaseProvider


class MockProvider(BaseProvider):
    """Mock provider for testing."""

    def __init__(self, responses: list[AgentResult], workspace_dir: str = "/tmp", **kwargs):
        super().__init__(model="mock-model", workspace_dir=workspace_dir)
        self._responses = list(responses)
        self._call_log: list[dict] = []

    @property
    def call_log(self) -> list[dict]:
        return self._call_log

    async def run_session(
        self,
        system_prompt: str,
        user_message: str,
        max_turns: int = 200,
        on_text: Callable[[str], None] | None = None,
        on_tool: Callable[[str, dict], None] | None = None,
    ) -> AgentResult:
        self._call_log.append({
            "system_prompt": system_prompt[:200],
            "user_message": user_message[:200],
            "max_turns": max_turns,
        })

        if not self._responses:
            return AgentResult(success=False, error="No more mock responses")

        result = self._responses.pop(0)

        if "MOCK_WRITE:" in result.final_response:
            for line in result.final_response.split("\n"):
                if line.startswith("MOCK_WRITE:"):
                    _, path, content = line.split(":", 2)
                    full_path = Path(self.workspace_dir) / path
                    full_path.parent.mkdir(parents=True, exist_ok=True)
                    full_path.write_text(content)

        if on_text and result.final_response:
            on_text(result.final_response)

        return result


@pytest.fixture
def workspace(tmp_path):
    ws = tmp_path / "workspace"
    ws.mkdir()
    return ws


@pytest.fixture
def workspace_with_ralph(workspace):
    (workspace / ".ralph").mkdir()
    return workspace


@pytest.fixture
def sample_prd_data():
    """Sample PRD in v3 hierarchical format (features → tasks)."""
    return {
        "project_name": "test-project",
        "branch_name": "ralph/test",
        "description": "A test project",
        "features": [
            {
                "id": "FEAT-001",
                "title": "Infrastructure",
                "priority": 1,
                "tasks": [
                    {
                        "id": "TASK-001", "category": "functional", "complexity": "simple",
                        "title": "Initialize project", "description": "Set up project",
                        "acceptance_criteria": ["Project exists", "Tests pass"],
                        "status": "pending", "test_command": "pytest tests/ -v", "notes": "",
                    },
                ],
            },
            {
                "id": "FEAT-002",
                "title": "User Management",
                "priority": 2,
                "tasks": [
                    {
                        "id": "TASK-002", "category": "functional", "complexity": "moderate",
                        "title": "Add user model", "description": "Create user model",
                        "acceptance_criteria": ["User model has fields", "Tests pass"],
                        "status": "pending", "test_command": "pytest tests/test_models.py -v", "notes": "",
                    },
                    {
                        "id": "TASK-003", "category": "integration", "complexity": "complex",
                        "title": "Add API endpoints", "description": "CRUD endpoints",
                        "acceptance_criteria": ["GET /users works", "POST creates user", "Tests pass"],
                        "status": "pending", "test_command": "pytest tests/test_api.py -v", "notes": "",
                    },
                ],
            },
        ],
    }


@pytest.fixture
def sample_prd_data_flat():
    """Sample PRD in v2 flat format (backward compat)."""
    return {
        "project_name": "flat-project",
        "branch_name": "main",
        "description": "Flat format test",
        "tasks": [
            {"id": "TASK-001", "category": "functional", "title": "Task one",
             "description": "d", "acceptance_criteria": ["works"], "status": "pending",
             "test_command": "echo ok", "notes": ""},
        ],
    }


@pytest.fixture
def workspace_with_prd(workspace_with_ralph, sample_prd_data):
    prd_path = workspace_with_ralph / ".ralph" / "prd.json"
    prd_path.write_text(json.dumps(sample_prd_data, indent=2))
    return workspace_with_ralph


@pytest.fixture
def config(workspace):
    return Config(
        provider="claude-sdk",
        model="mock-model",
        workspace_dir=workspace,
        max_iterations=5,
        max_healer_attempts=2,
        max_turns_per_session=10,
        max_incomplete_retries=2,
        session_timeout_seconds=60,
    )
