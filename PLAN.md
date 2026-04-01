# Ralph Loop - Remaining Tasks

## Status: 158 tests pass, 35/35 real API tasks completed (incl 12-task unit converter)

---

## NEXT UP - UI Overhaul

### Requirements (from user):
1. Light/dark theme toggle (default dark)
2. Catchy hero section with architecture flow diagram using icons
3. Show the 3-step process visually: Task → Spec → PRD → Code
4. Spec.md display in a nice scrollable UI component
5. PRD tasks in stepwise ladder/stepper display
6. Progress shown as tasks complete (highlight current, green done)
7. Proper file viewer for generated code
8. Push to new GitHub repo with attractive README
9. Update prompts for better quality

### Technical approach:
- Use framer-motion for animations (already installed)
- Add theme toggle with CSS variables (dark/light)
- Stepper component for the 3-phase flow
- Markdown renderer for spec.md display
- Fix the WebSocket event flow so UI updates in real-time during coding

---

## TODAY - Must Do

### 1. SWE-bench Lite Evaluation
- **Why:** Without a benchmark score, we can't prove the agent works on real-world bugs. This is the #1 credibility gap.
- **How:**
  - Clone SWE-bench lite (300 problems from real GitHub repos)
  - Write a harness that converts each SWE-bench problem into a Ralph PRD
  - Run Ralph on a subset (start with 20, then scale to 300)
  - Track: pass rate, cost per problem, common failure modes
- **Expected output:** "Ralph scores X% on SWE-bench lite at $Y per problem"
- **Effort:** 4-6 hours

### 2. Wire Parallel Execution into Loop
- **Why:** `parallel.py` exists but is never called. 10-task projects run 3x slower than necessary.
- **How:**
  - Add `--parallel` flag to CLI
  - In `_main_loop`, detect independent tasks (same priority level)
  - Use `run_parallel_batch` with git worktrees
  - Merge successful branches back
  - Test with real API on a project with 3+ independent tasks
- **Effort:** 2-3 hours

### 3. Wire Incremental Tests into Coding Prompt
- **Why:** Agent runs full test suite every time. On 50+ test projects, this wastes time.
- **How:**
  - After coding session, use `find_affected_tests` to detect changed files
  - Inject affected test paths into the QA prompt: "Run these specific tests first, then full suite"
  - Test on the existing 10-task Todo API project
- **Effort:** 1 hour

### 4. Real API Test: Existing Large Codebase
- **Why:** Only tested on projects we created. Need to prove it works on someone else's code.
- **How:**
  - Clone a real open-source Python project (e.g., httpie, click, or a small FastAPI app)
  - Create a PRD to add a feature (e.g., "add a new CLI flag" or "add a new endpoint")
  - Run Ralph and verify it works without breaking existing tests
- **Effort:** 2 hours

### 5. Deep Agents SDK Quality Fix
- **Why:** GPT-4o via Deep Agents produces minimal tests (5 vs Claude's 7). Prompt needs tuning.
- **How:**
  - Add "Write comprehensive tests including edge cases" to CODING_SYSTEM_PROMPT
  - Test Deep Agents with Anthropic key (fix auth issue found in testing)
  - Compare quality side-by-side again
- **Effort:** 1 hour

---

## NEXT WEEK - Should Do

### 6. Docker Sandbox by Default
- Wire `sandbox.py` into the loop as default mode when Docker is available
- Add `--no-sandbox` flag to opt out
- Test that agent code runs inside container, not on host

### 7. Multi-Language Support
- Test Ralph on a TypeScript/Node.js project
- Test on a Go project
- Verify prompts work across languages

### 8. Production Hardening
- Add file locking on .ralph/ files (concurrent access safety)
- Add graceful state save on SIGTERM (not just Ctrl+C)
- Add max cost per task (not just per run)
- Add model fallback (if Opus fails, try Sonnet)

### 9. Documentation
- Add detailed API docs for each module
- Add "How to Extend" guide (adding new providers, tools, skills)
- Add "Troubleshooting" section to README
- Record a demo video

---

## LATER - Nice to Have

### 10. OpenTelemetry Export
- Replace/supplement sessions.jsonl with OTLP spans
- Support Jaeger, Grafana Tempo, Elastic APM backends
- Add per-tool-call spans for fine-grained debugging

### 11. Team Features
- Multi-user support (different API keys per user)
- Shared PRD editing
- Slack/Discord notifications on task completion

### 12. Plugin System
- Allow users to register custom MCP tools via config
- Plugin marketplace (like Claude Code plugins)

---

## Tracking

| Task | Status | Date Started | Date Done |
|------|--------|-------------|-----------|
| SWE-bench lite | NOT STARTED | | |
| Parallel execution wired | NOT STARTED | | |
| Incremental tests wired | NOT STARTED | | |
| Large codebase test | NOT STARTED | | |
| Deep Agents quality fix | NOT STARTED | | |
| Docker sandbox default | NOT STARTED | | |
| Multi-language test | NOT STARTED | | |
| Production hardening | NOT STARTED | | |
| Documentation | NOT STARTED | | |
| OpenTelemetry | NOT STARTED | | |
