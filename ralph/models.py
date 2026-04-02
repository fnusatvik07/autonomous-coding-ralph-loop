"""Data models for Ralph Loop v3.

Hierarchical: PRD → Features → Tasks
Each Feature groups related tasks that a coder handles in one session.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class TaskStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    PASSED = "passed"
    FAILED = "failed"
    BLOCKED = "blocked"


class Task(BaseModel):
    """A single testable behavior within a feature."""

    id: str
    category: str = Field(default="functional")
    complexity: str = Field(default="simple", description="simple, moderate, complex")
    title: str
    description: str = ""
    acceptance_criteria: list[str] = Field(default_factory=list)
    status: TaskStatus = TaskStatus.PENDING
    test_command: str = ""
    notes: str = ""


class Feature(BaseModel):
    """A group of related tasks handled in one coding session."""

    id: str
    title: str
    priority: int = Field(default=0, description="Lower = higher priority")
    tasks: list[Task] = Field(default_factory=list)

    @property
    def pending_tasks(self) -> list[Task]:
        return [t for t in self.tasks if t.status == TaskStatus.PENDING]

    @property
    def completed_tasks(self) -> list[Task]:
        return [t for t in self.tasks if t.status == TaskStatus.PASSED]

    @property
    def is_complete(self) -> bool:
        return len(self.pending_tasks) == 0

    @property
    def max_complexity(self) -> str:
        """Highest complexity task in this feature (for review gating)."""
        levels = {"simple": 0, "moderate": 1, "complex": 2}
        max_level = max((levels.get(t.complexity, 0) for t in self.tasks), default=0)
        return {0: "simple", 1: "moderate", 2: "complex"}[max_level]


class PRD(BaseModel):
    """Product Requirements Document — hierarchical feature → task structure."""

    project_name: str
    branch_name: str = "main"
    description: str = ""
    features: list[Feature] = Field(default_factory=list)

    # Backward compat: flat task list (populated from features)
    @property
    def tasks(self) -> list[Task]:
        """All tasks across all features (flat view)."""
        all_tasks = []
        for f in self.features:
            all_tasks.extend(f.tasks)
        return all_tasks

    @property
    def pending_tasks(self) -> list[Task]:
        return [t for t in self.tasks if t.status == TaskStatus.PENDING]

    @property
    def completed_tasks(self) -> list[Task]:
        return [t for t in self.tasks if t.status == TaskStatus.PASSED]

    @property
    def progress_pct(self) -> float:
        all_tasks = self.tasks
        if not all_tasks:
            return 0.0
        return len(self.completed_tasks) / len(all_tasks) * 100

    def get_next_feature(self) -> Feature | None:
        """Get next feature with pending tasks, ordered by priority."""
        pending = [f for f in self.features if f.pending_tasks]
        if not pending:
            return None
        return sorted(pending, key=lambda f: f.priority)[0]

    def get_next_task(self) -> Task | None:
        """Get highest priority pending task (flat, backward compat)."""
        pending = self.pending_tasks
        if not pending:
            return None
        return pending[0]  # Already ordered by feature priority

    def mark_task(self, task_id: str, status: TaskStatus, notes: str = "") -> None:
        for f in self.features:
            for t in f.tasks:
                if t.id == task_id:
                    t.status = status
                    if notes:
                        t.notes = notes
                    return
        raise ValueError(f"Task '{task_id}' not found")


class AgentResult(BaseModel):
    """Result of a complete agent session."""

    success: bool
    final_response: str = ""
    tool_calls_made: int = 0
    error: str = ""
    cost_usd: float = 0.0
    duration_ms: int = 0


class QAResult(BaseModel):
    """Result of a QA/reviewer check."""

    passed: bool
    issues: list[str] = Field(default_factory=list)
    test_output: str = ""
    suggestions: list[str] = Field(default_factory=list)
    cost_usd: float = 0.0
    duration_ms: int = 0
