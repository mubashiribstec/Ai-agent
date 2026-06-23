"""Anthropic provider (Messages API).

Translates the normalized OpenAI-style messages/tools into Anthropic's native
format and back. Uses httpx so the SDK is optional.
"""

from __future__ import annotations

import json
import os
import uuid
from collections.abc import AsyncIterator
from typing import Any

import httpx

from xplogent.providers.base import (
    EFFORT_BUDGET,
    Message,
    Provider,
    Role,
    StreamEvent,
    StreamKind,
    ToolCall,
    ToolSpec,
    extract_gen_params,
    image_data_uri,
)

ANTHROPIC_VERSION = "2023-06-01"


class AnthropicProvider(Provider):
    name = "anthropic"

    def __init__(
        self,
        model: str,
        api_key: str | None = None,
        base_url: str | None = None,
        max_tokens: int = 4096,
        **kwargs: Any,
    ) -> None:
        super().__init__(model, **kwargs)
        self.base_url = (base_url or "https://api.anthropic.com/v1").rstrip("/")
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")
        self.max_tokens = max_tokens
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            headers={
                "x-api-key": self.api_key,
                "anthropic-version": ANTHROPIC_VERSION,
                "Content-Type": "application/json",
            },
            timeout=httpx.Timeout(300.0),
        )

    def _convert(self, messages: list[Message]) -> tuple[str, list[dict[str, Any]]]:
        """Return (system_prompt, anthropic_messages)."""
        system_parts: list[str] = []
        out: list[dict[str, Any]] = []
        for m in messages:
            if m.role == Role.SYSTEM:
                system_parts.append(m.content)
            elif m.role == Role.TOOL:
                out.append(
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "tool_result",
                                "tool_use_id": m.tool_call_id or "",
                                "content": m.content,
                            }
                        ],
                    }
                )
            elif m.role == Role.ASSISTANT:
                content: list[dict[str, Any]] = []
                if m.content:
                    content.append({"type": "text", "text": m.content})
                for tc in m.tool_calls:
                    content.append(
                        {"type": "tool_use", "id": tc.id, "name": tc.name, "input": tc.arguments}
                    )
                out.append({"role": "assistant", "content": content or ""})
            elif m.images:  # USER with vision input
                parts: list[dict[str, Any]] = []
                if m.content:
                    parts.append({"type": "text", "text": m.content})
                for img in m.images:
                    media, b64 = image_data_uri(img)
                    parts.append({"type": "image", "source": {
                        "type": "base64", "media_type": media, "data": b64}})
                out.append({"role": "user", "content": parts})
            else:  # USER
                out.append({"role": "user", "content": m.content})
        return "\n\n".join(system_parts), out

    async def stream(
        self,
        messages: list[Message],
        tools: list[ToolSpec] | None = None,
        *,
        temperature: float = 0.7,
        **kwargs: Any,
    ) -> AsyncIterator[StreamEvent]:
        system, conv = self._convert(messages)
        gen = extract_gen_params(kwargs)
        max_tokens = int(gen["max_tokens"] or self.max_tokens)
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": conv,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": True,
        }
        # Extended thinking: enabled by the thinking toggle or medium/high effort.
        if gen["thinking"] or gen["effort"] in ("medium", "high"):
            budget = EFFORT_BUDGET.get(gen["effort"] or "medium", 4096)
            payload["max_tokens"] = max(max_tokens, budget + 1024)
            payload["temperature"] = 1  # required when thinking is enabled
            payload["thinking"] = {"type": "enabled", "budget_tokens": budget}
        if system:
            payload["system"] = system
        if tools:
            payload["tools"] = [
                {"name": t.name, "description": t.description, "input_schema": t.parameters}
                for t in tools
            ]

        content_parts: list[str] = []
        tool_calls: list[ToolCall] = []
        cur_tool: dict[str, Any] | None = None
        cur_json = ""

        async with self._client.stream("POST", "/messages", json=payload) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                line = line.strip()
                if not line or not line.startswith("data:"):
                    continue
                event = json.loads(line[len("data:"):].strip())
                etype = event.get("type")
                if etype == "content_block_start":
                    block = event.get("content_block", {})
                    if block.get("type") == "tool_use":
                        cur_tool = {"id": block.get("id") or f"call_{uuid.uuid4().hex[:8]}",
                                    "name": block.get("name", "")}
                        cur_json = ""
                elif etype == "content_block_delta":
                    delta = event.get("delta", {})
                    if delta.get("type") == "text_delta":
                        text = delta.get("text", "")
                        content_parts.append(text)
                        yield StreamEvent(kind=StreamKind.TOKEN, text=text)
                    elif delta.get("type") == "input_json_delta":
                        cur_json += delta.get("partial_json", "")
                elif etype == "content_block_stop" and cur_tool is not None:
                    try:
                        args = json.loads(cur_json) if cur_json else {}
                    except json.JSONDecodeError:
                        args = {}
                    tool_calls.append(ToolCall(id=cur_tool["id"], name=cur_tool["name"], arguments=args))
                    cur_tool = None

        final = Message(role=Role.ASSISTANT, content="".join(content_parts), tool_calls=tool_calls)
        yield StreamEvent(kind=StreamKind.DONE, message=final)

    async def aclose(self) -> None:
        await self._client.aclose()
