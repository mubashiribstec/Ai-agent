"""Tools: schema generation and filesystem round-trip."""

from __future__ import annotations

import pytest

from xplogent.tools.filesystem import ReadFileTool, WriteFileTool
from xplogent.tools.registry import ToolRegistry


def test_tool_spec_is_openai_shaped():
    spec = WriteFileTool().spec().to_openai()
    assert spec["type"] == "function"
    assert spec["function"]["name"] == "write_file"
    assert "path" in spec["function"]["parameters"]["properties"]


def test_registry_from_config_filters_groups():
    reg = ToolRegistry.from_config(["filesystem"])
    names = {t.name for t in reg.all()}
    assert "write_file" in names
    assert "shell" not in names


@pytest.mark.asyncio
async def test_write_then_read(tmp_path):
    target = tmp_path / "note.txt"
    write = await WriteFileTool().run(path=str(target), content="hello xplogent")
    assert write.ok
    read = await ReadFileTool().run(path=str(target))
    assert read.ok
    assert "hello xplogent" in read.output


@pytest.mark.asyncio
async def test_read_missing_file_fails():
    res = await ReadFileTool().run(path="/no/such/file.xyz")
    assert not res.ok
