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
## User Input

{task_description}

## Instructions

The above is what the user provided. It could be a one-liner, bullet points,
a detailed spec, or a pasted document. Regardless of how detailed or vague it is:

1. Use Glob and Read to examine the current workspace for existing code
2. Expand the user's input into a COMPLETE application specification
3. Fill in every gap — if the user didn't specify something, decide it
4. Write the full spec to `.ralph/spec.md`
5. Every feature, every error case, every validation rule, every endpoint
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
