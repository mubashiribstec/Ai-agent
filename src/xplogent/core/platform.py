"""Cross-platform helpers (Windows + Linux + macOS).

Centralizes the few places where behavior differs by OS so the rest of the
codebase never branches on ``sys.platform`` directly.
"""

from __future__ import annotations

import os
import shutil
import sys


def is_windows() -> bool:
    return os.name == "nt"


def is_macos() -> bool:
    return sys.platform == "darwin"


def is_linux() -> bool:
    return sys.platform.startswith("linux")


def has_display() -> bool:
    """True if a GUI display is (likely) available for screen/mouse/keyboard."""
    if is_windows() or is_macos():
        return True
    return bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))


def default_shell() -> str | None:
    """Preferred shell executable for the current OS, or None for the default."""
    if is_windows():
        return os.environ.get("COMSPEC", "cmd.exe")
    return shutil.which("bash") or "/bin/sh"
