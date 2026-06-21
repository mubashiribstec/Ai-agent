"""Xplogent-as-MCP-server: catalog, dispatch, and rights enforcement."""

from __future__ import annotations

import pytest

from tests.conftest import ScriptedProvider
from xplogent.core.config import load_config
from xplogent.interfaces.mcp_server import XplogentMCP
from xplogent.providers.base import Message, Role


def _mcp(tmp_path, monkeypatch, role="operator", auto_approve=False, expose_raw=True):
    monkeypatch.setenv("XPLOGENT_HOME", str(tmp_path))
    cfg = load_config()
    cfg.mcp = {"server": {"agent_role": role, "auto_approve": auto_approve,
                          "expose_raw_tools": expose_raw}}
    return XplogentMCP(cfg)


def test_tool_specs_include_agent_and_raw_tools(tmp_path, monkeypatch):
    xpl = _mcp(tmp_path, monkeypatch)
    names = {s.name for s in xpl.tool_specs()}
    assert "xplogent_run_agent" in names
    assert "xplogent_orchestrate" in names
    assert "shell" in names          # raw PC-control tools exposed for operator
    assert "read_file" in names


def test_role_filters_raw_tools(tmp_path, monkeypatch):
    xpl = _mcp(tmp_path, monkeypatch, role="restricted")
    names = {s.name for s in xpl.tool_specs()}
    assert "read_file" in names      # restricted allows read_file
    assert "shell" not in names      # but not shell
    assert "xplogent_run_agent" in names  # agent tools always present


def test_expose_raw_tools_off(tmp_path, monkeypatch):
    xpl = _mcp(tmp_path, monkeypatch, expose_raw=False)
    names = {s.name for s in xpl.tool_specs()}
    assert "shell" not in names
    assert "xplogent_run_agent" in names


@pytest.mark.asyncio
async def test_dispatch_run_agent_returns_answer(tmp_path, monkeypatch):
    import xplogent.runtime as rt

    monkeypatch.setattr(
        rt, "build_provider",
        lambda *_a, **_k: ScriptedProvider([Message(role=Role.ASSISTANT, content="the answer")]),
    )
    xpl = _mcp(tmp_path, monkeypatch)
    out = await xpl.dispatch("xplogent_run_agent", {"task": "do a thing"})
    assert "the answer" in out


@pytest.mark.asyncio
async def test_dispatch_raw_read_file(tmp_path, monkeypatch):
    target = tmp_path / "note.txt"
    target.write_text("hello from disk")
    xpl = _mcp(tmp_path, monkeypatch, auto_approve=True)  # operator low=auto anyway
    out = await xpl.dispatch("read_file", {"path": str(target)})
    assert "hello from disk" in out


@pytest.mark.asyncio
async def test_raw_tool_blocked_without_approval(tmp_path, monkeypatch):
    # restricted policy makes read_file confirm-tier; no approver -> blocked.
    xpl = _mcp(tmp_path, monkeypatch, role="restricted", auto_approve=False)
    out = await xpl.dispatch("read_file", {"path": str(tmp_path / "x")})
    assert "BLOCKED" in out


def test_create_mcp_server_builds():
    pytest.importorskip("mcp")
    from xplogent.interfaces.mcp_server import create_mcp_server

    server = create_mcp_server(XplogentMCP())
    assert server.name == "xplogent"
