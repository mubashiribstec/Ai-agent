"""Computer-use operator: scoped toolset, prompt, and a bounded run."""

from __future__ import annotations

import pytest

from tests.conftest import ScriptedProvider
from xplogent.core import operator
from xplogent.providers.base import Message, Role


def test_build_operator_scopes_tools(monkeypatch):
    monkeypatch.setattr("xplogent.runtime.build_provider", lambda *_a, **_k: ScriptedProvider([]))
    rt = operator.build_operator(max_steps=7)
    names = {t.name for t in rt.agent.tools.all()}
    # Only vision + GUI (+ optional browser) tools are exposed — never shell/python.
    assert {"screenshot", "mouse", "keyboard", "analyze_image"} <= names
    assert "shell" not in names and "python_exec" not in names
    assert rt.agent._max_steps == 7
    assert "COMPUTER-USE" in rt.agent.config.agent["system_prompt"]


@pytest.mark.asyncio
async def test_run_operator_returns_summary(monkeypatch):
    # The model immediately reports completion (no tool calls) → returns its text.
    monkeypatch.setattr(
        "xplogent.runtime.build_provider",
        lambda *_a, **_k: ScriptedProvider([Message(role=Role.ASSISTANT, content="done: opened the app")]),
    )
    out = await operator.run_operator("open the app", max_steps=5)
    assert "opened the app" in out
