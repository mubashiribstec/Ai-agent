"""Cross-platform helpers + Windows-aware safety classification."""

from __future__ import annotations

import xplogent.core.platform as plat
from xplogent.safety.approval import RiskLevel, SafetyManager
from xplogent.tools.shell import ShellTool


def test_has_display_true_on_windows(monkeypatch):
    monkeypatch.setattr(plat.os, "name", "nt")
    assert plat.has_display() is True


def test_has_display_true_on_macos(monkeypatch):
    monkeypatch.setattr(plat.os, "name", "posix")
    monkeypatch.setattr(plat.sys, "platform", "darwin")
    assert plat.has_display() is True


def test_has_display_linux_depends_on_env(monkeypatch):
    monkeypatch.setattr(plat.os, "name", "posix")
    monkeypatch.setattr(plat.sys, "platform", "linux")
    monkeypatch.delenv("DISPLAY", raising=False)
    monkeypatch.delenv("WAYLAND_DISPLAY", raising=False)
    assert plat.has_display() is False
    monkeypatch.setenv("DISPLAY", ":0")
    assert plat.has_display() is True


def test_windows_format_command_is_critical():
    sm = SafetyManager()
    risk, _ = sm.classify(ShellTool(), {"command": "format c:"})
    assert risk == RiskLevel.CRITICAL


def test_windows_readonly_command_is_low_risk():
    assert ShellTool().risk_for({"command": "dir"}) == RiskLevel.LOW
