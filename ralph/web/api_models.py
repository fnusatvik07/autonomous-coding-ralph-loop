"""Pydantic models for the REST API responses."""

from __future__ import annotations

from pydantic import BaseModel, Field


class RunRequest(BaseModel):
    task: str
    provider: str = "claude-sdk"
    model: str = ""
    budget: float = 0.0
    max_iterations: int = 50
    approve_spec: bool = False
    auto_route: bool = False


class RunResponse(BaseModel):
    run_id: str
    status: str = "started"


class TaskResponse(BaseModel):
    id: str
    title: str
    description: str
    acceptance_criteria: list[str]
    priority: int
    status: str
    test_command: str
    notes: str


class PRDResponse(BaseModel):
    project_name: str
    branch_name: str
    description: str
    tasks: list[TaskResponse]


class SessionEntry(BaseModel):
    timestamp: str
    run_id: str = ""
    iteration: int = 0
    phase: str = ""
    task_id: str = ""
    success: bool | None = None
    passed: bool | None = None
    error: str | None = None
    tool_calls: int = 0
    cost_usd: float = 0.0
    duration_ms: int = 0
    issues: list[str] = Field(default_factory=list)


class AnalyticsResponse(BaseModel):
    sessions: int
    total_cost: float
    total_duration_ms: int
    total_tool_calls: int
    failures: int
    cost_by_phase: dict[str, float]


class FileEntry(BaseModel):
    name: str
    path: str
    is_dir: bool
    size: int = 0
    children: list[FileEntry] = Field(default_factory=list)


class FileContentResponse(BaseModel):
    path: str
    content: str
    language: str
    size: int


class GitCommit(BaseModel):
    hash: str
    message: str
