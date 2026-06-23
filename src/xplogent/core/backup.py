"""Backup / restore and knowledge export/import.

A backup is a ``.tar.gz`` of the SQLite DB (snapshotted via the consistent
``sqlite3`` backup API so it's safe while the server runs), the ``skills/``
directory, and ``config.yaml``. Secrets (``.env``) are excluded unless opted in.

Knowledge export/import moves just facts + skills (with their embeddings and the
embedding-model that produced them) as portable JSON between instances.
"""

from __future__ import annotations

import sqlite3
import tarfile
import tempfile
import time
from pathlib import Path
from typing import Any

from xplogent.core.config import env_path, xplogent_home
from xplogent.core.logging import get_logger
from xplogent.memory.store import Store

_log = get_logger("backup")


def _snapshot_db(db_path: Path, out: Path) -> None:
    src = sqlite3.connect(str(db_path))
    dst = sqlite3.connect(str(out))
    try:
        with dst:
            src.backup(dst)
    finally:
        dst.close()
        src.close()


def create_backup(dest: Path | str | None = None, *, include_secrets: bool = False) -> dict[str, Any]:
    """Write a .tar.gz of DB + skills + config. Returns ``{ok, path, size}``."""
    home = xplogent_home()
    if dest is None:
        backups = home / "backups"
        backups.mkdir(parents=True, exist_ok=True)
        dest = backups / f"xplogent-backup-{time.strftime('%Y%m%d-%H%M%S')}.tar.gz"
    dest = Path(dest)

    db = home / "xplogent.db"
    with tempfile.TemporaryDirectory() as tmp:
        tmp_db = Path(tmp) / "xplogent.db"
        if db.exists():
            _snapshot_db(db, tmp_db)
        with tarfile.open(dest, "w:gz") as tar:
            if tmp_db.exists():
                tar.add(tmp_db, arcname="xplogent.db")
            skills = home / "skills"
            if skills.is_dir():
                tar.add(skills, arcname="skills")
            cfg = home / "config.yaml"
            if cfg.exists():
                tar.add(cfg, arcname="config.yaml")
            if include_secrets and env_path().exists():
                tar.add(env_path(), arcname=".env")
    return {"ok": True, "path": str(dest), "size": dest.stat().st_size}


def _safe_members(tar: tarfile.TarFile, base: Path) -> list[tarfile.TarInfo]:
    safe = []
    for m in tar.getmembers():
        target = (base / m.name).resolve()
        if base.resolve() in target.parents or target == base.resolve():
            safe.append(m)
        else:
            _log.warning("skipping unsafe path in backup: %s", m.name)
    return safe


def restore_backup(path: Path | str) -> dict[str, Any]:
    """Extract a backup into the Xplogent home (overwrites DB/config/skills)."""
    path = Path(path)
    if not path.exists():
        return {"ok": False, "error": f"no such file: {path}"}
    home = xplogent_home()
    with tarfile.open(path, "r:gz") as tar:
        tar.extractall(home, members=_safe_members(tar, home))  # noqa: S202 - filtered above
    return {"ok": True, "restored_to": str(home)}


# ── knowledge (facts + skills) export / import ───────────────────────────────
def export_knowledge(store: Store) -> dict[str, Any]:
    return {
        "version": 1,
        "exported_at": time.time(),
        "facts": [
            {"content": f.content, "embedding": f.embedding, "source": f.source,
             "embed_model": f.embed_model}
            for f in store.all_facts()
        ],
        "skills": [
            {"name": s.name, "description": s.description, "body": s.body,
             "embedding": s.embedding, "uses": s.uses, "successes": s.successes,
             "failures": s.failures, "embed_model": s.embed_model}
            for s in store.all_skills()
        ],
    }


def import_knowledge(store: Store, data: dict[str, Any]) -> dict[str, Any]:
    """Merge exported facts + skills into the store. Returns counts + any warnings."""
    existing_facts = {f.content for f in store.all_facts()}
    existing_skills = {s.name for s in store.all_skills()}
    models = {s.embed_model for s in store.all_skills() if s.embed_model}
    models |= {f.embed_model for f in store.all_facts() if f.embed_model}

    added_f = added_s = 0
    warn: list[str] = []
    for f in data.get("facts", []):
        if f["content"] in existing_facts:
            continue
        store.add_fact(f["content"], f.get("embedding") or [], f.get("source", "import"),
                       embed_model=f.get("embed_model", ""))
        added_f += 1
    for s in data.get("skills", []):
        if s["name"] in existing_skills:
            continue
        store.upsert_skill(s["name"], s.get("description", ""), s.get("body", ""),
                           s.get("embedding") or [], embed_model=s.get("embed_model", ""))
        added_s += 1

    imported_models = {x.get("embed_model") for x in
                       data.get("facts", []) + data.get("skills", []) if x.get("embed_model")}
    if models and imported_models and not (models & imported_models):
        warn.append(f"embedding model mismatch (have {sorted(models)}, "
                    f"imported {sorted(imported_models)}); semantic recall on imported "
                    "items may be poor until re-embedded.")
    return {"ok": True, "facts_added": added_f, "skills_added": added_s, "warnings": warn}
