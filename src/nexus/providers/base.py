"""Provider abstraction.

Every LLM provider — local Ollama, OpenAI, Anthropic, OpenRouter — implements
the same small interface so the agent loop is provider-agnostic. Messages and
tool calls are normalized to an OpenAI-style shape internally; each provider
translates to/from its native wire format.
"""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class Role(StrEnum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


@dataclass
class ToolCall:
    """A model request to invoke a tool."""

    id: str
    name: str
    arguments: dict[str, Any] = field(default_factory=dict)


@dataclass
class Message:
    """A single conversation message in normalized form."""

    role: Role
    content: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
    tool_call_id: str | None = None  # set on TOOL messages
    name: str | None = None          # tool name on TOOL messages

    def to_openai(self) -> dict[str, Any]:
        msg: dict[str, Any] = {"role": self.role.value}
        if self.role == Role.TOOL:
            msg["content"] = self.content
            msg["tool_call_id"] = self.tool_call_id or ""
            return msg
        msg["content"] = self.content or ""
        if self.tool_calls:
            msg["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {"name": tc.name, "arguments": json.dumps(tc.arguments)},
                }
                for tc in self.tool_calls
            ]
        return msg


@dataclass
class ToolSpec:
    """A tool definition exposed to the model for function calling."""

    name: str
    description: str
    parameters: dict[str, Any]  # JSON schema

    def to_openai(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


class StreamKind(StrEnum):
    TOKEN = "token"      # a content delta
    DONE = "done"        # final assembled Message available


@dataclass
class StreamEvent:
    kind: StreamKind
    text: str = ""
    message: Message | None = None


class Provider(ABC):
    """Abstract LLM provider."""

    name: str = "base"

    def __init__(self, model: str, **kwargs: Any) -> None:
        self.model = model
        self.options = kwargs

    @abstractmethod
    def stream(
        self,
        messages: list[Message],
        tools: list[ToolSpec] | None = None,
        *,
        temperature: float = 0.7,
        **kwargs: Any,
    ) -> AsyncIterator[StreamEvent]:
        """Stream a completion, yielding TOKEN events then a final DONE event."""
        raise NotImplementedError

    async def complete(
        self,
        messages: list[Message],
        tools: list[ToolSpec] | None = None,
        **kwargs: Any,
    ) -> Message:
        """Non-streaming convenience wrapper that returns the final message."""
        final: Message | None = None
        async for event in self.stream(messages, tools, **kwargs):
            if event.kind == StreamKind.DONE:
                final = event.message
        return final or Message(role=Role.ASSISTANT, content="")

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Return embeddings for ``texts``. Override in providers that support it."""
        raise NotImplementedError(f"{self.name} does not support embeddings")

    async def aclose(self) -> None:  # pragma: no cover - cleanup hook
        return None
