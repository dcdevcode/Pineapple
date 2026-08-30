"""The ``analysis.db`` schema: one SQLite file per case, holding the parsed data.

Kept deliberately flat -- one table per artifact kind, ISO-8601 UTC strings for
every timestamp so the frontend never converts. ``case_meta`` mirrors the
essentials of the ``<title>.json`` descriptor for tools that only open the DB.
"""

from __future__ import annotations

import sqlite3

SCHEMA_VERSION = 1

_DDL = """
CREATE TABLE case_meta (
    key   TEXT PRIMARY KEY,
    value TEXT
);

CREATE TABLE backup_info (
    device_name       TEXT,
    product_type      TEXT,
    product_name      TEXT,
    product_version   TEXT,
    build_version     TEXT,
    serial            TEXT,
    udid              TEXT,
    last_backup_date  TEXT,
    is_encrypted      INTEGER NOT NULL DEFAULT 0,
    was_passcode_set  INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE apps (
    bundle_id TEXT PRIMARY KEY,
    name      TEXT,
    version   TEXT
);

CREATE TABLE files (
    file_id       TEXT PRIMARY KEY,
    domain        TEXT NOT NULL,
    relative_path TEXT NOT NULL,
    flags         INTEGER,
    is_dir        INTEGER NOT NULL DEFAULT 0,
    size          INTEGER NOT NULL DEFAULT 0,
    mtime         TEXT,
    ctime         TEXT,
    btime         TEXT,
    mode          INTEGER,
    target        TEXT
);
CREATE INDEX idx_files_domain ON files(domain);

CREATE TABLE messages (
    rowid       INTEGER PRIMARY KEY,
    chat_id     INTEGER,
    address     TEXT,
    service     TEXT,
    is_from_me  INTEGER NOT NULL DEFAULT 0,
    date_utc    TEXT,
    text        TEXT,
    attachments INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX idx_messages_date ON messages(date_utc);

CREATE TABLE calls (
    rowid            INTEGER PRIMARY KEY,
    address          TEXT,
    service          TEXT,
    direction        TEXT,
    date_utc         TEXT,
    duration_seconds INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX idx_calls_date ON calls(date_utc);

CREATE TABLE contacts (
    rowid        INTEGER PRIMARY KEY,
    first        TEXT,
    last         TEXT,
    organization TEXT,
    phones       TEXT,
    emails       TEXT
);
"""


def initialize(conn: sqlite3.Connection) -> None:
    """Create every table on a fresh connection and stamp the schema version."""
    conn.executescript(_DDL)
    conn.execute(
        "INSERT INTO case_meta(key, value) VALUES ('schema_version', ?)",
        (str(SCHEMA_VERSION),),
    )
    conn.commit()
