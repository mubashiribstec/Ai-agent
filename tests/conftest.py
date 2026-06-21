"""Shared test fixtures and fakes."""

from __future__ import annotations

from collections.abc import AsyncIterator

from xplogent.providers.base import (
    Message,
    Provider,
    Role,
    StreamEvent,
    StreamKind,
    ToolSpec,
)


class ScriptedProvider(Provider):
    """A provider that replays a predetermined list of assistant messages."""

    name = "scripted"

    def __init__(self, replies: list[Message], embeddings: dict[str, list[float]] | None = None):
        super().__init__(model="scripted")
        self._replies = list(replies)
        self._embeddings = embeddings or {}

    async def stream(  # type: ignore[override]
        self, messages: list[Message], tools: list[ToolSpec] | None = None, **kwargs
    ) -> AsyncIterator[StreamEvent]:
        reply = self._replies.pop(0) if self._replies else Message(role=Role.ASSISTANT, content="done")
        if reply.content:
            yield StreamEvent(kind=StreamKind.TOKEN, text=reply.content)
        yield StreamEvent(kind=StreamKind.DONE, message=reply)

    async def embed(self, texts: list[str]) -> list[list[float]]:
        out = []
        for t in texts:
            # deterministic tiny embedding based on word overlap buckets
            vec = [0.0] * 8
            for _i, ch in enumerate(t.lower()):
                vec[ord(ch) % 8] += 1.0
            out.append(vec)
        return out
