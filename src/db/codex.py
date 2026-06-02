"""Mixin: codex (resoconti narrativi)."""
from __future__ import annotations

import sqlite3
from typing import Optional

from config import MASTER_NAME, SEALED_MARKER

from .models import CodexEntry
from ._fts import fts_words


def _row_to_codex(row) -> CodexEntry:
    d = dict(row)
    if d.get("sealed"):
        d["body"] = SEALED_MARKER
    return CodexEntry(**{k: d.get(k) for k in (
        "id", "title", "body", "happened_at", "tags",
        "secret", "sealed", "deleted_at", "origin", "remote_id",
        "created_at", "updated_at",
    ) if k in d})


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
        self._emit("codex", "upsert", {
            "title": title, "body": body, "happened_at": happened_at,
            "tags": tags, "updated_at": now,
        })
        return cur.lastrowid

    def append_codex(self, title: str, additional_body: str) -> int:
        cur = self._conn.execute(
            "SELECT id, body FROM codex WHERE title = ? "
            "AND deleted_at IS NULL ORDER BY id DESC LIMIT 1",
            (title,),
        )
        row = cur.fetchone()
        if row is None:
            return self.add_codex(title, additional_body)
        new_body = (row["body"] + "\n\n" + additional_body).strip()
        now = self._now()
        self._conn.execute(
            "UPDATE codex SET body = ?, updated_at = ? WHERE id = ?",
            (new_body, now, row["id"]),
        )
        self._conn.commit()
        self._emit("codex", "upsert", {
            "title": title, "body": new_body, "updated_at": now,
        })
        return row["id"]

    def remove_codex(self, title: str) -> int:
        cur = self._conn.execute("DELETE FROM codex WHERE title = ?", (title,))
        self._conn.commit()
        if cur.rowcount:
            self._emit("codex", "delete", {
                "title": title, "updated_at": self._now(),
            })
        return cur.rowcount

    def all_codex(self, limit: int = 100) -> list[CodexEntry]:
        cur = self._conn.execute(
            "SELECT id, title, body, happened_at, tags, sealed FROM codex "
            "WHERE deleted_at IS NULL "
            "ORDER BY happened_at DESC NULLS LAST, id DESC LIMIT ?",
            (limit,),
        )
        return [_row_to_codex(r) for r in cur.fetchall()]

    def merge_codex_from_remote(self, payload: dict) -> str:
        """Server-wins merge da sito. Vedi LoreMixin.merge_lore_from_remote."""
        self._sync_local.suppressed = True
        try:
            title = payload["title"]
            remote_ts = payload.get("updated_at") or self._now()
            cur = self._conn.execute(
                "SELECT id, updated_at FROM codex WHERE title=?",
                (title,),
            )
            row = cur.fetchone()
            if payload.get("deleted_at"):
                if row:
                    self._conn.execute("DELETE FROM codex WHERE id=?", (row["id"],))
                    self._conn.commit()
                    return "deleted"
                return "skipped"
            if row and row["updated_at"] and remote_ts < row["updated_at"]:
                return "skipped"
            body = payload.get("body", "")
            happened_at = payload.get("happened_at")
            tags = payload.get("tags")
            secret = 1 if payload.get("secret") else 0
            sealed = 1 if payload.get("sealed") else 0
            remote_id = payload.get("remote_id")
            origin = payload.get("origin", "site")
            now = self._now()
            if row:
                self._conn.execute(
                    "UPDATE codex SET body=?, happened_at=?, tags=?, "
                    "updated_at=?, secret=?, sealed=?, origin=?, remote_id=?, "
                    "deleted_at=NULL WHERE id=?",
                    (body, happened_at, tags, remote_ts, secret, sealed,
                     origin, remote_id, row["id"]),
                )
                self._conn.commit()
                return "updated"
            self._conn.execute(
                "INSERT INTO codex(title, body, happened_at, tags, "
                "created_at, updated_at, secret, sealed, origin, remote_id) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (title, body, happened_at, tags, now, remote_ts,
                 secret, sealed, origin, remote_id),
            )
            self._conn.commit()
            return "inserted"
        finally:
            self._sync_local.suppressed = False

    def search_codex(self, query: str, limit: int = 3) -> list[CodexEntry]:
        words = fts_words(query)
        if not words:
            return []
        fts_q = " OR ".join(words)
        try:
            cur = self._conn.execute(
                "SELECT c.id, c.title, c.body, c.happened_at, c.tags, c.sealed "
                "FROM codex c JOIN codex_fts f ON c.id = f.rowid "
                "WHERE codex_fts MATCH ? AND c.deleted_at IS NULL "
                "ORDER BY rank LIMIT ?",
                (fts_q, limit),
            )
            rows = cur.fetchall()
            if rows:
                return [_row_to_codex(r) for r in rows]
        except sqlite3.OperationalError:
            pass

        like_terms = [f"%{w}%" for w in words]
        clause = " OR ".join(["title LIKE ? OR body LIKE ?"] * len(words))
        params = []
        for t in like_terms:
            params.extend([t, t])
        params.append(limit)
        cur = self._conn.execute(
            f"SELECT id, title, body, happened_at, tags, sealed FROM codex "
            f"WHERE deleted_at IS NULL AND ({clause}) LIMIT ?",
            params,
        )
        return [_row_to_codex(r) for r in cur.fetchall()]

    def codex_context_for(self, user_text: str, max_entries: int = 5) -> str:
        matches = self.search_codex(user_text, limit=max_entries)
        # Per domande temporali ("ultimo", "prossimo", "recente", "ora", "dopo",
        # "destinazione") aggiungo anche le ultime N voci per ID, perché spesso
        # la risposta sta nell'ultima sessione anche se la query non matcha le
        # sue parole esatte.
        tl = user_text.lower()
        temporal = any(k in tl for k in (
            "ultim", "recent", "prossim", "ora", "dopo",
            "destinazion", "siamo", "abbiamo", "succederà",
        ))
        if temporal:
            recent = self.all_codex(limit=3)
            seen_ids = {m.id for m in matches}
            for r in recent:
                if r.id not in seen_ids:
                    matches.append(r)
                    seen_ids.add(r.id)
        if not matches:
            return ""
        lines = [m.to_context_line() for m in matches]
        return (
            "\n\nMEMORIA NARRATIVA (eventi realmente accaduti nelle "
            f"sessioni passate; sono la VERITÀ vissuta da {MASTER_NAME} e prevalgono "
            "sul lore generale quando la domanda è 'cosa è successo', "
            "'ultimo', 'recente', 'dove siamo stati'):\n"
            + "\n".join(lines)
        )
