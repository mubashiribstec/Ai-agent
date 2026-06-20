"""Prompt construction and the short-term conversation window."""

from __future__ import annotations

from nexus.providers.base import Message, Role

DEFAULT_SYSTEM_PROMPT = """You are Nexus, a capable, self-improving personal AI agent \
running on the user's own machine. You can control the computer through tools: run \
shell commands, read/write files, execute Python, search and fetch the web, and (when a \
display is available) control the mouse, keyboard, screen, and a browser.

Operate as an autonomous agent:
- Think step by step. Break tasks into concrete actions.
- Prefer using tools to gather real information instead of guessing.
- After a tool returns, read its output and decide the next step.
- When the task is complete, give a clear final answer WITHOUT calling more tools.
- Be careful with destructive actions; the user must approve risky operations.

You have persistent memory across sessions. Relevant facts and learned skills are \
injected below when available — use them."""


def _approx_tokens(text: str) -> int:
    return max(1, len(text) // 4)


def build_system_prompt(
    base: str | None,
    facts: list[str],
    skills: list[tuple[str, str, str]],  # (name, description, body)
) -> str:
    parts = [base or DEFAULT_SYSTEM_PROMPT]
    if facts:
        parts.append("## What you remember\n" + "\n".join(f"- {f}" for f in facts))
    if skills:
        skill_block = ["## Learned skills (apply when relevant)"]
        for name, desc, body in skills:
            skill_block.append(f"### {name}\n{desc}\n{body}")
        parts.append("\n".join(skill_block))
    return "\n\n".join(parts)


class ShortTermMemory:
    """The live conversation window with a soft token budget.

    When the running message history exceeds the budget, the oldest exchanges are
    folded into a compact summary placeholder so the context stays bounded.
    """

    def __init__(self, max_tokens: int = 6000) -> None:
        self.max_tokens = max_tokens
        self.messages: list[Message] = []
        self._summary: str = ""

    def add(self, message: Message) -> None:
        self.messages.append(message)

    def _total_tokens(self) -> int:
        return sum(_approx_tokens(m.content) for m in self.messages)

    def trim(self) -> None:
        """Fold oldest messages into a summary placeholder when over budget."""
        while self._total_tokens() > self.max_tokens and len(self.messages) > 4:
            old = self.messages.pop(0)
            snippet = old.content[:200].replace("\n", " ")
            self._summary += f"\n[{old.role.value}] {snippet}"

    def render(self) -> list[Message]:
        msgs: list[Message] = []
        if self._summary:
            msgs.append(
                Message(role=Role.SYSTEM, content="Earlier conversation summary:" + self._summary)
            )
        msgs.extend(self.messages)
        return msgs
