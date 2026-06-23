"""Service hardening (Windows task, launch validation) and atomic update."""

from __future__ import annotations

from pathlib import Path

from xplogent.core import service, updater


def test_can_launch_validates_import(monkeypatch):
    class _R:
        returncode = 0
        stderr = ""
    monkeypatch.setattr(service.subprocess, "run", lambda *a, **k: _R())
    ok, err = service._can_launch()
    assert ok and err == ""

    class _Bad:
        returncode = 1
        stderr = "ModuleNotFoundError: xplogent"
    monkeypatch.setattr(service.subprocess, "run", lambda *a, **k: _Bad())
    ok, err = service._can_launch()
    assert not ok and "xplogent" in err


def test_start_aborts_when_unlaunchable(monkeypatch):
    monkeypatch.setattr(service, "_read_state", lambda: {})
    monkeypatch.setattr(service, "_can_launch", lambda: (False, "broken venv"))
    res = service.start()
    assert res["ok"] is False
    assert "broken venv" in res["error"]


def test_windows_service_writes_bat(monkeypatch, tmp_path):
    monkeypatch.setenv("XPLOGENT_HOME", str(tmp_path))
    monkeypatch.setattr(service, "is_windows", lambda: True)
    monkeypatch.setattr(service, "_workdir", lambda: tmp_path)

    calls = []

    class _R:
        returncode = 0
        stdout = ""
        stderr = ""
    monkeypatch.setattr(service.subprocess, "run",
                        lambda cmd, **k: calls.append(cmd) or _R())
    res = service.install_service(port=9000)
    assert res["ok"]
    bat = Path(res["script"])
    assert bat.exists()
    assert "xplogent up --port 9000" in bat.read_text()
    # schtasks was invoked to create + query
    assert any("/Create" in c for c in calls)
    assert any("/Query" in c for c in calls)


def test_update_and_restart_runs_stages_in_order(monkeypatch):
    order = []
    monkeypatch.setattr("xplogent.core.backup.create_backup",
                        lambda *a, **k: order.append("backup") or {"path": "/b.tar.gz"})
    monkeypatch.setattr(updater, "pull", lambda: order.append("pull") or {"ok": True, "output": "ok"})
    monkeypatch.setattr(updater, "reinstall", lambda: order.append("reinstall") or {"ok": True, "output": "ok"})
    monkeypatch.setattr(updater, "rebuild_web", lambda: order.append("rebuild") or {"ok": True, "output": "ok"})
    monkeypatch.setattr(updater, "restart", lambda *a, **k: order.append("restart"))
    res = updater.update_and_restart()
    assert res["ok"]
    assert order == ["backup", "pull", "reinstall", "rebuild", "restart"]


def test_update_and_restart_stops_on_pull_failure(monkeypatch):
    monkeypatch.setattr("xplogent.core.backup.create_backup", lambda *a, **k: {"path": "x"})
    monkeypatch.setattr(updater, "pull", lambda: {"ok": False, "output": "conflict"})
    called = {"restart": False}
    monkeypatch.setattr(updater, "restart", lambda *a, **k: called.__setitem__("restart", True))
    res = updater.update_and_restart()
    assert res["ok"] is False
    assert res["stage"] == "pull"
    assert called["restart"] is False
