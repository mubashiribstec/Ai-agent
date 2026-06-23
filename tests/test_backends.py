"""Execution backends: local runs for real; docker/ssh build correct argv (mocked)."""

from __future__ import annotations

import pytest

from xplogent.core.backends import (
    DockerBackend,
    LocalBackend,
    SSHBackend,
    build_backend,
)
from xplogent.tools.shell import ShellTool


class _Cfg:
    def __init__(self, execution):
        self.execution = execution


def test_build_backend_selects_kind():
    assert build_backend(_Cfg({"backend": "local"})).name == "local"
    assert build_backend(_Cfg({"backend": "docker"})).name == "docker"
    assert build_backend(_Cfg({"backend": "ssh"})).name == "ssh"
    assert build_backend(_Cfg({})).name == "local"  # default


def test_docker_run_argv_ephemeral():
    be = DockerBackend(image="python:3.11-slim", workdir="/work")
    argv = be.argv("echo hi", cwd=None)
    assert argv[:3] == ["docker", "run", "--rm"]
    assert argv[-3:] == ["sh", "-lc", "echo hi"]
    assert "python:3.11-slim" in argv


def test_docker_exec_argv_named_container():
    be = DockerBackend(container="mybox")
    argv = be.argv("ls", cwd="/srv")
    assert argv[:2] == ["docker", "exec"]
    assert "mybox" in argv
    assert "-w" in argv and "/srv" in argv


def test_ssh_argv_includes_target_and_cd():
    be = SSHBackend(host="h.example", user="bob", key_path="/k", port=2222)
    argv = be.argv("uptime", cwd="/home/bob")
    assert argv[0] == "ssh"
    assert "bob@h.example" in argv
    assert "-i" in argv and "/k" in argv
    assert "-p" in argv and "2222" in argv
    assert argv[-1].startswith("cd ") and argv[-1].endswith("uptime")


@pytest.mark.asyncio
async def test_local_backend_runs_command():
    rc, out, err = await LocalBackend().run("echo hello-backend")
    assert rc == 0
    assert "hello-backend" in out


@pytest.mark.asyncio
async def test_shell_tool_uses_injected_backend():
    rc_out = await ShellTool(backend=LocalBackend()).run("echo via-tool")
    assert rc_out.ok
    assert "via-tool" in rc_out.output
    assert rc_out.data["backend"] == "local"


@pytest.mark.asyncio
async def test_ssh_backend_without_host_errors():
    rc, out, err = await SSHBackend().run("ls")
    assert rc == 1
    assert "no host" in err.lower()
