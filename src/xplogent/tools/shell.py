"""Shell command execution."""

from __future__ import annotations

import asyncio
from typing import Any

from xplogent.safety.approval import RiskLevel
from xplogent.tools.base import Tool, ToolResult

_DESTRUCTIVE = (
    # POSIX
    "rm ", "rmdir", "mv ", "dd ", "mkfs", "shutdown", "reboot", "kill", ">", "sudo",
    # Windows
    "del ", "erase ", "format ", "rd ", "rmdir ", "diskpart", "rundll32", "reg delete",
)


class ShellTool(Tool):
    name = "shell"
    description = (
        "Run a shell command on the local machine and return its stdout/stderr. "
        "Use for system tasks, running programs, git, package managers, etc."
    )
    parameters = {
        "type": "object",
        "properties": {
            "command": {"type": "string", "description": "The shell command to execute."},
            "timeout": {"type": "integer", "description": "Timeout in seconds (default 120)."},
            "cwd": {"type": "string", "description": "Working directory (optional)."},
        },
        "required": ["command"],
    }
    risk = RiskLevel.HIGH

    def risk_for(self, arguments: dict[str, Any]) -> RiskLevel:
        cmd = str(arguments.get("command", "")).lower()
        if any(tok in cmd for tok in _DESTRUCTIVE):
            return RiskLevel.HIGH
        # Read-only-ish commands are lower risk.
        first = cmd.strip().split(" ", 1)[0] if cmd.strip() else ""
        if first in {
            # POSIX read-only-ish
            "ls", "cat", "pwd", "echo", "whoami", "date", "df", "ps", "grep", "find", "which",
            # Windows read-only-ish
            "dir", "type", "where", "cd", "hostname", "ver", "tasklist",
        }:
            return RiskLevel.LOW
        return RiskLevel.MEDIUM

    async def run(self, command: str, timeout: int = 120, cwd: str | None = None) -> ToolResult:
        try:
            proc = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd,
            )
            try:
                stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
            except TimeoutError:
                proc.kill()
                return ToolResult.failure(f"Command timed out after {timeout}s")
        except Exception as exc:  # noqa: BLE001
            return ToolResult.failure(f"Failed to run command: {exc}")

        out = stdout.decode("utf-8", "replace")
        err = stderr.decode("utf-8", "replace")
        code = proc.returncode or 0
        body = out
        if err:
            body += ("\n[stderr]\n" + err)
        body = f"(exit {code})\n{body}".strip()
        return ToolResult(ok=code == 0, output=body, error="" if code == 0 else body,
                          data={"exit_code": code})
