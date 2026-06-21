"""Collaboration tools — how agents tell each other what they're doing.

Each tool is bound to the calling agent's identity and the shared
:class:`~xplogent.core.messaging.MessageBus`. They are registered only in
multi-agent runs.
"""

from __future__ import annotations

from xplogent.core.messaging import MessageBus
from xplogent.safety.approval import RiskLevel
from xplogent.tools.base import Tool, ToolResult


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


def collab_tools(bus: MessageBus, agent_id: str, agent_name: str) -> list[Tool]:
    return [
        BroadcastTool(bus, agent_id, agent_name),
        SendMessageTool(bus, agent_id, agent_name),
        ReadInboxTool(bus, agent_id, agent_name),
        ListAgentsTool(bus, agent_id, agent_name),
    ]
