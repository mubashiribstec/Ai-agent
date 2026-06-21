"""Filesystem read / write / list / edit tools."""

from __future__ import annotations

from pathlib import Path

from xplogent.safety.approval import RiskLevel
from xplogent.tools.base import Tool, ToolResult

_MAX_READ = 200_000


class ReadFileTool(Tool):
    name = "read_file"
    description = "Read the contents of a text file."
    parameters = {
        "type": "object",
        "properties": {"path": {"type": "string", "description": "Path to the file."}},
        "required": ["path"],
    }
    risk = RiskLevel.LOW

    async def run(self, path: str) -> ToolResult:
        p = Path(path).expanduser()
        if not p.exists():
            return ToolResult.failure(f"No such file: {path}")
        try:
            text = p.read_text(encoding="utf-8", errors="replace")[:_MAX_READ]
        except Exception as exc:  # noqa: BLE001
            return ToolResult.failure(f"Could not read {path}: {exc}")
        return ToolResult.success(text, path=str(p))


class WriteFileTool(Tool):
    name = "write_file"
    description = "Create or overwrite a text file with the given content."
    parameters = {
        "type": "object",
        "properties": {
            "path": {"type": "string"},
            "content": {"type": "string"},
            "append": {"type": "boolean", "description": "Append instead of overwrite."},
        },
        "required": ["path", "content"],
    }
    risk = RiskLevel.MEDIUM

    async def run(self, path: str, content: str, append: bool = False) -> ToolResult:
        p = Path(path).expanduser()
        try:
            p.parent.mkdir(parents=True, exist_ok=True)
            with p.open("a" if append else "w", encoding="utf-8") as fh:
                fh.write(content)
        except Exception as exc:  # noqa: BLE001
            return ToolResult.failure(f"Could not write {path}: {exc}")
        return ToolResult.success(f"Wrote {len(content)} chars to {p}", path=str(p))


class ListDirTool(Tool):
    name = "list_dir"
    description = "List the entries of a directory."
    parameters = {
        "type": "object",
        "properties": {"path": {"type": "string", "description": "Directory path (default '.')."}},
    }
    risk = RiskLevel.LOW

    async def run(self, path: str = ".") -> ToolResult:
        p = Path(path).expanduser()
        if not p.is_dir():
            return ToolResult.failure(f"Not a directory: {path}")
        entries = []
        for child in sorted(p.iterdir()):
            entries.append(("📁 " if child.is_dir() else "📄 ") + child.name)
        return ToolResult.success("\n".join(entries) or "(empty)", count=len(entries))


class EditFileTool(Tool):
    name = "edit_file"
    description = "Replace the first occurrence of a string in a file with another string."
    parameters = {
        "type": "object",
        "properties": {
            "path": {"type": "string"},
            "old": {"type": "string", "description": "Exact text to find."},
            "new": {"type": "string", "description": "Replacement text."},
        },
        "required": ["path", "old", "new"],
    }
    risk = RiskLevel.MEDIUM

    async def run(self, path: str, old: str, new: str) -> ToolResult:
        p = Path(path).expanduser()
        if not p.exists():
            return ToolResult.failure(f"No such file: {path}")
        text = p.read_text(encoding="utf-8", errors="replace")
        if old not in text:
            return ToolResult.failure("The 'old' text was not found in the file.")
        p.write_text(text.replace(old, new, 1), encoding="utf-8")
        return ToolResult.success(f"Edited {p}")


def filesystem_tools() -> list[Tool]:
    return [ReadFileTool(), WriteFileTool(), ListDirTool(), EditFileTool()]
