"""SQLite persistence for sessions, messages, facts, skills, and run traces.

Embeddings are stored as JSON arrays; similarity search is done in Python
(cosine) which is plenty fast at personal scale and keeps the dependency
footprint to the standard library.

The connection is opened with ``check_same_thread=False`` and WAL mode, and all
mutations are guarded by a lock, so multiple concurrently-running agents (and
the API threadpool) can share one store safely.
"""

from __future__ import annotations

import json
import sqlite3
import threading
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
CREATE TABLE IF NOT EXISTS runs (
    id TEXT PRIMARY KEY,
    goal TEXT,
    mode TEXT,
    status TEXT,
    started_at REAL,
    ended_at REAL
);
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT,
    agent_id TEXT,
    type TEXT,
    data TEXT,
    created_at REAL
);
CREATE TABLE IF NOT EXISTS agent_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT,
    sender TEXT,
    recipient TEXT,
    content TEXT,
    created_at REAL
);
CREATE INDEX IF NOT EXISTS idx_events_run ON events(run_id);
CREATE INDEX IF NOT EXISTS idx_msgs_run ON agent_messages(run_id);
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
        self.conn = sqlite3.connect(str(path), check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._lock = threading.RLock()
        with self._lock:
            self.conn.execute("PRAGMA journal_mode=WAL")
            self.conn.executescript(_SCHEMA)
            self.conn.commit()

    def _write(self, sql: str, params: tuple = ()) -> sqlite3.Cursor:
        with self._lock:
            cur = self.conn.execute(sql, params)
            self.conn.commit()
            return cur

    def _query(self, sql: str, params: tuple = ()) -> list[sqlite3.Row]:
        with self._lock:
            return self.conn.execute(sql, params).fetchall()

    # -- sessions --------------------------------------------------------------
    def create_session(self, title: str = "") -> int:
        cur = self._write(
            "INSERT INTO sessions (title, summary, created_at) VALUES (?,?,?)",
            (title, "", time.time()),
        )
        return int(cur.lastrowid)

    def set_session_summary(self, session_id: int, summary: str) -> None:
        self._write("UPDATE sessions SET summary=? WHERE id=?", (summary, session_id))

    def set_session_title(self, session_id: int, title: str) -> None:
        """Set the title only if it's still the default, so it reads as the first message."""
        self._write(
            "UPDATE sessions SET title=? WHERE id=? "
            "AND (title IS NULL OR title='' OR title='chat')",
            (title, session_id),
        )

    def list_sessions(self, limit: int = 50) -> list[dict[str, Any]]:
        rows = self._query(
            "SELECT s.*, (SELECT COUNT(*) FROM messages m WHERE m.session_id=s.id) AS message_count "
            "FROM sessions s ORDER BY created_at DESC LIMIT ?", (limit,)
        )
        return [dict(r) for r in rows]

    def delete_session(self, session_id: int) -> None:
        self._write("DELETE FROM messages WHERE session_id=?", (session_id,))
        self._write("DELETE FROM sessions WHERE id=?", (session_id,))

    # -- messages --------------------------------------------------------------
    def add_message(self, session_id: int, role: str, content: str) -> None:
        self._write(
            "INSERT INTO messages (session_id, role, content, created_at) VALUES (?,?,?,?)",
            (session_id, role, content, time.time()),
        )

    def session_messages(self, session_id: int) -> list[dict[str, Any]]:
        rows = self._query(
            "SELECT role, content, created_at FROM messages WHERE session_id=? ORDER BY id",
            (session_id,),
        )
        return [dict(r) for r in rows]

    def search_messages(self, query: str, limit: int = 10) -> list[dict[str, Any]]:
        rows = self._query(
            "SELECT session_id, role, content FROM messages WHERE content LIKE ? "
            "ORDER BY id DESC LIMIT ?",
            (f"%{query}%", limit),
        )
        return [dict(r) for r in rows]

    # -- facts -----------------------------------------------------------------
    def add_fact(self, content: str, embedding: list[float], source: str = "") -> int:
        cur = self._write(
            "INSERT INTO facts (content, embedding, source, created_at) VALUES (?,?,?,?)",
            (content, json.dumps(embedding), source, time.time()),
        )
        return int(cur.lastrowid)

    def all_facts(self) -> list[Fact]:
        rows = self._query("SELECT * FROM facts")
        return [
            Fact(r["id"], r["content"], json.loads(r["embedding"] or "[]"),
                 r["source"], r["created_at"])
            for r in rows
        ]

    def delete_fact(self, fact_id: int) -> None:
        self._write("DELETE FROM facts WHERE id=?", (fact_id,))

    # -- skills ----------------------------------------------------------------
    def upsert_skill(self, name: str, description: str, body: str,
                     embedding: list[float]) -> None:
        self._write(
            "INSERT INTO skills (name, description, body, embedding, uses, created_at) "
            "VALUES (?,?,?,?,0,?) "
            "ON CONFLICT(name) DO UPDATE SET description=excluded.description, "
            "body=excluded.body, embedding=excluded.embedding",
            (name, description, body, json.dumps(embedding), time.time()),
        )

    def all_skills(self) -> list[SkillRow]:
        rows = self._query("SELECT * FROM skills")
        return [
            SkillRow(r["id"], r["name"], r["description"], r["body"],
                     json.loads(r["embedding"] or "[]"), r["uses"])
            for r in rows
        ]

    def increment_skill_use(self, name: str) -> None:
        self._write("UPDATE skills SET uses = uses + 1 WHERE name=?", (name,))

    def delete_skill(self, name: str) -> None:
        self._write("DELETE FROM skills WHERE name=?", (name,))

    # -- runs / events / agent messages (monitoring) ---------------------------
    def create_run(self, run_id: str, goal: str, mode: str) -> None:
        self._write(
            "INSERT OR REPLACE INTO runs (id, goal, mode, status, started_at, ended_at) "
            "VALUES (?,?,?,?,?,?)",
            (run_id, goal, mode, "running", time.time(), None),
        )

    def finish_run(self, run_id: str, status: str = "done") -> None:
        self._write(
            "UPDATE runs SET status=?, ended_at=? WHERE id=?",
            (status, time.time(), run_id),
        )

    def list_runs(self, limit: int = 50) -> list[dict[str, Any]]:
        return [dict(r) for r in self._query(
            "SELECT * FROM runs ORDER BY started_at DESC LIMIT ?", (limit,)
        )]

    def get_run(self, run_id: str) -> dict[str, Any] | None:
        rows = self._query("SELECT * FROM runs WHERE id=?", (run_id,))
        return dict(rows[0]) if rows else None

    def add_event(self, run_id: str, agent_id: str, type_: str, data: dict[str, Any]) -> None:
        self._write(
            "INSERT INTO events (run_id, agent_id, type, data, created_at) VALUES (?,?,?,?,?)",
            (run_id, agent_id, type_, json.dumps(data, default=str), time.time()),
        )

    def run_events(self, run_id: str, limit: int = 2000) -> list[dict[str, Any]]:
        rows = self._query(
            "SELECT agent_id, type, data, created_at FROM events WHERE run_id=? "
            "ORDER BY id LIMIT ?",
            (run_id, limit),
        )
        out = []
        for r in rows:
            out.append({
                "agent_id": r["agent_id"], "type": r["type"],
                "data": json.loads(r["data"] or "{}"), "created_at": r["created_at"],
            })
        return out

    def add_agent_message(self, run_id: str, sender: str, recipient: str | None,
                          content: str) -> None:
        self._write(
            "INSERT INTO agent_messages (run_id, sender, recipient, content, created_at) "
            "VALUES (?,?,?,?,?)",
            (run_id, sender, recipient, content, time.time()),
        )

    def list_agent_messages(self, run_id: str | None = None, limit: int = 200) -> list[dict[str, Any]]:
        if run_id:
            rows = self._query(
                "SELECT * FROM agent_messages WHERE run_id=? ORDER BY id DESC LIMIT ?",
                (run_id, limit),
            )
        else:
            rows = self._query(
                "SELECT * FROM agent_messages ORDER BY id DESC LIMIT ?", (limit,)
            )
        return [dict(r) for r in rows]

    def close(self) -> None:
        with self._lock:
            self.conn.close()
