"""Mixin: lore + ricerca FTS5/LIKE + iniezione contesto RAG."""
from __future__ import annotations

import sqlite3
from typing import Optional

from config import SEALED_MARKER

from .models import Lore
from ._fts import fts_words


def _row_to_lore(row) -> Lore:
    """Costruisce un Lore da una riga; sostituisce description col marker
    di sigillo se `sealed=1` (la description reale è cifrata lato sito e
    non è qui — l'LLM deve sapere che esiste ma non rivelarla)."""
    d = dict(row)
    if d.get("sealed"):
        d["description"] = SEALED_MARKER
    return Lore(**{k: d.get(k) for k in (
        "id", "name", "kind", "description", "tags",
        "secret", "sealed", "deleted_at", "origin", "remote_id",
        "created_at", "updated_at",
    ) if k in d})


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
        self._emit("lore", "upsert", {
            "name": name, "kind": kind, "description": description,
            "tags": tags, "updated_at": now,
        })
        return cur.lastrowid

    def remove_lore(self, name: str, kind: Optional[str] = None) -> int:
        if kind:
            cur = self._conn.execute("DELETE FROM lore WHERE name=? AND kind=?", (name, kind))
        else:
            cur = self._conn.execute("DELETE FROM lore WHERE name=?", (name,))
        self._conn.commit()
        if cur.rowcount:
            self._emit("lore", "delete", {
                "name": name, "kind": kind, "updated_at": self._now(),
            })
        return cur.rowcount

    # ------------------------------------------------------------------
    # Merge da remoto (sync). Chiamato da src/sync.py quando arriva una
    # push dal sito o un delta dal pull HTTP. Idempotente: applica solo
    # se il timestamp remoto è più recente del locale.
    # Sopprime self.on_write per la durata dell'operazione (evita echo).
    # ------------------------------------------------------------------
    def merge_lore_from_remote(self, payload: dict) -> str:
        """Applica un cambio di lore proveniente dal sito.

        payload obbligatorio: name, kind, updated_at.
        Opzionali: description, tags (list[str] o stringa CSV legacy),
        secret, sealed, visibility, remote_id, deleted_at.

        Ritorna 'inserted' | 'updated' | 'deleted' | 'skipped'.
        """
        self._sync_local.suppressed = True
        try:
            name = payload["name"]
            kind = payload["kind"]
            remote_ts = payload.get("updated_at") or self._now()
            cur = self._conn.execute(
                "SELECT id, updated_at FROM lore WHERE name=? AND kind=?",
                (name, kind),
            )
            row = cur.fetchone()
            # Tombstone (delete dal sito)
            if payload.get("deleted_at"):
                if row:
                    self._conn.execute(
                        "DELETE FROM lore WHERE id=?", (row["id"],),
                    )
                    self._conn.commit()
                    return "deleted"
                return "skipped"
            # Server-wins: applico sempre quando il record non esiste oppure
            # quando il remote_ts è >= locale.
            if row and row["updated_at"] and remote_ts < row["updated_at"]:
                return "skipped"
            description = payload.get("description", "")
            # tags puo' arrivare come list[str] (nuovo formato) o stringa CSV
            # (legacy). Normalizzo a CSV per la colonna `tags` (usata da FTS5)
            # e a list per la tabella lore_tags.
            raw_tags = payload.get("tags")
            tag_list: list[str] = []
            if isinstance(raw_tags, list):
                tag_list = [str(t).strip().lower() for t in raw_tags if str(t).strip()]
            elif isinstance(raw_tags, str) and raw_tags.strip():
                tag_list = [t.strip().lower() for t in raw_tags.split(",") if t.strip()]
            tags_csv = ", ".join(tag_list) if tag_list else None
            secret = 1 if payload.get("secret") else 0
            sealed = 1 if payload.get("sealed") else 0
            remote_id = payload.get("remote_id")
            origin = payload.get("origin", "site")
            now = self._now()
            self._conn.execute(
                "INSERT OR REPLACE INTO lore("
                "  name, kind, description, tags, created_at, updated_at, "
                "  secret, sealed, deleted_at, origin, remote_id) "
                "VALUES (?, ?, ?, ?, "
                "  COALESCE((SELECT created_at FROM lore WHERE name=? AND kind=?), ?), "
                "  ?, ?, ?, NULL, ?, ?)",
                (name, kind, description, tags_csv,
                 name, kind, now, remote_ts, secret, sealed, origin, remote_id),
            )
            # Replace tag list in lore_tags
            lore_row = self._conn.execute(
                "SELECT id FROM lore WHERE name=? AND kind=?", (name, kind),
            ).fetchone()
            if lore_row is not None:
                lore_id = lore_row["id"]
                self._conn.execute("DELETE FROM lore_tags WHERE lore_id=?", (lore_id,))
                for tag in set(tag_list):
                    self._conn.execute(
                        "INSERT OR IGNORE INTO lore_tags(lore_id, tag) VALUES (?, ?)",
                        (lore_id, tag),
                    )
            self._conn.commit()
            return "updated" if row else "inserted"
        finally:
            self._sync_local.suppressed = False

    def all_lore(self) -> list[Lore]:
        cur = self._conn.execute(
            "SELECT id, name, kind, description, tags, sealed "
            "FROM lore WHERE deleted_at IS NULL ORDER BY kind, name"
        )
        return [_row_to_lore(r) for r in cur.fetchall()]

    def search_lore(self, query: str, limit: int = 5) -> list[Lore]:
        """Tag-boost + name-boost + FTS5 + fallback LIKE.

        Priorità:
          1. Voci taggate con un tag presente nella query (peso massimo).
          2. Voci il cui NOME contiene una parola della query.
          3. FTS5 bm25 sul resto.
        """
        words = fts_words(query)
        if not words:
            return []
        wl = [w.lower() for w in words]

        # Pass 0: tag-boost — match esatto fra parola della query (normalizzata)
        # e tag in lore_tags. Slug normalizzato lato Pi: lowercase, [a-z0-9_-].
        tag_candidates = {
            "".join(c for c in w.lower() if c.isalnum() or c in "-_")
            for w in words
        }
        tag_candidates.discard("")
        tag_ids: list[int] = []
        if tag_candidates:
            try:
                placeholders = ",".join("?" * len(tag_candidates))
                cur = self._conn.execute(
                    f"SELECT DISTINCT lore_id FROM lore_tags "
                    f"WHERE tag IN ({placeholders})",
                    list(tag_candidates),
                )
                tag_ids = [r["lore_id"] for r in cur.fetchall()]
            except sqlite3.OperationalError:
                # Tabella lore_tags non ancora migrata: ignora.
                pass
        tag_boost: list[Lore] = []
        if tag_ids:
            placeholders = ",".join("?" * len(tag_ids))
            cur = self._conn.execute(
                f"SELECT id, name, kind, description, tags, sealed "
                f"FROM lore WHERE id IN ({placeholders}) AND deleted_at IS NULL",
                tag_ids,
            )
            tag_boost = [_row_to_lore(r) for r in cur.fetchall()]

        # Pass 1: boost — lore con nome che contiene una parola della query.
        # RANK fra i boost: il nome che matcha PIÙ parole vince (es. "Pianeta
        # Carota" matcha 2 parole su "Chi vive sul Pianeta Carota?" e batte
        # gli altri pianeti che ne matchano solo 1).
        like_name = [f"%{w}%" for w in words]
        clause_name = " OR ".join(["name LIKE ?"] * len(words))
        cur = self._conn.execute(
            f"SELECT id, name, kind, description, tags, sealed "
            f"FROM lore WHERE deleted_at IS NULL AND ({clause_name})",
            like_name,
        )
        raw_boost = [_row_to_lore(r) for r in cur.fetchall()]
        # Ordino per numero di parole della query trovate nel nome (desc),
        # poi a parità nome più corto (più specifico) vince.
        def _name_score(lore_obj):
            n = lore_obj.name.lower()
            hits = sum(1 for w in wl if w in n)
            return (-hits, len(lore_obj.name))
        boost = sorted(raw_boost, key=_name_score)
        seen_ids = {b.id for b in tag_boost} | {b.id for b in boost}

        # Pass 2: FTS5 ordinato per rank
        fts_q = " OR ".join(words)
        rest: list[Lore] = []
        try:
            cur = self._conn.execute(
                "SELECT l.id, l.name, l.kind, l.description, l.tags, l.sealed "
                "FROM lore l JOIN lore_fts f ON l.id = f.rowid "
                "WHERE lore_fts MATCH ? AND l.deleted_at IS NULL "
                "ORDER BY rank LIMIT ?",
                (fts_q, limit * 2),
            )
            rest = [_row_to_lore(r) for r in cur.fetchall() if r["id"] not in seen_ids]
        except sqlite3.OperationalError:
            pass

        # Merge ordine: tag-boost > name-boost > FTS, deduplicato.
        boost_filtered = [b for b in boost if b.id not in {t.id for t in tag_boost}]
        merged = tag_boost + boost_filtered + rest
        if merged:
            try:
                from config import log_event
                log_event(
                    "rag.lore_search",
                    q=query[:60],
                    tag_hits=len(tag_boost),
                    name_hits=len(boost_filtered),
                    fts_hits=len(rest),
                )
            except Exception:
                pass
            return merged[:limit]

        # Fallback LIKE su description (caso FTS spento)
        clause_desc = " OR ".join(["description LIKE ?"] * len(words))
        cur = self._conn.execute(
            f"SELECT id, name, kind, description, tags, sealed "
            f"FROM lore WHERE deleted_at IS NULL AND ({clause_desc}) LIMIT ?",
            like_name + [limit],
        )
        return [_row_to_lore(r) for r in cur.fetchall()]

    def lore_context_for(self, user_text: str, max_entries: int = 5) -> str:
        matches = self.search_lore(user_text, limit=max_entries)
        if not matches:
            return ""
        lines = [m.to_context_line() for m in matches]
        return (
            "\n\nCONTESTO RILEVANTE (lore della campagna, usa questo "
            "sapere se pertinente):\n" + "\n".join(lines)
        )
