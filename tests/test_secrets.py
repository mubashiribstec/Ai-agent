"""Encrypted secrets at rest + one-time plaintext .env migration."""

from __future__ import annotations

import os

import pytest

from xplogent.core import secrets

# A broken native cryptography build degrades to plaintext; skip the encrypted-
# store tests there (the graceful-degradation path is covered by the API tests).
pytestmark = pytest.mark.skipif(
    not secrets.available(), reason="cryptography (Fernet) not usable in this environment")


def test_secrets_round_trip(monkeypatch, tmp_path):
    monkeypatch.setenv("XPLOGENT_HOME", str(tmp_path))

    assert secrets.available()
    try:
        assert secrets.write_secrets({"OPENAI_API_KEY": "sk-secret-value"})
        assert secrets.read_secrets()["OPENAI_API_KEY"] == "sk-secret-value"
        # The on-disk store is ciphertext, never plaintext.
        blob = (tmp_path / "secrets.enc").read_bytes()
        assert b"sk-secret-value" not in blob
    finally:
        os.environ.pop("OPENAI_API_KEY", None)


def test_load_into_env(monkeypatch, tmp_path):
    monkeypatch.setenv("XPLOGENT_HOME", str(tmp_path))

    secrets.write_secrets({"ANTHROPIC_API_KEY": "ak-123"})
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    secrets.load_into_env(["ANTHROPIC_API_KEY"])
    assert os.environ.get("ANTHROPIC_API_KEY") == "ak-123"
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)


def test_plaintext_env_migrates_to_encrypted(monkeypatch, tmp_path):
    monkeypatch.setenv("XPLOGENT_HOME", str(tmp_path))
    from xplogent.core import config

    config.env_path().write_text("OPENAI_API_KEY=sk-leaked\nFOO=bar\n", encoding="utf-8")
    monkeypatch.setattr(config, "_secrets_migrated", False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    try:
        config.load_dotenv()
        env_text = config.env_path().read_text(encoding="utf-8")
        assert "sk-leaked" not in env_text          # secret stripped from plaintext
        assert "FOO=bar" in env_text                 # non-secret preserved
        assert secrets.read_secrets()["OPENAI_API_KEY"] == "sk-leaked"  # now encrypted
    finally:
        os.environ.pop("OPENAI_API_KEY", None)
        os.environ.pop("FOO", None)
