"""Database: connessione SQLite + composizione dei mixin."""
from __future__ import annotations

import sqlite3
import threading
import time
from pathlib import Path
from typing import Callable, Optional

from .schema import SCHEMA_SQL, SCHEMA_VERSION
from .sessions import SessionsMixin
from .lore import LoreMixin
from .codex import CodexMixin
from .gm import GmConfigMixin


class Database(SessionsMixin, LoreMixin, CodexMixin, GmConfigMixin):
    """Facade SQLite con FTS5. Tutte le operazioni live in classi-mixin per
    sezione (sessions/lore/codex/gm).

    Sync hook: setta `db.on_write = callback(table, op, payload)` per essere
    notificato dopo ogni write su lore/codex/messages. La callback gira
    sincrona ma deve essere veloce (push asincrono in coda lato consumatore).
    Durante un merge proveniente dal sito, `db._sync_local.suppressed = True`
    sopprime il callback per evitare echo (Pi -> sito -> Pi -> sito ...).
    """

    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._conn.execute("PRAGMA journal_mode = WAL")
        self.on_write: Optional[Callable[[str, str, dict], None]] = None
        self._sync_local = threading.local()
        self._init_schema()

    def _emit(self, table: str, op: str, payload: dict):
        """Notifica il sync layer di una write locale, se registrato e non
        siamo dentro un merge in arrivo dal sito."""
        if self.on_write is None:
            return
        if getattr(self._sync_local, "suppressed", False):
            return
        try:
            self.on_write(table, op, payload)
        except Exception:
            # Non vogliamo che un sync rotto blocchi la TUI.
            pass

    def _init_schema(self):
        with self._conn:
            self._conn.executescript(SCHEMA_SQL)
            cur = self._conn.execute("SELECT version FROM schema_version")
            row = cur.fetchone()
            current = row["version"] if row else 0
            if current < SCHEMA_VERSION:
                self._migrate(current)
                self._conn.execute(
                    "INSERT OR REPLACE INTO schema_version(version) VALUES (?)",
                    (SCHEMA_VERSION,))

    def _migrate(self, from_version: int):
        """Migrazioni idempotenti per DB pre-esistenti. Aggiunge colonne
        nuove senza perdere dati. SQLite non supporta IF NOT EXISTS su
        ALTER TABLE ADD COLUMN, quindi controllo via PRAGMA table_info."""
        def has_col(table: str, col: str) -> bool:
            cur = self._conn.execute(f"PRAGMA table_info({table})")
            return any(r["name"] == col for r in cur.fetchall())

        for table in ("lore", "codex"):
            for col, ddl in (
                ("secret",     "INTEGER NOT NULL DEFAULT 0"),
                ("sealed",     "INTEGER NOT NULL DEFAULT 0"),
                ("deleted_at", "TEXT"),
                ("origin",     "TEXT NOT NULL DEFAULT 'pi'"),
                ("remote_id",  "TEXT"),
            ):
                if not has_col(table, col):
                    self._conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} {ddl}")

        # v5: rilasciamo il vecchio CHECK su lore.kind (limitato a
        # 'npc/pg/place/item/event/note') per accettare i nuovi kind
        # 'faction' / 'knowledge' propagati dal sito.
        # SQLite non supporta DROP CONSTRAINT, quindi sondiamo prima
        # se il CHECK c'e' tentando l'INSERT di un kind ignoto in
        # rollback. Se il vincolo blocca, rebuilda la tabella senza CHECK.
        if from_version < 5:
            try:
                self._conn.execute("SAVEPOINT _check_probe")
                self._conn.execute(
                    "INSERT INTO lore(name,kind,description,created_at,updated_at) "
                    "VALUES ('__probe__','faction','',?,?)",
                    (self._now(), self._now()),
                )
                self._conn.execute("ROLLBACK TO _check_probe")
                self._conn.execute("RELEASE _check_probe")
            except Exception:
                self._conn.execute("ROLLBACK TO _check_probe")
                self._conn.execute("RELEASE _check_probe")
                # Rebuild: copia in tabella temp senza CHECK e rinomina.
                self._conn.executescript(
                    "CREATE TABLE lore_new ("
                    "  id INTEGER PRIMARY KEY AUTOINCREMENT,"
                    "  name TEXT NOT NULL,"
                    "  kind TEXT NOT NULL,"
                    "  description TEXT NOT NULL,"
                    "  tags TEXT,"
                    "  created_at TEXT NOT NULL,"
                    "  updated_at TEXT NOT NULL,"
                    "  secret INTEGER NOT NULL DEFAULT 0,"
                    "  sealed INTEGER NOT NULL DEFAULT 0,"
                    "  deleted_at TEXT,"
                    "  origin TEXT NOT NULL DEFAULT 'pi',"
                    "  remote_id TEXT,"
                    "  UNIQUE(name, kind)"
                    ");"
                    "INSERT INTO lore_new SELECT id,name,kind,description,tags,"
                    "created_at,updated_at,secret,sealed,deleted_at,origin,remote_id FROM lore;"
                    "DROP TABLE lore;"
                    "ALTER TABLE lore_new RENAME TO lore;"
                )

    @staticmethod
    def _now() -> str:
        return time.strftime("%Y-%m-%d %H:%M:%S")

    def close(self):
        try:
            self._conn.close()
        except Exception:
            pass
