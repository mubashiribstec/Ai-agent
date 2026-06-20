"""SQLite persistence for sessions, messages, facts, and skills.

Embeddings are stored as JSON arrays; similarity search is done in Python
(cosine) which is plenty fast at personal scale and keeps the dependency
footprint to the standard library.
"""

from __future__ import annotations

import json
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

_SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT,
    summary TEXT,
    created_at REAL
);
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER,
    role TEXT,
    content TEXT,
    created_at REAL
);
CREATE TABLE IF NOT EXISTS facts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    content TEXT,
    embedding TEXT,
    source TEXT,
    created_at REAL
);
CREATE TABLE IF NOT EXISTS skills (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE,
    description TEXT,
    body TEXT,
    embedding TEXT,
    uses INTEGER DEFAULT 0,
    created_at REAL
);
"""


@dataclass
class Fact:
    id: int
    content: str
    embedding: list[float]
    source: str
    created_at: float


@dataclass
class SkillRow:
    id: int
    name: str
    description: str
    body: str
    embedding: list[float]
    uses: int


class Store:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.conn = sqlite3.connect(str(path))
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(_SCHEMA)
        self.conn.commit()

    # -- sessions --------------------------------------------------------------
    def create_session(self, title: str = "") -> int:
        cur = self.conn.execute(
            "INSERT INTO sessions (title, summary, created_at) VALUES (?,?,?)",
            (title, "", time.time()),
        )
        self.conn.commit()
        return int(cur.lastrowid)

    def set_session_summary(self, session_id: int, summary: str) -> None:
        self.conn.execute("UPDATE sessions SET summary=? WHERE id=?", (summary, session_id))
        self.conn.commit()

    def list_sessions(self, limit: int = 20) -> list[dict[str, Any]]:
        rows = self.conn.execute(
            "SELECT * FROM sessions ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(r) for r in rows]

    # -- messages --------------------------------------------------------------
    def add_message(self, session_id: int, role: str, content: str) -> None:
        self.conn.execute(
            "INSERT INTO messages (session_id, role, content, created_at) VALUES (?,?,?,?)",
            (session_id, role, content, time.time()),
        )
        self.conn.commit()

    def session_messages(self, session_id: int) -> list[dict[str, Any]]:
        rows = self.conn.execute(
            "SELECT role, content, created_at FROM messages WHERE session_id=? ORDER BY id",
            (session_id,),
        ).fetchall()
        return [dict(r) for r in rows]

    def search_messages(self, query: str, limit: int = 10) -> list[dict[str, Any]]:
        rows = self.conn.execute(
            "SELECT session_id, role, content FROM messages WHERE content LIKE ? "
            "ORDER BY id DESC LIMIT ?",
            (f"%{query}%", limit),
        ).fetchall()
        return [dict(r) for r in rows]

    # -- facts -----------------------------------------------------------------
    def add_fact(self, content: str, embedding: list[float], source: str = "") -> int:
        cur = self.conn.execute(
            "INSERT INTO facts (content, embedding, source, created_at) VALUES (?,?,?,?)",
            (content, json.dumps(embedding), source, time.time()),
        )
        self.conn.commit()
        return int(cur.lastrowid)

    def all_facts(self) -> list[Fact]:
        rows = self.conn.execute("SELECT * FROM facts").fetchall()
        return [
            Fact(r["id"], r["content"], json.loads(r["embedding"] or "[]"),
                 r["source"], r["created_at"])
            for r in rows
        ]

    # -- skills ----------------------------------------------------------------
    def upsert_skill(self, name: str, description: str, body: str,
                     embedding: list[float]) -> None:
        self.conn.execute(
            "INSERT INTO skills (name, description, body, embedding, uses, created_at) "
            "VALUES (?,?,?,?,0,?) "
            "ON CONFLICT(name) DO UPDATE SET description=excluded.description, "
            "body=excluded.body, embedding=excluded.embedding",
            (name, description, body, json.dumps(embedding), time.time()),
        )
        self.conn.commit()

    def all_skills(self) -> list[SkillRow]:
        rows = self.conn.execute("SELECT * FROM skills").fetchall()
        return [
            SkillRow(r["id"], r["name"], r["description"], r["body"],
                     json.loads(r["embedding"] or "[]"), r["uses"])
            for r in rows
        ]

    def increment_skill_use(self, name: str) -> None:
        self.conn.execute("UPDATE skills SET uses = uses + 1 WHERE name=?", (name,))
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()
