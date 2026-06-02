"""DDL del database. Idempotente (CREATE IF NOT EXISTS).

Schema v2: aggiunte colonne per il sync col sito campagna.pignalabs.it.
- secret/sealed: voci GM-only, sealed=true significa che description è
  cifrata lato sito e qui arriva sostituita dal SEALED_MARKER.
- deleted_at: soft-delete per propagare le cancellazioni via sync.
- origin: 'pi' o 'site' — tracciamento dove la voce è nata.
"""

SCHEMA_VERSION = 3

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
    secret      INTEGER NOT NULL DEFAULT 0,
    sealed      INTEGER NOT NULL DEFAULT 0,
    deleted_at  TEXT,
    origin      TEXT NOT NULL DEFAULT 'pi',
    remote_id   TEXT,
    UNIQUE(name, kind)
);
CREATE INDEX IF NOT EXISTS idx_lore_kind ON lore(kind);
CREATE INDEX IF NOT EXISTS idx_lore_updated ON lore(updated_at);

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

-- Tag normalizzati (schema v3). Mirror della tabella postgres lore_tags
-- sul sito. Popolato via sync.py quando arriva un'entry con campo
-- `tags: list[str]`. Usato da search_lore per tag-boost.
CREATE TABLE IF NOT EXISTS lore_tags (
    lore_id  INTEGER NOT NULL REFERENCES lore(id) ON DELETE CASCADE,
    tag      TEXT NOT NULL,
    PRIMARY KEY (lore_id, tag)
);
CREATE INDEX IF NOT EXISTS idx_lore_tags_tag ON lore_tags(tag);

CREATE TABLE IF NOT EXISTS codex (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    title       TEXT NOT NULL,
    body        TEXT NOT NULL,
    happened_at TEXT,
    tags        TEXT,
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL,
    secret      INTEGER NOT NULL DEFAULT 0,
    sealed      INTEGER NOT NULL DEFAULT 0,
    deleted_at  TEXT,
    origin      TEXT NOT NULL DEFAULT 'pi',
    remote_id   TEXT
);
CREATE INDEX IF NOT EXISTS idx_codex_happened ON codex(happened_at);
CREATE INDEX IF NOT EXISTS idx_codex_updated ON codex(updated_at);

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
