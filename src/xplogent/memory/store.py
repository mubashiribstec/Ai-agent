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
CREATE TABLE IF NOT EXISTS schedules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT,
    prompt TEXT,
    mode TEXT,
    spec TEXT,
    tz TEXT,
    enabled INTEGER DEFAULT 1,
    next_run REAL,
    last_run REAL,
    last_status TEXT,
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
        self._fts = False
        with self._lock:
            self.conn.execute("PRAGMA journal_mode=WAL")
            self.conn.executescript(_SCHEMA)
            self.conn.commit()
            self._init_fts()

    def _init_fts(self) -> None:
        """Best-effort full-text index over message content (FTS5 may be absent)."""
        try:
            self.conn.executescript(
                "CREATE VIRTUAL TABLE IF NOT EXISTS messages_fts USING fts5("
                "content, session_id UNINDEXED, role UNINDEXED);"
            )
            self.conn.commit()
            self._fts = True
        except sqlite3.OperationalError:
            self._fts = False
            return
        # Backfill once if the index is empty but messages already exist.
        have = self.conn.execute("SELECT COUNT(*) FROM messages_fts").fetchone()[0]
        if not have and self.conn.execute("SELECT COUNT(*) FROM messages").fetchone()[0]:
            self.conn.execute(
                "INSERT INTO messages_fts (rowid, content, session_id, role) "
                "SELECT id, content, session_id, role FROM messages"
            )
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
        if self._fts:
            self._write("DELETE FROM messages_fts WHERE session_id=?", (session_id,))

    # -- messages --------------------------------------------------------------
    def add_message(self, session_id: int, role: str, content: str) -> None:
        cur = self._write(
            "INSERT INTO messages (session_id, role, content, created_at) VALUES (?,?,?,?)",
            (session_id, role, content, time.time()),
        )
        if self._fts:
            self._write(
                "INSERT INTO messages_fts (rowid, content, session_id, role) VALUES (?,?,?,?)",
                (int(cur.lastrowid), content, session_id, role),
            )

    def session_messages(self, session_id: int) -> list[dict[str, Any]]:
        rows = self._query(
            "SELECT role, content, created_at FROM messages WHERE session_id=? ORDER BY id",
            (session_id,),
        )
        return [dict(r) for r in rows]

    def search_messages(self, query: str, limit: int = 10) -> list[dict[str, Any]]:
        """Full-text ranked search (FTS5) with a LIKE fallback when unavailable."""
        if self._fts and query.strip():
            # Require each term (quoted, AND-ed); bm25 ranks best matches first (lower=better).
            terms = [t for t in query.replace('"', " ").split() if t]
            match = " ".join(f'"{t}"' for t in terms)
            if not match:
                match = '"' + query.strip() + '"'
            try:
                rows = self._query(
                    "SELECT session_id, role, content FROM messages_fts "
                    "WHERE messages_fts MATCH ? ORDER BY bm25(messages_fts) LIMIT ?",
                    (match, limit),
                )
                return [dict(r) for r in rows]
            except sqlite3.OperationalError:
                pass  # malformed query → fall back to LIKE
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

    # -- schedules (recurring / timed agent jobs) ------------------------------
    def add_schedule(self, name: str, prompt: str, mode: str, spec: str,
                     tz: str, next_run: float) -> int:
        cur = self._write(
            "INSERT INTO schedules (name, prompt, mode, spec, tz, enabled, "
            "next_run, last_run, last_status, created_at) VALUES (?,?,?,?,?,1,?,?,?,?)",
            (name, prompt, mode, spec, tz, next_run, None, None, time.time()),
        )
        return int(cur.lastrowid)

    def list_schedules(self) -> list[dict[str, Any]]:
        return [dict(r) for r in self._query(
            "SELECT * FROM schedules ORDER BY id DESC")]

    def get_schedule(self, schedule_id: int) -> dict[str, Any] | None:
        rows = self._query("SELECT * FROM schedules WHERE id=?", (schedule_id,))
        return dict(rows[0]) if rows else None

    def due_schedules(self, now: float) -> list[dict[str, Any]]:
        return [dict(r) for r in self._query(
            "SELECT * FROM schedules WHERE enabled=1 AND next_run IS NOT NULL "
            "AND next_run<=? ORDER BY next_run", (now,))]

    def set_schedule_run(self, schedule_id: int, last_run: float | None,
                         last_status: str, next_run: float | None) -> None:
        self._write(
            "UPDATE schedules SET last_run=?, last_status=?, next_run=? WHERE id=?",
            (last_run, last_status, next_run, schedule_id),
        )

    def set_schedule_next(self, schedule_id: int, next_run: float | None) -> None:
        self._write("UPDATE schedules SET next_run=? WHERE id=?", (next_run, schedule_id))

    def set_schedule_enabled(self, schedule_id: int, enabled: bool) -> None:
        self._write("UPDATE schedules SET enabled=? WHERE id=?",
                    (1 if enabled else 0, schedule_id))

    def delete_schedule(self, schedule_id: int) -> None:
        self._write("DELETE FROM schedules WHERE id=?", (schedule_id,))

    def close(self) -> None:
        with self._lock:
            self.conn.close()
