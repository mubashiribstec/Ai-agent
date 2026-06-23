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
    """Config/secrets/logs directory (``~/.xplogent``), creating it if needed."""
    home = Path(os.environ.get("XPLOGENT_HOME", Path.home() / ".xplogent"))
    home.mkdir(parents=True, exist_ok=True)
    return home


def install_root() -> Path | None:
    """The framework's install/repo root (dir holding pyproject.toml or .git), or None."""
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "pyproject.toml").exists() or (parent / ".git").exists():
            return parent
    return None


_migrated = False


def data_dir() -> Path:
    """Fixed location for **skills + memory** — inside the install folder.

    ``XPLOGENT_HOME`` still overrides (used by tests/advanced setups). When the
    framework isn't a source/repo install (no pyproject/.git found), falls back to
    ``~/.xplogent`` so wheel installs keep working.
    """
    env = os.environ.get("XPLOGENT_HOME")
    if env:
        base = Path(env)
    else:
        root = install_root()
        base = (root / "data") if root else xplogent_home()
    base.mkdir(parents=True, exist_ok=True)
    _migrate_legacy_data(base)
    return base


def _migrate_legacy_data(base: Path) -> None:
    """One-time copy of an existing ~/.xplogent db + skills into the new data dir."""
    global _migrated
    if _migrated:
        return
    _migrated = True
    legacy = Path.home() / ".xplogent"
    try:
        if base.resolve() == legacy.resolve():
            return
        import shutil

        if not (base / "xplogent.db").exists() and (legacy / "xplogent.db").exists():
            shutil.copy2(legacy / "xplogent.db", base / "xplogent.db")
        if not (base / "skills").exists() and (legacy / "skills").is_dir():
            shutil.copytree(legacy / "skills", base / "skills")
    except OSError:
        pass  # best-effort migration


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
    vision_model: str = ""  # empty → use `model`; set to a vision-capable model
    agent: dict[str, Any] = field(default_factory=dict)
    memory: dict[str, Any] = field(default_factory=dict)
    safety: dict[str, Any] = field(default_factory=dict)
    tools: dict[str, Any] = field(default_factory=dict)
    execution: dict[str, Any] = field(default_factory=dict)
    skills: dict[str, Any] = field(default_factory=dict)
    orchestrator: dict[str, Any] = field(default_factory=dict)
    scheduler: dict[str, Any] = field(default_factory=dict)
    roles: dict[str, Any] = field(default_factory=dict)
    mcp: dict[str, Any] = field(default_factory=dict)
    models: list[dict[str, Any]] = field(default_factory=list)
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
        # Memory (the SQLite DB) is pinned to the install data dir.
        return data_dir() / "xplogent.db"

    @property
    def skills_dir(self) -> Path:
        d = data_dir() / "skills"
        d.mkdir(parents=True, exist_ok=True)
        return d


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


# ─── dotenv + writable config (used by the setup wizard and the GUI) ──────────
_SECRET_KEYS = ["OPENAI_API_KEY", "ANTHROPIC_API_KEY", "OPENROUTER_API_KEY", "GOOGLE_API_KEY"]


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
        vision_model=data.get("vision_model", ""),
        agent=data.get("agent", {}),
        memory=data.get("memory", {}),
        safety=data.get("safety", {}),
        tools=data.get("tools", {}),
        execution=data.get("execution", {}),
        skills=data.get("skills", {}),
        orchestrator=data.get("orchestrator", {}),
        scheduler=data.get("scheduler", {}),
        roles=data.get("roles", {}),
        mcp=data.get("mcp", {}),
        models=data.get("models", []),
        raw=data,
    )
