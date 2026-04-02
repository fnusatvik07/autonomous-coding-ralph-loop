"""Web dashboard for monitoring Ralph Loop runs.

Simple single-file dashboard using only stdlib (no Flask/Streamlit dependency).
Serves HTML via http.server, reads data from .ralph/ directory.

Usage:
    ralph dashboard           # Start on port 8420
    ralph dashboard -p 9000   # Custom port
"""

from __future__ import annotations

import html
import json
import logging
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path

logger = logging.getLogger("ralph")


def generate_dashboard_html(workspace_dir: str) -> str:
    """Generate a self-contained HTML dashboard from .ralph/ data."""
    ralph_dir = Path(workspace_dir) / ".ralph"

    # Load data
    prd_data = _load_json(ralph_dir / "prd.json")
    sessions = _load_jsonl(ralph_dir / "sessions.jsonl")
    progress = _load_text(ralph_dir / "progress.md")
    guardrails = _load_text(ralph_dir / "guardrails.md")
    reflections = _load_text(ralph_dir / "reflections.md")

    # Compute metrics — handle both v3 (features→tasks) and v2 (flat tasks)
    tasks = []
    if prd_data:
        if "features" in prd_data:
            for f in prd_data["features"]:
                tasks.extend(f.get("tasks", []))
        else:
            tasks = prd_data.get("tasks", [])
    total = len(tasks)
    passed = sum(1 for t in tasks if t.get("status") == "passed")
    failed = sum(1 for t in tasks if t.get("status") == "failed")
    pending = total - passed - failed
    pct = (passed / total * 100) if total else 0

    total_cost = sum(s.get("cost_usd", 0) for s in sessions)
    total_tools = sum(s.get("tool_calls", 0) for s in sessions)
    total_duration = sum(s.get("duration_ms", 0) for s in sessions)

    cost_by_phase: dict[str, float] = {}
    for s in sessions:
        phase = s.get("phase", "?")
        cost_by_phase[phase] = cost_by_phase.get(phase, 0) + s.get("cost_usd", 0)

    # Build HTML
    task_rows = ""
    for t in tasks:
        status = t.get("status", "?")
        color = {"passed": "#22c55e", "failed": "#ef4444", "pending": "#eab308"}.get(status, "#888")
        task_rows += f"""
        <tr>
            <td><strong>{html.escape(t.get('id',''))}</strong></td>
            <td>{html.escape(t.get('title',''))}</td>
            <td style="color:{color};font-weight:bold">{status.upper()}</td>
            <td>{t.get('priority','')}</td>
        </tr>"""

    session_rows = ""
    for s in sessions[-50:]:  # Last 50
        phase = s.get("phase", "?")
        task_id = s.get("task_id", "?")
        cost = s.get("cost_usd", 0)
        dur = s.get("duration_ms", 0) / 1000
        success = s.get("success", s.get("passed", True))
        color = "#22c55e" if success else "#ef4444"
        session_rows += f"""
        <tr>
            <td>{s.get('iteration','')}</td>
            <td>{phase}</td>
            <td>{task_id}</td>
            <td style="color:{color}">{"OK" if success else "FAIL"}</td>
            <td>${cost:.4f}</td>
            <td>{dur:.1f}s</td>
            <td>{s.get('tool_calls','')}</td>
        </tr>"""

    phase_rows = ""
    for phase, cost in sorted(cost_by_phase.items()):
        phase_rows += f"<tr><td>{phase}</td><td>${cost:.4f}</td></tr>"

    project_name = html.escape(prd_data.get("project_name", "Unknown")) if prd_data else "No PRD"

    return f"""<!DOCTYPE html>
<html><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Ralph Loop Dashboard</title>
<style>
  * {{ margin:0; padding:0; box-sizing:border-box; }}
  body {{ font-family:-apple-system,BlinkMacSystemFont,sans-serif; background:#0f172a; color:#e2e8f0; padding:24px; }}
  h1 {{ color:#38bdf8; margin-bottom:8px; }}
  h2 {{ color:#94a3b8; margin:24px 0 12px; font-size:18px; }}
  .grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(200px,1fr)); gap:16px; margin:16px 0; }}
  .card {{ background:#1e293b; border-radius:12px; padding:20px; }}
  .card .value {{ font-size:32px; font-weight:bold; color:#f1f5f9; }}
  .card .label {{ color:#64748b; font-size:14px; margin-top:4px; }}
  .bar {{ height:24px; border-radius:6px; background:#1e293b; overflow:hidden; margin:8px 0; }}
  .bar-fill {{ height:100%; background:linear-gradient(90deg,#22c55e,#38bdf8); border-radius:6px; }}
  table {{ width:100%; border-collapse:collapse; margin:8px 0; }}
  th {{ text-align:left; color:#64748b; font-size:13px; padding:8px; border-bottom:1px solid #334155; }}
  td {{ padding:8px; border-bottom:1px solid #1e293b; font-size:14px; }}
  tr:hover {{ background:#1e293b; }}
  pre {{ background:#1e293b; padding:16px; border-radius:8px; overflow-x:auto; font-size:13px; white-space:pre-wrap; max-height:400px; overflow-y:auto; }}
</style></head><body>
<h1>Ralph Loop Dashboard</h1>
<p style="color:#64748b">{project_name}</p>

<div class="grid">
  <div class="card"><div class="value">{passed}/{total}</div><div class="label">Tasks Passed</div></div>
  <div class="card"><div class="value">${total_cost:.2f}</div><div class="label">Total Cost</div></div>
  <div class="card"><div class="value">{total_tools}</div><div class="label">Tool Calls</div></div>
  <div class="card"><div class="value">{total_duration/1000:.0f}s</div><div class="label">Total Duration</div></div>
</div>

<div class="bar"><div class="bar-fill" style="width:{pct:.0f}%"></div></div>
<p style="color:#64748b;font-size:14px">{pct:.0f}% complete — {passed} passed, {pending} pending, {failed} failed</p>

<h2>Tasks</h2>
<table><tr><th>ID</th><th>Title</th><th>Status</th><th>Priority</th></tr>{task_rows}</table>

<h2>Sessions</h2>
<table><tr><th>Iter</th><th>Phase</th><th>Task</th><th>Result</th><th>Cost</th><th>Duration</th><th>Tools</th></tr>{session_rows}</table>

<h2>Cost by Phase</h2>
<table><tr><th>Phase</th><th>Cost</th></tr>{phase_rows}</table>

<h2>Progress Log</h2>
<pre>{html.escape(progress or 'No progress yet.')}</pre>

<h2>Guardrails</h2>
<pre>{html.escape(guardrails or 'No guardrails.')}</pre>

<h2>Reflections</h2>
<pre>{html.escape(reflections or 'No reflections.')}</pre>

<p style="color:#475569;margin-top:24px;font-size:12px">Generated by Ralph Loop • Refresh page to update</p>
</body></html>"""


def serve_dashboard(workspace_dir: str, port: int = 8420) -> None:
    """Start the dashboard HTTP server."""
    html_content = generate_dashboard_html(workspace_dir)

    class Handler(SimpleHTTPRequestHandler):
        def do_GET(self):
            # Regenerate on each request for live data
            content = generate_dashboard_html(workspace_dir)
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(content.encode())

        def log_message(self, format, *args):
            pass  # Suppress request logs

    print(f"Dashboard: http://localhost:{port}")
    print("Press Ctrl+C to stop")
    HTTPServer(("", port), Handler).serve_forever()


def _load_json(path: Path) -> dict | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError:
        return None


def _load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    entries = []
    for line in path.read_text().splitlines():
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError:
            pass
    return entries


def _load_text(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text()
