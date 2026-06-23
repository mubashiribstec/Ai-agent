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
