"""
Security Hooks for Ralph Loop
==============================

Bash command validation using an allowlist approach.
Adapted from Anthropic's autonomous coding quickstart security.py.

Uses shlex parsing (not regex) for robust command extraction.
Commands not in ALLOWED_COMMANDS are blocked.
Sensitive commands (pkill, chmod, rm) get additional validation.
"""

import os
import re
import shlex


# Allowed commands for development tasks
ALLOWED_COMMANDS = {
    # File inspection
    "ls", "cat", "head", "tail", "wc", "grep", "find", "diff", "which",
    # File operations
    "cp", "mv", "mkdir", "touch", "chmod",
    # Directory
    "pwd", "cd",
    # Python development
    "python", "python3", "pip", "pip3", "uv", "pytest", "mypy", "ruff",
    # Node.js development
    "npm", "npx", "node", "yarn", "pnpm", "bun",
    # Build tools
    "cargo", "rustc", "go", "make", "cmake",
    # Version control
    "git",
    # Process management
    "ps", "lsof", "sleep", "pkill", "kill",
    # Shell utilities
    "echo", "sort", "uniq", "cut", "tr", "sed", "awk", "xargs",
    "date", "env", "export", "test", "true", "false",
    # Network (limited)
    "curl", "wget",
    # Docker
    "docker", "docker-compose",
    # Script execution
    "init.sh", "sh", "bash",
}

# Explicitly blocked (even if they somehow pass allowlist)
BLOCKED_COMMANDS = {
    "sudo", "su", "ssh", "scp", "rsync",
    "shutdown", "reboot", "poweroff", "halt",
    "fdisk", "mkfs", "mount", "umount",
    "iptables", "ufw",
    "useradd", "userdel", "passwd", "chown",
}

# Commands requiring extra validation
SENSITIVE_COMMANDS = {"pkill", "chmod", "rm", "init.sh"}


def extract_commands(command_string: str) -> list[str]:
    """Extract command names from a shell command string.

    Handles pipes, chaining (&&, ||, ;), and paths.
    Returns base command names (without paths).
    """
    commands = []

    # Split on semicolons not inside quotes
    segments = re.split(r'(?<!["\'])\s*;\s*(?!["\'])', command_string)

    for segment in segments:
        segment = segment.strip()
        if not segment:
            continue

        try:
            tokens = shlex.split(segment)
        except ValueError:
            # Malformed command — fail safe by returning empty (triggers block)
            return []

        if not tokens:
            continue

        expect_command = True

        for token in tokens:
            # Shell operators mean next token is a command
            if token in ("|", "||", "&&", "&"):
                expect_command = True
                continue

            # Skip shell keywords
            if token in ("if", "then", "else", "elif", "fi", "for", "while",
                         "until", "do", "done", "case", "esac", "in", "!", "{", "}"):
                continue

            # Skip flags
            if token.startswith("-"):
                continue

            # Skip variable assignments
            if "=" in token and not token.startswith("="):
                continue

            if expect_command:
                cmd = os.path.basename(token)
                commands.append(cmd)
                expect_command = False

    return commands


def split_command_segments(command_string: str) -> list[str]:
    """Split compound command into individual segments."""
    segments = re.split(r"\s*(?:&&|\|\|)\s*", command_string)
    result = []
    for segment in segments:
        subs = re.split(r'(?<!["\'])\s*;\s*(?!["\'])', segment)
        for sub in subs:
            sub = sub.strip()
            if sub:
                result.append(sub)
    return result


def validate_pkill(command_string: str) -> tuple[bool, str]:
    """Only allow pkill for dev processes."""
    allowed_targets = {"node", "npm", "npx", "vite", "next", "python", "uvicorn"}
    try:
        tokens = shlex.split(command_string)
    except ValueError:
        return False, "Could not parse pkill command"

    args = [t for t in tokens[1:] if not t.startswith("-")]
    if not args:
        return False, "pkill requires a process name"

    target = args[-1].split()[0] if " " in args[-1] else args[-1]
    if target in allowed_targets:
        return True, ""
    return False, f"pkill only allowed for: {allowed_targets}"


def validate_chmod(command_string: str) -> tuple[bool, str]:
    """Only allow chmod +x (make executable)."""
    try:
        tokens = shlex.split(command_string)
    except ValueError:
        return False, "Could not parse chmod command"

    if len(tokens) < 3:
        return False, "chmod requires mode and file"

    mode = tokens[1]
    if not re.match(r"^[ugoa]*\+x$", mode):
        return False, f"chmod only allowed with +x mode, got: {mode}"
    return True, ""


def validate_rm(command_string: str) -> tuple[bool, str]:
    """Block rm -rf on dangerous paths. Allow rm on specific files."""
    try:
        tokens = shlex.split(command_string)
    except ValueError:
        return False, "Could not parse rm command"

    # Collect flags and targets
    flags = "".join(t.lstrip("-") for t in tokens[1:] if t.startswith("-"))
    targets = [t for t in tokens[1:] if not t.startswith("-")]

    # Block recursive force on dangerous paths
    has_recursive = "r" in flags
    has_force = "f" in flags

    if has_recursive and has_force:
        for target in targets:
            if target in ("/", "~", ".", "..", os.path.expanduser("~")):
                return False, f"rm -rf blocked on dangerous path: {target}"
            if target.startswith("/") and target.count("/") <= 2:
                return False, f"rm -rf blocked on system path: {target}"

    return True, ""


def validate_init_script(command_string: str) -> tuple[bool, str]:
    """Only allow ./init.sh or paths ending in /init.sh."""
    try:
        tokens = shlex.split(command_string)
    except ValueError:
        return False, "Could not parse init script command"

    if not tokens:
        return False, "Empty command"

    script = tokens[0]
    if script == "./init.sh" or script.endswith("/init.sh"):
        return True, ""
    return False, f"Only ./init.sh allowed, got: {script}"


def get_segment_for_command(cmd: str, segments: list[str]) -> str:
    """Find the segment containing a specific command."""
    for segment in segments:
        if cmd in extract_commands(segment):
            return segment
    return ""


async def bash_security_hook(input_data, tool_use_id=None, context=None):
    """Pre-tool-use hook that validates bash commands.

    Only commands in ALLOWED_COMMANDS are permitted.
    Sensitive commands get additional validation.

    Returns empty dict to allow, or block decision to deny.
    """
    if input_data.get("tool_name") != "Bash":
        return {}

    command = input_data.get("tool_input", {}).get("command", "")
    if not command:
        return {}

    commands = extract_commands(command)

    if not commands:
        return {
            "decision": "block",
            "reason": f"Could not parse command: {command[:100]}",
        }

    segments = split_command_segments(command)

    for cmd in commands:
        # Check blocklist first
        if cmd in BLOCKED_COMMANDS:
            return {
                "decision": "block",
                "reason": f"Command '{cmd}' is blocked for security",
            }

        # Check allowlist
        if cmd not in ALLOWED_COMMANDS:
            return {
                "decision": "block",
                "reason": f"Command '{cmd}' is not in the allowed list",
            }

        # Extra validation for sensitive commands
        if cmd in SENSITIVE_COMMANDS:
            segment = get_segment_for_command(cmd, segments) or command

            if cmd == "pkill":
                ok, reason = validate_pkill(segment)
            elif cmd == "chmod":
                ok, reason = validate_chmod(segment)
            elif cmd == "rm":
                ok, reason = validate_rm(segment)
            elif cmd == "init.sh":
                ok, reason = validate_init_script(segment)
            else:
                ok, reason = True, ""

            if not ok:
                return {"decision": "block", "reason": reason}

    return {}
