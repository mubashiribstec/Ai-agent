"""Self-update logic (git calls mocked — no network)."""

from __future__ import annotations

from pathlib import Path

from xplogent.core import updater


def test_repo_root_finds_repo():
    root = updater.repo_root()
    assert root is not None
    assert (root / ".git").exists()


def test_check_update_parses_behind(monkeypatch):
    calls = {
        ("fetch", "--quiet"): (0, ""),
        ("rev-parse", "--abbrev-ref", "HEAD"): (0, "main"),
        ("rev-list", "--left-right", "--count", "HEAD...origin/main"): (0, "0\t3"),
        ("log", "--oneline", "HEAD..origin/main"): (0, "abc feat\ndef fix"),
        ("rev-parse", "--short", "HEAD"): (0, "deadbee"),
    }

    def fake_git(root, *args):
        return calls.get(tuple(args), (0, ""))

    monkeypatch.setattr(updater, "_git", fake_git)
    monkeypatch.setattr(updater, "repo_root", lambda: Path("/tmp/repo"))
    result = updater.check_update()
    assert result["git"] is True
    assert result["update_available"] is True
    assert result["behind_by"] == 3
    assert "feat" in result["changelog"]


def test_check_update_no_git(monkeypatch):
    monkeypatch.setattr(updater, "repo_root", lambda: None)
    result = updater.check_update()
    assert result["git"] is False
    assert result["update_available"] is False


def test_pull_not_a_checkout(monkeypatch):
    monkeypatch.setattr(updater, "repo_root", lambda: None)
    assert updater.pull()["ok"] is False


def test_rebuild_web_runs_npm(monkeypatch, tmp_path):
    web = tmp_path / "web"
    web.mkdir()
    monkeypatch.setattr(updater, "repo_root", lambda: tmp_path)
    import shutil
    monkeypatch.setattr(shutil, "which", lambda _x: "/usr/bin/npm")
    calls = []

    class _R:
        returncode = 0
        stdout = "built"
        stderr = ""

    monkeypatch.setattr(updater.subprocess, "run",
                        lambda cmd, **k: calls.append(cmd) or _R())
    res = updater.rebuild_web()
    assert res["ok"]
    assert any("build" in c for c in calls)


def test_rebuild_web_no_npm(monkeypatch, tmp_path):
    (tmp_path / "web").mkdir()
    monkeypatch.setattr(updater, "repo_root", lambda: tmp_path)
    import shutil
    monkeypatch.setattr(shutil, "which", lambda _x: None)
    assert "skipped" in updater.rebuild_web()
