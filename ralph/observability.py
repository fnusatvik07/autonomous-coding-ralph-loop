"""Observability - structured logging, cost tracking, session analytics, run IDs."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from ralph.models import AgentResult, QAResult

logger = logging.getLogger("ralph")

_setup_done = False


def generate_run_id() -> str:
    """Generate a unique run ID for correlating all sessions in one ralph run."""
    return uuid4().hex[:8]


def setup_logging(workspace_dir: str, verbose: bool = False) -> None:
    """Configure structured logging to file + console. Idempotent."""
    global _setup_done
    if _setup_done:
        return
    _setup_done = True

    ralph_dir = Path(workspace_dir) / ".ralph"
    ralph_dir.mkdir(exist_ok=True)

    file_handler = logging.FileHandler(ralph_dir / "ralph.log")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter(
        "%(asctime)s %(levelname)s %(message)s"
    ))

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.DEBUG if verbose else logging.WARNING)
    console_handler.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))

    logger.setLevel(logging.DEBUG)
    logger.handlers.clear()
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)


def log_session(
    workspace_dir: str,
    run_id: str,
    iteration: int,
    phase: str,
    task_id: str,
    result: AgentResult,
) -> None:
    """Log a session result to sessions.jsonl."""
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "run_id": run_id,
        "iteration": iteration,
        "phase": phase,
        "task_id": task_id,
        "success": result.success,
        "error": result.error or None,
        "tool_calls": result.tool_calls_made,
        "cost_usd": result.cost_usd,
        "duration_ms": result.duration_ms,
        "response_length": len(result.final_response),
    }

    path = Path(workspace_dir) / ".ralph" / "sessions.jsonl"
    with open(path, "a") as f:
        f.write(json.dumps(entry) + "\n")

    logger.info(
        "session: run=%s phase=%s task=%s success=%s tools=%d cost=$%.4f duration=%dms",
        run_id, phase, task_id, result.success, result.tool_calls_made,
        result.cost_usd, result.duration_ms,
    )


def log_qa(
    workspace_dir: str,
    run_id: str,
    iteration: int,
    task_id: str,
    qa_result: QAResult,
) -> None:
    """Log a QA result."""
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "run_id": run_id,
        "iteration": iteration,
        "phase": "qa",
        "task_id": task_id,
        "passed": qa_result.passed,
        "issues": qa_result.issues,
        "cost_usd": qa_result.cost_usd,
        "duration_ms": qa_result.duration_ms,
    }

    path = Path(workspace_dir) / ".ralph" / "sessions.jsonl"
    with open(path, "a") as f:
        f.write(json.dumps(entry) + "\n")

    if qa_result.passed:
        logger.info("qa: run=%s task=%s PASSED", run_id, task_id)
    else:
        logger.warning("qa: run=%s task=%s FAILED issues=%s", run_id, task_id, qa_result.issues[:3])


def log_task_transition(
    workspace_dir: str,
    run_id: str,
    task_id: str,
    old_status: str,
    new_status: str,
    iteration: int,
) -> None:
    """Log a task status transition."""
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "run_id": run_id,
        "iteration": iteration,
        "event": "task_transition",
        "task_id": task_id,
        "old_status": old_status,
        "new_status": new_status,
    }

    path = Path(workspace_dir) / ".ralph" / "sessions.jsonl"
    with open(path, "a") as f:
        f.write(json.dumps(entry) + "\n")

    logger.info("task: run=%s %s %s -> %s", run_id, task_id, old_status, new_status)


def get_session_analytics(workspace_dir: str) -> dict:
    """Read sessions.jsonl and compute analytics."""
    path = Path(workspace_dir) / ".ralph" / "sessions.jsonl"
    if not path.exists():
        return {"sessions": 0, "total_cost": 0.0}

    sessions = []
    for line in path.read_text().splitlines():
        if line.strip():
            try:
                sessions.append(json.loads(line))
            except json.JSONDecodeError:
                continue

    total_cost = sum(s.get("cost_usd", 0) for s in sessions)
    total_duration = sum(s.get("duration_ms", 0) for s in sessions)
    total_tools = sum(s.get("tool_calls", 0) for s in sessions)
    failures = sum(1 for s in sessions if not s.get("success", True) and not s.get("passed", True))

    cost_by_phase: dict[str, float] = {}
    for s in sessions:
        phase = s.get("phase", "unknown")
        cost_by_phase[phase] = cost_by_phase.get(phase, 0) + s.get("cost_usd", 0)

    return {
        "sessions": len(sessions),
        "total_cost": total_cost,
        "total_duration_ms": total_duration,
        "total_tool_calls": total_tools,
        "failures": failures,
        "cost_by_phase": cost_by_phase,
    }
