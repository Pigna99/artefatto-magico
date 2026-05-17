"""Database: connessione SQLite + composizione dei mixin."""
from __future__ import annotations

import sqlite3
import time
from pathlib import Path

from .schema import SCHEMA_SQL, SCHEMA_VERSION
from .sessions import SessionsMixin
from .lore import LoreMixin
from .codex import CodexMixin
from .gm import GmConfigMixin


class Database(SessionsMixin, LoreMixin, CodexMixin, GmConfigMixin):
    """Facade SQLite con FTS5. Tutte le operazioni live in classi-mixin per
    sezione (sessions/lore/codex/gm)."""

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
            if cur.fetchone() is None:
                self._conn.execute("INSERT INTO schema_version(version) VALUES (?)",
                                   (SCHEMA_VERSION,))

    @staticmethod
    def _now() -> str:
        return time.strftime("%Y-%m-%d %H:%M:%S")

    def close(self):
        try:
            self._conn.close()
        except Exception:
            pass
