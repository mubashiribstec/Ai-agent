"""OpenAI-compatible provider.

Works with the OpenAI Chat Completions API and any compatible endpoint
(OpenRouter, local servers, etc.). Uses httpx directly so the official SDK is
optional. Supports streaming, tool calling, and embeddings.
"""

from __future__ import annotations

import json
import os
from collections.abc import AsyncIterator
from typing import Any

import httpx

from nexus.providers.base import (
    Message,
    Provider,
    Role,
    StreamEvent,
    StreamKind,
    ToolCall,
    ToolSpec,
)


class OpenAIProvider(Provider):
    name = "openai"
    default_base_url = "https://api.openai.com/v1"
    api_key_env = "OPENAI_API_KEY"

    def __init__(
        self,
        model: str,
        api_key: str | None = None,
        base_url: str | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(model, **kwargs)
        self.base_url = (base_url or self.default_base_url).rstrip("/")
        self.api_key = api_key or os.environ.get(self.api_key_env, "")
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        self._extra_headers(headers)
        self._client = httpx.AsyncClient(
            base_url=self.base_url, headers=headers, timeout=httpx.Timeout(300.0)
        )

    def _extra_headers(self, headers: dict[str, str]) -> None:
        """Hook for subclasses (e.g. OpenRouter) to add headers."""

    async def stream(
        self,
        messages: list[Message],
        tools: list[ToolSpec] | None = None,
        *,
        temperature: float = 0.7,
        **kwargs: Any,
    ) -> AsyncIterator[StreamEvent]:
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": [m.to_openai() for m in messages],
            "stream": True,
            "temperature": temperature,
        }
        if tools:
            payload["tools"] = [t.to_openai() for t in tools]

        content_parts: list[str] = []
        # tool call deltas accumulate by index
        tc_acc: dict[int, dict[str, Any]] = {}

        async with self._client.stream("POST", "/chat/completions", json=payload) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                line = line.strip()
                if not line or not line.startswith("data:"):
                    continue
                data = line[len("data:"):].strip()
                if data == "[DONE]":
                    break
                chunk = json.loads(data)
                choices = chunk.get("choices") or []
                if not choices:
                    continue
                delta = choices[0].get("delta") or {}
                if text := delta.get("content"):
                    content_parts.append(text)
                    yield StreamEvent(kind=StreamKind.TOKEN, text=text)
                for tc in delta.get("tool_calls", []) or []:
                    idx = tc.get("index", 0)
                    slot = tc_acc.setdefault(idx, {"id": "", "name": "", "args": ""})
                    if tc.get("id"):
                        slot["id"] = tc["id"]
                    fn = tc.get("function") or {}
                    if fn.get("name"):
                        slot["name"] = fn["name"]
                    if fn.get("arguments"):
                        slot["args"] += fn["arguments"]

        tool_calls = []
        for slot in tc_acc.values():
            try:
                args = json.loads(slot["args"]) if slot["args"] else {}
            except json.JSONDecodeError:
                args = {}
            tool_calls.append(ToolCall(id=slot["id"] or "call_0", name=slot["name"], arguments=args))

        final = Message(role=Role.ASSISTANT, content="".join(content_parts), tool_calls=tool_calls)
        yield StreamEvent(kind=StreamKind.DONE, message=final)

    async def embed(self, texts: list[str]) -> list[list[float]]:
        resp = await self._client.post(
            "/embeddings", json={"model": self.model, "input": texts}
        )
        resp.raise_for_status()
        return [item["embedding"] for item in resp.json()["data"]]

    async def aclose(self) -> None:
        await self._client.aclose()
