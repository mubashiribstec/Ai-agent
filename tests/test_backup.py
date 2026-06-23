"""Backup/restore round-trip and knowledge export/import."""

from __future__ import annotations

import pytest

from xplogent.core import backup as backup_mod
from xplogent.memory.store import Store


def test_backup_and_restore_roundtrip(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("XPLOGENT_HOME", str(home))
    # seed some state
    store = Store(home / "xplogent.db")
    sid = store.create_session("chat")
    store.add_message(sid, "user", "remember the alamo")
    store.close()
    (home / "config.yaml").write_text("model: ollama:llama3.1\n")
    (home / "skills").mkdir()
    (home / "skills" / "greet.md").write_text("# greet\n")

    res = backup_mod.create_backup()
    assert res["ok"]
    archive = res["path"]

    # wipe and restore
    (home / "config.yaml").unlink()
    (home / "skills" / "greet.md").unlink()
    out = backup_mod.restore_backup(archive)
    assert out["ok"]
    assert (home / "config.yaml").exists()
    assert (home / "skills" / "greet.md").exists()
    store = Store(home / "xplogent.db")
    msgs = store.search_messages("alamo")
    assert msgs
    store.close()


def test_backup_excludes_secrets_by_default(tmp_path, monkeypatch):
    import tarfile

    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("XPLOGENT_HOME", str(home))
    Store(home / "xplogent.db").close()
    (home / ".env").write_text("OPENAI_API_KEY=secret123\n")

    res = backup_mod.create_backup()
    with tarfile.open(res["path"]) as tar:
        assert ".env" not in tar.getnames()

    res2 = backup_mod.create_backup(include_secrets=True)
    with tarfile.open(res2["path"]) as tar:
        assert ".env" in tar.getnames()


@pytest.mark.asyncio
async def test_knowledge_export_import(tmp_path):
    src = Store(tmp_path / "src.db")
    src.add_fact("the sky is blue", [0.1, 0.2], source="test", embed_model="scripted:e")
    src.upsert_skill("greet", "say hi", "wave", [0.3, 0.4], embed_model="scripted:e")
    data = backup_mod.export_knowledge(src)
    src.close()
    assert len(data["facts"]) == 1
    assert len(data["skills"]) == 1

    dst = Store(tmp_path / "dst.db")
    res = backup_mod.import_knowledge(dst, data)
    assert res["facts_added"] == 1
    assert res["skills_added"] == 1
    # idempotent second import adds nothing
    res2 = backup_mod.import_knowledge(dst, data)
    assert res2["facts_added"] == 0 and res2["skills_added"] == 0
    dst.close()


def test_import_warns_on_embed_model_mismatch(tmp_path):
    dst = Store(tmp_path / "dst.db")
    dst.add_fact("local fact", [0.1], embed_model="ollama:nomic")
    data = {"facts": [{"content": "imported", "embedding": [0.2], "embed_model": "openai:te3"}],
            "skills": []}
    res = backup_mod.import_knowledge(dst, data)
    assert res["warnings"]
    dst.close()
