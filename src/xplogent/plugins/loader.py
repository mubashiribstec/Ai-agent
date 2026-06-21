"""Drop-in plugin loader.

Any ``*.py`` file in ``$XPLOGENT_HOME/plugins`` that defines a top-level
``register(registry)`` function is imported and given the chance to add tools (or
register providers). Plugins are user code, so loading is best-effort and never
fatal to startup.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

from xplogent.core.config import xplogent_home
from xplogent.core.logging import get_logger
from xplogent.tools.registry import ToolRegistry

_log = get_logger("plugins")


def plugins_dir() -> Path:
    d = xplogent_home() / "plugins"
    d.mkdir(parents=True, exist_ok=True)
    return d


def load_plugins(registry: ToolRegistry) -> list[str]:
    """Import every plugin and let it register tools. Returns loaded plugin names."""
    loaded: list[str] = []
    for path in sorted(plugins_dir().glob("*.py")):
        if path.name.startswith("_"):
            continue
        try:
            spec = importlib.util.spec_from_file_location(f"xplogent_plugin_{path.stem}", path)
            if not spec or not spec.loader:
                continue
            module = importlib.util.module_from_spec(spec)
            sys.modules[spec.name] = module
            spec.loader.exec_module(module)
            if hasattr(module, "register"):
                module.register(registry)
                loaded.append(path.stem)
        except Exception:  # noqa: BLE001 - a broken plugin must not crash Xplogent
            _log.exception("Failed to load plugin %s", path.name)
    return loaded
