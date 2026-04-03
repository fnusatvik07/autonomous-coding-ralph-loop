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
from ralph.learning import maybe_aggregate_learnings
from ralph.memory.guardrails import add_guardrail, init_guardrails
from ralph.memory.progress import append_progress, init_progress, update_project_state, update_codebase_patterns
from ralph.models import AgentResult, PRD, QAResult, TaskStatus
from ralph.observability import (
    generate_run_id, log_qa, log_session,
    log_task_transition, setup_logging,
)
from ralph.checkpoint import cleanup_checkpoints, create_checkpoint, rollback_to_checkpoint
from ralph.formatting import auto_format
from ralph.indexer import index_codebase
from ralph.prompts.templates import CODING_SYSTEM_PROMPT, CODING_USER_TEMPLATE, FEATURE_CODING_USER_TEMPLATE
from ralph.shipper import ship as shipper_ship
from ralph.providers import create_provider
from ralph.providers.base import BaseProvider
from ralph.qa.healer import run_healer
from ralph.qa.reviewer import run_reviewer
from ralph.qa.sentinel import run_sentinel
from ralph.reflexion import get_reflections, init_reflections, reflect_on_failure
from ralph.routing import get_model_for_phase, get_model_for_task, should_review_feature
from ralph.spec.generator import generate_spec, load_prd, save_prd

console = Console()
logger = logging.getLogger("ralph")

INTER_ITERATION_DELAY = 3
RALPH_DIR = ".ralph"
MAX_FIXER_ATTEMPTS = 3
WIND_DOWN_TOOL_CALLS = 150
WIND_DOWN_DURATION_S = 300


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


def _print_iteration_header(prd: PRD, iteration: int, max_iter: int, cost: float, feature) -> None:
    """Print a rich iteration header with progress bar."""
    completed = len(prd.completed_tasks)
    total = len(prd.tasks)
    failed = total - completed - len(prd.pending_tasks)
    pct = prd.progress_pct

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
        f"  [bold]► {feature.id}[/bold]: {feature.title}"
        f"  [dim]({len(feature.pending_tasks)} tasks │ {feature.max_complexity})[/dim]"
    )
    for t in feature.pending_tasks:
        console.print(f"    {t.id}: {t.title} [dim]({t.complexity})[/dim]")
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
    Uses exact match only for XML markers (no fuzzy matching).
    """
    # Signal 1: Explicit XML marker — find ALL markers, exact match only
    for match in re.finditer(r"<ralph:task_complete>(.*?)</ralph:task_complete>", response):
        detected_id = match.group(1).strip()
        if detected_id == current_task_id:
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

    _stop_requested: bool = False

    def __init__(self, config: Config):
        self.config = config
        self.workspace_dir = str(config.workspace_dir)
        self.cumulative_cost = 0.0
        self.run_id = generate_run_id()
        self._incomplete_counts: dict[str, int] = {}
        self._prev_feature_had_issues = False

    def request_stop(self):
        self._stop_requested = True

    def on_text(self, text: str) -> None:
        """Text streaming callback. Override in WebRalphLoop for WS events."""
        _on_text(text)

    def on_tool(self, name: str, tool_input: dict) -> None:
        """Tool call callback. Override in WebRalphLoop for WS events."""
        _on_tool(name, tool_input)

    async def run(self, task_description: str) -> None:
        # Create runs directory inside workspace
        ws = Path(self.workspace_dir)
        ws.mkdir(parents=True, exist_ok=True)
        runs_root = ws / "runs"
        runs_root.mkdir(exist_ok=True)

        # Each run gets its own folder — code AND state files go here
        run_dir = runs_root / f"ralph_{self.run_id}"
        run_dir.mkdir(parents=True, exist_ok=True)
        (run_dir / RALPH_DIR).mkdir(exist_ok=True)  # .ralph inside run dir for state files

        # run_dir = where code is generated AND where state lives
        self.run_dir = str(run_dir)
        # Override workspace_dir so the agent writes code INTO the run folder
        self.workspace_dir = str(run_dir)

        # ALL state files go in run directory — nothing in .ralph/ root
        setup_logging(self.run_dir)
        init_progress(self.run_dir)
        init_guardrails(self.run_dir)
        init_reflections(self.run_dir)
        logger.info("ralph loop starting: run=%s dir=%s provider=%s model=%s",
                     self.run_id, self.run_dir, self.config.provider, self.config.model)

        console.print()
        console.print(f"[bold]Run:[/bold] ralph_{self.run_id}")
        console.print(f"[bold]Dir:[/bold] {self.run_dir}")
        console.print()

        # ── Step 1: Generate or Load Spec + PRD ──
        console.print("[bold]Step 1: Specification & Task List[/bold]")
        console.print("[dim]  Generating application spec and breaking it into testable tasks...[/dim]")
        console.print()

        prd = await self._ensure_prd(task_description)

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
            if self._stop_requested:
                console.print("[yellow]Stop requested. Saving progress.[/yellow]")
                break
            if self._budget_exceeded():
                break

            try:
                prd = load_prd(self.run_dir)
            except (FileNotFoundError, json.JSONDecodeError) as e:
                console.print(f"[red]PRD error: {e}[/red]")
                break

            feature = prd.get_next_feature()
            if not feature:
                cleanup_checkpoints(self.workspace_dir)
                await self._ship(prd)
                completed = len(prd.completed_tasks)
                console.print()
                console.print(f"[bold green]{'═' * 70}[/bold green]")
                console.print(f"  [bold green]ALL {completed} TASKS COMPLETE![/bold green]")
                console.print(f"  Run: {self.run_id} │ Iterations: {iteration - 1} │ Cost: ${self.cumulative_cost:.4f}")
                console.print(f"[bold green]{'═' * 70}[/bold green]")
                logger.info("complete: run=%s iterations=%d cost=$%.4f",
                             self.run_id, iteration - 1, self.cumulative_cost)
                return

            pending_tasks = feature.pending_tasks
            _print_iteration_header(prd, iteration, self.config.max_iterations, self.cumulative_cost, feature)
            logger.info("iteration %d: feature %s (%d tasks)", iteration, feature.id, len(pending_tasks))

            # Git checkpoint before feature (rollback point)
            checkpoint_tag = create_checkpoint(self.workspace_dir, feature.id, iteration)

            # Route model based on feature's max complexity
            routed_model = ""
            if self.config.auto_route_models:
                routed_model = get_model_for_task(
                    feature.title, "",
                    [ac for t in pending_tasks for ac in t.acceptance_criteria],
                    self.config.provider,
                )
                if routed_model != self.config.model:
                    console.print(f"  [dim]Routed to: {routed_model}[/dim]")

            provider = _create_provider(self.config, model_override=routed_model)

            # Build enriched system prompt
            system_prompt = CODING_SYSTEM_PROMPT
            codebase_idx = index_codebase(self.workspace_dir, max_tokens=3000)
            if codebase_idx and len(codebase_idx) > 100:
                system_prompt += f"\n\n{codebase_idx}"
            reflections = get_reflections(self.run_dir, max_entries=5)
            if reflections:
                system_prompt += f"\n\n{reflections}"

            # Build feature-level user message with ALL pending tasks
            if len(pending_tasks) == 1:
                # Single task — use simple template (backward compat with mocks)
                user_message = CODING_USER_TEMPLATE.format(
                    task_id=pending_tasks[0].id,
                    task_title=pending_tasks[0].title,
                )
            else:
                tasks_list = "\n".join(
                    f"{i}. **{t.id}** — {t.title}\n"
                    f"   {t.description}\n"
                    f"   Acceptance: {', '.join(t.acceptance_criteria[:3])}\n"
                    f"   Test: `{t.test_command or 'pytest'}`"
                    for i, t in enumerate(pending_tasks, 1)
                )
                user_message = FEATURE_CODING_USER_TEMPLATE.format(
                    feature_id=feature.id,
                    feature_title=feature.title,
                    tasks_list=tasks_list,
                )

            # Context wind-down: inject tool call limit into system prompt
            effective_max_turns = min(self.config.max_turns_per_session, WIND_DOWN_TOOL_CALLS)
            system_prompt += (
                f"\n\n## Session Limits\n"
                f"You have a maximum of {effective_max_turns} tool calls in this session. "
                f"Plan your work accordingly — prioritize completing tasks over exploring."
            )

            # Coding session — one session for the entire feature
            coding_result = await self._run_with_timeout(
                provider.run_session(
                    system_prompt=system_prompt,
                    user_message=user_message,
                    max_turns=effective_max_turns,
                    on_text=self.on_text,
                    on_tool=self.on_tool,
                ),
                label=f"coding {feature.id}",
            )
            self.cumulative_cost += coding_result.cost_usd
            log_session(self.run_dir, self.run_id, iteration, "coding", feature.id, coding_result)

            console.print(
                f"  [dim]───── Coding: ${coding_result.cost_usd:.4f} │ "
                f"{coding_result.tool_calls_made} tools │ "
                f"{coding_result.duration_ms / 1000:.0f}s ─────[/dim]"
            )

            # Handle session failure
            if not coding_result.success:
                console.print(f"  [bold red]✗ Session FAILED[/bold red]: {coding_result.error[:200]}")
                for t in pending_tasks:
                    self._handle_incomplete(prd, t, iteration, f"Session error: {coding_result.error[:300]}")
                await self._inter_delay()
                continue

            # Auto-format
            fmt_ok, fmt_out = await auto_format(self.workspace_dir)
            if fmt_ok and "reformatted" in fmt_out.lower():
                console.print("  [dim]Auto-formatted[/dim]")

            # Split tasks into completed vs incomplete based on completion signals
            completed_tasks = []
            incomplete_tasks = []
            for task in pending_tasks:
                if _detect_completion(coding_result.final_response, self.run_dir, task.id):
                    completed_tasks.append(task)
                else:
                    incomplete_tasks.append(task)

            # Smart gate: decide if this feature needs review
            needs_review = should_review_feature(feature) or self._prev_feature_had_issues
            feature_had_issues = False

            if completed_tasks:
                if needs_review:
                    # Reviewed path: QA sentinel per task, fixer on failure
                    for task in completed_tasks:
                        console.print(f"  [cyan]QA: {task.id}...[/cyan]")
                        qa_result = await self._run_qa(task, iteration)

                        if qa_result.passed:
                            console.print(f"  [bold green]✓ QA PASSED[/bold green] — {task.id}")
                            await self._complete_task(prd, task, iteration)
                        else:
                            console.print(f"  [bold red]✗ QA FAILED[/bold red] — {task.id}: {'; '.join(qa_result.issues[:2])}")
                            feature_had_issues = True
                            console.print(f"  [yellow]Fixer: {task.id}...[/yellow]")
                            fixed = await self._run_fixer_loop(task, qa_result, iteration)
                            if fixed:
                                console.print(f"  [bold green]✓ Fixer FIXED[/bold green] — {task.id}")
                                await self._complete_task(prd, task, iteration, "(after fixing)")
                            else:
                                self._block_task(prd, task, iteration, qa_result)
                                if self.config.enable_reflexion:
                                    await self._reflect(task, iteration, "QA_FAILED",
                                                        "; ".join(qa_result.issues[:5]))

                    # Feature-level review after all tasks pass
                    await self._run_feature_review(feature, iteration)
                else:
                    # Fast path: trust coder, skip QA for simple features
                    for task in completed_tasks:
                        console.print(f"  [bold green]✓ PASSED (fast path)[/bold green] — {task.id}")
                        await self._complete_task(prd, task, iteration, "(fast path)")

            # Handle incomplete tasks individually
            for task in incomplete_tasks:
                blocked = _detect_blocked(coding_result.final_response)
                if blocked and task.id in str(blocked):
                    console.print(f"  [red]BLOCKED: {task.id} — {blocked[:80]}[/red]")
                    add_guardrail(self.run_dir, sign=blocked, context=task.title)

            self._prev_feature_had_issues = feature_had_issues

            if not completed_tasks:
                # No tasks completed — count as incomplete for the first pending task
                first = pending_tasks[0]
                blocked = _detect_blocked(coding_result.final_response)
                if blocked:
                    add_guardrail(self.run_dir, sign=blocked, context=feature.title)
                self._handle_incomplete(prd, first, iteration, blocked or "No completion signal")
                # Rollback if nothing was achieved
                if checkpoint_tag:
                    rollback_to_checkpoint(self.workspace_dir, checkpoint_tag)

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
            self.run_dir, iteration=iteration,
            task_id=task.id, task_title=task.title,
            status=f"INCOMPLETE ({count}/{self.config.max_incomplete_retries})",
            notes=notes,
        )

        if count >= self.config.max_incomplete_retries:
            console.print(f"  [red]{task.id}: max incomplete retries ({count}) - marking FAILED[/red]")
            prd.mark_task(task.id, TaskStatus.FAILED, notes=f"Failed after {count} incomplete attempts")
            save_prd(prd, self.run_dir)
            log_task_transition(self.run_dir, self.run_id, task.id, "pending", "failed", iteration)

    async def _ensure_prd(self, task_description: str) -> PRD:
        prd_path = Path(self.run_dir) / RALPH_DIR / "prd.json"
        if prd_path.exists():
            console.print("[dim]Loading existing PRD...[/dim]")
            try:
                return load_prd(self.run_dir)
            except (json.JSONDecodeError, KeyError) as e:
                console.print(f"[yellow]PRD corrupted ({e}), regenerating...[/yellow]")
                logger.warning("corrupted prd.json: %s", e)
                prd_path.unlink()
        if not task_description:
            raise RuntimeError("No PRD and no task description provided. Use 'ralph run' with a task.")
        provider = _create_provider(self.config)
        prd = await generate_spec(task_description, provider, self.run_dir)
        # Verify init.sh exists after spec generation
        init_sh = Path(self.run_dir) / "init.sh"
        if not init_sh.exists():
            console.print("  [yellow]Warning: init.sh not created by spec generator[/yellow]")
            logger.warning("init.sh missing after spec generation")
        return prd

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
        log_qa(self.run_dir, self.run_id, iteration, task.id, qa)
        return qa

    async def _run_healer_loop(self, task, qa_result: QAResult, iteration: int) -> bool:
        for attempt in range(1, self.config.max_healer_attempts + 1):
            provider = _create_provider(self.config)
            healer_result = await self._run_with_timeout(
                run_healer(
                    qa_result=qa_result, provider=provider,
                    task_id=task.id, task_title=task.title,
                    max_attempts=self.config.max_healer_attempts, attempt=attempt,
                    workspace_dir=self.workspace_dir,
                ),
                label=f"healer {task.id} attempt {attempt}",
            )
            if isinstance(healer_result, AgentResult):
                self.cumulative_cost += healer_result.cost_usd
                log_session(self.run_dir, self.run_id, iteration,
                            f"healer-{attempt}", task.id, healer_result)

            provider = _create_provider(self.config)
            qa_result = await self._run_with_timeout(
                run_sentinel(task, provider, self.workspace_dir),
                label=f"qa-post-heal {task.id}",
            )
            if not isinstance(qa_result, QAResult):
                qa_result = QAResult(passed=False, issues=["QA timed out after heal"])
            log_qa(self.run_dir, self.run_id, iteration, task.id, qa_result)

            if qa_result.passed:
                return True
            console.print(f"    [yellow]Heal attempt {attempt} - still failing[/yellow]")
        return False

    async def _run_fixer_loop(self, task, qa_result: QAResult, iteration: int) -> bool:
        """Run fixer loop (uses healer internally). Max MAX_FIXER_ATTEMPTS."""
        for attempt in range(1, MAX_FIXER_ATTEMPTS + 1):
            provider = _create_provider(self.config)
            healer_result = await self._run_with_timeout(
                run_healer(
                    qa_result=qa_result, provider=provider,
                    task_id=task.id, task_title=task.title,
                    max_attempts=MAX_FIXER_ATTEMPTS, attempt=attempt,
                    workspace_dir=self.workspace_dir,
                ),
                label=f"fixer {task.id} attempt {attempt}",
            )
            if isinstance(healer_result, AgentResult):
                self.cumulative_cost += healer_result.cost_usd
                log_session(self.run_dir, self.run_id, iteration,
                            f"fixer-{attempt}", task.id, healer_result)

            provider = _create_provider(self.config)
            qa_result = await self._run_with_timeout(
                run_sentinel(task, provider, self.workspace_dir),
                label=f"qa-post-fix {task.id}",
            )
            if not isinstance(qa_result, QAResult):
                qa_result = QAResult(passed=False, issues=["QA timed out after fix"])
            log_qa(self.run_dir, self.run_id, iteration, task.id, qa_result)

            if qa_result.passed:
                return True
            console.print(f"    [yellow]Fix attempt {attempt} - still failing[/yellow]")
        return False

    def _block_task(self, prd: PRD, task, iteration: int, qa_result: QAResult) -> None:
        """Mark task as BLOCKED (not FAILED) and write guardrail."""
        console.print(f"  [red]BLOCKED: {task.id}[/red]")
        old_status = task.status.value
        prd.mark_task(task.id, TaskStatus.BLOCKED, notes=f"QA: {'; '.join(qa_result.issues[:3])}")
        save_prd(prd, self.run_dir)
        log_task_transition(self.run_dir, self.run_id, task.id, old_status, "blocked", iteration)
        add_guardrail(self.run_dir, sign=f"{task.id} blocked: {'; '.join(qa_result.issues[:3])}", context=task.title)
        append_progress(
            self.run_dir, iteration=iteration,
            task_id=task.id, task_title=task.title,
            status="BLOCKED", notes=f"QA: {'; '.join(qa_result.issues[:3])}",
        )
        logger.warning("task %s BLOCKED: %s", task.id, qa_result.issues[:3])

    async def _run_feature_review(self, feature, iteration: int) -> None:
        """Run feature-level code review after all tasks pass."""
        try:
            provider = _create_provider(self.config)
            console.print(f"  [dim]Feature review: {feature.id}...[/dim]")
            all_criteria = [
                ac for t in feature.tasks for ac in t.acceptance_criteria
            ]
            review_result = await self._run_with_timeout(
                run_reviewer(
                    workspace_dir=self.workspace_dir,
                    provider=provider,
                    feature_title=feature.title,
                    acceptance_criteria=all_criteria[:20],
                ),
                label=f"review {feature.id}",
            )
            if isinstance(review_result, QAResult):
                self.cumulative_cost += review_result.cost_usd
                if review_result.passed:
                    console.print(f"  [green]Feature review: approved[/green]")
                else:
                    console.print(f"  [yellow]Feature review: {'; '.join(review_result.issues[:2])}[/yellow]")
                if review_result.suggestions:
                    for s in review_result.suggestions[:3]:
                        console.print(f"    [dim]Suggestion: {s}[/dim]")
        except Exception as e:
            logger.debug("feature review skipped: %s", e)

    async def _complete_task(self, prd: PRD, task, iteration: int, suffix: str = "") -> None:
        old_status = task.status.value
        prd.mark_task(task.id, TaskStatus.PASSED)
        save_prd(prd, self.run_dir)
        log_task_transition(self.run_dir, self.run_id, task.id, old_status, "passed", iteration)
        append_progress(
            self.run_dir, iteration=iteration,
            task_id=task.id, task_title=task.title,
            status=f"PASSED {suffix}".strip(),
        )
        logger.info("task %s PASSED %s", task.id, suffix)
        # Reset incomplete counter
        self._incomplete_counts.pop(task.id, None)
        # Update project state and aggregate learnings
        update_project_state(self.run_dir)
        maybe_aggregate_learnings(self.run_dir)

    def _fail_task(self, prd: PRD, task, iteration: int, qa_result: QAResult) -> None:
        console.print(f"  [red]FAILED: {task.id}[/red]")
        old_status = task.status.value
        prd.mark_task(task.id, TaskStatus.FAILED, notes=f"QA: {'; '.join(qa_result.issues[:3])}")
        save_prd(prd, self.run_dir)
        log_task_transition(self.run_dir, self.run_id, task.id, old_status, "failed", iteration)
        add_guardrail(self.run_dir, sign=f"{task.id} failed: {'; '.join(qa_result.issues[:3])}", context=task.title)
        append_progress(
            self.run_dir, iteration=iteration,
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
                workspace_dir=self.run_dir,
                provider=provider,
                task_id=task.id,
                task_title=task.title,
                iteration=iteration,
                failure_type=failure_type,
                error_context=error_context,
            )
        except Exception as e:
            logger.warning("reflection failed (non-critical): %s", e)

    async def _ship(self, prd: PRD) -> None:
        """Push to branch and create PR via shipper agent."""
        try:
            result = await shipper_ship(
                workspace_dir=self.workspace_dir,
                prd=prd,
                cumulative_cost=self.cumulative_cost,
            )
            if result.get("pushed"):
                console.print(f"  [green]Pushed to origin/{prd.branch_name}[/green]")
            if result.get("pr_url"):
                console.print(f"  [bold green]PR created: {result['pr_url']}[/bold green]")
            if result.get("error"):
                console.print(f"  [dim]Ship: {result['error']}[/dim]")
        except Exception as e:
            logger.debug("shipping skipped: %s", e)

    async def _inter_delay(self) -> None:
        console.print(f"[dim]Next in {INTER_ITERATION_DELAY}s (Ctrl+C to stop)...[/dim]")
        await asyncio.sleep(INTER_ITERATION_DELAY)

    def _prd_previously_approved(self) -> bool:
        return (Path(self.run_dir) / ".approved").exists()

    def _mark_prd_approved(self) -> None:
        (Path(self.run_dir) / ".approved").write_text("approved")

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
