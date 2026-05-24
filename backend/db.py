"""SQLite persistence layer for analysis sessions and step results."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

import aiosqlite

_DB_PATH = Path(os.getenv("DB_PATH", "agent_monitor.db"))

_CREATE_SESSIONS = """
CREATE TABLE IF NOT EXISTS sessions (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    source       TEXT    NOT NULL,
    log_path     TEXT,
    started_at   TEXT    NOT NULL,
    completed_at TEXT,
    total_steps  INTEGER NOT NULL DEFAULT 0,
    flagged_count INTEGER NOT NULL DEFAULT 0
)
"""

_CREATE_STEPS = """
CREATE TABLE IF NOT EXISTS analysis_steps (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id       INTEGER NOT NULL REFERENCES sessions(id),
    step             INTEGER NOT NULL,
    reasoning        TEXT    NOT NULL,
    tool             TEXT    NOT NULL,
    args_json        TEXT    NOT NULL,
    divergence_score REAL    NOT NULL,
    flagged          INTEGER NOT NULL,
    explanation      TEXT    NOT NULL,
    rule_name        TEXT,
    severity         TEXT
)
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


async def init_db() -> None:
    """Create tables and enable WAL mode. Call once at application startup."""
    async with aiosqlite.connect(_DB_PATH) as conn:
        await conn.execute("PRAGMA journal_mode=WAL")
        await conn.execute(_CREATE_SESSIONS)
        await conn.execute(_CREATE_STEPS)
        await conn.commit()


async def create_session(source: str, log_path: str | None = None) -> int:
    """Insert a new session row and return its id."""
    async with aiosqlite.connect(_DB_PATH) as conn:
        cursor = await conn.execute(
            "INSERT INTO sessions (source, log_path, started_at) VALUES (?, ?, ?)",
            (source, log_path, _now()),
        )
        await conn.commit()
        return cursor.lastrowid  # type: ignore[return-value]


async def save_step(session_id: int, payload: dict) -> None:
    """Persist one judged step payload (the dict produced by _build_payload)."""
    async with aiosqlite.connect(_DB_PATH) as conn:
        await conn.execute(
            """
            INSERT INTO analysis_steps
                (session_id, step, reasoning, tool, args_json,
                 divergence_score, flagged, explanation, rule_name, severity)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                session_id,
                payload["step"],
                payload["reasoning"],
                payload["tool"],
                json.dumps(payload["args"]),
                payload["divergence_score"],
                int(payload["flagged"]),
                payload["explanation"],
                payload.get("rule_name"),
                payload.get("severity"),
            ),
        )
        await conn.commit()


async def close_session(session_id: int) -> None:
    """Set completed_at, total_steps, and flagged_count for a finished session."""
    async with aiosqlite.connect(_DB_PATH) as conn:
        await conn.execute(
            """
            UPDATE sessions
            SET completed_at  = ?,
                total_steps   = (SELECT COUNT(*) FROM analysis_steps WHERE session_id = ?),
                flagged_count = (SELECT COUNT(*) FROM analysis_steps WHERE session_id = ? AND flagged = 1)
            WHERE id = ?
            """,
            (_now(), session_id, session_id, session_id),
        )
        await conn.commit()


async def list_sessions() -> list[dict]:
    """Return all sessions, most-recent-first."""
    async with aiosqlite.connect(_DB_PATH) as conn:
        conn.row_factory = aiosqlite.Row
        cursor = await conn.execute(
            "SELECT * FROM sessions ORDER BY id DESC"
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]


async def get_session_steps(session_id: int) -> list[dict]:
    """Return all steps for a session, ordered by step number."""
    async with aiosqlite.connect(_DB_PATH) as conn:
        conn.row_factory = aiosqlite.Row
        cursor = await conn.execute(
            "SELECT * FROM analysis_steps WHERE session_id = ? ORDER BY step ASC",
            (session_id,),
        )
        rows = await cursor.fetchall()
        result = []
        for r in rows:
            row = dict(r)
            row["args"] = json.loads(row.pop("args_json"))
            row["flagged"] = bool(row["flagged"])
            result.append(row)
        return result


async def get_session(session_id: int) -> dict | None:
    """Return a single session row, or None if not found."""
    async with aiosqlite.connect(_DB_PATH) as conn:
        conn.row_factory = aiosqlite.Row
        cursor = await conn.execute(
            "SELECT * FROM sessions WHERE id = ?",
            (session_id,),
        )
        row = await cursor.fetchone()
        return dict(row) if row else None
