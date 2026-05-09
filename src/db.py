"""Persistenza SQLite per l'artefatto.

Schema: sessioni, messaggi (user/assistant/gm), lore della campagna,
eventi GM, configurazione k/v. FTS5 sui campi testo del lore per la
ricerca contestuale leggera.

Uso tipico:
    db = Database(Path.home() / "artefatto" / "data" / "artefatto.db")
    sid = db.start_session(model="gemma3:1b", turbo=False)
    db.log_message(sid, "user", "Maestro, chi è Eldrin?")
    db.log_message(sid, "assistant", "Tuo fratello, caduto nelle Lande di Vetro.",
                   model="gemma3:1b", tokens=15, duration_s=2.3)
    matches = db.search_lore("Eldrin")  # → list[Lore]
    db.end_session(sid)
"""
from __future__ import annotations

import re
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional


SCHEMA_VERSION = 1

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY
);

CREATE TABLE IF NOT EXISTS sessions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at  TEXT NOT NULL,
    ended_at    TEXT,
    model_used  TEXT,
    turbo       INTEGER NOT NULL DEFAULT 0,
    notes       TEXT
);

CREATE TABLE IF NOT EXISTS messages (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id  INTEGER REFERENCES sessions(id) ON DELETE CASCADE,
    timestamp   TEXT NOT NULL,
    role        TEXT NOT NULL CHECK (role IN ('user','assistant','gm','system')),
    content     TEXT NOT NULL,
    model       TEXT,
    tokens      INTEGER,
    duration_s  REAL
);
CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id);
CREATE INDEX IF NOT EXISTS idx_messages_role    ON messages(role);

CREATE TABLE IF NOT EXISTS lore (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,
    kind        TEXT NOT NULL CHECK (kind IN ('npc','pg','place','item','event','note')),
    description TEXT NOT NULL,
    tags        TEXT,
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL,
    UNIQUE(name, kind)
);
CREATE INDEX IF NOT EXISTS idx_lore_kind ON lore(kind);

-- FTS5 per ricerca testuale veloce
CREATE VIRTUAL TABLE IF NOT EXISTS lore_fts USING fts5(
    name, description, tags,
    content=lore, content_rowid=id,
    tokenize='unicode61 remove_diacritics 1'
);

CREATE TRIGGER IF NOT EXISTS lore_ai AFTER INSERT ON lore BEGIN
    INSERT INTO lore_fts(rowid, name, description, tags)
    VALUES (new.id, new.name, new.description, COALESCE(new.tags,''));
END;
CREATE TRIGGER IF NOT EXISTS lore_ad AFTER DELETE ON lore BEGIN
    INSERT INTO lore_fts(lore_fts, rowid, name, description, tags)
    VALUES ('delete', old.id, old.name, old.description, COALESCE(old.tags,''));
END;
CREATE TRIGGER IF NOT EXISTS lore_au AFTER UPDATE ON lore BEGIN
    INSERT INTO lore_fts(lore_fts, rowid, name, description, tags)
    VALUES ('delete', old.id, old.name, old.description, COALESCE(old.tags,''));
    INSERT INTO lore_fts(rowid, name, description, tags)
    VALUES (new.id, new.name, new.description, COALESCE(new.tags,''));
END;

-- Codex: voci narrative/cronologiche della campagna (resoconti di sessione,
-- eventi importanti, scoperte). Differisce da `lore` perche' non e' un'entita'
-- ma una "pagina di diario".
CREATE TABLE IF NOT EXISTS codex (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    title       TEXT NOT NULL,
    body        TEXT NOT NULL,
    happened_at TEXT,             -- data narrativa (es. "Sessione 4" o "12/03/2026")
    tags        TEXT,
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_codex_happened ON codex(happened_at);

CREATE VIRTUAL TABLE IF NOT EXISTS codex_fts USING fts5(
    title, body, tags,
    content=codex, content_rowid=id,
    tokenize='unicode61 remove_diacritics 1'
);

CREATE TRIGGER IF NOT EXISTS codex_ai AFTER INSERT ON codex BEGIN
    INSERT INTO codex_fts(rowid, title, body, tags)
    VALUES (new.id, new.title, new.body, COALESCE(new.tags,''));
END;
CREATE TRIGGER IF NOT EXISTS codex_ad AFTER DELETE ON codex BEGIN
    INSERT INTO codex_fts(codex_fts, rowid, title, body, tags)
    VALUES ('delete', old.id, old.title, old.body, COALESCE(old.tags,''));
END;
CREATE TRIGGER IF NOT EXISTS codex_au AFTER UPDATE ON codex BEGIN
    INSERT INTO codex_fts(codex_fts, rowid, title, body, tags)
    VALUES ('delete', old.id, old.title, old.body, COALESCE(old.tags,''));
    INSERT INTO codex_fts(rowid, title, body, tags)
    VALUES (new.id, new.title, new.body, COALESCE(new.tags,''));
END;

CREATE TABLE IF NOT EXISTS gm_events (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp   TEXT NOT NULL,
    session_id  INTEGER REFERENCES sessions(id),
    command     TEXT NOT NULL,
    raw         TEXT,
    response    TEXT,
    consumed    INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_gm_consumed ON gm_events(consumed);

CREATE TABLE IF NOT EXISTS config (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""


@dataclass
class Lore:
    id: int
    name: str
    kind: str
    description: str
    tags: Optional[str] = None

    def to_context_line(self) -> str:
        tag_part = f" [{self.tags}]" if self.tags else ""
        return f"- {self.kind.upper()} {self.name}{tag_part}: {self.description}"


@dataclass
class CodexEntry:
    id: int
    title: str
    body: str
    happened_at: Optional[str] = None
    tags: Optional[str] = None

    def to_context_line(self) -> str:
        when = f" ({self.happened_at})" if self.happened_at else ""
        # Tronco il body a ~200 char per non saturare il context dell'LLM
        body = self.body if len(self.body) <= 200 else self.body[:200] + "..."
        return f"- CODEX{when} {self.title}: {body}"


class Database:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._conn.execute("PRAGMA journal_mode = WAL")
        self._init_schema()

    def _init_schema(self):
        with self._conn:
            self._conn.executescript(SCHEMA_SQL)
            cur = self._conn.execute("SELECT version FROM schema_version")
            row = cur.fetchone()
            if row is None:
                self._conn.execute("INSERT INTO schema_version(version) VALUES (?)",
                                   (SCHEMA_VERSION,))

    def close(self):
        try:
            self._conn.close()
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Sessions
    # ------------------------------------------------------------------

    def start_session(self, model: str, turbo: bool = False) -> int:
        cur = self._conn.execute(
            "INSERT INTO sessions(started_at, model_used, turbo) VALUES (?, ?, ?)",
            (_now(), model, 1 if turbo else 0),
        )
        self._conn.commit()
        return cur.lastrowid

    def end_session(self, session_id: int):
        self._conn.execute(
            "UPDATE sessions SET ended_at = ? WHERE id = ?",
            (_now(), session_id),
        )
        self._conn.commit()

    # ------------------------------------------------------------------
    # Messages
    # ------------------------------------------------------------------

    def log_message(self, session_id: Optional[int], role: str, content: str,
                    model: Optional[str] = None, tokens: Optional[int] = None,
                    duration_s: Optional[float] = None) -> int:
        cur = self._conn.execute(
            "INSERT INTO messages(session_id, timestamp, role, content, model, tokens, duration_s) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (session_id, _now(), role, content, model, tokens, duration_s),
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

    # ------------------------------------------------------------------
    # Lore
    # ------------------------------------------------------------------

    def add_lore(self, name: str, kind: str, description: str,
                 tags: Optional[str] = None) -> int:
        now = _now()
        cur = self._conn.execute(
            "INSERT OR REPLACE INTO lore(name, kind, description, tags, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, COALESCE((SELECT created_at FROM lore WHERE name=? AND kind=?), ?), ?)",
            (name, kind, description, tags, name, kind, now, now),
        )
        self._conn.commit()
        return cur.lastrowid

    def remove_lore(self, name: str, kind: Optional[str] = None) -> int:
        if kind:
            cur = self._conn.execute("DELETE FROM lore WHERE name=? AND kind=?",
                                     (name, kind))
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
        """FTS5 match. Se la query e' troppo vaga (1 token corto) usa LIKE."""
        query = query.strip()
        if not query:
            return []
        # Estraggo parole significative (>= 3 char, niente stopword grezza)
        words = [w for w in re.findall(r"\w+", query, re.UNICODE)
                 if len(w) >= 3]
        if not words:
            return []

        # Costruisco una query FTS con OR fra le parole
        fts_query = " OR ".join(words)
        try:
            cur = self._conn.execute(
                "SELECT l.id, l.name, l.kind, l.description, l.tags "
                "FROM lore l JOIN lore_fts f ON l.id = f.rowid "
                "WHERE lore_fts MATCH ? "
                "ORDER BY rank LIMIT ?",
                (fts_query, limit),
            )
            rows = cur.fetchall()
            if rows:
                return [Lore(**dict(r)) for r in rows]
        except sqlite3.OperationalError:
            pass

        # Fallback LIKE (case-insensitive, su nome+description)
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
        """Ritorna un blocco testuale da iniettare nel system prompt, vuoto
        se nessun match. Pensato per essere appeso al prompt esistente."""
        matches = self.search_lore(user_text, limit=max_entries)
        if not matches:
            return ""
        lines = [m.to_context_line() for m in matches]
        return (
            "\n\nCONTESTO RILEVANTE (lore della campagna, usa questo "
            "sapere se pertinente):\n" + "\n".join(lines)
        )

    # ------------------------------------------------------------------
    # Codex (resoconti narrativi)
    # ------------------------------------------------------------------

    def add_codex(self, title: str, body: str,
                  happened_at: Optional[str] = None,
                  tags: Optional[str] = None) -> int:
        now = _now()
        cur = self._conn.execute(
            "INSERT INTO codex(title, body, happened_at, tags, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (title, body, happened_at, tags, now, now),
        )
        self._conn.commit()
        return cur.lastrowid

    def append_codex(self, title: str, additional_body: str) -> int:
        """Appende testo a una voce codex esistente (cerca per titolo).
        Se non esiste, la crea."""
        cur = self._conn.execute(
            "SELECT id, body FROM codex WHERE title = ? ORDER BY id DESC LIMIT 1",
            (title,),
        )
        row = cur.fetchone()
        now = _now()
        if row is None:
            return self.add_codex(title, additional_body)
        new_body = (row["body"] + "\n\n" + additional_body).strip()
        self._conn.execute(
            "UPDATE codex SET body = ?, updated_at = ? WHERE id = ?",
            (new_body, now, row["id"]),
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
        query = query.strip()
        if not query:
            return []
        words = [w for w in re.findall(r"\w+", query, re.UNICODE) if len(w) >= 3]
        if not words:
            return []
        fts_query = " OR ".join(words)
        try:
            cur = self._conn.execute(
                "SELECT c.id, c.title, c.body, c.happened_at, c.tags "
                "FROM codex c JOIN codex_fts f ON c.id = f.rowid "
                "WHERE codex_fts MATCH ? "
                "ORDER BY rank LIMIT ?",
                (fts_query, limit),
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
            "\n\nMEMORIA NARRATIVA (resoconti di sessione passati):\n"
            + "\n".join(lines)
        )

    # ------------------------------------------------------------------
    # GM events (per Telegram in futuro)
    # ------------------------------------------------------------------

    def add_gm_event(self, session_id: Optional[int], command: str,
                     raw: Optional[str] = None) -> int:
        cur = self._conn.execute(
            "INSERT INTO gm_events(timestamp, session_id, command, raw) "
            "VALUES (?, ?, ?, ?)",
            (_now(), session_id, command, raw),
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

    # ------------------------------------------------------------------
    # Config k/v
    # ------------------------------------------------------------------

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


def _now() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S")
