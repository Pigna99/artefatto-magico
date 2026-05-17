"""Mixin: sessioni e messaggi."""
from __future__ import annotations

import sqlite3
from typing import Optional


class SessionsMixin:
    _conn: sqlite3.Connection
    _now: callable

    def start_session(self, model: str, turbo: bool = False) -> int:
        cur = self._conn.execute(
            "INSERT INTO sessions(started_at, model_used, turbo) VALUES (?, ?, ?)",
            (self._now(), model, 1 if turbo else 0),
        )
        self._conn.commit()
        return cur.lastrowid

    def end_session(self, session_id: int):
        self._conn.execute(
            "UPDATE sessions SET ended_at = ? WHERE id = ?",
            (self._now(), session_id),
        )
        self._conn.commit()

    def log_message(self, session_id: Optional[int], role: str, content: str,
                    model: Optional[str] = None, tokens: Optional[int] = None,
                    duration_s: Optional[float] = None) -> int:
        cur = self._conn.execute(
            "INSERT INTO messages(session_id, timestamp, role, content, model, tokens, duration_s) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (session_id, self._now(), role, content, model, tokens, duration_s),
        )
        self._conn.commit()
        return cur.lastrowid

    def recent_messages(self, session_id: int, limit: int = 20) -> list[sqlite3.Row]:
        cur = self._conn.execute(
            "SELECT * FROM messages WHERE session_id = ? "
            "ORDER BY id DESC LIMIT ?",
            (session_id, limit),
        )
        return list(reversed(cur.fetchall()))
