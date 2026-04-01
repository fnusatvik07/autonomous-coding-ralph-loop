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

# User templates (lightweight formatters)
SPEC_USER_TEMPLATE = """\
## Task Description

{task_description}

## Instructions

1. Use Glob and Read to examine the current workspace
2. Write a comprehensive spec to `.ralph/spec.md`
3. Cover every feature, edge case, and error condition
"""

PRD_USER_TEMPLATE = """\
Read the approved spec at `.ralph/spec.md` and convert it into `.ralph/prd.json`.

Scale tasks to project complexity (20-200 test cases).
Each task = one testable behavior. Be granular.
Order by dependency: infrastructure, core, validation, errors, tests, polish.
"""

CODING_USER_TEMPLATE = """\
Start a new coding session for: {task_id} - {task_title}

Follow the 10-step protocol. Begin with Step 1 (Get Your Bearings).
Output <ralph:task_complete>{task_id}</ralph:task_complete> when verified.
"""

QA_USER_TEMPLATE = """\
Review changes for: {task_id} - {task_title}

Required test command: {test_command}
Run this FIRST. If it fails, the review automatically fails.

Acceptance criteria (verify each step):
{acceptance_criteria}

Read `.ralph/guardrails.md` for known failure patterns.
Write verdict to `.ralph/qa_result.json`.
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
