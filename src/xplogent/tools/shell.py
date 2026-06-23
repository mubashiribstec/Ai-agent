"""Shell command execution (via the configured terminal backend)."""

from __future__ import annotations

from typing import Any

from xplogent.core.backends import TerminalBackend, resolve_backend
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

    def __init__(self, backend: TerminalBackend | None = None) -> None:
        self._backend = backend

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
        backend = self._backend or resolve_backend()
        code, out, err = await backend.run(command, timeout=timeout, cwd=cwd)
        body = out
        if err:
            body += ("\n[stderr]\n" + err)
        body = f"(exit {code})\n{body}".strip()
        return ToolResult(ok=code == 0, output=body, error="" if code == 0 else body,
                          data={"exit_code": code, "backend": backend.name})
