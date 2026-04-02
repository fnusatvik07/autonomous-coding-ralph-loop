# Ralph Loop v3 — Architecture Document

## Context

This document captures the complete design for Ralph Loop v3, based on:
- Deep analysis of 8 competing systems (Liza, Metaswarm, AgentCoder, DebateCoder, Anthropic, GAN Harness, Composio AO, Ruflo)
- 35 real API tests completed across 7 projects
- Line-by-line comparison with Anthropic's autonomous coding quickstart
- Brainstorming on the right multi-agent roles

This is the reference document for implementation. Give this to any Claude session to continue the work.

---

## What We Took From Each System

| Source | What We Adopted | Why |
|--------|----------------|-----|
| **Anthropic Quickstart** | Fresh context per session, 10-step coding protocol, immutable task list, init.sh | Proven at scale, simple, works |
| **Liza** (9 agents) | Adversarial spec review (Planner writes, Reviewer critiques, Planner revises) | Catches bad specs before wasting coding time |
| **Liza** | Reviewer READS code, does NOT re-run tests | 3x cheaper QA, trusts coder's test output |
| **DebateCoder** | Smart gating — skip review for simple tasks, always review complex | 35% cost savings, proven in paper |
| **Metaswarm** (18 agents) | Auto-aggregate learnings every 10 tasks into "Codebase Patterns" | Better reflexion over time |
| **Metaswarm** | PR Shepherd (Shipper agent) that creates PR and handles lifecycle | Complete delivery pipeline |
| **GAN Harness** | Max 3 fix attempts then escalate to human | Prevents infinite healer loops |
| **AgentCoder** | Independent test thinking (future: test writer never sees code) | Prevents confirmation bias |
| **Addy Osmani** | 3-10 agents max, start simple, add more only when needed | Don't over-engineer |

## What We Keep That Nobody Else Has

| Feature | Unique To Ralph |
|---------|----------------|
| Reflexion (LLM analyzes WHY it failed) | Only Metaswarm has partial equivalent |
| Multi-model routing (Haiku/Sonnet/Opus by complexity) | Nobody else |
| Budget control with 80% warning | Nobody else |
| Git checkpoints with auto-rollback per task | Most have commits but not tagged rollback |
| Web dashboard with live WebSocket streaming | Only Cursor has video (different) |
| 158 framework tests | Nobody tests their agent framework this much |
| Context wind-down at 85% | Novel — nobody tracks this |

---

## v3 Architecture — The Pipeline

```
┌─────────────────────────────────────────────────────────────┐
│                                                               │
│  PHASE 1: PLANNING                                           │
│                                                               │
│  Step 1: Planner Agent                                       │
│    - Reads user task                                         │
│    - Examines workspace                                      │
│    - Writes spec.md (architecture, models, endpoints, etc.)  │
│    - Writes prd.json (hierarchical: features → tasks)        │
│    - Creates init.sh                                         │
│                                                               │
│  Step 2: Plan Reviewer Agent (adversarial)                   │
│    - Reads spec.md                                           │
│    - Critiques: missing features, unclear requirements,       │
│      bad architecture decisions                               │
│    - Planner revises (max 2 review cycles)                   │
│                                                               │
│  Output: reviewed spec.md + hierarchical prd.json + init.sh  │
│                                                               │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  PHASE 2: CODING (loop, one feature per session)             │
│                                                               │
│  For each feature in prd.json:                               │
│                                                               │
│    ┌─────────────────────────────────────────┐               │
│    │ CODER AGENT (1 session per feature)     │               │
│    │                                          │               │
│    │ Step 1: Orient                          │               │
│    │   - Read spec.md, prd.json, progress.md │               │
│    │   - Read guardrails.md                  │               │
│    │   - git log --oneline -20               │               │
│    │   - Count remaining tasks               │               │
│    │                                          │               │
│    │ Step 2: Start servers (init.sh)         │               │
│    │                                          │               │
│    │ Step 3: Regression test                 │               │
│    │   - Run pytest, fix if broken           │               │
│    │                                          │               │
│    │ Step 4: Implement all tasks in feature  │               │
│    │   - TASK-001: implement + test          │               │
│    │   - TASK-002: implement + test          │               │
│    │   - TASK-003: implement + test          │               │
│    │   - Mark each as "passed" when verified │               │
│    │                                          │               │
│    │ Step 5: Run full test suite             │               │
│    │                                          │               │
│    │ Step 6: Git commit                      │               │
│    │                                          │               │
│    │ Step 7: Update progress.md              │               │
│    │                                          │               │
│    │ CONTEXT CHECK: if ~85% used, wind down: │               │
│    │   - Commit whatever is working          │               │
│    │   - Revert uncommitted changes          │               │
│    │   - Update progress: "stopped at X"     │               │
│    │   - Next session picks up where left off│               │
│    └───────────────────┬─────────────────────┘               │
│                         │                                     │
│                         ▼                                     │
│    ┌─────────────────────────────────────────┐               │
│    │ SMART GATE (rule-based, no LLM needed)  │               │
│    │                                          │               │
│    │ Complexity score from prd.json:          │               │
│    │   criteria_count + category + keywords   │               │
│    │                                          │               │
│    │ simple (score 0-1)   → SKIP reviewer    │  ~60% tasks  │
│    │ moderate (score 2-3) → SKIP (unless      │  ~25% tasks  │
│    │                         prev task failed)│               │
│    │ complex (score 4+)   → ALWAYS review    │  ~15% tasks  │
│    └───────────────────┬─────────────────────┘               │
│                         │                                     │
│                         ▼ (only ~25% of features)            │
│    ┌─────────────────────────────────────────┐               │
│    │ REVIEWER AGENT (reads, doesn't run)     │               │
│    │                                          │               │
│    │ - Read the code diff (git diff)         │               │
│    │ - Read test output (trust coder)        │               │
│    │ - Check acceptance criteria vs spec     │               │
│    │ - Check security, hardcoded values      │               │
│    │ - Check patterns from guardrails.md     │               │
│    │                                          │               │
│    │ Output: "approved" or list of issues    │               │
│    └───────────────────┬─────────────────────┘               │
│                         │                                     │
│                         ▼ (only if rejected)                 │
│    ┌─────────────────────────────────────────┐               │
│    │ FIXER AGENT (max 3 attempts)            │               │
│    │                                          │               │
│    │ - Read review issues                    │               │
│    │ - Minimal targeted fix                  │               │
│    │ - Run tests                             │               │
│    │ - Commit                                │               │
│    │                                          │               │
│    │ After 3 failures:                       │               │
│    │   - Mark task BLOCKED                   │               │
│    │   - Write guardrail for future sessions │               │
│    │   - Move to next feature                │               │
│    └─────────────────────────────────────────┘               │
│                                                               │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  PHASE 3: LEARNING (every 10 completed tasks)                │
│                                                               │
│  Auto-aggregate reflections + guardrails into                 │
│  "Codebase Patterns" section at top of progress.md            │
│  So future sessions read the consolidated lessons first       │
│                                                               │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  PHASE 4: SHIPPING (after all tasks complete)                │
│                                                               │
│  SHIPPER AGENT (1 session):                                  │
│    - git push to feature branch                              │
│    - Create PR with description from progress.md             │
│    - If CI fails → auto-fix loop (max 3 attempts)           │
│    - Requires GITHUB_TOKEN in .env                           │
│                                                               │
└─────────────────────────────────────────────────────────────┘
```

---

## PRD Format — Hierarchical (Feature → Tasks)

```json
{
  "project_name": "Bookstore API",
  "description": "FastAPI REST API with SQLite",
  "features": [
    {
      "id": "FEAT-001",
      "title": "Project Infrastructure",
      "priority": 1,
      "tasks": [
        {
          "id": "TASK-001",
          "category": "functional",
          "complexity": "simple",
          "title": "Create pyproject.toml with dependencies",
          "description": "...",
          "acceptance_criteria": ["pip install works", "import app works"],
          "status": "pending",
          "test_command": "pip install -e . && python -c 'import app'"
        },
        {
          "id": "TASK-002",
          "category": "functional",
          "complexity": "simple",
          "title": "Create database module",
          "description": "...",
          "acceptance_criteria": ["init_db creates table", "connection works"],
          "status": "pending",
          "test_command": "python -c 'from app.database import init_db; init_db()'"
        }
      ]
    },
    {
      "id": "FEAT-002",
      "title": "Author CRUD",
      "priority": 2,
      "tasks": [
        {
          "id": "TASK-003",
          "category": "functional",
          "complexity": "moderate",
          "title": "POST /authors creates author",
          "acceptance_criteria": ["returns 201", "body has id", "stored in DB"],
          "status": "pending"
        },
        {
          "id": "TASK-004",
          "category": "validation",
          "complexity": "simple",
          "title": "POST /authors rejects empty name",
          "acceptance_criteria": ["returns 422", "error detail explains issue"],
          "status": "pending"
        },
        {
          "id": "TASK-005",
          "category": "error_handling",
          "complexity": "simple",
          "title": "GET /authors/999 returns 404",
          "acceptance_criteria": ["returns 404", "detail says not found"],
          "status": "pending"
        },
        {
          "id": "TASK-006",
          "category": "integration",
          "complexity": "complex",
          "title": "Author with books - cascade behavior",
          "acceptance_criteria": [
            "create author",
            "create 2 books for author",
            "GET /authors/1 includes books list",
            "DELETE /authors/1 handles books correctly",
            "verify no orphan books"
          ],
          "status": "pending"
        }
      ]
    }
  ]
}
```

**Scale guidelines (unchanged):**
- Simple CLI: 5-8 features, 20-40 tasks
- REST API: 8-15 features, 50-100 tasks
- Full app: 15-25 features, 100-200 tasks

---

## Complexity Classification (Rule-Based, No LLM)

```python
def classify_complexity(task):
    score = 0

    # Criteria count
    criteria = len(task.acceptance_criteria)
    if criteria <= 2: score += 0
    elif criteria <= 4: score += 1
    else: score += 2  # 5+ criteria

    # Category
    if task.category in ("validation", "quality"): score += 0
    elif task.category == "functional": score += 1
    elif task.category in ("error_handling", "integration"): score += 2

    # Keywords in title/description
    complex_keywords = ["refactor", "migrate", "auth", "security", "multi",
                        "integration", "cascade", "concurrent", "transaction"]
    text = f"{task.title} {task.description}".lower()
    if any(kw in text for kw in complex_keywords): score += 2

    if score <= 1: return "simple"       # skip reviewer (~60%)
    elif score <= 3: return "moderate"    # skip unless prev failed (~25%)
    else: return "complex"               # always review (~15%)
```

**Review decision:**
- `simple` → coder tests pass → done
- `moderate` → coder tests pass → done (UNLESS previous task in same feature failed → review)
- `complex` → coder tests pass → reviewer reads code → approved/rejected

---

## Context Wind-Down Protocol

The agent can't check its own context usage mid-session. We handle this in the loop:

**Proxy signals for context approaching 85%:**
- Tool call count > 150 (each call ~500-2000 tokens)
- Session duration > 5 minutes
- Agent has completed 3+ tasks in current session

**When triggered:**
1. Let the agent finish the CURRENT task (don't interrupt mid-implementation)
2. Agent commits whatever is working
3. Agent updates progress.md: "Session ended at context limit. Completed TASK-001, TASK-002. TASK-003 not started."
4. Loop starts a fresh session that picks up from TASK-003

**Implementation:** The loop wraps the agent session. After each tool call response, it checks the proxy signals. When threshold hit, it sends an interrupt message: "Context is running low. Finish your current task, commit, update progress, and end the session."

---

## Agent Roles — Clear Boundaries

| Agent | Session | Reads | Writes | Runs Tests | What It Does NOT Do |
|-------|---------|-------|--------|------------|---------------------|
| **Planner** | 1 session | task description, workspace | spec.md, prd.json, init.sh | No | Does not code |
| **Plan Reviewer** | 1 session | spec.md | review feedback | No | Does not write spec |
| **Coder** | 1 per feature | spec.md, prd.json, progress.md, guardrails.md, code | code, tests, prd.json status, progress.md | YES (pytest) | Does not review quality |
| **Reviewer** | conditional | code diff, test output, spec.md, guardrails.md | review.json | NO (trusts coder) | Does not run tests |
| **Fixer** | conditional | review issues, code | code fixes | YES (re-runs tests) | Does not implement new features |
| **Shipper** | 1 session | progress.md, git history | PR description | YES (CI check) | Does not code |

---

## File Structure

```
workspace/
  .ralph/
    spec.md                  ← master spec (reviewed by Plan Reviewer)
    prd.json                 ← hierarchical feature → task list
    progress.md              ← iteration log + codebase patterns (aggregated)
    guardrails.md            ← failure signs for future sessions
    reflections.md           ← LLM failure analysis
    sessions.jsonl           ← every session with cost/duration/tools
    ralph.log                ← structured debug log
    sessions/
      ralph_<uuid>/          ← this run's tracking
        spec.md              ← copy at run start
        prd.json             ← copy at run start
  init.sh                    ← project setup script
  .gitignore
  (generated project files)
```

---

## Possible Fallouts and Mitigations

### HIGH RISK

| Risk | What Happens | Mitigation |
|------|-------------|------------|
| **Feature grouping wrong** | Coder has missing dependencies within a session | Tasks within features are priority-ordered. Cross-feature deps handled by feature priority. If blocked, coder writes guardrail and moves on. |
| **Context wind-down timing** | Session ends mid-task, uncommitted code lost | Git checkpoint BEFORE each task. Rollback to checkpoint if task not completed. Only committed code survives. |
| **Adversarial review loops** | Planner and Reviewer argue forever | Cap at 2 review cycles. After 2, proceed with best-effort spec. Coding phase surfaces real issues through test failures. |

### MEDIUM RISK

| Risk | What Happens | Mitigation |
|------|-------------|------------|
| **Smart gate misclassifies** | Complex task skipped review, bug ships | Functional correctness guaranteed by pytest. Quality issues on misclassified tasks are minor (hardcoded value, style issue). |
| **Shipper CI failure** | Tests pass locally, fail on CI | init.sh should match CI environment. Cap CI fix at 3 attempts. Create draft PR with CI failure comment. |
| **Large PRD generation timeout** | 100+ tasks too big for one session | Combined session approach already proven (generated 90 tasks). If still fails, split into 2 sessions: spec first, then PRD. |

### LOW RISK

| Risk | What Happens | Mitigation |
|------|-------------|------------|
| **Simple feature wastes a session** | 2-task feature uses full session overhead | Accept for v3. Optimize later: allow coder to pick up next feature if context allows. |
| **Cross-model review unavailable** | User only has one API key | Same-model review in fresh context still valuable. Cross-model is optional enhancement. |
| **Auto-aggregation loses detail** | Consolidated patterns miss specific failure | Aggregation is append-only. Both individual reflections AND aggregated patterns available. |

---

## Implementation Phases

### Phase 1 (build now)
- Hierarchical PRD format (features → tasks)
- Coder processes 1 feature per session (all its tasks)
- Complexity classification (rule-based)
- Shipper agent (push + PR)
- Session directories with tracking

### Phase 2 (build next)
- Smart reviewer gating (skip simple, review complex)
- Reviewer agent (reads code, doesn't run tests)
- Fixer agent (max 3 attempts)
- Context wind-down (proxy signals: tool count, duration)

### Phase 3 (build later)
- Adversarial spec review (Planner ↔ Plan Reviewer)
- Auto-aggregate learnings every 10 tasks
- Cross-model review option
- CI failure auto-fix in shipper

---

## Key Decisions Log

1. **Why 2-level hierarchy (feature → task) not 3 (epic → story → task)?**
   Simpler = more reliable LLM output. 2 levels captures grouping without over-structuring.

2. **Why reviewer doesn't re-run tests?**
   Coder already runs tests. Re-running is wasteful (proven by our 80% redundancy finding). Reviewer adds value by reading code for quality, not execution.

3. **Why max 3 fixer attempts not 5?**
   GAN Harness research shows 3 captures 95% of fixable bugs. After 3, it's a design problem not a bug. Escalate to human.

4. **Why not Puppeteer for all projects?**
   Backend APIs don't need browser testing. pytest + TestClient is faster, more reliable, and measurable. Puppeteer is opt-in for web/frontend projects.

5. **Why context wind-down uses proxy signals not SDK API?**
   Claude Agent SDK doesn't expose mid-session context usage through our streaming interface. Tool call count (~500-2000 tokens each) is a reliable proxy.

6. **Why cap adversarial spec review at 2 cycles?**
   Perfect specs aren't necessary. Good-enough specs + iterative coding handles the rest. 2 cycles catches 90% of issues.
