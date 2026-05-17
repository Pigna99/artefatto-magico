"""Mixin: eventi GM (Telegram) + config k/v."""
from __future__ import annotations

import sqlite3
from typing import Optional


class GmConfigMixin:
    _conn: sqlite3.Connection
    _now: callable

    def add_gm_event(self, session_id: Optional[int], command: str,
                     raw: Optional[str] = None) -> int:
        cur = self._conn.execute(
            "INSERT INTO gm_events(timestamp, session_id, command, raw) "
            "VALUES (?, ?, ?, ?)",
            (self._now(), session_id, command, raw),
        )
        self._conn.commit()
        return cur.lastrowid

    def pending_gm_events(self) -> list[sqlite3.Row]:
        cur = self._conn.execute(
            "SELECT * FROM gm_events WHERE consumed = 0 ORDER BY id"
        )
        return cur.fetchall()

    def consume_gm_event(self, event_id: int, response: str):
        self._conn.execute(
            "UPDATE gm_events SET consumed = 1, response = ? WHERE id = ?",
            (response, event_id),
        )
        self._conn.commit()

    def get_config(self, key: str, default: Optional[str] = None) -> Optional[str]:
        cur = self._conn.execute("SELECT value FROM config WHERE key = ?", (key,))
        row = cur.fetchone()
        return row["value"] if row else default

    def set_config(self, key: str, value: str):
        self._conn.execute(
            "INSERT INTO config(key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, value),
        )
        self._conn.commit()
