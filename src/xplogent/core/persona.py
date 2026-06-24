"""SOUL.md persona + MEMORY.md curated memory (OpenClaw's file-first identity).

SOUL.md defines *who the agent is* (persona, instructions, boundaries, values) and
MEMORY.md is a compact, curated long-term memory. Both live in the install data dir
so they travel with the install, are version-friendly, and get injected into every
session's system prompt. ``compact_memory`` periodically distills recent history +
facts into MEMORY.md via the reflection model.
"""

from __future__ import annotations

from pathlib import Path

from xplogent.core.config import data_dir
from xplogent.core.logging import get_logger

_log = get_logger("persona")

DEFAULT_SOUL = """# SOUL

You are **Xplogent**, the user's personal AI agent.

## Persona
- Capable, direct, and resourceful. You get things done on the user's own machine.
- Warm but concise. No filler, no flattery.

## Instructions
- Prefer doing over describing: use tools to gather real information and act.
- Explain briefly what you did and why; show results, not promises.
- When unsure, ask one sharp question instead of guessing.

## Boundaries
- Never take destructive or irreversible actions without explicit approval.
- Respect the user's privacy; keep their data on their machine.

## Values
- Usefulness, honesty, and the user's time and trust above all.

> Edit this file to shape how your agent thinks and behaves.
"""

DEFAULT_MEMORY = """# MEMORY

_Curated long-term memory. The agent distills durable facts, preferences, and
standing decisions here. You can edit it directly._
"""


def soul_path() -> Path:
    return data_dir() / "SOUL.md"


def memory_path() -> Path:
    return data_dir() / "MEMORY.md"


def _read_or_seed(path: Path, default: str) -> str:
    if not path.exists():
        try:
            path.write_text(default, encoding="utf-8")
        except OSError:
            return default
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return default


def load_soul() -> str:
    return _read_or_seed(soul_path(), DEFAULT_SOUL)


def load_memory() -> str:
    return _read_or_seed(memory_path(), DEFAULT_MEMORY)


def save_soul(text: str) -> None:
    soul_path().write_text(text, encoding="utf-8")


def save_memory(text: str) -> None:
    memory_path().write_text(text, encoding="utf-8")


_COMPACT_PROMPT = """You maintain an AI agent's curated long-term memory file (MEMORY.md).
Given the CURRENT memory, recently learned FACTS, and recent CONVERSATION snippets,
produce an updated MEMORY.md: a compact, well-organized markdown note capturing only
durable, reusable knowledge — the user's preferences, standing decisions, important
context, and stable facts. Merge and de-duplicate; drop transient chatter. Keep it
under ~400 words. Return ONLY the markdown for the new MEMORY.md (no fences)."""


async def compact_memory(store, provider) -> str:
    """Distill recent history + facts into MEMORY.md; returns the new content."""
    from xplogent.providers.base import Message, Role

    facts = [f.content for f in store.all_facts()][-50:]
    recent: list[str] = []
    for s in store.list_sessions(limit=5):
        for m in store.session_messages(s["id"])[-12:]:
            recent.append(f"[{m['role']}] {m['content'][:200]}")
    current = load_memory()
    user = (f"CURRENT MEMORY.md:\n{current}\n\nFACTS:\n- "
            + "\n- ".join(facts) + "\n\nRECENT CONVERSATION:\n" + "\n".join(recent[-60:]))
    try:
        reply = await provider.complete(
            [Message(role=Role.SYSTEM, content=_COMPACT_PROMPT),
             Message(role=Role.USER, content=user[:14000])], temperature=0.2)
    except Exception as exc:  # noqa: BLE001 - compaction must never break anything
        _log.warning("memory compaction failed: %s", exc)
        return current
    text = (reply.content or "").strip()
    if text:
        save_memory(text)
    return text or current
