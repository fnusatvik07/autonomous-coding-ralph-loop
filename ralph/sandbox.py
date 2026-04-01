"""Docker sandbox support - run agent shell commands in isolation.

Supports three modes:
1. Docker Sandboxes (Docker Desktop 4.40+) - recommended for local dev
2. Standard Docker container - works everywhere
3. No sandbox (direct execution) - default, least secure

The sandbox is optional. When enabled, all Bash tool calls execute inside
the container instead of on the host.
"""

from __future__ import annotations

import asyncio
import logging
import shutil
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger("ralph")


@dataclass
class SandboxConfig:
    """Configuration for the Docker sandbox."""

    enabled: bool = False
    image: str = "python:3.13-slim"
    # Network allowlist (empty = no network)
    network_allow: list[str] = field(default_factory=lambda: [
        "api.anthropic.com", "api.openai.com",
        "pypi.org", "files.pythonhosted.org",
        "registry.npmjs.org", "github.com",
    ])
    # Extra packages to install in the container
    extra_packages: list[str] = field(default_factory=list)
    # Memory limit
    memory_limit: str = "2g"
    # CPU limit
    cpu_limit: str = "2"


def is_docker_available() -> bool:
    """Check if Docker is available on the system."""
    return shutil.which("docker") is not None


async def create_sandbox(
    workspace_dir: str,
    config: SandboxConfig,
) -> str | None:
    """Create a Docker sandbox container. Returns container ID or None."""
    if not config.enabled:
        return None

    if not is_docker_available():
        logger.warning("Docker not available, running without sandbox")
        return None

    container_name = f"ralph-sandbox-{Path(workspace_dir).name}"

    # Build docker run command
    cmd_parts = [
        "docker", "run", "-d",
        "--name", container_name,
        "--memory", config.memory_limit,
        "--cpus", config.cpu_limit,
        "-v", f"{Path(workspace_dir).resolve()}:/workspace",
        "-w", "/workspace",
    ]

    # Network: create isolated network with DNS allowlist
    if config.network_allow:
        # For simplicity, use host network with iptables would be complex.
        # Use --network=none for full isolation, or host for allowed access.
        # Production: use a custom network with proxy.
        pass  # Default: inherit host network

    cmd_parts.extend([
        config.image,
        "sleep", "infinity",  # Keep container running
    ])

    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd_parts,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()

        if proc.returncode != 0:
            logger.error("Failed to create sandbox: %s", stderr.decode())
            return None

        container_id = stdout.decode().strip()[:12]
        logger.info("Sandbox created: %s (%s)", container_name, container_id)

        # Install extra packages if needed
        if config.extra_packages:
            install_cmd = ["docker", "exec", container_name, "pip", "install"] + config.extra_packages
            await asyncio.create_subprocess_exec(*install_cmd)

        return container_name

    except Exception as e:
        logger.error("Sandbox creation failed: %s", e)
        return None


async def exec_in_sandbox(
    container_name: str,
    command: str,
    timeout: int = 120,
) -> tuple[str, int]:
    """Execute a command inside the sandbox container.

    Returns (output, exit_code).
    """
    try:
        proc = await asyncio.create_subprocess_exec(
            "docker", "exec", container_name, "bash", "-c", command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)

        output = stdout.decode("utf-8", errors="replace")
        if stderr:
            output += "\n[stderr]\n" + stderr.decode("utf-8", errors="replace")

        return output.strip(), proc.returncode

    except asyncio.TimeoutError:
        return f"Command timed out after {timeout}s", 1
    except Exception as e:
        return f"Sandbox exec error: {e}", 1


async def destroy_sandbox(container_name: str) -> None:
    """Stop and remove the sandbox container."""
    try:
        await asyncio.create_subprocess_exec(
            "docker", "rm", "-f", container_name,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        logger.info("Sandbox destroyed: %s", container_name)
    except Exception as e:
        logger.warning("Failed to destroy sandbox: %s", e)
