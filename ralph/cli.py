"""CLI entry point for Ralph Loop."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from ralph.config import Config

console = Console()


@click.group()
@click.version_option(version="0.2.0", prog_name="ralph")
def cli():
    """Ralph Loop - Autonomous Coding Agent.

    Takes a task, creates a spec, and iteratively builds code using
    Claude Agent SDK or Deep Agents SDK.
    """


@cli.command()
@click.argument("task", required=False)
@click.option("--task-file", "-f", type=click.Path(exists=True), help="Read task from a file")
@click.option("--provider", "-p", type=click.Choice(["claude-sdk", "deep-agents"]), help="Agent SDK")
@click.option("--model", "-m", help="Model: claude-sonnet-4-20250514, claude-opus-4-20250514, claude-haiku-4-5-20251001, or openai:gpt-4o (with deep-agents)")
@click.option("--workspace", "-w", default=".", help="Project workspace directory")
@click.option("--max-iterations", "-n", type=int, help="Max coding iterations")
@click.option("--budget", "-b", type=float, help="Max spend in USD (0=unlimited)")
@click.option("--approve", is_flag=True, help="Pause for human review after spec generation")
@click.option("--auto-route", is_flag=True, help="Auto-select model per task complexity")
@click.option("--no-reflexion", is_flag=True, help="Disable failure reflection")
@click.option("--env-file", "-e", type=click.Path(exists=True), help="Path to .env file")
def run(task, task_file, provider, model, workspace, max_iterations, budget, approve, auto_route, no_reflexion, env_file):
    """Start the autonomous coding loop.

    Examples:

        ralph run "Build a REST API with FastAPI"

        ralph run "Build a CLI tool" -m claude-opus-4-20250514

        ralph run -f task.md --budget 5.00 --approve

        ralph run "Add auth" -p deep-agents -m openai:gpt-4o
    """
    if task_file:
        task = Path(task_file).read_text().strip()
    elif not task:
        task = click.prompt("Describe your task")

    if not task:
        console.print("[red]No task provided.[/red]")
        return

    config = Config.load(
        provider=provider,
        model=model,
        workspace_dir=workspace,
        max_iterations=max_iterations,
        max_budget_usd=budget,
        approve_spec=approve,
        env_file=env_file,
    )
    if auto_route:
        config.auto_route_models = True
    if no_reflexion:
        config.enable_reflexion = False

    console.print(Panel(
        f"[bold]Task:[/bold] {task[:200]}\n"
        f"[bold]Provider:[/bold] {config.provider}\n"
        f"[bold]Model:[/bold] {config.model}\n"
        f"[bold]Workspace:[/bold] {config.workspace_dir}"
        + (f"\n[bold]Budget:[/bold] ${config.max_budget_usd:.2f}" if config.max_budget_usd > 0 else ""),
        title="Ralph Loop",
    ))

    from ralph.loop import RalphLoop
    loop = RalphLoop(config)

    try:
        asyncio.run(loop.run(task))
    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted. Progress saved to .ralph/[/yellow]")
    except Exception as e:
        console.print(f"\n[red]Error: {e}[/red]")
        raise


@cli.command()
@click.option("--workspace", "-w", default=".", help="Project workspace directory")
@click.option("--provider", "-p", type=click.Choice(["claude-sdk", "deep-agents"]))
@click.option("--model", "-m")
@click.option("--max-iterations", "-n", type=int)
@click.option("--budget", "-b", type=float, help="Max spend in USD")
@click.option("--env-file", "-e", type=click.Path(exists=True))
def resume(workspace, provider, model, max_iterations, budget, env_file):
    """Resume the coding loop from existing PRD."""
    prd_path = Path(workspace).resolve() / ".ralph" / "prd.json"
    if not prd_path.exists():
        console.print("[red]No PRD found. Use 'ralph run' to start.[/red]")
        return

    config = Config.load(
        provider=provider, model=model,
        workspace_dir=workspace, max_iterations=max_iterations,
        max_budget_usd=budget, env_file=env_file,
    )

    from ralph.loop import RalphLoop
    loop = RalphLoop(config)

    try:
        asyncio.run(loop.run(""))
    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted. Progress saved.[/yellow]")


@cli.command()
@click.option("--workspace", "-w", default=".")
def status(workspace):
    """Show current PRD progress."""
    prd_path = Path(workspace).resolve() / ".ralph" / "prd.json"
    if not prd_path.exists():
        console.print("[yellow]No PRD found. Run 'ralph run' first.[/yellow]")
        return

    data = json.loads(prd_path.read_text())
    tasks = data.get("tasks", [])

    console.print(Panel(
        f"[bold]{data.get('project_name', 'Unknown')}[/bold]\n"
        f"{data.get('description', '')}",
        title="Project",
    ))

    table = Table()
    table.add_column("ID", style="bold")
    table.add_column("Title")
    table.add_column("P", justify="right")
    table.add_column("Status")

    styles = {
        "pending": "[yellow]pending[/yellow]",
        "in_progress": "[blue]in_progress[/blue]",
        "passed": "[green]passed[/green]",
        "failed": "[red]failed[/red]",
    }

    for t in tasks:
        table.add_row(t["id"], t["title"], str(t.get("priority", "")), styles.get(t["status"], t["status"]))

    console.print(table)

    total = len(tasks)
    passed = sum(1 for t in tasks if t["status"] == "passed")
    failed = sum(1 for t in tasks if t["status"] == "failed")
    pending = sum(1 for t in tasks if t["status"] == "pending")
    pct = (passed / total * 100) if total else 0

    console.print(
        f"\n[bold]{passed}/{total} ({pct:.0f}%)[/bold] | "
        f"[green]{passed} done[/green] [yellow]{pending} pending[/yellow] [red]{failed} failed[/red]"
    )


@cli.command()
@click.option("--workspace", "-w", default=".")
def analytics(workspace):
    """Show session analytics (cost, duration, failures)."""
    from ralph.observability import get_session_analytics

    stats = get_session_analytics(str(Path(workspace).resolve()))

    if stats["sessions"] == 0:
        console.print("[yellow]No sessions recorded yet.[/yellow]")
        return

    table = Table(title="Session Analytics")
    table.add_column("Metric", style="bold")
    table.add_column("Value", justify="right")

    table.add_row("Total Sessions", str(stats["sessions"]))
    table.add_row("Total Cost", f"${stats['total_cost']:.4f}")
    table.add_row("Total Duration", f"{stats['total_duration_ms'] / 1000:.1f}s")
    table.add_row("Total Tool Calls", str(stats["total_tool_calls"]))
    table.add_row("Failures", str(stats["failures"]))

    console.print(table)

    if stats["cost_by_phase"]:
        phase_table = Table(title="Cost by Phase")
        phase_table.add_column("Phase", style="bold")
        phase_table.add_column("Cost", justify="right")
        for phase, cost in sorted(stats["cost_by_phase"].items()):
            phase_table.add_row(phase, f"${cost:.4f}")
        console.print(phase_table)


@cli.command()
@click.option("--workspace", "-w", default=".")
def progress(workspace):
    """Show the iteration progress log."""
    path = Path(workspace).resolve() / ".ralph" / "progress.md"
    if not path.exists():
        console.print("[yellow]No progress log yet.[/yellow]")
        return
    console.print(path.read_text())


@cli.command()
@click.option("--workspace", "-w", default=".")
def guardrails(workspace):
    """Show failure memory (guardrails)."""
    path = Path(workspace).resolve() / ".ralph" / "guardrails.md"
    if not path.exists():
        console.print("[yellow]No guardrails set.[/yellow]")
        return
    console.print(path.read_text())


@cli.command()
@click.option("--workspace", "-w", default=".", help="Project workspace")
@click.option("--port", "-p", default=8420, type=int, help="Port number")
def dashboard(workspace, port):
    """Launch web dashboard for monitoring runs."""
    from ralph.dashboard import serve_dashboard
    serve_dashboard(str(Path(workspace).resolve()), port)


@cli.command()
@click.option("--workspace", "-w", default=".", help="Project workspace")
def index(workspace):
    """Show codebase index (function signatures, file tree)."""
    from ralph.indexer import index_codebase
    result = index_codebase(str(Path(workspace).resolve()))
    console.print(result)


@cli.command()
@click.option("--workspace", "-w", default=".", help="Project workspace")
@click.option("--port", "-p", default=8420, type=int, help="Port number")
@click.option("--no-open", is_flag=True, help="Don't open browser automatically")
def web(workspace, port, no_open):
    """Launch the full web dashboard (React UI + API).

    Requires: pip install ralph-loop[web]
    """
    try:
        from ralph.web.server import create_app
    except ImportError:
        console.print("[red]Web dependencies not installed.[/red]")
        console.print("Run: pip install ralph-loop[web]")
        return

    import uvicorn

    ws_path = str(Path(workspace).resolve())
    app = create_app(workspace_dir=ws_path)

    if not no_open:
        import webbrowser
        import threading
        threading.Timer(1.0, lambda: webbrowser.open(f"http://localhost:{port}")).start()

    console.print(f"[bold]Ralph Loop Web Dashboard[/bold]")
    console.print(f"  URL: http://localhost:{port}")
    console.print(f"  Workspace: {ws_path}")
    console.print(f"  API: http://localhost:{port}/api/health")
    console.print(f"  Press Ctrl+C to stop\n")

    uvicorn.run(app, host="0.0.0.0", port=port, log_level="warning")
