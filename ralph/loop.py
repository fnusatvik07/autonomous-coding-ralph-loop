"""The Ralph Loop - outer orchestration loop for autonomous coding.

Each iteration spawns a FRESH agent session. Filesystem is the memory.

Bug fixes applied:
- Incomplete tasks auto-fail after N retries (no infinite loop)
- Session failures handled explicitly (not silently ignored)
- Session timeout via asyncio.wait_for
- Completion detection scoped to current task (no stale IDs)
- Graceful Ctrl+C with state persistence
- Budget warning at 80%
- Run ID for correlating sessions
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from ralph.config import Config
from ralph.memory.guardrails import add_guardrail, init_guardrails
from ralph.memory.progress import append_progress, init_progress
from ralph.models import AgentResult, PRD, QAResult, TaskStatus
from ralph.observability import (
    generate_run_id, log_qa, log_session,
    log_task_transition, setup_logging,
)
from ralph.checkpoint import cleanup_checkpoints, create_checkpoint, rollback_to_checkpoint
from ralph.formatting import auto_format
from ralph.indexer import index_codebase
from ralph.github_pr import create_pull_request, generate_pr_body, is_gh_available
from ralph.prompts.templates import CODING_SYSTEM_PROMPT, CODING_USER_TEMPLATE
from ralph.providers import create_provider
from ralph.providers.base import BaseProvider
from ralph.qa.healer import run_healer
from ralph.qa.sentinel import run_sentinel
from ralph.reflexion import get_reflections, init_reflections, reflect_on_failure
from ralph.routing import get_model_for_phase, get_model_for_task
from ralph.spec.generator import generate_spec, load_prd, save_prd

console = Console()
logger = logging.getLogger("ralph")

INTER_ITERATION_DELAY = 3
RALPH_DIR = ".ralph"


def _create_provider(config: Config, model_override: str = "") -> BaseProvider:
    """Create a fresh provider instance, optionally with a different model."""
    kwargs = {
        "model": model_override or config.model,
        "workspace_dir": str(config.workspace_dir),
        "max_retries": config.max_retries,
        "retry_delay": config.retry_delay_seconds,
    }
    if config.provider == "deep-agents":
        kwargs["api_key"] = config.anthropic_api_key or config.openai_api_key
    if config.provider == "claude-sdk":
        import os
        env = {}
        if config.use_foundry:
            env["CLAUDE_CODE_USE_FOUNDRY"] = "1"
            env["ANTHROPIC_FOUNDRY_API_KEY"] = config.foundry_api_key
            env["ANTHROPIC_FOUNDRY_BASE_URL"] = config.foundry_base_url
            # Pass model override env vars so Claude Code CLI uses the right model
            for key in ("ANTHROPIC_DEFAULT_SONNET_MODEL", "ANTHROPIC_DEFAULT_OPUS_MODEL",
                        "ANTHROPIC_DEFAULT_HAIKU_MODEL"):
                val = os.getenv(key)
                if val:
                    env[key] = val
        if config.enable_puppeteer:
            env["RALPH_ENABLE_PUPPETEER"] = "1"
        if config.enable_sandbox:
            env["RALPH_ENABLE_SANDBOX"] = "1"
        kwargs["env"] = env
        if config.max_budget_usd > 0:
            kwargs["max_budget_usd"] = config.max_budget_usd
    return create_provider(config.provider, **kwargs)


def _print_iteration_header(prd: PRD, iteration: int, max_iter: int, cost: float, task) -> None:
    """Print a rich iteration header with progress bar."""
    completed = len(prd.completed_tasks)
    total = len(prd.tasks)
    failed = total - completed - len(prd.pending_tasks)
    pct = prd.progress_pct

    # Progress bar
    bar_width = 30
    filled = int(bar_width * pct / 100)
    bar = f"[green]{'█' * filled}[/green][dim]{'░' * (bar_width - filled)}[/dim]"

    console.print()
    console.print(f"[bold]{'─' * 70}[/bold]")
    console.print(
        f"  [bold cyan]Iteration {iteration}/{max_iter}[/bold cyan]"
        f"  │  {bar} [bold]{pct:.0f}%[/bold]"
        f"  │  [green]{completed}[/green]/[yellow]{len(prd.pending_tasks)}[/yellow]"
        f"{'/' + f'[red]{failed}[/red]' if failed else ''}"
        f"  │  [dim]${cost:.2f}[/dim]"
    )
    console.print(
        f"  [bold]► {task.id}[/bold]: {task.title}"
        f"  [dim]({task.category} │ {task.complexity} │ {len(task.acceptance_criteria)} criteria)[/dim]"
    )
    console.print(f"[bold]{'─' * 70}[/bold]")


def _on_text(text: str) -> None:
    """Default text callback."""
    if text.strip():
        console.print(f"  {text.strip()}", highlight=False)


def _on_tool(name: str, _input: dict) -> None:
    """Default tool callback with colored tool names."""
    color = "cyan" if name in ("Read", "Glob", "Grep") else "yellow" if name in ("Write", "Edit") else "blue" if name == "Bash" else "dim"
    console.print(f"  [{color}]▸ {name}[/{color}]")


def _detect_completion(response: str, workspace_dir: str, current_task_id: str) -> bool:
    """Detect if the CURRENT task was completed. Returns True/False.

    Scoped to current_task_id to prevent stale ID false positives.
    """
    # Signal 1: Explicit XML marker
    match = re.search(r"<ralph:task_complete>(.*?)</ralph:task_complete>", response)
    if match:
        detected_id = match.group(1).strip()
        if detected_id == current_task_id:
            return True
        # Accept if it's close (e.g., agent wrote task ID without prefix)
        if current_task_id.endswith(detected_id) or detected_id.endswith(current_task_id):
            return True

    # Signal 2: Agent updated prd.json - check if THIS task is now passed
    prd_path = Path(workspace_dir) / RALPH_DIR / "prd.json"
    if prd_path.exists():
        try:
            data = json.loads(prd_path.read_text())
            for task in data.get("tasks", []):
                if task.get("id") == current_task_id and task.get("status") == "passed":
                    return True
        except (json.JSONDecodeError, KeyError):
            pass

    # Signal 3: Common phrases + current task ID mentioned
    phrases = [
        r"task.*(?:complete|done|finished|implemented)",
        r"all tests pass",
        r"successfully implemented",
        r"committed",
    ]
    for phrase in phrases:
        if re.search(phrase, response, re.IGNORECASE):
            if current_task_id in response:
                return True

    return False


def _detect_blocked(response: str) -> str | None:
    match = re.search(r"<ralph:task_blocked>(.*?)</ralph:task_blocked>", response)
    if match:
        return match.group(1).strip()
    phrases = [
        r"cannot (?:complete|proceed|continue)",
        r"blocked by",
        r"(?:stuck|unable) to (?:fix|resolve)",
    ]
    for phrase in phrases:
        if re.search(phrase, response, re.IGNORECASE):
            ctx = re.search(rf"(.{{0,100}}{phrase}.{{0,100}})", response, re.IGNORECASE)
            return ctx.group(1).strip() if ctx else "Agent reported being stuck"
    return None


class RalphLoop:
    """Main orchestrator for the Ralph coding loop."""

    def __init__(self, config: Config):
        self.config = config
        self.workspace_dir = str(config.workspace_dir)
        self.cumulative_cost = 0.0
        self.run_id = generate_run_id()
        self._incomplete_counts: dict[str, int] = {}

    def on_text(self, text: str) -> None:
        """Text streaming callback. Override in WebRalphLoop for WS events."""
        _on_text(text)

    def on_tool(self, name: str, tool_input: dict) -> None:
        """Tool call callback. Override in WebRalphLoop for WS events."""
        _on_tool(name, tool_input)

    async def run(self, task_description: str) -> None:
        # Workspace = directory where code lives
        ws = Path(self.workspace_dir)
        ws.mkdir(parents=True, exist_ok=True)

        # Run directory: .ralph/runs/ralph_<uuid>/
        ralph_root = ws / RALPH_DIR
        ralph_root.mkdir(exist_ok=True)
        run_dir = ralph_root / "runs" / f"ralph_{self.run_id}"
        run_dir.mkdir(parents=True, exist_ok=True)
        self.run_dir = str(run_dir)

        # State files go in .ralph/ (shared) for agent access
        # Run directory stores copies for tracking
        setup_logging(self.workspace_dir)
        init_progress(self.workspace_dir)
        init_guardrails(self.workspace_dir)
        init_reflections(self.workspace_dir)
        logger.info("ralph loop starting: run=%s provider=%s model=%s",
                     self.run_id, self.config.provider, self.config.model)

        # ── Step 1: Generate or Load Spec + PRD ──
        console.print()
        console.print("[bold]Step 1: Specification & Task List[/bold]")
        console.print("[dim]  Generating application spec and breaking it into testable tasks...[/dim]")
        console.print()

        # Generate spec + PRD into run directory, copy to .ralph/ root for agent access
        prd = await self._ensure_prd(task_description)

        # Copy spec + prd to run directory for tracking
        import shutil
        for fname in ("spec.md", "prd.json"):
            src = Path(self.workspace_dir) / RALPH_DIR / fname
            dst = Path(self.run_dir) / fname
            if src.exists() and not dst.exists():
                shutil.copy2(src, dst)

        # ── Step 2: Review (if enabled) ──
        if self.config.approve_spec and not self._prd_previously_approved():
            console.print()
            console.print("[bold]Step 2: Human Review[/bold]")
            console.print("[dim]  Review the spec and task list before coding begins.[/dim]")
            console.print()
            console.print(self._format_prd_summary(prd))
            if not self._ask_approval("Approve this spec and start coding?"):
                console.print("[yellow]Spec not approved. Exiting.[/yellow]")
                return
            self._mark_prd_approved()

        # ── Smart defaults ──
        total_tasks = len(prd.tasks)
        if self.config.max_iterations == 50 and total_tasks > 50:
            # Auto-adjust max_iterations to task count + buffer for healer retries
            self.config.max_iterations = total_tasks + max(10, total_tasks // 5)
            logger.info("auto-adjusted max_iterations to %d (tasks=%d + buffer)",
                        self.config.max_iterations, total_tasks)

        # ── Step 3: Coding Loop ──
        console.print()
        console.print("[bold]Step 3: Autonomous Coding[/bold]")
        console.print(f"[dim]  {total_tasks} tasks to complete. Each iteration: code → test → QA → commit.[/dim]")
        console.print()
        console.print(Panel(
            f"[bold]Run:[/bold] ralph_{self.run_id}\n"
            f"[bold]Project:[/bold] {prd.project_name}\n"
            f"[bold]Tasks:[/bold] {total_tasks} ({len(prd.pending_tasks)} pending)\n"
            f"[bold]Provider:[/bold] {self.config.provider} | [bold]Model:[/bold] {self.config.model}\n"
            f"[bold]Max iterations:[/bold] {self.config.max_iterations}"
            + (f" | [bold]Budget:[/bold] ${self.config.max_budget_usd:.2f}" if self.config.max_budget_usd > 0 else ""),
            title="Ralph Loop",
        ))

        try:
            await self._main_loop(prd)
        except (KeyboardInterrupt, asyncio.CancelledError):
            console.print("\n[yellow]Interrupted. Progress saved.[/yellow]")
            logger.info("interrupted: run=%s cost=$%.4f", self.run_id, self.cumulative_cost)

    async def _main_loop(self, prd: PRD) -> None:
        for iteration in range(1, self.config.max_iterations + 1):
            # Budget check
            if self._budget_exceeded():
                break

            try:
                prd = load_prd(self.workspace_dir)
            except (FileNotFoundError, json.JSONDecodeError) as e:
                console.print(f"[red]PRD error: {e}[/red]")
                break

            next_task = prd.get_next_task()
            if not next_task:
                cleanup_checkpoints(self.workspace_dir)
                await self._maybe_create_pr(prd, iteration - 1)
                completed = len(prd.completed_tasks)
                total = len(prd.tasks)
                console.print()
                console.print(f"[bold green]{'═' * 70}[/bold green]")
                console.print(f"  [bold green]ALL {completed} TASKS COMPLETE![/bold green]")
                console.print(f"  Run: {self.run_id} │ Iterations: {iteration - 1} │ Cost: ${self.cumulative_cost:.4f}")
                console.print(f"[bold green]{'═' * 70}[/bold green]")
                logger.info("complete: run=%s iterations=%d cost=$%.4f",
                             self.run_id, iteration - 1, self.cumulative_cost)
                return

            _print_iteration_header(prd, iteration, self.config.max_iterations, self.cumulative_cost, next_task)
            logger.info("iteration %d: %s - %s", iteration, next_task.id, next_task.title)

            # Git checkpoint before starting task (rollback point)
            checkpoint_tag = create_checkpoint(self.workspace_dir, next_task.id, iteration)

            # Route to optimal model for this task's complexity
            routed_model = ""
            if self.config.auto_route_models:
                routed_model = get_model_for_task(
                    next_task.title, next_task.description,
                    next_task.acceptance_criteria, self.config.provider,
                )
                if routed_model != self.config.model:
                    console.print(f"  [dim]Routed to: {routed_model}[/dim]")

            provider = _create_provider(self.config, model_override=routed_model)

            # Build enriched system prompt: base + codebase index + reflections
            system_prompt = CODING_SYSTEM_PROMPT
            # Inject codebase index for large repos (helps agent orient faster)
            codebase_idx = index_codebase(self.workspace_dir, max_tokens=3000)
            if codebase_idx and len(codebase_idx) > 100:
                system_prompt += f"\n\n{codebase_idx}"
            reflections = get_reflections(self.workspace_dir, max_entries=5)
            if reflections:
                system_prompt += f"\n\n{reflections}"

            # Coding session with timeout
            coding_result = await self._run_with_timeout(
                provider.run_session(
                    system_prompt=system_prompt,
                    user_message=CODING_USER_TEMPLATE.format(
                        task_id=next_task.id,
                        task_title=next_task.title,
                    ),
                    max_turns=self.config.max_turns_per_session,
                    on_text=self.on_text,
                    on_tool=self.on_tool,
                ),
                label=f"coding {next_task.id}",
            )
            self.cumulative_cost += coding_result.cost_usd
            log_session(self.workspace_dir, self.run_id, iteration, "coding", next_task.id, coding_result)

            # Session summary
            console.print(
                f"  [dim]───── Coding: ${coding_result.cost_usd:.4f} │ "
                f"{coding_result.tool_calls_made} tools │ "
                f"{coding_result.duration_ms / 1000:.0f}s ─────[/dim]"
            )

            # Handle session failure
            if not coding_result.success:
                console.print(f"  [bold red]✗ Session FAILED[/bold red]: {coding_result.error[:200]}")
                self._handle_incomplete(prd, next_task, iteration, f"Session error: {coding_result.error[:300]}")
                await self._inter_delay()
                continue

            # Auto-format
            fmt_ok, fmt_out = await auto_format(self.workspace_dir)
            if fmt_ok and "reformatted" in fmt_out.lower():
                console.print("  [dim]Auto-formatted[/dim]")

            # Detect completion
            completed = _detect_completion(coding_result.final_response, self.workspace_dir, next_task.id)

            if completed:
                console.print(f"  [cyan]Running QA Sentinel...[/cyan]")
                qa_result = await self._run_qa(next_task, iteration)

                if qa_result.passed:
                    console.print(f"  [bold green]✓ QA PASSED[/bold green] — {next_task.id}")
                    self._complete_task(prd, next_task, iteration)
                else:
                    console.print(f"  [bold red]✗ QA FAILED[/bold red] — {'; '.join(qa_result.issues[:2])}")
                    console.print(f"  [yellow]Starting Healer...[/yellow]")
                    healed = await self._run_healer_loop(next_task, qa_result, iteration)
                    if healed:
                        console.print(f"  [bold green]✓ Healer FIXED[/bold green] — {next_task.id}")
                        self._complete_task(prd, next_task, iteration, "(after healing)")
                    else:
                        self._fail_task(prd, next_task, iteration, qa_result)
                        # Rollback to checkpoint on final failure
                        if checkpoint_tag:
                            console.print(f"  [dim]Rolling back to checkpoint...[/dim]")
                            rollback_to_checkpoint(self.workspace_dir, checkpoint_tag)
                        # Reflexion: learn from QA failure
                        if self.config.enable_reflexion:
                            await self._reflect(next_task, iteration, "QA_FAILED",
                                                "; ".join(qa_result.issues[:5]))
            else:
                blocked = _detect_blocked(coding_result.final_response)
                if blocked:
                    console.print(f"  [red]BLOCKED: {blocked[:100]}[/red]")
                    add_guardrail(self.workspace_dir, sign=blocked, context=next_task.title)
                else:
                    console.print(f"  [yellow]No completion signal for {next_task.id}[/yellow]")

                self._handle_incomplete(prd, next_task, iteration, blocked or "No completion signal")

            await self._inter_delay()

        console.print(f"[yellow]Max iterations ({self.config.max_iterations}). Cost: ${self.cumulative_cost:.4f}[/yellow]")

    # --- Internal ---

    async def _run_with_timeout(self, coro, label: str = "") -> AgentResult:
        """Wrap a coroutine with session timeout."""
        try:
            return await asyncio.wait_for(coro, timeout=self.config.session_timeout_seconds)
        except asyncio.TimeoutError:
            logger.error("session timeout (%ds): %s", self.config.session_timeout_seconds, label)
            return AgentResult(
                success=False,
                error=f"Session timed out after {self.config.session_timeout_seconds}s",
            )

    def _budget_exceeded(self) -> bool:
        if self.config.max_budget_usd <= 0:
            return False
        # 80% warning
        if self.cumulative_cost >= self.config.max_budget_usd * 0.8:
            if self.cumulative_cost < self.config.max_budget_usd:
                console.print(
                    f"[yellow]WARNING: 80% of budget used "
                    f"(${self.cumulative_cost:.4f}/${self.config.max_budget_usd:.2f})[/yellow]"
                )
        if self.cumulative_cost >= self.config.max_budget_usd:
            console.print(f"[red]Budget exhausted (${self.cumulative_cost:.4f})[/red]")
            logger.warning("budget exhausted: $%.4f", self.cumulative_cost)
            return True
        return False

    def _handle_incomplete(self, prd: PRD, task, iteration: int, notes: str) -> None:
        """Handle incomplete task - auto-fail after max retries."""
        self._incomplete_counts[task.id] = self._incomplete_counts.get(task.id, 0) + 1
        count = self._incomplete_counts[task.id]

        append_progress(
            self.workspace_dir, iteration=iteration,
            task_id=task.id, task_title=task.title,
            status=f"INCOMPLETE ({count}/{self.config.max_incomplete_retries})",
            notes=notes,
        )

        if count >= self.config.max_incomplete_retries:
            console.print(f"  [red]{task.id}: max incomplete retries ({count}) - marking FAILED[/red]")
            prd.mark_task(task.id, TaskStatus.FAILED, notes=f"Failed after {count} incomplete attempts")
            save_prd(prd, self.workspace_dir)
            log_task_transition(self.workspace_dir, self.run_id, task.id, "pending", "failed", iteration)

    async def _ensure_prd(self, task_description: str) -> PRD:
        prd_path = Path(self.workspace_dir) / RALPH_DIR / "prd.json"
        if prd_path.exists():
            console.print("[dim]Loading existing PRD...[/dim]")
            try:
                return load_prd(self.workspace_dir)
            except (json.JSONDecodeError, KeyError) as e:
                console.print(f"[yellow]PRD corrupted ({e}), regenerating...[/yellow]")
                logger.warning("corrupted prd.json: %s", e)
                prd_path.unlink()
        if not task_description:
            raise RuntimeError("No PRD and no task description provided. Use 'ralph run' with a task.")
        provider = _create_provider(self.config)
        return await generate_spec(task_description, provider, self.workspace_dir)

    async def _run_qa(self, task, iteration: int) -> QAResult:
        provider = _create_provider(self.config)
        qa = await self._run_with_timeout(
            run_sentinel(task, provider, self.workspace_dir),
            label=f"qa {task.id}",
        )
        if not isinstance(qa, QAResult):
            qa = QAResult(passed=False, issues=["QA session timed out"])
        # Track QA cost
        self.cumulative_cost += qa.cost_usd
        if qa.cost_usd > 0:
            console.print(f"    [dim]QA: ${qa.cost_usd:.4f} | {qa.duration_ms / 1000:.1f}s[/dim]")
        log_qa(self.workspace_dir, self.run_id, iteration, task.id, qa)
        return qa

    async def _run_healer_loop(self, task, qa_result: QAResult, iteration: int) -> bool:
        for attempt in range(1, self.config.max_healer_attempts + 1):
            provider = _create_provider(self.config)
            healer_result = await self._run_with_timeout(
                run_healer(
                    qa_result=qa_result, provider=provider,
                    task_id=task.id, task_title=task.title,
                    max_attempts=self.config.max_healer_attempts, attempt=attempt,
                ),
                label=f"healer {task.id} attempt {attempt}",
            )
            if isinstance(healer_result, AgentResult):
                self.cumulative_cost += healer_result.cost_usd
                log_session(self.workspace_dir, self.run_id, iteration,
                            f"healer-{attempt}", task.id, healer_result)

            provider = _create_provider(self.config)
            qa_result = await self._run_with_timeout(
                run_sentinel(task, provider, self.workspace_dir),
                label=f"qa-post-heal {task.id}",
            )
            if not isinstance(qa_result, QAResult):
                qa_result = QAResult(passed=False, issues=["QA timed out after heal"])
            log_qa(self.workspace_dir, self.run_id, iteration, task.id, qa_result)

            if qa_result.passed:
                return True
            console.print(f"    [yellow]Heal attempt {attempt} - still failing[/yellow]")
        return False

    def _complete_task(self, prd: PRD, task, iteration: int, suffix: str = "") -> None:
        old_status = task.status.value
        prd.mark_task(task.id, TaskStatus.PASSED)
        save_prd(prd, self.workspace_dir)
        log_task_transition(self.workspace_dir, self.run_id, task.id, old_status, "passed", iteration)
        append_progress(
            self.workspace_dir, iteration=iteration,
            task_id=task.id, task_title=task.title,
            status=f"PASSED {suffix}".strip(),
        )
        logger.info("task %s PASSED %s", task.id, suffix)
        # Reset incomplete counter
        self._incomplete_counts.pop(task.id, None)

    def _fail_task(self, prd: PRD, task, iteration: int, qa_result: QAResult) -> None:
        console.print(f"  [red]FAILED: {task.id}[/red]")
        old_status = task.status.value
        prd.mark_task(task.id, TaskStatus.FAILED, notes=f"QA: {'; '.join(qa_result.issues[:3])}")
        save_prd(prd, self.workspace_dir)
        log_task_transition(self.workspace_dir, self.run_id, task.id, old_status, "failed", iteration)
        add_guardrail(self.workspace_dir, sign=f"{task.id} failed: {'; '.join(qa_result.issues[:3])}", context=task.title)
        append_progress(
            self.workspace_dir, iteration=iteration,
            task_id=task.id, task_title=task.title,
            status="FAILED", notes=f"QA: {'; '.join(qa_result.issues[:3])}",
        )
        logger.warning("task %s FAILED: %s", task.id, qa_result.issues[:3])

    async def _reflect(self, task, iteration: int, failure_type: str, error_context: str) -> None:
        """Trigger LLM reflection on a failure (Reflexion pattern)."""
        try:
            provider = _create_provider(self.config)
            console.print(f"  [dim]Reflecting on failure...[/dim]")
            await reflect_on_failure(
                workspace_dir=self.workspace_dir,
                provider=provider,
                task_id=task.id,
                task_title=task.title,
                iteration=iteration,
                failure_type=failure_type,
                error_context=error_context,
            )
        except Exception as e:
            logger.warning("reflection failed (non-critical): %s", e)

    async def _maybe_create_pr(self, prd: PRD, iterations: int) -> None:
        """Create a GitHub PR if gh CLI is available and remote is configured."""
        if not is_gh_available():
            return
        try:
            completed = [
                {"id": t.id, "title": t.title}
                for t in prd.tasks if t.status == TaskStatus.PASSED
            ]
            body = generate_pr_body(
                project_name=prd.project_name,
                tasks_completed=completed,
                total_cost=self.cumulative_cost,
                total_tests=0,  # Could count from test suite
            )
            pr_url = await create_pull_request(
                workspace_dir=self.workspace_dir,
                title=f"feat: {prd.project_name} ({len(completed)} tasks)",
                body=body,
                branch=prd.branch_name,
            )
            if pr_url:
                console.print(f"  [bold green]PR created: {pr_url}[/bold green]")
        except Exception as e:
            logger.debug("PR creation skipped: %s", e)

    async def _inter_delay(self) -> None:
        console.print(f"[dim]Next in {INTER_ITERATION_DELAY}s (Ctrl+C to stop)...[/dim]")
        await asyncio.sleep(INTER_ITERATION_DELAY)

    def _prd_previously_approved(self) -> bool:
        return (Path(self.workspace_dir) / RALPH_DIR / ".approved").exists()

    def _mark_prd_approved(self) -> None:
        (Path(self.workspace_dir) / RALPH_DIR / ".approved").write_text("approved")

    @staticmethod
    def _ask_approval(prompt: str) -> bool:
        try:
            return input(f"\n{prompt} [y/N] ").strip().lower() in ("y", "yes")
        except (EOFError, KeyboardInterrupt):
            return False

    @staticmethod
    def _format_prd_summary(prd: PRD) -> str:
        lines = [f"[bold]{prd.project_name}[/bold]", prd.description, ""]
        for feat in prd.features:
            lines.append(f"  [bold]{feat.id}: {feat.title}[/bold] (P{feat.priority})")
            for t in feat.tasks:
                lines.append(f"    {t.id} [{t.category}] {t.title}")
                for ac in t.acceptance_criteria[:2]:
                    lines.append(f"      - {ac}")
        return "\n".join(lines)
