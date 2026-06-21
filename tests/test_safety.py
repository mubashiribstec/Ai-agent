"""Safety: risk classification and approval policy."""

from __future__ import annotations

import pytest

from xplogent.safety.approval import RiskLevel, SafetyManager
from xplogent.tools.shell import ShellTool


def test_destructive_command_is_critical_and_denied():
    sm = SafetyManager()
    tool = ShellTool()
    risk, _ = sm.classify(tool, {"command": "rm -rf /"})
    assert risk == RiskLevel.CRITICAL


def test_read_only_command_is_low_risk():
    sm = SafetyManager()
    risk, _ = sm.classify(ShellTool(), {"command": "ls -la"})
    assert risk == RiskLevel.LOW


@pytest.mark.asyncio
async def test_low_risk_auto_allows():
    sm = SafetyManager()
    decision = await sm.evaluate(ShellTool(), {"command": "ls"})
    assert decision.allowed is True
    assert decision.needed_confirmation is False


@pytest.mark.asyncio
async def test_confirm_tier_uses_approver():
    sm = SafetyManager()
    seen = {}

    async def approve(req):
        seen["tool"] = req.tool
        return True

    # a medium-risk shell command (e.g. 'pip install x') needs confirmation
    decision = await sm.evaluate(ShellTool(), {"command": "pip install requests"}, approve)
    assert decision.allowed is True
    assert decision.needed_confirmation is True
    assert seen["tool"] == "shell"


@pytest.mark.asyncio
async def test_confirm_blocks_without_approver():
    sm = SafetyManager()
    decision = await sm.evaluate(ShellTool(), {"command": "pip install requests"}, None)
    assert decision.allowed is False
