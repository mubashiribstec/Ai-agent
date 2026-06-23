"""Collaboration tools — how agents tell each other what they're doing.

Each tool is bound to the calling agent's identity and the shared
:class:`~xplogent.core.messaging.MessageBus`. They are registered only in
multi-agent runs.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from xplogent.core.messaging import MessageBus
from xplogent.safety.approval import RiskLevel
from xplogent.tools.base import Tool, ToolResult

# Spawns a sub-agent: (task, role, depth) -> answer.
DelegateCallback = Callable[[str, str, int], Awaitable[str]]


class BroadcastTool(Tool):
    name = "broadcast"
    description = (
        "Announce what you are doing (or what you found) to all other agents on "
        "the team. Use this to keep everyone in sync."
    )
    parameters = {
        "type": "object",
        "properties": {"content": {"type": "string", "description": "Status update to share."}},
        "required": ["content"],
    }
    risk = RiskLevel.LOW

    def __init__(self, bus: MessageBus, agent_id: str, agent_name: str) -> None:
        self._bus, self._id, self._name = bus, agent_id, agent_name

    async def run(self, content: str) -> ToolResult:
        await self._bus.broadcast(self._id, self._name, content)
        return ToolResult.success("broadcast sent to the team")


class SendMessageTool(Tool):
    name = "send_message"
    description = "Send a direct message to one specific agent (by name)."
    parameters = {
        "type": "object",
        "properties": {
            "to": {"type": "string", "description": "Recipient agent name."},
            "content": {"type": "string"},
        },
        "required": ["to", "content"],
    }
    risk = RiskLevel.LOW

    def __init__(self, bus: MessageBus, agent_id: str, agent_name: str) -> None:
        self._bus, self._id, self._name = bus, agent_id, agent_name

    async def run(self, to: str, content: str) -> ToolResult:
        result = await self._bus.send(self._id, self._name, to, content)
        return ToolResult.success(result)


class ReadInboxTool(Tool):
    name = "read_inbox"
    description = "Read and clear messages other agents have sent you since you last checked."
    parameters = {"type": "object", "properties": {}}
    risk = RiskLevel.LOW

    def __init__(self, bus: MessageBus, agent_id: str, agent_name: str) -> None:
        self._bus, self._id, self._name = bus, agent_id, agent_name

    async def run(self) -> ToolResult:
        msgs = self._bus.read_inbox(self._id)
        if not msgs:
            return ToolResult.success("(no new messages)")
        lines = [
            f"[{m.sender_name}{'' if m.recipient is None else ' →you'}]: {m.content}"
            for m in msgs
        ]
        return ToolResult.success("\n".join(lines))


class ListAgentsTool(Tool):
    name = "list_agents"
    description = "List the other agents currently on the team and their roles."
    parameters = {"type": "object", "properties": {}}
    risk = RiskLevel.LOW

    def __init__(self, bus: MessageBus, agent_id: str, agent_name: str) -> None:
        self._bus, self._id, self._name = bus, agent_id, agent_name

    async def run(self) -> ToolResult:
        others = [a for a in self._bus.agents() if a["id"] != self._id]
        if not others:
            return ToolResult.success("(you are the only agent)")
        return ToolResult.success("\n".join(f"{a['name']} ({a['role']})" for a in others))


class DelegateTool(Tool):
    name = "delegate_task"
    description = (
        "Spin up a focused helper agent to handle a self-contained subtask and "
        "return its result. Use this to parallelize independent work or hand off a "
        "specialized job (give it a clear, complete instruction)."
    )
    parameters = {
        "type": "object",
        "properties": {
            "task": {"type": "string", "description": "The complete instruction for the helper."},
            "role": {"type": "string",
                     "description": "Role profile for the helper (default 'operator')."},
        },
        "required": ["task"],
    }
    risk = RiskLevel.MEDIUM

    def __init__(self, delegate: DelegateCallback, depth: int, max_depth: int) -> None:
        self._delegate, self._depth, self._max = delegate, depth, max_depth

    async def run(self, task: str, role: str = "operator") -> ToolResult:
        if self._depth >= self._max:
            return ToolResult.failure(
                f"delegation depth limit reached ({self._max}); do this work yourself."
            )
        answer = await self._delegate(task, role, self._depth + 1)
        return ToolResult.success(answer or "(helper returned no answer)")


def collab_tools(
    bus: MessageBus,
    agent_id: str,
    agent_name: str,
    *,
    delegate: DelegateCallback | None = None,
    depth: int = 0,
    max_depth: int = 2,
) -> list[Tool]:
    tools: list[Tool] = [
        BroadcastTool(bus, agent_id, agent_name),
        SendMessageTool(bus, agent_id, agent_name),
        ReadInboxTool(bus, agent_id, agent_name),
        ListAgentsTool(bus, agent_id, agent_name),
    ]
    # Only offer delegation while there's still depth budget left.
    if delegate is not None and depth < max_depth:
        tools.append(DelegateTool(delegate, depth, max_depth))
    return tools
