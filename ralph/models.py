"""Data models for Ralph Loop."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class TaskStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    PASSED = "passed"
    FAILED = "failed"


class Task(BaseModel):
    """A single task/user story in the PRD."""

    id: str
    category: str = Field(default="functional", description="functional, validation, error_handling, style, integration, quality")
    title: str
    description: str
    acceptance_criteria: list[str] = Field(default_factory=list)
    priority: int = Field(default=0, description="Lower = higher priority")
    status: TaskStatus = TaskStatus.PENDING
    test_command: str = Field(default="", description="Command to verify this task")
    notes: str = ""


class PRD(BaseModel):
    """Product Requirements Document - the task queue."""

    project_name: str
    branch_name: str = "main"
    description: str = ""
    tasks: list[Task] = Field(default_factory=list)

    @property
    def pending_tasks(self) -> list[Task]:
        return [t for t in self.tasks if t.status == TaskStatus.PENDING]

    @property
    def completed_tasks(self) -> list[Task]:
        return [t for t in self.tasks if t.status == TaskStatus.PASSED]

    @property
    def progress_pct(self) -> float:
        if not self.tasks:
            return 0.0
        return len(self.completed_tasks) / len(self.tasks) * 100

    def get_next_task(self) -> Task | None:
        """Get highest priority pending task."""
        pending = self.pending_tasks
        if not pending:
            return None
        return sorted(pending, key=lambda t: t.priority)[0]

    def mark_task(self, task_id: str, status: TaskStatus, notes: str = "") -> None:
        for t in self.tasks:
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
    """Result of a QA sentinel check."""

    passed: bool
    issues: list[str] = Field(default_factory=list)
    test_output: str = ""
    suggestions: list[str] = Field(default_factory=list)
    cost_usd: float = 0.0
    duration_ms: int = 0
