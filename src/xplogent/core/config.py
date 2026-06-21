"""Configuration loading.

Precedence (highest wins):
    1. Environment variables (``XPLOGENT_*`` and provider keys)
    2. User config at ``$XPLOGENT_HOME/config.yaml`` (default ``~/.xplogent``)
    3. Packaged ``config/default.yaml``
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

_PACKAGE_ROOT = Path(__file__).resolve().parents[3]
_DEFAULT_CONFIG = _PACKAGE_ROOT / "config" / "default.yaml"


def xplogent_home() -> Path:
    """Return the Xplogent data directory, creating it if needed."""
    home = Path(os.environ.get("XPLOGENT_HOME", Path.home() / ".xplogent"))
    home.mkdir(parents=True, exist_ok=True)
    return home


def _deep_merge(base: dict, override: dict) -> dict:
    out = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _deep_merge(out[key], value)
        else:
            out[key] = value
    return out


@dataclass
class Config:
    """Resolved runtime configuration."""

    model: str = "ollama:llama3.1"
    reflection_model: str = "ollama:llama3.1"
    embedding_model: str = "ollama:nomic-embed-text"
    agent: dict[str, Any] = field(default_factory=dict)
    memory: dict[str, Any] = field(default_factory=dict)
    safety: dict[str, Any] = field(default_factory=dict)
    tools: dict[str, Any] = field(default_factory=dict)
    skills: dict[str, Any] = field(default_factory=dict)
    orchestrator: dict[str, Any] = field(default_factory=dict)
    roles: dict[str, Any] = field(default_factory=dict)
    mcp: dict[str, Any] = field(default_factory=dict)
    home: Path = field(default_factory=xplogent_home)
    raw: dict[str, Any] = field(default_factory=dict)

    # -- convenience accessors -------------------------------------------------
    @property
    def provider_name(self) -> str:
        return self.model.split(":", 1)[0]

    @property
    def model_name(self) -> str:
        return self.model.split(":", 1)[1] if ":" in self.model else self.model

    def split_model(self, spec: str) -> tuple[str, str]:
        """Split a ``provider:model`` spec into its parts."""
        provider, _, name = spec.partition(":")
        return provider, name or provider

    @property
    def db_path(self) -> Path:
        return self.home / "xplogent.db"

    @property
    def skills_dir(self) -> Path:
        d = self.home / "skills"
        d.mkdir(parents=True, exist_ok=True)
        return d


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


# ─── dotenv + writable config (used by the setup wizard and the GUI) ──────────
_SECRET_KEYS = ["OPENAI_API_KEY", "ANTHROPIC_API_KEY", "OPENROUTER_API_KEY"]


def env_path() -> Path:
    return xplogent_home() / ".env"


def load_dotenv() -> None:
    """Load ``~/.xplogent/.env`` into ``os.environ`` without overriding real env."""
    path = env_path()
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def save_env(updates: dict[str, str]) -> None:
    """Merge ``KEY=VALUE`` pairs into ``~/.xplogent/.env`` (creating it)."""
    path = env_path()
    existing: dict[str, str] = {}
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.strip().startswith("#"):
                k, _, v = line.partition("=")
                existing[k.strip()] = v.strip()
    for k, v in updates.items():
        if v:
            existing[k] = v
            os.environ[k] = v  # reflect immediately in-process
    body = "\n".join(f"{k}={v}" for k, v in existing.items()) + "\n"
    path.write_text(body, encoding="utf-8")
    try:
        path.chmod(0o600)
    except OSError:
        pass


def secret_status() -> dict[str, bool]:
    """Which provider keys are set (without revealing them)."""
    return {k: bool(os.environ.get(k)) for k in _SECRET_KEYS}


def save_user_config(updates: dict[str, Any]) -> dict[str, Any]:
    """Deep-merge ``updates`` into ``~/.xplogent/config.yaml`` and return the merged dict."""
    path = xplogent_home() / "config.yaml"
    current = _load_yaml(path)
    merged = _deep_merge(current, updates)
    path.write_text(yaml.safe_dump(merged, sort_keys=False), encoding="utf-8")
    return merged


def load_config(overrides: dict[str, Any] | None = None) -> Config:
    """Build a :class:`Config` from defaults, user file, env, and explicit overrides."""
    load_dotenv()
    data = _load_yaml(_DEFAULT_CONFIG)

    user_cfg = xplogent_home() / "config.yaml"
    data = _deep_merge(data, _load_yaml(user_cfg))

    # Environment overrides
    if model := os.environ.get("XPLOGENT_MODEL"):
        data["model"] = model
    if rmodel := os.environ.get("XPLOGENT_REFLECTION_MODEL"):
        data["reflection_model"] = rmodel
    if emodel := os.environ.get("XPLOGENT_EMBEDDING_MODEL"):
        data["embedding_model"] = emodel

    if overrides:
        data = _deep_merge(data, overrides)

    return Config(
        model=data.get("model", "ollama:llama3.1"),
        reflection_model=data.get("reflection_model", data.get("model", "ollama:llama3.1")),
        embedding_model=data.get("embedding_model", "ollama:nomic-embed-text"),
        agent=data.get("agent", {}),
        memory=data.get("memory", {}),
        safety=data.get("safety", {}),
        tools=data.get("tools", {}),
        skills=data.get("skills", {}),
        orchestrator=data.get("orchestrator", {}),
        roles=data.get("roles", {}),
        mcp=data.get("mcp", {}),
        raw=data,
    )
