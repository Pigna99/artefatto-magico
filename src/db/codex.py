"""Mixin: codex (resoconti narrativi)."""
from __future__ import annotations

import sqlite3
from typing import Optional

from .models import CodexEntry
from ._fts import fts_words


class CodexMixin:
    _conn: sqlite3.Connection
    _now: callable

    def add_codex(self, title: str, body: str,
                  happened_at: Optional[str] = None,
                  tags: Optional[str] = None) -> int:
        now = self._now()
        cur = self._conn.execute(
            "INSERT INTO codex(title, body, happened_at, tags, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (title, body, happened_at, tags, now, now),
        )
        self._conn.commit()
        return cur.lastrowid

    def append_codex(self, title: str, additional_body: str) -> int:
        cur = self._conn.execute(
            "SELECT id, body FROM codex WHERE title = ? ORDER BY id DESC LIMIT 1",
            (title,),
        )
        row = cur.fetchone()
        if row is None:
            return self.add_codex(title, additional_body)
        new_body = (row["body"] + "\n\n" + additional_body).strip()
        self._conn.execute(
            "UPDATE codex SET body = ?, updated_at = ? WHERE id = ?",
            (new_body, self._now(), row["id"]),
        )
        self._conn.commit()
        return row["id"]

    def remove_codex(self, title: str) -> int:
        cur = self._conn.execute("DELETE FROM codex WHERE title = ?", (title,))
        self._conn.commit()
        return cur.rowcount

    def all_codex(self, limit: int = 100) -> list[CodexEntry]:
        cur = self._conn.execute(
            "SELECT id, title, body, happened_at, tags FROM codex "
            "ORDER BY happened_at DESC NULLS LAST, id DESC LIMIT ?",
            (limit,),
        )
        return [CodexEntry(**dict(r)) for r in cur.fetchall()]

    def search_codex(self, query: str, limit: int = 3) -> list[CodexEntry]:
        words = fts_words(query)
        if not words:
            return []
        fts_q = " OR ".join(words)
        try:
            cur = self._conn.execute(
                "SELECT c.id, c.title, c.body, c.happened_at, c.tags "
                "FROM codex c JOIN codex_fts f ON c.id = f.rowid "
                "WHERE codex_fts MATCH ? "
                "ORDER BY rank LIMIT ?",
                (fts_q, limit),
            )
            rows = cur.fetchall()
            if rows:
                return [CodexEntry(**dict(r)) for r in rows]
        except sqlite3.OperationalError:
            pass

        like_terms = [f"%{w}%" for w in words]
        clause = " OR ".join(["title LIKE ? OR body LIKE ?"] * len(words))
        params = []
        for t in like_terms:
            params.extend([t, t])
        params.append(limit)
        cur = self._conn.execute(
            f"SELECT id, title, body, happened_at, tags FROM codex "
            f"WHERE {clause} LIMIT ?",
            params,
        )
        return [CodexEntry(**dict(r)) for r in cur.fetchall()]

    def codex_context_for(self, user_text: str, max_entries: int = 3) -> str:
        matches = self.search_codex(user_text, limit=max_entries)
        if not matches:
            return ""
        lines = [m.to_context_line() for m in matches]
        return (
            "\n\nMEMORIA NARRATIVA (eventi realmente accaduti nelle "
            "sessioni passate; sono la VERITÀ vissuta da Pigna e prevalgono "
            "sul lore generale quando la domanda è 'cosa è successo', "
            "'ultimo', 'recente', 'dove siamo stati'):\n"
            + "\n".join(lines)
        )
