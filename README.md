# ⚡ Ralph Loop — Autonomous Coding Agent

> **Describe it. Ralph builds it.** From a single task description to tested, committed, production-ready code — with human approval at every step.

Ralph Loop is an open-source autonomous coding agent that takes a task, generates a detailed specification, breaks it into atomic tasks, and iteratively codes each one with QA review, healer loops, and full observability. Powered by **Claude Agent SDK** and **Deep Agents SDK**.

## ✨ What It Does

```
You: "Build a REST API with FastAPI for managing todo items"
                    ↓
        Ralph generates spec.md (architecture, models, API design)
                    ↓
        You review and approve the spec
                    ↓
        Ralph breaks it into 12 atomic tasks (prd.json)
                    ↓
        You review and approve the task list
                    ↓
        Ralph codes each task autonomously:
          • Fresh context per iteration (no context rot)
          • Writes code + tests
          • QA Sentinel reviews every change
          • Healer auto-fixes failures
          • Git commit per task
                    ↓
        12/12 tasks complete | 66 tests | 98% coverage | $5.73
```

## 🎯 Real Results (Not Benchmarks — Actual API Runs)

| Project | Tasks | Tests | Coverage | Cost | Time |
|---------|-------|-------|----------|------|------|
| **Todo API** (FastAPI + SQLite + CRUD) | 10/10 ✅ | 47 pass | — | $2.48 | 20m |
| **URL Shortener** (cache + rate limit + stats) | 6/6 ✅ | 35 pass | — | $2.81 | 20m |
| **Unit Converter** (CLI + 3 unit types) | 12/12 ✅ | 66 pass | 98% | $5.73 | 30m |
| **Existing Codebase** (add search to Todo API) | 2/2 ✅ | 58 pass (0 regressions) | — | $0.89 | 9m |

**Total: 35/35 real tasks completed. 158 framework tests pass.**

## 🖥️ Web Dashboard

Ralph includes a full web dashboard built with React + TypeScript + Tailwind CSS.

### Landing Page
Clean hero section with animated terminal mockup showing Ralph in action, architecture flow diagram, feature cards, and real project stats.

### Task Input (`/new`)
Full-screen input experience with:
- Large textarea for task description
- Drag & drop file upload for context
- Reference link management
- Quick-start template cards (REST API, CLI Tool, URL Shortener, Data Pipeline)
- Expandable settings (provider, model, budget, max iterations)

### Dashboard (`/dashboard`)
Step-by-step wizard with horizontal stepper:
1. **Spec Generation** — animated progress with dynamic status messages
2. **Spec Review** — full-screen markdown viewer with Edit, Copy, Download buttons
3. **Task Breakdown** — animated loading with progress dots
4. **Task Review** — gradient project header + expandable task cards with acceptance criteria
5. **Coding** — three-panel layout: task list (with progress bar) + colored terminal + metrics sidebar

### Results (`/results`)
- **Code tab** — file tree + syntax-highlighted code viewer with line numbers
- **Spec tab** — rendered markdown of the full spec
- **Progress tab** — iteration log, guardrails, reflections
- **Analytics tab** — cost breakdown, session stats, duration metrics
- **Git tab** — commit history

## 🚀 Quick Start

### Prerequisites
- Python 3.12+
- [Claude Code CLI](https://docs.anthropic.com/en/docs/claude-code) installed (`npm install -g @anthropic-ai/claude-code`)
- An Anthropic API key (or Azure Foundry endpoint)

### Install

```bash
git clone https://github.com/satvik/autonomous-coding-ralph-loop.git
cd autonomous-coding-ralph-loop

# Install with uv (recommended)
uv pip install -e ".[web]"

# Or with pip
pip install -e ".[web]"
```

### Configure

```bash
cp .env.example .env
# Edit .env — set your ANTHROPIC_API_KEY
```

**Minimal .env:**
```env
ANTHROPIC_API_KEY=sk-ant-your-key-here
```

**With Azure Foundry:**
```env
CLAUDE_CODE_USE_FOUNDRY=1
ANTHROPIC_FOUNDRY_API_KEY=your-foundry-key
ANTHROPIC_FOUNDRY_BASE_URL=https://your-endpoint.azure.com/anthropic/
ANTHROPIC_DEFAULT_SONNET_MODEL=claude-opus-4-6
```

### Run via CLI

```bash
# Start with a task description
ralph run "Build a REST API with FastAPI for a todo app"

# Specify model
ralph run "Build a CLI tool" -m claude-opus-4-20250514

# Set budget limit
ralph run "Build something" --budget 10.00

# Resume a previous run
ralph resume -w ./my-project

# Check progress
ralph status -w ./my-project
```

### Run via Web Dashboard

```bash
ralph web
# Opens http://localhost:8420
```

Then:
1. Click **Start Building** on the landing page
2. Describe your project, add context files/links
3. Review the generated spec → Approve
4. Review the task breakdown → Start Coding
5. Watch the live terminal as Ralph codes each task
6. Browse results: generated code, tests, analytics, git history

## 🏗️ Architecture

```
ralph/
  cli.py              # CLI commands (run, resume, status, web, analytics)
  config.py           # Configuration from .env + CLI flags
  loop.py             # Main Ralph Loop orchestrator
  models.py           # PRD, Task, AgentResult, QAResult
  providers/
    claude_sdk.py     # Claude Agent SDK (wraps Claude Code CLI)
    deep_agents.py    # Deep Agents SDK (LangGraph-based, any LLM)
  prompts/
    templates.py      # Spec, PRD, Coding, QA, Healer prompts
  spec/
    generator.py      # 2-step: task → spec.md → prd.json
  qa/
    sentinel.py       # Quality gate (separate LLM session)
    healer.py         # Iterative fix loop
  routing.py          # Multi-model routing (Haiku/Sonnet/Opus)
  reflexion.py        # Learn from failures across iterations
  checkpoint.py       # Git tag/rollback per task
  formatting.py       # Auto ruff/black after code gen
  indexer.py          # AST-based codebase indexing
  observability.py    # sessions.jsonl, logging, analytics
  memory/
    progress.py       # Iteration log with learnings
    guardrails.py     # Failure signs for future iterations
  web/
    server.py         # FastAPI + WebSocket backend
    runner.py         # WebRalphLoop (emits WS events)
    events.py         # Event bus for real-time streaming
frontend/             # React + TypeScript + Tailwind
  src/
    pages/            # HomePage, NewRunPage, DashboardPage, ResultsPage
    components/       # Shell, theme toggle
    stores/           # Zustand state management
    api/              # REST + WebSocket clients
.claude/skills/       # /spec, /code, /qa, /status skills
tests/                # 158 tests across 20 test files
```

## 🔑 Key Features

| Feature | Description |
|---------|-------------|
| **2-Step Spec Flow** | Task → spec.md (human reviews) → prd.json (human reviews) → coding |
| **Fresh Context Per Task** | Each coding session starts clean. No context rot. Filesystem is the memory. |
| **QA Sentinel** | Separate LLM session reviews every change. Blocks on failing tests or security issues. |
| **Healer Loop** | Up to 5 fix attempts when QA fails. Auto-rollback on final failure. |
| **Multi-Model Routing** | Haiku for simple tasks, Sonnet for features, Opus for architecture. |
| **Reflexion** | LLM analyzes failures and injects lessons into future iterations. |
| **Git Checkpoints** | Tag before each task. Rollback to last good state on failure. |
| **Budget Control** | `--budget 5.00` with 80% warning and hard stop. |
| **Observability** | sessions.jsonl, ralph.log, analytics CLI, web dashboard. |
| **Safety** | 15 regex patterns blocking dangerous commands. acceptEdits permission model. |

## 📁 Workspace State (`.ralph/`)

When Ralph runs on a project, it creates:

```
your-project/.ralph/
  spec.md           # Application specification (human-readable)
  prd.json          # Task queue with status tracking
  progress.md       # Iteration log with learnings
  guardrails.md     # Failure signs for future iterations
  reflections.md    # LLM failure analysis (Reflexion pattern)
  qa_result.json    # Latest QA verdict
  sessions.jsonl    # Per-session cost/duration/tool tracking
  ralph.log         # Structured debug log
```

## 🤝 Providers

| Provider | SDK | Models | Best For |
|----------|-----|--------|----------|
| **claude-sdk** (default) | Claude Agent SDK | Claude Sonnet, Opus, Haiku | Best quality, native tools |
| **deep-agents** | Deep Agents SDK | Any LangChain model | Multi-model, OpenAI/Gemini |

## 📊 CLI Commands

```bash
ralph run "task"              # Start autonomous coding loop
ralph run -f task.md          # Task from file
ralph resume                  # Continue from existing PRD
ralph status                  # Show task progress
ralph analytics               # Show cost/session analytics
ralph web                     # Launch web dashboard
ralph dashboard               # Simple HTML dashboard
ralph index                   # Show codebase index
ralph progress                # Show iteration log
ralph guardrails              # Show failure memory
```

## 🧪 Testing

```bash
# Run the 158 mock tests
python -m pytest tests/ -v

# Tests cover:
# - Models, config, spec generation, memory, QA parsing
# - Completion/blocked detection, safety patterns
# - Routing, reflexion, checkpoints, parallel detection
# - Full E2E loop (mock): happy path, QA fail+heal, session failure,
#   budget exhaustion, incomplete auto-fail, corrupted PRD
# - Skills validation, dashboard, formatting, incremental tests
```

## 🙏 Inspired By

- [Anthropic's Autonomous Coding Quickstart](https://github.com/anthropics/claude-quickstarts/tree/main/autonomous-coding) — Two-agent pattern
- [snarktank/ralph](https://github.com/snarktank/ralph) — The original Ralph loop pattern
- [Geoffrey Huntley's Ralph Pattern](https://ghuntley.com/ralph/) — Fresh context per iteration
- [Deep Agents (LangChain)](https://github.com/langchain-ai/deepagents) — Planning + sub-agents

## 📄 License

MIT
