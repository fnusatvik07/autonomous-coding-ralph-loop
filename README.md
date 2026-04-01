# Ralph Loop - Autonomous Coding Agent

An autonomous coding agent that takes a task, creates a spec, and iteratively builds code until done. Powered by **Claude Agent SDK** and **Deep Agents SDK** - real agent frameworks, not toy wrappers.

## How It Works

```
Task Description
       |
       v
  +-----------+
  | Spec Gen  |  LLM analyzes workspace, creates PRD with atomic user stories
  +-----------+
       |
       v  (--approve flag pauses here for human review)
  +===========+
  | LOOP      |  Each iteration = FRESH agent session (no context rot):
  |           |
  |  Orient   |  Read PRD, progress, guardrails, codebase
  |  Code     |  Implement one task, write tests
  |  Test     |  Run full test suite
  |  QA Gate  |  Sentinel reviews quality + acceptance criteria
  |  Heal     |  If QA fails, fix issues (up to 5x)
  |  Commit   |  Git commit, update PRD, log progress
  +===========+
       |
       v
  All Tasks Complete ($X.XX total cost)
```

## Quick Start

```bash
# Install
git clone https://github.com/satvik/autonomous-coding-ralph-loop.git
cd autonomous-coding-ralph-loop
uv pip install -e .

# Configure
cp .env.example .env
# Edit .env - add your ANTHROPIC_API_KEY

# Run
ralph run "Build a REST API with FastAPI for a todo app with user auth"
```

## Two Agent SDKs

### Claude Agent SDK (recommended)

Uses the real Claude Code CLI under the hood. Gets professional-grade tools (Read, Write, Edit, Bash, Glob, Grep) with sandboxing, streaming, and cost tracking. No homemade tools.

```bash
ralph run "Build a todo app" -p claude-sdk
```

### Deep Agents SDK

Uses LangGraph with built-in planning (todo tool), sub-agent delegation, auto-summarization, and filesystem access. Works with any LangChain-compatible model.

```bash
ralph run "Build a todo app" -p deep-agents -m "anthropic:claude-sonnet-4-20250514"
ralph run "Build a todo app" -p deep-agents -m "openai:gpt-4o"
```

## CLI Commands

```bash
ralph run "task"              # Start with a task
ralph run -f task.md          # Task from file
ralph run "task" --approve    # Pause after spec for human review
ralph resume                  # Continue from existing PRD
ralph status                  # Show task progress table
ralph progress                # Show iteration log
ralph guardrails              # Show failure memory
```

### Flags

| Flag | Short | Description |
|------|-------|-------------|
| `--provider` | `-p` | `claude-sdk` (default) or `deep-agents` |
| `--model` | `-m` | Model name |
| `--workspace` | `-w` | Project directory |
| `--max-iterations` | `-n` | Max loop iterations (default: 50) |
| `--approve` | | Human review after spec generation |
| `--env-file` | `-e` | Path to .env file |

## Claude Code Skills

When working on this repo with Claude Code, four skills are available:

| Skill | Description |
|-------|-------------|
| `/spec <task>` | Generate a Ralph PRD from a task description |
| `/code [task-id]` | Execute one coding iteration manually |
| `/qa` | Run QA sentinel review on recent changes |
| `/status` | Show Ralph loop progress |

## Architecture

```
ralph/
  cli.py              # CLI (run, resume, status, progress, guardrails)
  config.py           # Config from .env + CLI flags
  loop.py             # Main Ralph Loop orchestrator
  models.py           # PRD, Task, AgentResult, QAResult
  providers/
    base.py           # Abstract provider interface
    claude_sdk.py     # Claude Agent SDK (wraps Claude Code CLI)
    deep_agents.py    # Deep Agents SDK (LangGraph-based)
  prompts/
    templates.py      # System prompts for spec, coding, QA, healer
  spec/
    generator.py      # PRD generation + load/save
  qa/
    sentinel.py       # Quality gate
    healer.py         # Iterative fix loop
  memory/
    progress.py       # Progress tracking across iterations
    guardrails.py     # Failure memory for future iterations
.claude/skills/       # Claude Code skills (/spec, /code, /qa, /status)
```

### Why Two SDKs?

| | Claude Agent SDK | Deep Agents SDK |
|---|---|---|
| **Tools** | Professional (Claude Code's own) | Built-in (LangGraph filesystem) |
| **Planning** | Via prompt instructions | Built-in `write_todos` tool |
| **Sub-agents** | Via `AgentDefinition` | Via `SubAgent` / `CompiledSubAgent` |
| **Models** | Claude only | Any LangChain model |
| **Streaming** | Native via `query()` events | Via `astream_events()` |
| **Cost tracking** | Built-in (`ResultMessage.total_cost_usd`) | Manual |
| **Best for** | Claude-only projects | Multi-model or LangGraph ecosystem |

### Key Design Decisions

- **Fresh context per iteration** - Each session starts clean. Filesystem is the memory, not the conversation. Prevents context rot.
- **QA Sentinel** - Separate LLM session reviews every change. Blocks on failing tests, security issues, missing coverage.
- **Healer Loop** - Up to 5 attempts to fix QA failures before marking a task as failed.
- **Guardrails** - Failed iterations leave "signs" for future agents to avoid repeating mistakes.
- **Robust completion** - Checks XML markers, prd.json state, AND response patterns.
- **Cost tracking** - Every session reports cost; cumulative total shown per iteration.

### Workspace State (`.ralph/`)

```
your-project/.ralph/
  prd.json          # Task queue with status
  progress.md       # Iteration log + patterns learned
  guardrails.md     # Failure signs for future iterations
  spec.md           # Human-readable spec summary
  qa_result.json    # Latest QA verdict
  .approved         # Flag that spec was human-approved
```

## Inspired By

- [Anthropic Autonomous Coding Quickstart](https://github.com/anthropics/claude-quickstarts/tree/main/autonomous-coding)
- [snarktank/ralph](https://github.com/snarktank/ralph) - The original Ralph loop
- [Geoffrey Huntley's Ralph Pattern](https://ghuntley.com/ralph/)
- [Deep Agents (LangChain)](https://github.com/langchain-ai/deepagents)

## License

MIT
