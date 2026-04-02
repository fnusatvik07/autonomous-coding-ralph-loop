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
from ralph.memory.progress import append_progress, init_progress, update_project_state, update_codebase_patterns
from ralph.models import AgentResult, PRD, QAResult, TaskStatus
from ralph.observability import (
    generate_run_id, log_qa, log_session,
    log_task_transition, setup_logging,
)
from ralph.checkpoint import cleanup_checkpoints, create_checkpoint, rollback_to_checkpoint
from ralph.formatting import auto_format
from ralph.indexer import index_codebase
from ralph.learning import maybe_aggregate_learnings
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
MAX_FIXER_ATTEMPTS = 3  # Phase 2: max fix attempts before marking BLOCKED
WIND_DOWN_TOOL_CALLS = 150  # Phase 2: signal wind-down at this many tool calls
WIND_DOWN_DURATION_S = 300  # Phase 2: signal wind-down at 5 min


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
    """
    # Signal 1: Explicit XML marker
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


def _extract_session_summary(response: str, task_id: str) -> dict:
    """Extract structured summary from the agent's response for progress.md.

    Returns dict with: notes, files_changed, test_results, patterns.
    This is what the NEXT agent reads to understand what happened.
    """
    lines = response.split("\n")
    result = {"notes": "", "files_changed": [], "test_results": "", "patterns": []}

    # Extract file paths mentioned in response
    _EXT = (".py", ".js", ".ts", ".json", ".toml", ".yaml", ".yml", ".md",
            ".html", ".css", ".sql", ".sh", ".cfg", ".txt")
    files_touched = set()
    for line in lines:
        for word in line.split():
            word = word.strip("`,'\"|()[]{}:")
            if "/" in word or (("." in word) and any(word.endswith(ext) for ext in _EXT)):
                # Filter out obvious non-files
                if not word.startswith("http") and len(word) < 100:
                    clean = word.lstrip("./")
                    if clean and "." in clean:
                        files_touched.add(clean)

    result["files_changed"] = sorted(files_touched)[:15]

    # Extract test results
    for line in lines:
        line_s = line.strip()
        if ("passed" in line_s.lower() or "failed" in line_s.lower()) and \
           ("test" in line_s.lower() or "pytest" in line_s.lower()):
            result["test_results"] = line_s[:150]
            break

    # Extract context around the task_complete marker
    marker = f"<ralph:task_complete>{task_id}</ralph:task_complete>"
    idx = response.find(marker)
    if idx > 0:
        before = response[max(0, idx - 500):idx].strip()
        sentences = [s.strip() for s in before.replace("\n", ". ").split(". ") if len(s.strip()) > 10]
        if sentences:
            result["notes"] = ". ".join(sentences[-3:])[:300]

    # Extract patterns (lines that look like learnings/conventions)
    for line in lines:
        line_s = line.strip()
        if any(kw in line_s.lower() for kw in ["pattern:", "convention:", "note:", "important:",
                                                  "learned:", "discovered:"]):
            result["patterns"].append(line_s[:150])

    return result


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
        self._prev_feature_had_issues = False  # Smart gate: escalate if previous feature failed

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

    _stop_requested: bool = False

    def request_stop(self) -> None:
        """Request graceful stop (used by WebRalphLoop)."""
        self._stop_requested = True

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

            # Context wind-down: inject instructions into system prompt
            system_prompt += (
                f"\n\n## CONTEXT LIMITS\n"
                f"You have a maximum of {WIND_DOWN_TOOL_CALLS} tool calls and "
                f"{WIND_DOWN_DURATION_S // 60} minutes for this session.\n"
                f"When you've used ~80% of your tool calls ({int(WIND_DOWN_TOOL_CALLS * 0.8)}+), "
                f"WIND DOWN:\n"
                f"1. Finish the current task you're working on\n"
                f"2. Commit whatever is working\n"
                f"3. Update progress.md with where you stopped\n"
                f"4. Output <ralph:task_complete>TASK-ID</ralph:task_complete> for any completed tasks\n"
                f"5. Do NOT start a new task — the next session will pick up\n"
            )

            # Coding session — one session for the entire feature
            coding_result = await self._run_with_timeout(
                provider.run_session(
                    system_prompt=system_prompt,
                    user_message=user_message,
                    max_turns=min(self.config.max_turns_per_session, WIND_DOWN_TOOL_CALLS),
                    on_text=self.on_text,
                    on_tool=self.on_tool,
                ),
                label=f"coding {feature.id}",
            )
            self.cumulative_cost += coding_result.cost_usd
            log_session(self.run_dir, self.run_id, iteration, "coding", feature.id, coding_result)

            # Detect wind-down
            wound_down = coding_result.tool_calls_made >= int(WIND_DOWN_TOOL_CALLS * 0.8)
            if wound_down:
                console.print(f"  [yellow]Context wind-down: {coding_result.tool_calls_made} tool calls[/yellow]")

            console.print(
                f"  [dim]───── Coding: ${coding_result.cost_usd:.4f} │ "
                f"{coding_result.tool_calls_made} tools │ "
                f"{coding_result.duration_ms / 1000:.0f}s ─────[/dim]"
            )

            # Handle session failure — but check if some tasks were completed before the crash
            if not coding_result.success:
                console.print(f"  [bold red]✗ Session FAILED[/bold red]: {coding_result.error[:200]}")
                # Even failed sessions may have partial output — check each task
                for t in pending_tasks:
                    if coding_result.final_response and _detect_completion(coding_result.final_response, self.run_dir, t.id):
                        console.print(f"  [yellow]Salvaged: {t.id} (completed before crash)[/yellow]")
                        summary = _extract_session_summary(coding_result.final_response, t.id)
                        await self._complete_task(prd, t, iteration, suffix="(salvaged)", summary=summary)
                    else:
                        self._handle_incomplete(prd, t, iteration, f"Session error: {coding_result.error[:300]}")
                await self._inter_delay()
                continue

            # Auto-format
            fmt_ok, fmt_out = await auto_format(self.workspace_dir)
            if fmt_ok and "reformatted" in fmt_out.lower():
                console.print("  [dim]Auto-formatted[/dim]")

            # ── Detect which tasks were completed ──
            completed_tasks = []
            incomplete_tasks = []
            for task in pending_tasks:
                if _detect_completion(coding_result.final_response, self.run_dir, task.id):
                    completed_tasks.append(task)
                else:
                    incomplete_tasks.append(task)

            if not completed_tasks:
                # Nothing completed — handle as incomplete
                first = pending_tasks[0]
                blocked = _detect_blocked(coding_result.final_response)
                if blocked:
                    add_guardrail(self.run_dir, sign=blocked, context=feature.title)
                self._handle_incomplete(prd, first, iteration, blocked or "No completion signal")
                if checkpoint_tag:
                    rollback_to_checkpoint(self.workspace_dir, checkpoint_tag)
                await self._inter_delay()
                continue

            # ── Smart Gate: decide review level for this feature ──
            needs_review = should_review_feature(feature) or self._prev_feature_had_issues
            feature_had_issues = False

            if needs_review:
                console.print(f"  [magenta]Smart Gate → REVIEW (complex feature)[/magenta]")
            else:
                console.print(f"  [green]Smart Gate → SKIP review (simple feature)[/green]")

            for task in completed_tasks:
                summary = _extract_session_summary(coding_result.final_response, task.id)

                if needs_review:
                    # ── Reviewed path: run QA sentinel per task ──
                    console.print(f"  [cyan]QA: {task.id}...[/cyan]")
                    qa_result = await self._run_qa(task, iteration)

                    if qa_result.passed:
                        console.print(f"  [bold green]✓ QA PASSED[/bold green] — {task.id}")
                        await self._complete_task(prd, task, iteration, summary=summary)
                    else:
                        console.print(f"  [bold red]✗ QA FAILED[/bold red] — {task.id}: {'; '.join(qa_result.issues[:2])}")
                        feature_had_issues = True
                        # Fixer: max 3 attempts, then BLOCKED
                        fixed = await self._run_fixer_loop(task, qa_result, iteration)
                        if fixed:
                            console.print(f"  [bold green]✓ Fixer FIXED[/bold green] — {task.id}")
                            await self._complete_task(prd, task, iteration, suffix="(after fix)", summary=summary)
                        else:
                            self._block_task(prd, task, iteration, qa_result)
                            if self.config.enable_reflexion:
                                await self._reflect(task, iteration, "QA_FAILED",
                                                    "; ".join(qa_result.issues[:5]))
                else:
                    # ── Fast path: trust coder, skip QA ──
                    console.print(f"  [bold green]✓ PASSED[/bold green] — {task.id} [dim](review skipped)[/dim]")
                    await self._complete_task(prd, task, iteration, summary=summary)

            # Handle tasks the coder didn't complete
            for task in incomplete_tasks:
                blocked = _detect_blocked(coding_result.final_response)
                if blocked and task.id in str(blocked):
                    add_guardrail(self.run_dir, sign=blocked, context=task.title)

            # Feature-level review (if gate says review the whole feature)
            if needs_review and completed_tasks and not feature_had_issues:
                console.print(f"  [magenta]Feature review: {feature.id}...[/magenta]")
                review_result = await self._run_feature_review(feature, iteration)
                if not review_result.passed:
                    console.print(f"  [yellow]Reviewer issues: {'; '.join(review_result.issues[:2])}[/yellow]")
                    feature_had_issues = True
                    # Don't fail tasks — just log for next iteration
                    add_guardrail(self.run_dir,
                                  sign=f"Reviewer: {'; '.join(review_result.issues[:3])}",
                                  context=feature.title)
                else:
                    console.print(f"  [green]Feature review: approved[/green]")

            self._prev_feature_had_issues = feature_had_issues
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

        # Verify init.sh was created — warn if missing so coding agent knows
        init_sh = Path(self.run_dir) / "init.sh"
        if not init_sh.exists():
            logger.warning("init.sh not created during PRD generation")
            console.print("  [yellow]init.sh missing — coding agent will skip server startup[/yellow]")

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
                    workspace_dir=self.run_dir,
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

    async def _complete_task(self, prd: PRD, task, iteration: int, suffix: str = "", summary: dict | None = None) -> None:
        old_status = task.status.value
        prd.mark_task(task.id, TaskStatus.PASSED)
        save_prd(prd, self.run_dir)
        log_task_transition(self.run_dir, self.run_id, task.id, old_status, "passed", iteration)

        s = summary or {}
        append_progress(
            self.run_dir, iteration=iteration,
            task_id=task.id, task_title=task.title,
            status=f"PASSED {suffix}".strip(),
            notes=s.get("notes", ""),
            files_changed=s.get("files_changed"),
            test_results=s.get("test_results", ""),
            patterns=s.get("patterns"),
        )

        # Update project state snapshot after each task
        completed = len(prd.completed_tasks)
        total = len(prd.tasks)
        update_project_state(self.run_dir, f"{completed}/{total} tasks passed ({prd.progress_pct:.0f}%)")

        # Store any patterns learned
        if s.get("patterns"):
            update_codebase_patterns(self.run_dir, s["patterns"])

        # Auto-aggregate learnings every 10 tasks
        try:
            provider = _create_provider(self.config)
            await maybe_aggregate_learnings(self.run_dir, provider, completed)
        except Exception as e:
            logger.debug("learning aggregation skipped: %s", e)

        logger.info("task %s PASSED %s", task.id, suffix)
        self._incomplete_counts.pop(task.id, None)

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

    async def _run_fixer_loop(self, task, qa_result: QAResult, iteration: int) -> bool:
        """Phase 2 fixer: max 3 attempts, then mark BLOCKED (not FAILED)."""
        for attempt in range(1, MAX_FIXER_ATTEMPTS + 1):
            console.print(f"    [yellow]Fix attempt {attempt}/{MAX_FIXER_ATTEMPTS}[/yellow]")
            provider = _create_provider(self.config)
            fixer_result = await self._run_with_timeout(
                run_healer(
                    qa_result=qa_result, provider=provider,
                    task_id=task.id, task_title=task.title,
                    max_attempts=MAX_FIXER_ATTEMPTS, attempt=attempt,
                    workspace_dir=self.run_dir,
                ),
                label=f"fixer {task.id} attempt {attempt}",
            )
            if isinstance(fixer_result, AgentResult):
                self.cumulative_cost += fixer_result.cost_usd
                log_session(self.run_dir, self.run_id, iteration,
                            f"fixer-{attempt}", task.id, fixer_result)

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
            console.print(f"    [yellow]Fix attempt {attempt} — still failing[/yellow]")
        return False

    def _block_task(self, prd: PRD, task, iteration: int, qa_result: QAResult) -> None:
        """Phase 2: mark task BLOCKED (not FAILED) after max fixer attempts."""
        console.print(f"  [red]BLOCKED: {task.id} (after {MAX_FIXER_ATTEMPTS} fix attempts)[/red]")
        old_status = task.status.value
        prd.mark_task(task.id, TaskStatus.BLOCKED,
                      notes=f"Blocked after {MAX_FIXER_ATTEMPTS} fix attempts: {'; '.join(qa_result.issues[:3])}")
        save_prd(prd, self.run_dir)
        log_task_transition(self.run_dir, self.run_id, task.id, old_status, "blocked", iteration)
        add_guardrail(self.run_dir,
                      sign=f"{task.id} BLOCKED: {'; '.join(qa_result.issues[:3])}",
                      context=task.title)
        append_progress(
            self.run_dir, iteration=iteration,
            task_id=task.id, task_title=task.title,
            status="BLOCKED",
            notes=f"After {MAX_FIXER_ATTEMPTS} fix attempts: {'; '.join(qa_result.issues[:3])}",
        )
        logger.warning("task %s BLOCKED: %s", task.id, qa_result.issues[:3])

    async def _run_feature_review(self, feature, iteration: int) -> QAResult:
        """Phase 2: lightweight code review of the whole feature (reads, doesn't run).

        Phase 3 cross-model: if a second provider is available (e.g., OpenAI),
        use it for the review so a different model catches different blind spots.
        """
        # Cross-model review: use alternate provider if available
        if self.config.provider == "claude-sdk" and self.config.openai_api_key:
            try:
                reviewer_provider = create_provider(
                    "deep-agents", model="openai:gpt-4o",
                    workspace_dir=self.workspace_dir,
                    api_key=self.config.openai_api_key,
                )
                console.print("  [dim]Cross-model review: GPT-4o[/dim]")
            except Exception:
                reviewer_provider = _create_provider(self.config)
        else:
            reviewer_provider = _create_provider(self.config)

        review = await self._run_with_timeout(
            run_reviewer(feature, reviewer_provider, self.workspace_dir),
            label=f"reviewer {feature.id}",
        )
        if not isinstance(review, QAResult):
            review = QAResult(passed=True, issues=[])  # Timeout = don't block
        self.cumulative_cost += review.cost_usd
        if review.cost_usd > 0:
            console.print(f"    [dim]Review: ${review.cost_usd:.4f} | {review.duration_ms / 1000:.1f}s[/dim]")
        log_session(self.run_dir, self.run_id, iteration, "reviewer", feature.id,
                    AgentResult(success=True, cost_usd=review.cost_usd, duration_ms=review.duration_ms))
        return review

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
