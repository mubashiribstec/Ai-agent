"""Access-token middleware + audit log over the REST API."""

from __future__ import annotations

import pytest


def test_auth_gate_and_audit(tmp_path, monkeypatch):
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    monkeypatch.setenv("XPLOGENT_HOME", str(tmp_path))
    from xplogent.core.config import save_user_config

    save_user_config({"server": {"auth_token": "secret123"}})

    from xplogent.interfaces.api.server import create_app

    c = TestClient(create_app())
    hdr = {"Authorization": "Bearer secret123"}

    # /health is public and advertises that auth is on.
    assert c.get("/health").json()["auth"] is True

    # A protected route is 401 without the token, 200 with it.
    assert c.get("/status").status_code == 401
    assert c.get("/status", headers=hdr).status_code == 200

    # /auth/check validates a candidate token.
    assert c.get("/auth/check", headers=hdr).json() == {"required": True, "ok": True}
    assert c.get("/auth/check").json()["ok"] is False

    # A config change is recorded in the audit log.
    assert c.patch("/config", json={"updates": {"model": "ollama:llama3.1"}},
                   headers=hdr).status_code == 200
    entries = c.get("/audit", headers=hdr).json()["entries"]
    assert any(e["action"] == "config_change" for e in entries)


def test_no_auth_by_default(tmp_path, monkeypatch):
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    monkeypatch.setenv("XPLOGENT_HOME", str(tmp_path))
    from xplogent.interfaces.api.server import create_app

    c = TestClient(create_app())
    assert c.get("/health").json()["auth"] is False
    assert c.get("/status").status_code == 200          # open on localhost
    assert c.get("/auth/check").json() == {"required": False, "ok": True}
