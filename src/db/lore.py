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
        """FTS5 con fallback LIKE + boost name-match.

        Il rank di FTS5 (bm25) può relegare un nome di lore esatto sotto
        risultati con token più rari ma meno pertinenti. Compensiamo cercando
        prima i lore il cui NOME contiene una delle parole della query.
        """
        words = fts_words(query)
        if not words:
            return []

        # Pass 1: boost — lore con nome che contiene una parola della query.
        # RANK fra i boost: il nome che matcha PIÙ parole vince (es. "Pianeta
        # Carota" matcha 2 parole su "Chi vive sul Pianeta Carota?" e batte
        # gli altri pianeti che ne matchano solo 1).
        like_name = [f"%{w}%" for w in words]
        clause_name = " OR ".join(["name LIKE ?"] * len(words))
        cur = self._conn.execute(
            f"SELECT id, name, kind, description, tags FROM lore WHERE {clause_name}",
            like_name,
        )
        raw_boost = [Lore(**dict(r)) for r in cur.fetchall()]
        # Ordino per numero di parole della query trovate nel nome (desc),
        # poi a parità nome più corto (più specifico) vince.
        wl = [w.lower() for w in words]
        def _name_score(lore_obj):
            n = lore_obj.name.lower()
            hits = sum(1 for w in wl if w in n)
            return (-hits, len(lore_obj.name))
        boost = sorted(raw_boost, key=_name_score)
        boost_ids = {b.id for b in boost}

        # Pass 2: FTS5 ordinato per rank
        fts_q = " OR ".join(words)
        rest: list[Lore] = []
        try:
            cur = self._conn.execute(
                "SELECT l.id, l.name, l.kind, l.description, l.tags "
                "FROM lore l JOIN lore_fts f ON l.id = f.rowid "
                "WHERE lore_fts MATCH ? "
                "ORDER BY rank LIMIT ?",
                (fts_q, limit * 2),
            )
            rest = [Lore(**dict(r)) for r in cur.fetchall() if r["id"] not in boost_ids]
        except sqlite3.OperationalError:
            pass

        # Merge: prima i name-match, poi FTS, deduplicato, tagliato a limit
        merged = boost + rest
        if merged:
            return merged[:limit]

        # Fallback LIKE su description (caso FTS spento)
        clause_desc = " OR ".join(["description LIKE ?"] * len(words))
        cur = self._conn.execute(
            f"SELECT id, name, kind, description, tags FROM lore WHERE {clause_desc} LIMIT ?",
            like_name + [limit],
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
