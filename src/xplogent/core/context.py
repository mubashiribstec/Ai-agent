"""Prompt construction and the short-term conversation window."""

from __future__ import annotations

from xplogent.providers.base import Message, Role

DEFAULT_SYSTEM_PROMPT = """You are Xplogent, a capable, self-improving personal AI agent \
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
    skills: list[tuple],  # (name, description, body[, trigger, tools])
    persona: str = "",
    memory_md: str = "",
    graph_block: str = "",
) -> str:
    parts: list[str] = []
    if persona.strip():
        parts.append(persona.strip())
    parts.append(base or DEFAULT_SYSTEM_PROMPT)
    if memory_md.strip():
        parts.append("## Curated memory (MEMORY.md)\n" + memory_md.strip())
    if facts:
        parts.append("## What you remember\n" + "\n".join(f"- {f}" for f in facts))
    if graph_block.strip():
        parts.append(graph_block.strip())
    if skills:
        skill_block = ["## Learned skills (apply when relevant)"]
        for s in skills:
            name, desc, body = s[0], s[1], s[2]
            trigger = s[3] if len(s) > 3 else ""
            tools = s[4] if len(s) > 4 else []
            head = f"### {name}\n{desc}"
            if trigger:
                head += f"\n_When:_ {trigger}"
            if tools:
                head += f"\n_Uses tools:_ {', '.join(tools)}"
            skill_block.append(f"{head}\n{body}")
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
