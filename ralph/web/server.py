"""FastAPI server - REST API + WebSocket for the Ralph Loop web dashboard.

Flow:
1. POST /api/runs → generates spec, returns PRD for approval
2. POST /api/runs/{run_id}/approve → starts coding loop
3. WS /ws/events → streams live progress
4. GET /api/* → read state from .ralph/
"""

from __future__ import annotations

import asyncio
import json
import logging
import subprocess
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from ralph.config import Config
from ralph.observability import get_session_analytics
from ralph.spec.generator import load_prd, save_prd
from ralph.web.api_models import (
    AnalyticsResponse, FileContentResponse, FileEntry,
    GitCommit, PRDResponse, RunRequest, RunResponse,
    SessionEntry, TaskResponse,
)
from ralph.web.events import EventType, event_bus
from ralph.web.runner import WebRalphLoop

logger = logging.getLogger("ralph")

_active_runs: dict[str, WebRalphLoop] = {}
_pending_approval: dict[str, dict] = {}  # run_id -> {config, task}


def create_app(workspace_dir: str) -> FastAPI:
    from dotenv import load_dotenv
    load_dotenv()  # Ensure env vars are loaded for the web process

    ws_dir = Path(workspace_dir).resolve()
    ralph_dir = ws_dir / ".ralph"

    app = FastAPI(title="Ralph Loop", version="0.2.0")
    app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

    static_dir = Path(__file__).parent / "static"
    if static_dir.exists() and (static_dir / "assets").exists():
        app.mount("/assets", StaticFiles(directory=str(static_dir / "assets")), name="assets")

    # --- State ---

    @app.get("/api/health")
    def health():
        return {
            "status": "ok",
            "workspace": str(ws_dir),
            "active_runs": len(_active_runs),
            "pending_approval": len(_pending_approval),
        }

    @app.get("/api/state")
    def get_state():
        """Full UI state in one call - PRD, analytics, run status."""
        prd = None
        try:
            prd = load_prd(str(ws_dir)).model_dump()
        except Exception:
            pass

        sessions = _load_jsonl(ralph_dir / "sessions.jsonl")
        analytics = get_session_analytics(str(ws_dir))
        progress = _load_text(ralph_dir / "progress.md")
        guardrails = _load_text(ralph_dir / "guardrails.md")

        # Determine run status
        run_status = "idle"
        run_id = None
        if _active_runs:
            run_status = "running"
            run_id = list(_active_runs.keys())[0]
        elif _pending_approval:
            run_status = "awaiting_approval"
            run_id = list(_pending_approval.keys())[0]

        return {
            "prd": prd,
            "sessions": sessions[-100:],  # Last 100
            "analytics": analytics,
            "progress": progress,
            "guardrails": guardrails,
            "run_status": run_status,
            "run_id": run_id,
        }

    @app.get("/api/prd")
    def get_prd():
        try:
            return load_prd(str(ws_dir)).model_dump()
        except FileNotFoundError:
            return {"project_name": "", "tasks": [], "description": "No PRD found"}

    @app.get("/api/sessions")
    def get_sessions():
        return _load_jsonl(ralph_dir / "sessions.jsonl")

    @app.get("/api/analytics")
    def get_analytics():
        return get_session_analytics(str(ws_dir))

    @app.get("/api/progress")
    def get_progress():
        return {"content": _load_text(ralph_dir / "progress.md")}

    @app.get("/api/guardrails")
    def get_guardrails():
        return {"content": _load_text(ralph_dir / "guardrails.md")}

    @app.get("/api/reflections")
    def get_reflections():
        return {"content": _load_text(ralph_dir / "reflections.md")}

    @app.get("/api/files")
    def get_files():
        return _build_file_tree(ws_dir)

    @app.get("/api/files/{file_path:path}")
    def get_file_content(file_path: str):
        full_path = ws_dir / file_path
        if not full_path.exists() or not full_path.is_file():
            raise HTTPException(404, "File not found")
        if not str(full_path.resolve()).startswith(str(ws_dir)):
            raise HTTPException(403, "Path traversal blocked")
        try:
            content = full_path.read_text(errors="replace")
        except Exception:
            raise HTTPException(500, "Cannot read file")
        return FileContentResponse(
            path=file_path, content=content,
            language=_detect_language(full_path.suffix),
            size=full_path.stat().st_size,
        )

    @app.get("/api/git/log")
    def get_git_log():
        try:
            r = subprocess.run(
                ["git", "log", "--oneline", "-30"],
                cwd=str(ws_dir), capture_output=True, text=True, timeout=5,
            )
            return [
                GitCommit(hash=parts[0], message=parts[1])
                for line in r.stdout.strip().splitlines()
                if len(parts := line.split(" ", 1)) == 2
            ]
        except Exception:
            return []

    @app.get("/api/config")
    def get_config():
        import os
        # Detect actual available models from env
        foundry_model = os.getenv("ANTHROPIC_DEFAULT_SONNET_MODEL") or os.getenv("ANTHROPIC_DEFAULT_OPUS_MODEL")
        claude_models = [foundry_model] if foundry_model else []
        claude_models += [
            m for m in ["claude-sonnet-4-20250514", "claude-opus-4-20250514", "claude-haiku-4-5-20251001"]
            if m not in claude_models
        ]
        return {
            "providers": ["claude-sdk", "deep-agents"],
            "default_provider": "claude-sdk",
            "default_model": foundry_model or "claude-sonnet-4-20250514",
            "models": {
                "claude-sdk": claude_models,
                "deep-agents": [
                    "anthropic:claude-sonnet-4-20250514",
                    "openai:gpt-4o",
                ],
            },
        }

    # --- Run Lifecycle ---

    @app.post("/api/runs")
    async def start_run(req: RunRequest):
        """Step 1: Generate spec.md from task. Returns spec for user approval."""
        config = Config.load(
            provider=req.provider,
            model=req.model or None,
            workspace_dir=str(ws_dir),
            max_iterations=req.max_iterations,
            max_budget_usd=req.budget or None,
        )
        if req.auto_route:
            config.auto_route_models = True

        run_id = f"{__import__('uuid').uuid4().hex[:8]}"

        event_bus.emit(EventType.RUN_STARTED, {
            "run_id": run_id,
            "task": req.task[:500],
            "phase": "generating_spec",
        })

        async def _generate_spec():
            try:
                from ralph.prompts.templates import SPEC_SYSTEM_PROMPT, SPEC_USER_TEMPLATE
                from ralph.memory.progress import init_progress
                from ralph.memory.guardrails import init_guardrails
                from ralph.reflexion import init_reflections
                from ralph.observability import setup_logging
                from ralph.loop import _create_provider

                ralph_dir.mkdir(exist_ok=True)
                setup_logging(str(ws_dir))
                init_progress(str(ws_dir))
                init_guardrails(str(ws_dir))
                init_reflections(str(ws_dir))

                # Step 1: Generate spec.md
                provider = _create_provider(config)
                user_msg = SPEC_USER_TEMPLATE.format(task_description=req.task)
                result = await provider.run_session(
                    system_prompt=SPEC_SYSTEM_PROMPT,
                    user_message=user_msg,
                    max_turns=30,
                )

                spec_path = ralph_dir / "spec.md"
                spec_content = spec_path.read_text() if spec_path.exists() else result.final_response

                _pending_approval[run_id] = {
                    "config": config,
                    "task": req.task,
                    "phase": "spec",  # Waiting for spec approval
                }

                event_bus.emit(EventType.SPEC_AWAITING_APPROVAL, {
                    "run_id": run_id,
                    "phase": "spec",
                    "spec_content": spec_content[:10000],
                    "spec_cost": result.cost_usd,
                })
            except Exception as e:
                logger.error("spec gen failed: %s", e)
                import traceback; traceback.print_exc()
                event_bus.emit(EventType.RUN_ERROR, {"run_id": run_id, "error": str(e)})

        asyncio.create_task(_generate_spec())
        return RunResponse(run_id=run_id, status="generating_spec")

    @app.post("/api/runs/{run_id}/approve")
    async def approve_run(run_id: str):
        """Approve current phase (spec → generate PRD, or PRD → start coding)."""
        pending = _pending_approval.get(run_id)
        if not pending:
            raise HTTPException(404, "No pending run to approve")

        current_phase = pending.get("phase", "spec")
        config: Config = pending["config"]

        if current_phase == "spec":
            # Step 2: spec.md approved → generate prd.json from it
            _pending_approval[run_id]["phase"] = "generating_prd"

            event_bus.emit(EventType.RUN_STARTED, {
                "run_id": run_id,
                "phase": "generating_prd",
            })

            async def _generate_prd():
                try:
                    from ralph.prompts.templates import PRD_SYSTEM_PROMPT, PRD_USER_TEMPLATE
                    from ralph.loop import _create_provider

                    provider = _create_provider(config)
                    result = await provider.run_session(
                        system_prompt=PRD_SYSTEM_PROMPT,
                        user_message=PRD_USER_TEMPLATE,
                        max_turns=20,
                    )

                    # Load the generated PRD
                    prd = load_prd(str(ws_dir))
                    _pending_approval[run_id]["phase"] = "prd"

                    event_bus.emit(EventType.SPEC_AWAITING_APPROVAL, {
                        "run_id": run_id,
                        "phase": "prd",
                        "prd": prd.model_dump(),
                        "prd_cost": result.cost_usd,
                    })
                except Exception as e:
                    logger.error("prd gen failed: %s", e)
                    import traceback; traceback.print_exc()
                    event_bus.emit(EventType.RUN_ERROR, {"run_id": run_id, "error": str(e)})

            asyncio.create_task(_generate_prd())
            return {"status": "generating_prd", "run_id": run_id}

        elif current_phase == "prd":
            # Step 3: PRD approved → start coding loop
            _pending_approval.pop(run_id, None)
            config.approve_spec = False

            fresh_loop = WebRalphLoop(config, event_bus)
            _active_runs[fresh_loop.run_id] = fresh_loop

            event_bus.emit(EventType.RUN_STARTED, {
                "run_id": fresh_loop.run_id,
                "phase": "coding",
            })

            async def _run_loop():
                try:
                    logger.info("Starting coding loop %s", fresh_loop.run_id)
                    await fresh_loop.run("")
                except Exception as e:
                    logger.error("run %s failed: %s", fresh_loop.run_id, e)
                    event_bus.emit(EventType.RUN_ERROR, {"run_id": fresh_loop.run_id, "error": str(e)})
                    import traceback; traceback.print_exc()
                finally:
                    _active_runs.pop(fresh_loop.run_id, None)

            asyncio.create_task(_run_loop())
            return {"status": "coding", "run_id": fresh_loop.run_id}

        return {"status": "unknown_phase"}

    @app.post("/api/runs/{run_id}/reject")
    def reject_run(run_id: str):
        pending = _pending_approval.pop(run_id, None)
        if not pending:
            raise HTTPException(404, "No pending run")
        event_bus.emit(EventType.RUN_COMPLETED, {"run_id": run_id, "rejected": True})
        return {"status": "rejected"}

    @app.post("/api/runs/{run_id}/stop")
    def stop_run(run_id: str):
        loop = _active_runs.get(run_id)
        if not loop:
            raise HTTPException(404, "Run not found or already completed")
        loop.request_stop()
        return {"status": "stop_requested"}

    # --- WebSocket ---

    @app.websocket("/ws/events")
    async def websocket_events(ws: WebSocket):
        await ws.accept()
        queue = event_bus.subscribe()
        try:
            while True:
                event = await queue.get()
                await ws.send_json(event)
        except WebSocketDisconnect:
            pass
        except Exception:
            pass
        finally:
            event_bus.unsubscribe(queue)

    # --- SPA Fallback ---

    @app.get("/{full_path:path}")
    async def spa_fallback(full_path: str):
        index = static_dir / "index.html" if static_dir.exists() else None
        if index and index.exists():
            return HTMLResponse(index.read_text())
        return HTMLResponse(_fallback_html(str(ws_dir)))

    return app


def _build_file_tree(ws_dir: Path) -> list[dict]:
    skip = {".git", ".ralph", ".venv", "venv", "node_modules", "__pycache__", ".pytest_cache", ".egg-info"}

    def _walk(path: Path):
        entries = []
        try:
            items = sorted(path.iterdir(), key=lambda p: (not p.is_dir(), p.name))
        except PermissionError:
            return entries
        for item in items:
            if item.name in skip or item.name.startswith("."):
                continue
            rel = str(item.relative_to(ws_dir))
            if item.is_dir():
                entries.append({"name": item.name, "path": rel, "is_dir": True, "size": 0, "children": _walk(item)})
            else:
                entries.append({"name": item.name, "path": rel, "is_dir": False, "size": item.stat().st_size, "children": []})
        return entries

    return _walk(ws_dir)


def _detect_language(suffix: str) -> str:
    return {
        ".py": "python", ".js": "javascript", ".ts": "typescript",
        ".tsx": "tsx", ".jsx": "jsx", ".json": "json", ".md": "markdown",
        ".toml": "toml", ".yaml": "yaml", ".yml": "yaml",
        ".html": "html", ".css": "css", ".sql": "sql",
        ".sh": "bash", ".rs": "rust", ".go": "go",
    }.get(suffix, "text")


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
    return path.read_text() if path.exists() else ""


def _fallback_html(workspace: str) -> str:
    return f"""<!DOCTYPE html>
<html><head><title>Ralph Loop</title>
<style>body{{background:#0f172a;color:#e2e8f0;font-family:system-ui;display:flex;justify-content:center;align-items:center;height:100vh;margin:0}}
.box{{text-align:center;max-width:500px}}h1{{color:#38bdf8}}code{{background:#1e293b;padding:8px 16px;border-radius:8px;display:block;margin:16px 0}}</style>
</head><body><div class="box">
<h1>Ralph Loop Dashboard</h1>
<p>Frontend not built. Run:</p>
<code>cd frontend && npm install && npm run build</code>
<p style="color:#475569;margin-top:24px">Workspace: {workspace}</p>
</div></body></html>"""
