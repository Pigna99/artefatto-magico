"""Mixin: lore + ricerca FTS5/LIKE + iniezione contesto RAG."""
from __future__ import annotations

import sqlite3
from typing import Optional

from .models import Lore
from ._fts import fts_words


class LoreMixin:
    _conn: sqlite3.Connection
    _now: callable

    def add_lore(self, name: str, kind: str, description: str,
                 tags: Optional[str] = None) -> int:
        now = self._now()
        cur = self._conn.execute(
            "INSERT OR REPLACE INTO lore(name, kind, description, tags, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, COALESCE((SELECT created_at FROM lore WHERE name=? AND kind=?), ?), ?)",
            (name, kind, description, tags, name, kind, now, now),
        )
        self._conn.commit()
        return cur.lastrowid

    def remove_lore(self, name: str, kind: Optional[str] = None) -> int:
        if kind:
            cur = self._conn.execute("DELETE FROM lore WHERE name=? AND kind=?", (name, kind))
        else:
            cur = self._conn.execute("DELETE FROM lore WHERE name=?", (name,))
        self._conn.commit()
        return cur.rowcount

    def all_lore(self) -> list[Lore]:
        cur = self._conn.execute(
            "SELECT id, name, kind, description, tags FROM lore ORDER BY kind, name"
        )
        return [Lore(**dict(r)) for r in cur.fetchall()]

    def search_lore(self, query: str, limit: int = 5) -> list[Lore]:
        """FTS5 con fallback LIKE."""
        words = fts_words(query)
        if not words:
            return []
        fts_q = " OR ".join(words)
        try:
            cur = self._conn.execute(
                "SELECT l.id, l.name, l.kind, l.description, l.tags "
                "FROM lore l JOIN lore_fts f ON l.id = f.rowid "
                "WHERE lore_fts MATCH ? "
                "ORDER BY rank LIMIT ?",
                (fts_q, limit),
            )
            rows = cur.fetchall()
            if rows:
                return [Lore(**dict(r)) for r in rows]
        except sqlite3.OperationalError:
            pass

        like_terms = [f"%{w}%" for w in words]
        clause = " OR ".join(["name LIKE ? OR description LIKE ?"] * len(words))
        params = []
        for t in like_terms:
            params.extend([t, t])
        params.append(limit)
        cur = self._conn.execute(
            f"SELECT id, name, kind, description, tags FROM lore WHERE {clause} LIMIT ?",
            params,
        )
        return [Lore(**dict(r)) for r in cur.fetchall()]

    def lore_context_for(self, user_text: str, max_entries: int = 5) -> str:
        matches = self.search_lore(user_text, limit=max_entries)
        if not matches:
            return ""
        lines = [m.to_context_line() for m in matches]
        return (
            "\n\nCONTESTO RILEVANTE (lore della campagna, usa questo "
            "sapere se pertinente):\n" + "\n".join(lines)
        )
