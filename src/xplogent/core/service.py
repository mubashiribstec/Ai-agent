"""Run Xplogent in the background so it survives closing the terminal.

A lightweight process manager (start/stop/status/restart) plus generators for
real OS services (systemd user unit on Linux, a Scheduled Task on Windows) for
boot/login auto-start.
"""

from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import httpx

from xplogent.core.config import xplogent_home
from xplogent.core.logging import get_logger
from xplogent.core.platform import is_windows

_log = get_logger("service")


def _state_path() -> Path:
    return xplogent_home() / "service.json"


def _log_path() -> Path:
    d = xplogent_home() / "logs"
    d.mkdir(parents=True, exist_ok=True)
    return d / "server.log"


def _read_state() -> dict:
    p = _state_path()
    if p.exists():
        try:
            return json.loads(p.read_text())
        except json.JSONDecodeError:
            return {}
    return {}


def _pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        if is_windows():
            out = subprocess.run(["tasklist", "/FI", f"PID eq {pid}"],
                                 capture_output=True, text=True)
            return str(pid) in out.stdout
        os.kill(pid, 0)
        return True
    except (OSError, ProcessLookupError):
        return False


def start(port: int = 8765, host: str = "127.0.0.1") -> dict:
    """Launch `xplogent up` detached. Returns status."""
    state = _read_state()
    if state.get("pid") and _pid_alive(state["pid"]):
        return {"ok": True, "already_running": True, **state}

    logf = open(_log_path(), "a")  # noqa: SIM115 - handed to the child process
    cmd = [sys.executable, "-m", "xplogent", "up",
           "--port", str(port), "--host", host, "--no-browser"]
    kwargs: dict = {"stdout": logf, "stderr": logf, "stdin": subprocess.DEVNULL}
    if is_windows():
        # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
        kwargs["creationflags"] = 0x00000008 | 0x00000200
    else:
        kwargs["start_new_session"] = True

    proc = subprocess.Popen(cmd, **kwargs)
    state = {"pid": proc.pid, "port": port, "host": host, "started_at": time.time()}
    _state_path().write_text(json.dumps(state))
    return {"ok": True, "started": True, **state}


def stop() -> dict:
    state = _read_state()
    pid = state.get("pid")
    if not pid or not _pid_alive(pid):
        return {"ok": True, "stopped": False, "reason": "not running"}
    try:
        if is_windows():
            subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True)
        else:
            os.kill(pid, signal.SIGTERM)
    except OSError as exc:  # noqa: BLE001
        return {"ok": False, "error": str(exc)}
    _state_path().unlink(missing_ok=True)
    return {"ok": True, "stopped": True}


def status() -> dict:
    state = _read_state()
    pid = state.get("pid")
    running = bool(pid and _pid_alive(pid))
    healthy = False
    if running:
        try:
            r = httpx.get(f"http://{state.get('host', '127.0.0.1')}:{state.get('port', 8765)}/health",
                          timeout=2)
            healthy = r.status_code == 200
        except httpx.HTTPError:
            healthy = False
    return {"running": running, "healthy": healthy, **state}


def restart(port: int = 8765, host: str = "127.0.0.1") -> dict:
    stop()
    time.sleep(1.0)
    return start(port=port, host=host)


# ── OS service generators (boot/login auto-start) ─────────────────────────────
def install_service(port: int = 8765) -> dict:
    """Generate (and best-effort register) an OS service for auto-start."""
    exe = sys.executable
    if is_windows():
        task = "XplogentServer"
        cmd = f'"{exe}" -m xplogent up --port {port} --no-browser'
        register = ["schtasks", "/Create", "/TN", task, "/SC", "ONLOGON",
                    "/TR", cmd, "/F"]
        try:
            subprocess.run(register, capture_output=True, text=True, check=True)
            return {"ok": True, "kind": "scheduled-task", "name": task}
        except (subprocess.CalledProcessError, FileNotFoundError) as exc:
            return {"ok": False, "kind": "scheduled-task",
                    "hint": "run this in an elevated shell:", "command": " ".join(register),
                    "error": str(exc)}
    # Linux: systemd user unit
    unit_dir = Path.home() / ".config" / "systemd" / "user"
    unit_dir.mkdir(parents=True, exist_ok=True)
    unit = unit_dir / "xplogent.service"
    unit.write_text(
        "[Unit]\nDescription=Xplogent agent server\nAfter=network.target\n\n"
        "[Service]\n"
        f"ExecStart={exe} -m xplogent up --port {port} --no-browser\n"
        "Restart=on-failure\n\n"
        "[Install]\nWantedBy=default.target\n"
    )
    return {"ok": True, "kind": "systemd-user", "unit": str(unit),
            "next": "systemctl --user enable --now xplogent  (and: loginctl enable-linger)"}


def uninstall_service() -> dict:
    if is_windows():
        subprocess.run(["schtasks", "/Delete", "/TN", "XplogentServer", "/F"],
                       capture_output=True)
        return {"ok": True}
    subprocess.run(["systemctl", "--user", "disable", "--now", "xplogent"],
                   capture_output=True)
    unit = Path.home() / ".config" / "systemd" / "user" / "xplogent.service"
    unit.unlink(missing_ok=True)
    return {"ok": True}
