"""
Prompt Loading
==============

Loads prompt templates from markdown files in prompts/files/.
Following Anthropic's pattern of externalizing prompts from code.

System prompts are loaded from .md files (easy to edit without code changes).
User templates are lightweight formatters defined here.
"""

from pathlib import Path

PROMPTS_DIR = Path(__file__).parent / "files"


def _load(name: str) -> str:
    """Load a prompt from the files directory."""
    return (PROMPTS_DIR / f"{name}.md").read_text()


# System prompts (loaded from markdown files)
SPEC_SYSTEM_PROMPT = _load("spec_system")
PRD_SYSTEM_PROMPT = _load("prd_system")
CODING_SYSTEM_PROMPT = _load("coding")
QA_SYSTEM_PROMPT = _load("qa_system")
HEALER_SYSTEM_PROMPT = _load("healer")
REVIEWER_SYSTEM_PROMPT = _load("reviewer")
SPEC_REVIEWER_SYSTEM_PROMPT = _load("spec_reviewer")

# User templates (lightweight formatters)
SPEC_USER_TEMPLATE = """\
## User Input

{task_description}

## Instructions

1. Use Glob and Read to examine the current workspace for existing code
2. Expand the user's input into a COMPLETE application specification
3. Fill in every gap — if the user didn't specify something, decide it

IMPORTANT: Output the ENTIRE specification as markdown directly in your response.
Do NOT use the Write tool for the spec. Just output it as text.
Start your output with: # Application Specification:
Include every section from the spec template.
"""

PRD_USER_TEMPLATE = """\
Read the approved spec at `.ralph/spec.md` and convert it into a task list.

IMPORTANT: Output the COMPLETE prd.json content inside a ```json code block
in your response. Do NOT use the Write tool for prd.json — just output it
as text and the system will save it automatically.

Scale tasks to project complexity. Each task = one testable behavior.
Order by dependency: infrastructure, core, validation, errors, tests, polish.
Also create init.sh in the workspace root using the Write tool.
"""

CODING_USER_TEMPLATE = """\
Start a new coding session for: {task_id} - {task_title}

Follow the 10-step protocol. Begin with Step 1 (Get Your Bearings).
Output <ralph:task_complete>{task_id}</ralph:task_complete> when verified.
"""

FEATURE_CODING_USER_TEMPLATE = """\
Start a new coding session for Feature: {feature_id} - {feature_title}

## Tasks to complete (in order):
{tasks_list}

## Instructions
Follow the 10-step protocol. Begin with Step 1 (Get Your Bearings).

Complete each task in the order listed above. After EACH task:
1. Write tests and verify they pass
2. Output <ralph:task_complete>TASK-ID</ralph:task_complete>

Continue to the next task without stopping. Complete ALL tasks in this feature.
"""

QA_USER_TEMPLATE = """\
Review changes for: {task_id} - {task_title}

Required test command: {test_command}
Run this FIRST. If it fails, the review automatically fails.

Acceptance criteria (verify each step):
{acceptance_criteria}

IMPORTANT: Output your verdict as a JSON code block in your response:

```json
{{"passed": true/false, "issues": [...], "test_output": "...", "suggestions": [...]}}
```

Do NOT use the Write tool for the verdict — just output it in your response text.
"""

HEALER_USER_TEMPLATE = """\
## Task: {task_id} - {task_title}
## QA Issues (Attempt {attempt}/{max_attempts})

{issues}

## Test Output

{test_output}

Fix these issues. Run tests after each fix.
When done: <ralph:healer_done>fixed</ralph:healer_done>
If stuck: <ralph:healer_done>stuck</ralph:healer_done>
"""
