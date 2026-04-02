"""End-to-end integration tests for the Ralph Loop with MockProvider.

Tests use the v3 hierarchical PRD format (features → tasks).
"""

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
    """Mock: generates spec (session 1) and PRD (session 2).

    Returns TWO responses consumed in sequence:
    - First call: spec.md content (saved by fallback)
    - Second call: prd.json as JSON in response text (extracted by _extract_json)

    But since the mock returns one response at a time, we return
    the PRD JSON in the response. generate_spec calls the provider twice
    (once for spec, once for PRD). The mock pops responses in order.
    """
    prd = {
        "project_name": "e2e-test", "branch_name": "ralph/e2e",
        "description": "E2E test project",
        "features": [
            {
                "id": "FEAT-001", "title": "Core", "priority": 1,
                "tasks": [
                    {"id": "TASK-001", "category": "functional", "complexity": "simple",
                     "title": "Create hello.py", "description": "hello world",
                     "acceptance_criteria": ["hello.py exists", "prints Hello"],
                     "status": "pending", "test_command": "python hello.py", "notes": ""},
                ],
            },
            {
                "id": "FEAT-002", "title": "Tests", "priority": 2,
                "tasks": [
                    {"id": "TASK-002", "category": "quality", "complexity": "simple",
                     "title": "Add tests", "description": "add tests",
                     "acceptance_criteria": ["test exists", "pytest passes"],
                     "status": "pending", "test_command": "pytest -v", "notes": ""},
                ],
            },
        ],
    }
    # Return JSON in response text — _extract_json will find it
    return AgentResult(
        success=True,
        final_response=f"Here is the spec.\n\n```json\n{json.dumps(prd, indent=2)}\n```",
        tool_calls_made=5, cost_usd=0.02,
    )


def _spec_only_response() -> AgentResult:
    """Mock: returns spec content (first session of generate_spec)."""
    return AgentResult(
        success=True,
        final_response="# Spec\n\nA simple project for testing.",
        tool_calls_made=3, cost_usd=0.01,
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
    ws = str(workspace)
    call_count = [0]

    def mock_create(config, model_override=""):
        idx = min(call_count[0], len(responses) - 1) if responses else 0
        item = responses[idx] if idx < len(responses) else []
        resps = item if isinstance(item, list) else [item]
        mock = MockProvider(responses=resps, workspace_dir=ws)
        call_count[0] += 1
        return mock

    defaults = dict(
        provider="claude-sdk", model="mock",
        workspace_dir=workspace, max_iterations=10,
        max_healer_attempts=2, max_incomplete_retries=2,
        session_timeout_seconds=60, enable_reflexion=False,
    )
    defaults.update(overrides)
    config = Config(**defaults)
    loop = RalphLoop(config)
    return loop, mock_create


class TestE2EHappyPath:
    @pytest.mark.asyncio
    async def test_full_loop_two_tasks_pass(self, workspace):
        ws = str(workspace)
        # generate_spec creates ONE provider that handles BOTH spec + PRD sessions
        # So the first provider needs TWO responses (spec text + PRD JSON)
        spec_and_prd = [_spec_only_response(), _spec_response(ws)]
        responses = [
            spec_and_prd,  # Provider 1: spec gen (2 responses for 2 run_session calls)
            [_coding_ok("TASK-001")], [_qa_pass(ws)],
            [_coding_ok("TASK-002")], [_qa_pass(ws)],
        ]

        call_count = [0]
        def mock_create(config, model_override=""):
            idx = min(call_count[0], len(responses) - 1) if responses else 0
            resps = responses[idx] if isinstance(responses[idx], list) else [responses[idx]]
            mock = MockProvider(responses=resps, workspace_dir=ws)
            call_count[0] += 1
            return mock

        config = Config(provider="claude-sdk", model="mock", workspace_dir=workspace,
                        max_iterations=10, max_healer_attempts=2, max_incomplete_retries=2, session_timeout_seconds=60)
        loop = RalphLoop(config)

        with patch("ralph.loop._create_provider", side_effect=mock_create), \
             patch("ralph.loop.asyncio.sleep", return_value=None):
            await loop.run("Build a hello world project")
        prd = load_prd(loop.run_dir)
        assert prd.progress_pct == 100.0


class TestE2EQAFailAndHeal:
    @pytest.mark.asyncio
    async def test_qa_fails_healer_fixes(self, workspace):
        ws = str(workspace)
        responses = [
            [_spec_only_response(), _spec_response(ws)],
            [_coding_ok("TASK-001")], [_qa_fail(ws)],
            [_healer_ok()], [_qa_pass(ws)],
            [_coding_ok("TASK-002")], [_qa_pass(ws)],
        ]
        loop, mock_create = _make_loop(workspace, responses)
        with patch("ralph.loop._create_provider", side_effect=mock_create), \
             patch("ralph.loop.asyncio.sleep", return_value=None):
            await loop.run("Build something")
        prd = load_prd(loop.run_dir)
        task1 = next(t for t in prd.tasks if t.id == "TASK-001")
        assert task1.status == TaskStatus.PASSED


class TestE2EFixerExhaustion:
    @pytest.mark.asyncio
    async def test_all_fix_attempts_fail_marks_blocked(self, workspace):
        """Phase 2: fixer marks BLOCKED after max attempts (not FAILED).

        Uses a complex feature so the smart gate triggers QA + fixer path.
        """
        ws = str(workspace)
        # Build a PRD with a COMPLEX feature (integration + 5 criteria → triggers review)
        complex_prd = {
            "project_name": "e2e-test", "branch_name": "ralph/e2e",
            "description": "E2E test project",
            "features": [
                {
                    "id": "FEAT-001", "title": "Auth Integration", "priority": 1,
                    "tasks": [
                        {"id": "TASK-001", "category": "integration", "complexity": "complex",
                         "title": "Auth middleware integration",
                         "description": "Multi-file security integration with token validation",
                         "acceptance_criteria": ["token works", "expired rejected", "missing rejected", "refresh works", "audit logged"],
                         "status": "pending", "test_command": "pytest -v", "notes": ""},
                    ],
                },
                {
                    "id": "FEAT-002", "title": "Tests", "priority": 2,
                    "tasks": [
                        {"id": "TASK-002", "category": "quality", "complexity": "simple",
                         "title": "Add tests", "acceptance_criteria": ["test exists", "pytest passes"],
                         "status": "pending", "test_command": "pytest -v", "notes": ""},
                    ],
                },
            ],
        }
        spec_resp = AgentResult(success=True, final_response="# Spec\nComplex test.", cost_usd=0.01)
        prd_resp = AgentResult(
            success=True,
            final_response=f"```json\n{json.dumps(complex_prd, indent=2)}\n```",
            cost_usd=0.01,
        )
        responses = [
            [spec_resp, prd_resp],
            # FEAT-001 (complex → reviewed path): code ok, QA fails, 3 fix attempts all fail
            [_coding_ok("TASK-001")], [_qa_fail(ws)],
            [_healer_ok()], [_qa_fail(ws)],
            [_healer_ok()], [_qa_fail(ws)],
            [_healer_ok()], [_qa_fail(ws)],
            # Feature review (won't run since task blocked)
            # FEAT-002 (simple → fast path)
            [_coding_ok("TASK-002")],
        ]
        loop, mock_create = _make_loop(workspace, responses)
        with patch("ralph.loop._create_provider", side_effect=mock_create), \
             patch("ralph.loop.asyncio.sleep", return_value=None):
            await loop.run("Build something")
        prd = load_prd(loop.run_dir)
        task1 = next(t for t in prd.tasks if t.id == "TASK-001")
        assert task1.status == TaskStatus.BLOCKED


class TestE2EBlocked:
    @pytest.mark.asyncio
    async def test_blocked_task_logged(self, workspace):
        ws = str(workspace)
        responses = [
            [_spec_only_response(), _spec_response(ws)],
            [_blocked("TASK-001")],
        ]
        loop, mock_create = _make_loop(workspace, responses, max_iterations=2)
        with patch("ralph.loop._create_provider", side_effect=mock_create), \
             patch("ralph.loop.asyncio.sleep", return_value=None):
            await loop.run("Build something")
        rails = get_guardrails(loop.run_dir)
        assert "missing db" in rails


class TestE2ESessionFailure:
    @pytest.mark.asyncio
    async def test_provider_failure_does_not_crash(self, workspace):
        ws = str(workspace)
        responses = [
            [_spec_only_response(), _spec_response(ws)],
            [_session_error()], [_session_error()], [_session_error()],
        ]
        loop, mock_create = _make_loop(workspace, responses, max_iterations=3, max_incomplete_retries=2)
        with patch("ralph.loop._create_provider", side_effect=mock_create), \
             patch("ralph.loop.asyncio.sleep", return_value=None):
            await loop.run("Build something")
        progress = get_progress_summary(loop.run_dir)
        assert "SESSION_ERROR" in progress or "INCOMPLETE" in progress


class TestE2EIncompleteAutoFail:
    @pytest.mark.asyncio
    async def test_incomplete_task_auto_fails_after_retries(self, workspace):
        ws = str(workspace)
        no_signal = AgentResult(success=True, final_response="I did some work but no marker", cost_usd=0.01)
        responses = [
            [_spec_only_response(), _spec_response(ws)],
            [no_signal], [no_signal], [no_signal], [no_signal],
        ]
        loop, mock_create = _make_loop(workspace, responses, max_iterations=5, max_incomplete_retries=2)
        with patch("ralph.loop._create_provider", side_effect=mock_create), \
             patch("ralph.loop.asyncio.sleep", return_value=None):
            await loop.run("Build something")
        prd = load_prd(loop.run_dir)
        task1 = next(t for t in prd.tasks if t.id == "TASK-001")
        assert task1.status in (TaskStatus.FAILED, TaskStatus.BLOCKED)


class TestE2EExistingPRD:
    @pytest.mark.asyncio
    async def test_resume_skips_spec_gen(self, workspace_with_prd):
        ws = str(workspace_with_prd)
        responses = [
            [_coding_ok("TASK-001")], [_qa_pass(ws)],
        ]
        loop, mock_create = _make_loop(workspace_with_prd, responses, max_iterations=2)
        # Pre-seed the run directory with the existing PRD so spec gen is skipped
        run_ralph_dir = Path(ws) / "runs" / f"ralph_{loop.run_id}" / ".ralph"
        run_ralph_dir.mkdir(parents=True)
        (run_ralph_dir / "prd.json").write_text(
            (Path(ws) / ".ralph" / "prd.json").read_text()
        )
        with patch("ralph.loop._create_provider", side_effect=mock_create), \
             patch("ralph.loop.asyncio.sleep", return_value=None):
            await loop.run("")
        prd = load_prd(loop.run_dir)
        task1 = next(t for t in prd.tasks if t.id == "TASK-001")
        assert task1.status == TaskStatus.PASSED


class TestE2EApprovalGate:
    @pytest.mark.asyncio
    async def test_approval_rejected_stops(self, workspace):
        ws = str(workspace)
        responses = [
            [_spec_only_response(), _spec_response(ws)],
        ]
        loop, mock_create = _make_loop(workspace, responses, approve_spec=True)
        with patch("ralph.loop._create_provider", side_effect=mock_create), \
             patch("ralph.loop.asyncio.sleep", return_value=None), \
             patch.object(RalphLoop, "_ask_approval", return_value=False):
            await loop.run("Build something")
        progress = get_progress_summary(loop.run_dir)
        assert "TASK" not in progress or "Iteration" not in progress


class TestE2EBudgetExhaustion:
    @pytest.mark.asyncio
    async def test_loop_stops_when_budget_exceeded(self, workspace):
        ws = str(workspace)
        prd = {
            "project_name": "x", "features": [
                {"id": "F-1", "title": "X", "priority": 1, "tasks": [
                    {"id": "T-1", "category": "functional", "complexity": "simple",
                     "title": "X", "description": "d",
                     "acceptance_criteria": ["ok"], "status": "pending",
                     "test_command": "", "notes": ""},
                    {"id": "T-2", "category": "functional", "complexity": "simple",
                     "title": "Y", "description": "d",
                     "acceptance_criteria": ["ok"], "status": "pending",
                     "test_command": "", "notes": ""},
                ]},
            ],
        }
        spec_resp = AgentResult(success=True, final_response="# Spec\nBudget test.", cost_usd=0.01)
        prd_resp = AgentResult(success=True, final_response=f"```json\n{json.dumps(prd, indent=2)}\n```", cost_usd=0.01)
        coding = AgentResult(success=True, final_response="<ralph:task_complete>T-1</ralph:task_complete>", cost_usd=0.50)
        responses = [
            [spec_resp, prd_resp],
            [coding], [_qa_pass(ws)],
        ]
        loop, mock_create = _make_loop(workspace, responses, max_budget_usd=0.05)
        with patch("ralph.loop._create_provider", side_effect=mock_create), \
             patch("ralph.loop.asyncio.sleep", return_value=None):
            await loop.run("test budget")
        assert loop.cumulative_cost >= 0.05


class TestE2ECorruptedPRD:
    @pytest.mark.asyncio
    async def test_corrupted_prd_handled(self, workspace_with_ralph):
        (workspace_with_ralph / ".ralph" / "prd.json").write_text("{broken json")
        config = Config(provider="claude-sdk", model="mock", workspace_dir=workspace_with_ralph, max_iterations=1)
        loop = RalphLoop(config)
        with pytest.raises(RuntimeError, match="No PRD and no task"):
            with patch("ralph.loop._create_provider", side_effect=lambda c, **kw: MockProvider([], str(workspace_with_ralph))), \
                 patch("ralph.loop.asyncio.sleep", return_value=None):
                await loop.run("")


class TestE2ECostTracking:
    @pytest.mark.asyncio
    async def test_cumulative_cost(self, workspace):
        ws = str(workspace)
        prd = {
            "project_name": "x", "features": [
                {"id": "F-1", "title": "X", "priority": 1, "tasks": [
                    {"id": "T-1", "category": "functional", "complexity": "simple",
                     "title": "X", "description": "d",
                     "acceptance_criteria": ["ok"], "status": "pending",
                     "test_command": "", "notes": ""},
                ]},
            ],
        }
        spec_resp = AgentResult(success=True, final_response="# Spec\nCost test.", cost_usd=0.01)
        prd_resp = AgentResult(success=True, final_response=f"```json\n{json.dumps(prd, indent=2)}\n```", cost_usd=0.02)
        coding = AgentResult(success=True, final_response="<ralph:task_complete>T-1</ralph:task_complete>", cost_usd=0.05)
        responses = [
            [spec_resp, prd_resp],
            [coding], [_qa_pass(ws)],
        ]
        loop, mock_create = _make_loop(workspace, responses, max_iterations=5)
        with patch("ralph.loop._create_provider", side_effect=mock_create), \
             patch("ralph.loop.asyncio.sleep", return_value=None):
            await loop.run("test cost")
        assert loop.cumulative_cost > 0
