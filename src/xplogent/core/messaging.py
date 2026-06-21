"""Inter-agent communication: a broadcast board + direct inboxes.

Agents announce what they're doing (broadcast) and address specific teammates
(direct). Every message is mirrored to the :class:`EventBus` (as ``AGENT_MESSAGE``)
for live monitoring and persisted to the store for the run trace.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from xplogent.core.events import Event, EventBus, EventType


@dataclass
class AgentMessage:
    sender_id: str
    sender_name: str
    recipient: str | None  # None == broadcast
    content: str
    ts: float = field(default_factory=time.time)


@dataclass
class _AgentRef:
    agent_id: str
    name: str
    role: str


class MessageBus:
    def __init__(self, bus: EventBus, store=None, run_id: str | None = None) -> None:
        self.bus = bus
        self.store = store
        self.run_id = run_id
        self._agents: dict[str, _AgentRef] = {}
        self._inboxes: dict[str, list[AgentMessage]] = {}
        self.history: list[AgentMessage] = []

    def register_agent(self, agent_id: str, name: str, role: str) -> None:
        self._agents[agent_id] = _AgentRef(agent_id, name, role)
        self._inboxes.setdefault(agent_id, [])

    def agents(self) -> list[dict[str, str]]:
        return [{"id": a.agent_id, "name": a.name, "role": a.role} for a in self._agents.values()]

    def _resolve(self, name_or_id: str) -> str | None:
        if name_or_id in self._agents:
            return name_or_id
        for ref in self._agents.values():
            if ref.name == name_or_id:
                return ref.agent_id
        return None

    async def _record(self, msg: AgentMessage) -> None:
        self.history.append(msg)
        if self.store and self.run_id:
            self.store.add_agent_message(self.run_id, msg.sender_name, msg.recipient, msg.content)
        await self.bus.publish(Event(
            type=EventType.AGENT_MESSAGE,
            data={
                "run_id": self.run_id, "agent_id": msg.sender_id,
                "sender": msg.sender_name, "recipient": msg.recipient, "content": msg.content,
            },
        ))

    async def broadcast(self, sender_id: str, sender_name: str, content: str) -> None:
        msg = AgentMessage(sender_id, sender_name, None, content)
        for aid, inbox in self._inboxes.items():
            if aid != sender_id:
                inbox.append(msg)
        await self._record(msg)

    async def send(self, sender_id: str, sender_name: str, to: str, content: str) -> str:
        target = self._resolve(to)
        if target is None:
            return f"no agent named '{to}'"
        msg = AgentMessage(sender_id, sender_name, to, content)
        self._inboxes.setdefault(target, []).append(msg)
        await self._record(msg)
        return f"delivered to {to}"

    def read_inbox(self, agent_id: str, clear: bool = True) -> list[AgentMessage]:
        msgs = list(self._inboxes.get(agent_id, []))
        if clear:
            self._inboxes[agent_id] = []
        return msgs
