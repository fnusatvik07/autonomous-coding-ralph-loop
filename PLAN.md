# Ralph Loop — Implementation Plan

## Current State (v2)
- 158 framework tests pass
- 35/35 real API tasks completed (Todo API, URL Shortener, Unit Converter, Bookstore)
- 90-task Bookstore API generated with categories (3/90 completed before stopping)
- Prompts aligned with Anthropic's quickstart (10-step protocol, immutable tasks)
- Web dashboard with React frontend
- Pushed to GitHub: https://github.com/fnusatvik07/autonomous-coding-ralph-loop

## Architecture Reference
**See ARCHITECTURE.md** for the full v3 design, including:
- What we took from each competing system (Liza, Metaswarm, DebateCoder, etc.)
- Complete pipeline diagram
- Hierarchical PRD format
- Complexity classification algorithm
- Context wind-down protocol
- Possible fallouts and mitigations
- Key decision log

---

## v3 Implementation Plan

### Phase 1: Core Refactor (build first)

1. **Hierarchical PRD**
   - Update models.py: add Feature model containing Tasks
   - Update prd_system.md prompt: generate features → tasks
   - Update spec/generator.py: handle new format
   - Update load_prd / save_prd for hierarchical format
   - Update all tests

2. **Coder processes 1 feature per session**
   - Update loop.py: iterate over features not tasks
   - Coder gets all tasks in the feature, completes them in order
   - Each task marked passed individually within the session
   - One git commit per feature (not per task)

3. **Complexity field in tasks**
   - Add classify_complexity() to routing.py
   - Run at PRD load time, populate task.complexity
   - Used by smart gate in Phase 2

4. **Shipper agent**
   - New file: ralph/shipper.py
   - Runs after all tasks complete
   - git push to feature branch
   - Create PR via gh CLI (requires GITHUB_TOKEN)
   - Write PR description from progress.md
   - If CI fails: read error, fix, retry (max 3)

5. **Session directories**
   - Already partially implemented
   - Each run: .ralph/sessions/ralph_<uuid>/
   - Copy spec.md + prd.json at start
   - Log each session's activity

### Phase 2: Smart Review (build next)

6. **Smart gate**
   - In loop.py after coder completes a feature
   - Check max complexity of tasks in that feature
   - simple → skip review
   - moderate → skip unless previous feature had issues
   - complex → send to reviewer

7. **Reviewer agent**
   - New prompt: ralph/prompts/files/reviewer.md
   - Reads git diff, test output, acceptance criteria
   - Does NOT run tests
   - Outputs: "approved" or list of issues
   - New file: ralph/qa/reviewer.py (replaces sentinel.py)

8. **Fixer agent (replaces healer)**
   - Max 3 attempts (down from 5)
   - After 3: mark BLOCKED, write guardrail
   - Reads reviewer issues, makes minimal fix

9. **Context wind-down**
   - Track tool_call_count in loop
   - At 150 tool calls or 5 min duration: signal wind-down
   - Coder finishes current task, commits, updates progress
   - Next session picks up remaining tasks in feature

### Phase 3: Advanced (build later)

10. **Adversarial spec review**
    - Plan Reviewer agent reads spec.md, critiques
    - Planner revises (max 2 cycles)
    - Only then generate prd.json

11. **Auto-aggregate learnings**
    - Every 10 completed tasks
    - Brief session reads all reflections + guardrails
    - Writes consolidated "Codebase Patterns" to progress.md

12. **Cross-model review (optional)**
    - If user has both ANTHROPIC_API_KEY and OPENAI_API_KEY
    - Coder uses Claude, Reviewer uses GPT (or vice versa)
    - Different model = different blind spots

13. **CI failure auto-fix in shipper**
    - After PR created, if CI fails
    - Shipper reads CI log, attempts fix (max 3)
    - If still fails: mark PR as draft, comment with CI error

---

## UI Enhancement Plan (separate track)

See the UI section in ARCHITECTURE.md. Key remaining items:
- Fill blank space on landing page
- Better terminal output in web dashboard
- Spec viewer with edit/download/copy
- Iteration counter and progress bar in terminal
- Loading states with dynamic messages
- File type icons in results page

---

## Testing Plan for v3

- Update existing 158 tests for new hierarchical PRD format
- Add tests for Feature model
- Add tests for classify_complexity()
- Add tests for smart gate logic
- Add tests for shipper agent
- Add tests for context wind-down proxy signals
- Run real E2E test: simple FastAPI app, verify full pipeline
- Run real E2E test: complex project, verify feature batching works
