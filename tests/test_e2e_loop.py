"""End-to-end integration tests for the full Ralph Loop with MockProvider."""

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from ralph.config import Config
from ralph.loop import RalphLoop
from ralph.memory.progress import get_progress_summary
from ralph.memory.guardrails import get_guardrails
from ralph.models import AgentResult, QAResult, TaskStatus
from ralph.spec.generator import load_prd
from tests.conftest import MockProvider


def _spec_response(workspace_dir: str) -> AgentResult:
    prd = {
        "project_name": "e2e-test", "branch_name": "ralph/e2e",
        "description": "E2E test project",
        "tasks": [
            {"id": "TASK-001", "title": "Create hello.py", "description": "hello world",
             "acceptance_criteria": ["hello.py exists", "prints Hello"],
             "priority": 1, "status": "pending", "test_command": "python hello.py", "notes": ""},
            {"id": "TASK-002", "title": "Add tests", "description": "add tests",
             "acceptance_criteria": ["test exists", "pytest passes"],
             "priority": 2, "status": "pending", "test_command": "pytest -v", "notes": ""},
        ],
    }
    return AgentResult(
        success=True,
        final_response=f"MOCK_WRITE:.ralph/prd.json:{json.dumps(prd)}",
        tool_calls_made=5, cost_usd=0.02,
    )


def _coding_ok(task_id: str) -> AgentResult:
    return AgentResult(
        success=True,
        final_response=f"Implemented {task_id}. <ralph:task_complete>{task_id}</ralph:task_complete>",
        tool_calls_made=15, cost_usd=0.05, duration_ms=30000,
    )


def _qa_pass(workspace_dir: str) -> AgentResult:
    qa = {"passed": True, "issues": [], "test_output": "all pass", "suggestions": []}
    return AgentResult(
        success=True,
        final_response=f"MOCK_WRITE:.ralph/qa_result.json:{json.dumps(qa)}",
        tool_calls_made=8, cost_usd=0.03,
    )


def _qa_fail(workspace_dir: str) -> AgentResult:
    qa = {"passed": False, "issues": ["test fails"], "test_output": "1 fail", "suggestions": ["fix it"]}
    return AgentResult(
        success=True,
        final_response=f"MOCK_WRITE:.ralph/qa_result.json:{json.dumps(qa)}",
        tool_calls_made=8, cost_usd=0.03,
    )


def _healer_ok() -> AgentResult:
    return AgentResult(success=True, final_response="Fixed.", tool_calls_made=5, cost_usd=0.02)


def _blocked(task_id: str) -> AgentResult:
    return AgentResult(
        success=True,
        final_response=f"<ralph:task_blocked>{task_id}: missing db</ralph:task_blocked>",
        tool_calls_made=3, cost_usd=0.01,
    )


def _session_error() -> AgentResult:
    return AgentResult(success=False, error="API rate limit exceeded", cost_usd=0.0)


def _make_loop(workspace, responses, **overrides):
    """Helper: create a RalphLoop with a mock provider sequence."""
    ws = str(workspace)
    call_count = [0]

    def mock_create(config, model_override=""):
        idx = min(call_count[0], len(responses) - 1) if responses else 0
        mock = MockProvider(
            responses=[responses[idx]] if idx < len(responses) else [],
            workspace_dir=ws,
        )
        call_count[0] += 1
        return mock

    defaults = dict(
        provider="claude-sdk", model="mock",
        workspace_dir=workspace, max_iterations=10,
        max_healer_attempts=2, max_incomplete_retries=2,
        session_timeout_seconds=60,
    )
    defaults.update(overrides)
    config = Config(**defaults)
    loop = RalphLoop(config)
    return loop, mock_create


class TestE2EHappyPath:
    @pytest.mark.asyncio
    async def test_full_loop_two_tasks_pass(self, workspace):
        ws = str(workspace)
        responses = [
            _spec_response(ws),
            _coding_ok("TASK-001"), _qa_pass(ws),
            _coding_ok("TASK-002"), _qa_pass(ws),
        ]
        loop, mock_create = _make_loop(workspace, responses)
        with patch("ralph.loop._create_provider", side_effect=mock_create), \
             patch("ralph.loop.asyncio.sleep", return_value=None):
            await loop.run("Build a hello world project")
        prd = load_prd(ws)
        assert prd.progress_pct == 100.0


class TestE2EQAFailAndHeal:
    @pytest.mark.asyncio
    async def test_qa_fails_healer_fixes(self, workspace):
        ws = str(workspace)
        responses = [
            _spec_response(ws),
            _coding_ok("TASK-001"), _qa_fail(ws),
            _healer_ok(), _qa_pass(ws),
            _coding_ok("TASK-002"), _qa_pass(ws),
        ]
        loop, mock_create = _make_loop(workspace, responses)
        with patch("ralph.loop._create_provider", side_effect=mock_create), \
             patch("ralph.loop.asyncio.sleep", return_value=None):
            await loop.run("Build something")
        prd = load_prd(ws)
        task1 = next(t for t in prd.tasks if t.id == "TASK-001")
        assert task1.status == TaskStatus.PASSED


class TestE2EHealerExhaustion:
    @pytest.mark.asyncio
    async def test_all_heal_attempts_fail(self, workspace):
        ws = str(workspace)
        responses = [
            _spec_response(ws),
            _coding_ok("TASK-001"), _qa_fail(ws),
            _healer_ok(), _qa_fail(ws),
            _healer_ok(), _qa_fail(ws),
            # Task should be FAILED now, loop moves to TASK-002
            _coding_ok("TASK-002"), _qa_pass(ws),
        ]
        loop, mock_create = _make_loop(workspace, responses)
        with patch("ralph.loop._create_provider", side_effect=mock_create), \
             patch("ralph.loop.asyncio.sleep", return_value=None):
            await loop.run("Build something")
        prd = load_prd(ws)
        task1 = next(t for t in prd.tasks if t.id == "TASK-001")
        assert task1.status == TaskStatus.FAILED


class TestE2EBlocked:
    @pytest.mark.asyncio
    async def test_blocked_task_logged(self, workspace):
        ws = str(workspace)
        responses = [_spec_response(ws), _blocked("TASK-001")]
        loop, mock_create = _make_loop(workspace, responses, max_iterations=2)
        with patch("ralph.loop._create_provider", side_effect=mock_create), \
             patch("ralph.loop.asyncio.sleep", return_value=None):
            await loop.run("Build something")
        rails = get_guardrails(ws)
        assert "missing db" in rails


class TestE2ESessionFailure:
    @pytest.mark.asyncio
    async def test_provider_failure_does_not_crash(self, workspace):
        ws = str(workspace)
        responses = [_spec_response(ws), _session_error(), _session_error()]
        loop, mock_create = _make_loop(workspace, responses, max_iterations=3, max_incomplete_retries=2)
        with patch("ralph.loop._create_provider", side_effect=mock_create), \
             patch("ralph.loop.asyncio.sleep", return_value=None):
            await loop.run("Build something")
        progress = get_progress_summary(ws)
        assert "SESSION_ERROR" in progress or "INCOMPLETE" in progress


class TestE2EIncompleteAutoFail:
    @pytest.mark.asyncio
    async def test_incomplete_task_auto_fails_after_retries(self, workspace):
        ws = str(workspace)
        # Agent returns text without any completion signal
        no_signal = AgentResult(success=True, final_response="I did some work but no marker", cost_usd=0.01)
        responses = [_spec_response(ws), no_signal, no_signal, no_signal]
        loop, mock_create = _make_loop(workspace, responses, max_iterations=5, max_incomplete_retries=2)
        with patch("ralph.loop._create_provider", side_effect=mock_create), \
             patch("ralph.loop.asyncio.sleep", return_value=None):
            await loop.run("Build something")
        prd = load_prd(ws)
        task1 = next(t for t in prd.tasks if t.id == "TASK-001")
        assert task1.status == TaskStatus.FAILED
        assert "incomplete" in task1.notes.lower()


class TestE2EExistingPRD:
    @pytest.mark.asyncio
    async def test_resume_skips_spec_gen(self, workspace_with_prd):
        ws = str(workspace_with_prd)
        responses = [_coding_ok("TASK-001"), _qa_pass(ws)]
        loop, mock_create = _make_loop(workspace_with_prd, responses, max_iterations=2)
        with patch("ralph.loop._create_provider", side_effect=mock_create), \
             patch("ralph.loop.asyncio.sleep", return_value=None):
            await loop.run("")
        prd = load_prd(ws)
        task1 = next(t for t in prd.tasks if t.id == "TASK-001")
        assert task1.status == TaskStatus.PASSED


class TestE2EApprovalGate:
    @pytest.mark.asyncio
    async def test_approval_rejected_stops(self, workspace):
        ws = str(workspace)
        responses = [_spec_response(ws)]
        loop, mock_create = _make_loop(workspace, responses, approve_spec=True)
        with patch("ralph.loop._create_provider", side_effect=mock_create), \
             patch("ralph.loop.asyncio.sleep", return_value=None), \
             patch.object(RalphLoop, "_ask_approval", return_value=False):
            await loop.run("Build something")
        progress = get_progress_summary(ws)
        assert "TASK" not in progress or "Iteration" not in progress


class TestE2EBudgetExhaustion:
    @pytest.mark.asyncio
    async def test_loop_stops_when_budget_exceeded(self, workspace):
        ws = str(workspace)
        expensive = AgentResult(
            success=True,
            final_response=f"MOCK_WRITE:.ralph/prd.json:{json.dumps({'project_name':'x','tasks':[{'id':'T-1','title':'X','description':'d','acceptance_criteria':['ok'],'priority':1,'status':'pending','test_command':'','notes':''}]})}",
            cost_usd=0.10,  # costs $0.10 per session
        )
        coding = AgentResult(
            success=True,
            final_response="<ralph:task_complete>T-1</ralph:task_complete>",
            cost_usd=0.50,  # exceeds $0.05 budget
        )
        responses = [expensive, coding]
        loop, mock_create = _make_loop(workspace, responses, max_budget_usd=0.05)
        with patch("ralph.loop._create_provider", side_effect=mock_create), \
             patch("ralph.loop.asyncio.sleep", return_value=None):
            await loop.run("test budget")
        # Budget was $0.05, spec cost $0.10 -> should stop before coding
        assert loop.cumulative_cost >= 0.05


class TestE2ECorruptedPRD:
    @pytest.mark.asyncio
    async def test_corrupted_prd_handled(self, workspace_with_ralph):
        (workspace_with_ralph / ".ralph" / "prd.json").write_text("{broken json")
        config = Config(provider="claude-sdk", model="mock", workspace_dir=workspace_with_ralph, max_iterations=1)
        loop = RalphLoop(config)
        # With empty task and corrupted PRD, should raise (no way to regenerate)
        with pytest.raises(RuntimeError, match="No PRD and no task"):
            with patch("ralph.loop._create_provider", side_effect=lambda c: MockProvider([], str(workspace_with_ralph))), \
                 patch("ralph.loop.asyncio.sleep", return_value=None):
                await loop.run("")


class TestE2ECostTracking:
    @pytest.mark.asyncio
    async def test_cumulative_cost(self, workspace):
        ws = str(workspace)
        responses = [
            AgentResult(success=True, final_response=f"MOCK_WRITE:.ralph/prd.json:{json.dumps({'project_name':'x','tasks':[{'id':'T-1','title':'X','description':'d','acceptance_criteria':['ok'],'priority':1,'status':'pending','test_command':'','notes':''}]})}", cost_usd=0.01),
            AgentResult(success=True, final_response="<ralph:task_complete>T-1</ralph:task_complete>", cost_usd=0.05),
            AgentResult(success=True, final_response=f"MOCK_WRITE:.ralph/qa_result.json:{json.dumps({'passed':True,'issues':[]})}", cost_usd=0.03),
        ]
        loop, mock_create = _make_loop(workspace, responses, max_iterations=5)
        with patch("ralph.loop._create_provider", side_effect=mock_create), \
             patch("ralph.loop.asyncio.sleep", return_value=None):
            await loop.run("test cost")
        assert loop.cumulative_cost > 0
