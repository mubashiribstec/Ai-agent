"""Vision input: multimodal message encoding + the analyze_image tool (offline)."""

from __future__ import annotations

import pytest

from tests.conftest import ScriptedProvider
from xplogent.providers.anthropic import AnthropicProvider
from xplogent.providers.base import Message, Role


def _png(tmp_path):
    p = tmp_path / "shot.png"
    p.write_bytes(b"\x89PNG\r\n\x1a\nFAKEIMAGEBYTES")
    return p


def test_openai_message_encodes_image(tmp_path):
    img = _png(tmp_path)
    msg = Message(role=Role.USER, content="what is this?", images=[str(img)])
    out = msg.to_openai()
    assert isinstance(out["content"], list)
    kinds = [part["type"] for part in out["content"]]
    assert kinds == ["text", "image_url"]
    assert out["content"][1]["image_url"]["url"].startswith("data:image/png;base64,")


def test_text_only_message_unchanged():
    msg = Message(role=Role.USER, content="hi")
    assert msg.to_openai() == {"role": "user", "content": "hi"}


def test_anthropic_convert_encodes_image(tmp_path):
    img = _png(tmp_path)
    prov = AnthropicProvider("claude-sonnet-4-6", api_key="x")
    _system, conv = prov._convert([Message(role=Role.USER, content="see", images=[str(img)])])
    block = conv[0]["content"]
    assert block[0]["type"] == "text"
    assert block[1]["type"] == "image"
    assert block[1]["source"]["type"] == "base64"
    assert block[1]["source"]["media_type"] == "image/png"


@pytest.mark.asyncio
async def test_analyze_image_returns_description(tmp_path, monkeypatch):
    img = _png(tmp_path)
    from xplogent.tools.vision import AnalyzeImageTool

    seen = {}

    def fake_build_provider(model, **_kw):
        seen["model"] = model
        return ScriptedProvider([Message(role=Role.ASSISTANT, content="a login screen")])

    monkeypatch.setattr("xplogent.providers.registry.build_provider", fake_build_provider)
    res = await AnalyzeImageTool().run(str(img), "what's on screen?")
    assert res.ok
    assert "login screen" in res.output


@pytest.mark.asyncio
async def test_analyze_image_missing_file(tmp_path):
    from xplogent.tools.vision import AnalyzeImageTool

    res = await AnalyzeImageTool().run(str(tmp_path / "nope.png"))
    assert not res.ok
    assert "No such image" in res.error


# ── toolless vision turns + ollama image payload (Phase 6) ────────────────────
from xplogent.core.agent import Agent  # noqa: E402
from xplogent.core.config import load_config  # noqa: E402
from xplogent.providers.ollama import _to_ollama  # noqa: E402
from xplogent.safety.approval import SafetyManager  # noqa: E402
from xplogent.tools.registry import ToolRegistry  # noqa: E402


class _CapturingProvider(ScriptedProvider):
    """Records the tool specs each stream() was given (to assert toolless turns)."""

    def __init__(self, replies):
        super().__init__(replies)
        self.tools_seen: list = []

    async def stream(self, messages, tools=None, **kwargs):  # type: ignore[override]
        self.tools_seen.append(tools)
        async for ev in super().stream(messages, tools, **kwargs):
            yield ev


@pytest.mark.asyncio
async def test_image_turn_is_toolless_by_default():
    prov = _CapturingProvider([Message(role=Role.ASSISTANT, content="a red square")])
    agent = Agent(load_config(), prov, ToolRegistry.from_config(["shell"]), SafetyManager())
    await agent.run("what is this?", images=["/tmp/x.png"])
    assert prov.tools_seen[0] == []          # no tools sent on the image turn


@pytest.mark.asyncio
async def test_text_turn_keeps_tools():
    prov = _CapturingProvider([Message(role=Role.ASSISTANT, content="hi")])
    agent = Agent(load_config(), prov, ToolRegistry.from_config(["shell"]), SafetyManager())
    await agent.run("just chatting")
    assert prov.tools_seen[0]                 # tools present on a normal turn


@pytest.mark.asyncio
async def test_vision_tools_opt_in_keeps_tools():
    cfg = load_config(overrides={"agent": {"vision_tools": True}})
    prov = _CapturingProvider([Message(role=Role.ASSISTANT, content="ok")])
    agent = Agent(cfg, prov, ToolRegistry.from_config(["shell"]), SafetyManager())
    await agent.run("see this", images=["/tmp/x.png"])
    assert prov.tools_seen[0]                 # opted in → tools kept


def test_ollama_payload_puts_image_in_images_field():
    msg = Message(role=Role.USER, content="describe", images=["data:image/png;base64,QUJD"])
    payload = _to_ollama([msg])[0]
    assert isinstance(payload["content"], str) and payload["content"] == "describe"
    assert payload["images"] == ["QUJD"]      # base64 in Ollama's images field
