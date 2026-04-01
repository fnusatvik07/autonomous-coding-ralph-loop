# Ralph Loop — Autonomous Coding Agent

**Describe it. Ralph builds it.** From a single task description to tested, committed, production-ready code — with human approval at every step.

![Ralph Loop Dashboard](docs/screenshot.png)

Ralph Loop is an open-source autonomous coding agent that takes a task, generates a detailed specification, breaks it into atomic tasks, and iteratively codes each one with QA review, healer loops, and full observability.

---

## What It Does

```
You: "Build a REST API with FastAPI for managing todo items"

Ralph:
  1. Generates spec.md (architecture, data models, API design, testing strategy)
  2. You review and approve the spec
  3. Breaks it into 12 atomic tasks (prd.json)
  4. You review and approve the task list
  5. Codes each task autonomously:
     - Fresh context per iteration (no context rot)
     - Writes code + tests
     - QA Sentinel reviews every change
     - Healer auto-fixes failures
     - Git commit per task
  6. Done: 12/12 tasks | 66 tests | 98% coverage | $5.73 total
```

---

## Real Results

These are actual runs with real API calls, not benchmarks or mocks.

| Project | Tasks | Tests | Coverage | Cost | Time |
|---------|-------|-------|----------|------|------|
| Todo API (FastAPI + SQLite + CRUD) | 10/10 | 47 pass | -- | $2.48 | 20m |
| URL Shortener (cache + rate limit + stats) | 6/6 | 35 pass | -- | $2.81 | 20m |
| Unit Converter (CLI + 3 unit types) | 12/12 | 66 pass | 98% | $5.73 | 30m |
| Existing Codebase (add search to Todo API) | 2/2 | 58 pass (0 regressions) | -- | $0.89 | 9m |

**35/35 real tasks completed. 158 framework tests pass.**

---

## Setup

### Prerequisites

- **Python 3.12+**
- **Claude Code CLI** — install with `npm install -g @anthropic-ai/claude-code`
- **Anthropic API key** (or Azure Foundry endpoint)
- **Node.js 18+** (only needed if you want to modify the web dashboard)

### Step 1: Clone the repo

```bash
git clone https://github.com/fnusatvik07/autonomous-coding-ralph-loop.git
cd autonomous-coding-ralph-loop
```

### Step 2: Install Python dependencies

Using uv (recommended):
```bash
uv pip install -e ".[web]"
```

Or with pip:
```bash
pip install -e ".[web]"
```

The `[web]` extra installs FastAPI, uvicorn, and websockets for the web dashboard. If you only want the CLI, run without it:
```bash
pip install -e .
```

### Step 3: Configure your API key

```bash
cp .env.example .env
```

Edit `.env` and set your API key. You only need ONE of these:

**Option A — Direct Anthropic API:**
```env
ANTHROPIC_API_KEY=sk-ant-your-key-here
```

**Option B — Azure Foundry:**
```env
CLAUDE_CODE_USE_FOUNDRY=1
ANTHROPIC_FOUNDRY_API_KEY=your-foundry-key
ANTHROPIC_FOUNDRY_BASE_URL=https://your-endpoint.azure.com/anthropic/
ANTHROPIC_DEFAULT_SONNET_MODEL=claude-opus-4-6
```

**Option C — OpenAI (via Deep Agents provider):**
```env
OPENAI_API_KEY=sk-proj-your-key-here
RALPH_PROVIDER=deep-agents
RALPH_MODEL=openai:gpt-4o
```

### Step 4: Verify it works

```bash
ralph --version
ralph status
```

---

## Usage

### Via CLI

```bash
# Start a new project
ralph run "Build a REST API with FastAPI for a todo app"

# Use a specific model
ralph run "Build a CLI tool" -m claude-opus-4-20250514

# Set a budget limit (stops when exceeded)
ralph run "Build something" --budget 10.00

# Point at an existing project directory
ralph run "Add pagination to the API" -w ./my-project

# Resume a previous run
ralph resume -w ./my-project

# Check progress
ralph status -w ./my-project

# View cost analytics
ralph analytics -w ./my-project
```

### Via Web Dashboard

```bash
ralph web
# Opens http://localhost:8420
```

The web dashboard provides:

1. **Landing page** — describes how Ralph works, shows real project stats
2. **Task input** (`/new`) — full-screen textarea, file upload, reference links, template cards, configurable settings
3. **Dashboard** (`/dashboard`) — step-by-step wizard:
   - Spec generation with animated status messages
   - Spec review with edit/copy/download
   - Task breakdown with expandable cards
   - Live coding terminal with iteration tracking and QA status
4. **Results** (`/results`) — file browser with syntax highlighting, spec viewer, analytics, git history

---

## How It Works

Ralph follows a 5-step pipeline:

**Step 1 — Generate Specification.** The LLM reads your task, examines the workspace, and writes `spec.md` — a detailed document covering architecture, data models, API endpoints, and testing strategy.

**Step 2 — Human Review.** You read the full spec in a markdown viewer. Approve it to continue, or reject and regenerate.

**Step 3 — Task Breakdown.** The approved spec is decomposed into atomic tasks (`prd.json`). Each task fits one coding session, is ordered by dependency, and has testable acceptance criteria.

**Step 4 — Autonomous Coding.** For each task, Ralph creates a fresh agent session (no context rot), reads the spec, implements the code, writes tests, and commits. A separate QA Sentinel session reviews every change. If QA fails, a Healer loop iterates up to 5 times to fix the issue.

**Step 5 — Delivered.** All tasks pass QA. Clean git history with one commit per feature. Full analytics available: cost per phase, tool usage, duration, test coverage.

---

## Key Features

| Feature | What it does |
|---------|-------------|
| 2-Step Spec Flow | task to spec.md (reviewed) to prd.json (reviewed) to coding |
| Fresh Context Per Task | Each session starts clean — filesystem is the memory |
| QA Sentinel | Separate LLM session reviews every change |
| Healer Loop | Auto-fixes QA failures up to 5 times, rollback on final failure |
| Multi-Model Routing | Haiku for simple, Sonnet for moderate, Opus for complex tasks |
| Reflexion | LLM analyzes failures, stores lessons for future iterations |
| Git Checkpoints | Tag before each task, rollback on failure |
| Budget Control | --budget flag with 80% warning and hard stop |
| Observability | sessions.jsonl, structured logging, analytics CLI + web dashboard |
| Safety | 15 regex patterns blocking dangerous shell commands |

---

## Project Structure

```
ralph/
  cli.py              # CLI (run, resume, status, web, analytics)
  config.py           # Configuration from .env + CLI flags
  loop.py             # Main loop orchestrator
  models.py           # PRD, Task, AgentResult, QAResult
  providers/
    claude_sdk.py     # Claude Agent SDK provider
    deep_agents.py    # Deep Agents SDK provider (any LangChain model)
  prompts/
    templates.py      # Spec, PRD, Coding, QA, Healer prompts
  spec/
    generator.py      # 2-step: task to spec.md to prd.json
  qa/
    sentinel.py       # Quality gate
    healer.py         # Fix loop
  routing.py          # Multi-model routing
  reflexion.py        # Failure analysis
  checkpoint.py       # Git checkpoints
  observability.py    # Logging + analytics
  web/
    server.py         # FastAPI + WebSocket
    runner.py         # WebRalphLoop
    events.py         # Event bus
frontend/             # React + TypeScript + Tailwind
tests/                # 158 tests
.claude/skills/       # /spec, /code, /qa, /status
```

---

## Workspace Files

When Ralph runs on a project, it creates a `.ralph/` directory:

```
.ralph/
  spec.md           # Application specification
  prd.json          # Task queue with status
  progress.md       # Iteration log with learnings
  guardrails.md     # Failure signs for future iterations
  reflections.md    # LLM failure analysis
  qa_result.json    # Latest QA verdict
  sessions.jsonl    # Per-session cost and duration
  ralph.log         # Debug log
```

---

## CLI Reference

| Command | Description |
|---------|-------------|
| `ralph run "task"` | Start the autonomous coding loop |
| `ralph run -f task.md` | Read task from a file |
| `ralph resume` | Continue from existing PRD |
| `ralph status` | Show task progress |
| `ralph analytics` | Show cost and session analytics |
| `ralph web` | Launch web dashboard |
| `ralph progress` | Show iteration log |
| `ralph guardrails` | Show failure memory |
| `ralph index` | Show codebase index |

---

## Running Tests

```bash
python -m pytest tests/ -v
# 158 tests across 20 test files
```

---

## License

MIT
