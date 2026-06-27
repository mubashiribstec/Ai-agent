"""Agent-curated long-term memory (MEMORY.md).

Gives the model a first-class tool to **deliberately** edit its curated memory —
not just the passive reflection/`compact_memory` path. Edits are applied as an
atomic batch of line-wise operations against a character budget, mirroring
Hermes' batched ``operations`` memory tool: if the result would blow the budget,
the whole batch is rejected so the file never grows unbounded.

MEMORY.md is injected into every turn's system prompt, so curated edits take
effect on the next turn.
"""

from __future__ import annotations

from typing import Any

from xplogent.core.persona import load_memory, save_memory
from xplogent.safety.approval import RiskLevel
from xplogent.tools.base import Tool, ToolResult

_VALID_OPS = {"add", "replace", "remove"}


def _apply_ops(text: str, operations: list[dict]) -> tuple[str, list[str]]:
    """Apply operations to MEMORY.md text. Returns (new_text, change_log)."""
    lines = text.splitlines()
    log: list[str] = []
    for raw in operations:
        if not isinstance(raw, dict):
            raise ValueError("each operation must be an object")
        op = str(raw.get("op", "")).lower().strip()
        if op not in _VALID_OPS:
            raise ValueError(f"unknown op '{op}' (use add/replace/remove)")
        match = str(raw.get("match", "")).strip()
        new_text = str(raw.get("text", "")).strip()

        if op == "add":
            if not new_text:
                raise ValueError("'add' needs 'text'")
            entry = new_text if new_text.startswith(("#", "-", "*")) else f"- {new_text}"
            lines.append(entry)
            log.append(f"added: {new_text[:60]}")
        elif op == "remove":
            if not match:
                raise ValueError("'remove' needs 'match'")
            before = len(lines)
            lines = [ln for ln in lines if match.lower() not in ln.lower()]
            log.append(f"removed {before - len(lines)} line(s) matching '{match[:40]}'")
        else:  # replace
            if not match or not new_text:
                raise ValueError("'replace' needs both 'match' and 'text'")
            hit = False
            for i, ln in enumerate(lines):
                if match.lower() in ln.lower():
                    prefix = "- " if not new_text.startswith(("#", "-", "*")) else ""
                    lines[i] = f"{prefix}{new_text}"
                    hit = True
                    break
            log.append(f"replaced '{match[:40]}'" if hit else f"no line matched '{match[:40]}'")
    return "\n".join(lines).rstrip() + "\n", log


class MemoryTool(Tool):
    name = "memory"
    description = (
        "Curate your durable long-term memory (MEMORY.md). Apply a batch of edits at "
        "once: add new durable facts/preferences, replace an outdated entry, or remove "
        "something. Use this to deliberately remember things across sessions. Keep it "
        "concise — edits over the character budget are rejected so you stay tidy."
    )
    parameters = {
        "type": "object",
        "properties": {
            "operations": {
                "type": "array",
                "description": "Batch of edits applied atomically.",
                "items": {
                    "type": "object",
                    "properties": {
                        "op": {"type": "string", "enum": ["add", "replace", "remove"]},
                        "text": {"type": "string", "description": "New content (for add/replace)."},
                        "match": {"type": "string",
                                  "description": "Substring identifying the line (for replace/remove)."},
                    },
                    "required": ["op"],
                },
            }
        },
        "required": ["operations"],
    }
    risk = RiskLevel.LOW

    def __init__(self, max_chars: int | None = None) -> None:
        self._max_chars = max_chars

    def _budget(self) -> int:
        if self._max_chars is not None:
            return self._max_chars
        from xplogent.core.config import load_config
        return int(load_config().memory.get("md_max_chars", 6000))

    async def run(self, operations: list[dict] | None = None, **_: Any) -> ToolResult:
        if not operations:
            return ToolResult.failure("provide a non-empty 'operations' array")
        current = load_memory()
        try:
            updated, log = _apply_ops(current, list(operations))
        except ValueError as exc:
            return ToolResult.failure(str(exc))

        budget = self._budget()
        if len(updated) > budget:
            over = len(updated) - budget
            return ToolResult.failure(
                f"batch rejected: MEMORY.md would be {len(updated)} chars, "
                f"{over} over the {budget} budget. Remove something first."
            )
        save_memory(updated)
        return ToolResult.success(
            "MEMORY.md updated (" + "; ".join(log) + f"). Now {len(updated)} chars.",
            chars=len(updated),
        )


def memory_tools() -> list[Tool]:
    return [MemoryTool()]
