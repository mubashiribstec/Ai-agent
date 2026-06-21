"""End-to-end agent loop with a scripted provider and a real tool."""

from __future__ import annotations

import pytest

from tests.conftest import ScriptedProvider
from xplogent.core.agent import Agent
from xplogent.core.config import load_config
from xplogent.providers.base import Message, Role, ToolCall
from xplogent.safety.approval import SafetyManager
from xplogent.tools.registry import ToolRegistry


@pytest.mark.asyncio
async def test_agent_runs_tool_then_answers(tmp_path):
    target = tmp_path / "out.txt"
    replies = [
        # step 1: model asks to write a file
        Message(
            role=Role.ASSISTANT,
            content="",
            tool_calls=[ToolCall(id="c1", name="write_file",
                                 arguments={"path": str(target), "content": "hi"})],
        ),
        # step 2: model gives the final answer
        Message(role=Role.ASSISTANT, content="Done. I wrote the file."),
    ]
    provider = ScriptedProvider(replies)
    config = load_config()
    # auto-allow medium risk so the test is non-interactive
    safety = SafetyManager(policy={"low": "auto", "medium": "auto", "high": "auto", "critical": "deny"})
    tools = ToolRegistry.from_config(["filesystem"])
    agent = Agent(config, provider, tools, safety)

    answer = await agent.run("create the file")
    assert "wrote the file" in answer.lower()
    assert target.read_text() == "hi"


@pytest.mark.asyncio
async def test_agent_blocks_denied_tool(tmp_path):
    target = tmp_path / "blocked.txt"
    replies = [
        Message(
            role=Role.ASSISTANT, content="",
            tool_calls=[ToolCall(id="c1", name="write_file",
                                 arguments={"path": str(target), "content": "x"})],
        ),
        Message(role=Role.ASSISTANT, content="I could not complete that."),
    ]
    safety = SafetyManager(policy={"low": "auto", "medium": "deny", "high": "deny", "critical": "deny"})
    agent = Agent(load_config(), ScriptedProvider(replies), ToolRegistry.from_config(["filesystem"]), safety)
    await agent.run("write a file")
    assert not target.exists()
