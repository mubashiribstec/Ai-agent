"""Goal decomposition: turn a high-level goal into a dependency graph of subtasks.

Uses the LLM to emit structured JSON. Falls back to a single operator task if the
model is unavailable or returns nothing usable, so orchestration always proceeds.
"""

from __future__ import annotations

import json
import re

from xplogent.core.taskboard import Task
from xplogent.providers.base import Message, Provider, Role

_PROMPT = """You are the planner of a multi-agent AI system. Break the user's GOAL \
into concrete subtasks that specialized agents execute in parallel where possible.

Available roles: {roles}.
Team size hint: up to {count} agents may run at once.

Return ONLY a JSON array; each item:
{{
  "id": "t1",
  "title": "short title",
  "description": "what this agent must do, self-contained and specific",
  "role": "one of the available roles",
  "deps": ["ids of subtasks that must finish first"]
}}
Rules:
- If the GOAL implies MULTIPLE agents or approaches ("all agents", "each", \
"different methods/sites/sources", "compare ways"), create EXACTLY {count} \
parallel subtasks (empty deps), each using a DISTINCT method — name the specific \
method in the description (e.g. different sites/commands/libraries). Then add ONE \
final synthesis task that depends on them.
- Otherwise use as few subtasks as the goal needs; prefer parallelism.
- Put synthesis/aggregation tasks last, depending on the others.
- Do not wrap the JSON in markdown fences."""


def _extract_json_array(text: str) -> list:
    text = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.MULTILINE).strip()
    match = re.search(r"\[.*\]", text, re.DOTALL)
    if not match:
        return []
    try:
        data = json.loads(match.group(0))
        return data if isinstance(data, list) else []
    except json.JSONDecodeError:
        return []


class Planner:
    def __init__(self, provider: Provider) -> None:
        self.provider = provider

    async def decompose(self, goal: str, roles: list[str], count: int = 3) -> list[Task]:
        messages = [
            Message(role=Role.SYSTEM,
                    content=_PROMPT.format(roles=", ".join(roles), count=count)),
            Message(role=Role.USER, content=f"GOAL:\n{goal}"),
        ]
        try:
            reply = await self.provider.complete(messages, temperature=0.2)
            items = _extract_json_array(reply.content)
        except Exception:  # noqa: BLE001 - planning must never hard-fail
            items = []

        tasks: list[Task] = []
        valid_roles = set(roles)
        for i, item in enumerate(items):
            if not isinstance(item, dict) or not item.get("description"):
                continue
            tid = str(item.get("id") or f"t{i+1}")
            role = item.get("role") if item.get("role") in valid_roles else "operator"
            tasks.append(Task(
                id=tid,
                title=str(item.get("title") or tid),
                description=str(item["description"]),
                role=role,
                deps=[str(d) for d in item.get("deps", []) if isinstance(d, (str, int))],
            ))

        if not tasks:
            # Fallback: one operator task that just does the whole goal.
            tasks = [Task(id="t1", title="complete the goal", description=goal, role="operator")]
        return tasks
