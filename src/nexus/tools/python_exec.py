"""Execute Python code in a subprocess and capture its output."""

from __future__ import annotations

import asyncio
import sys

from nexus.safety.approval import RiskLevel
from nexus.tools.base import Tool, ToolResult


class PythonExecTool(Tool):
    name = "python_exec"
    description = (
        "Execute a snippet of Python code in a fresh subprocess and return whatever "
        "it prints to stdout/stderr. Good for calculations, data work, and quick scripts."
    )
    parameters = {
        "type": "object",
        "properties": {
            "code": {"type": "string", "description": "Python source to run."},
            "timeout": {"type": "integer", "description": "Timeout in seconds (default 60)."},
        },
        "required": ["code"],
    }
    risk = RiskLevel.HIGH

    async def run(self, code: str, timeout: int = 60) -> ToolResult:
        try:
            proc = await asyncio.create_subprocess_exec(
                sys.executable, "-c", code,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            try:
                stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
            except TimeoutError:
                proc.kill()
                return ToolResult.failure(f"Execution timed out after {timeout}s")
        except Exception as exc:  # noqa: BLE001
            return ToolResult.failure(f"Failed to execute: {exc}")

        out = stdout.decode("utf-8", "replace")
        err = stderr.decode("utf-8", "replace")
        body = out + (("\n[stderr]\n" + err) if err else "")
        code_ok = (proc.returncode or 0) == 0
        return ToolResult(ok=code_ok, output=body.strip(),
                          error="" if code_ok else err.strip() or "non-zero exit")
