"""The ``analysis.db`` schema: one SQLite file per case, holding the parsed data.

Kept deliberately flat -- one table per artifact kind, ISO-8601 UTC strings for
every timestamp so the frontend never converts. ``case_meta`` mirrors the
essentials of the ``<title>.json`` descriptor for tools that only open the DB.
"""

from __future__ import annotations

import sqlite3

SCHEMA_VERSION = 3

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

-- `flags`, `mode` and `ctime` are captured from the Manifest for forensic
-- completeness; no query reads them yet (the browser shows is_dir / size /
-- mtime / btime / target).
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

CREATE TABLE notes (
    rowid        INTEGER PRIMARY KEY,
    folder       TEXT,
    title        TEXT,
    snippet      TEXT,
    body         TEXT,
    created_utc  TEXT,
    modified_utc TEXT
);

CREATE TABLE safari_history (
    rowid       INTEGER PRIMARY KEY,
    url         TEXT,
    title       TEXT,
    visit_utc   TEXT,
    visit_count INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX idx_safari_history_visit ON safari_history(visit_utc);

CREATE TABLE safari_bookmarks (
    rowid  INTEGER PRIMARY KEY,
    title  TEXT,
    url    TEXT,
    folder TEXT
);

CREATE TABLE whatsapp_chats (
    rowid             INTEGER PRIMARY KEY,
    jid               TEXT,
    name              TEXT,
    last_message_utc  TEXT,
    message_count     INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE whatsapp_messages (
    rowid      INTEGER PRIMARY KEY,
    chat_jid   TEXT,
    chat_name  TEXT,
    from_me    INTEGER NOT NULL DEFAULT 0,
    sender     TEXT,
    date_utc   TEXT,
    text       TEXT,
    media_type TEXT
);
CREATE INDEX idx_whatsapp_messages_date ON whatsapp_messages(date_utc);

-- One row per camera-roll asset. `file_id` is the Manifest id of the asset file
-- itself (domain + relative path hashed), so the browser can preview it.
CREATE TABLE photos (
    rowid       INTEGER PRIMARY KEY,
    file_id     TEXT,
    filename    TEXT,
    directory   TEXT,
    kind        TEXT,
    created_utc TEXT,
    added_utc   TEXT,
    width       INTEGER,
    height      INTEGER,
    favorite    INTEGER NOT NULL DEFAULT 0,
    hidden      INTEGER NOT NULL DEFAULT 0,
    trashed     INTEGER NOT NULL DEFAULT 0,
    latitude    REAL,
    longitude   REAL
);
CREATE INDEX idx_photos_created ON photos(created_utc);

CREATE TABLE photo_albums (
    rowid     INTEGER PRIMARY KEY,
    title     TEXT,
    kind      TEXT,
    count     INTEGER NOT NULL DEFAULT 0,
    start_utc TEXT,
    end_utc   TEXT
);

-- One row per keychain item. `secret` is the decrypted value when the backup
-- keybag could unwrap it; otherwise `secret` is NULL and `secret_error` says why.
CREATE TABLE keychain (
    rowid            INTEGER PRIMARY KEY,
    item_class       TEXT,
    account          TEXT,
    service          TEXT,
    server           TEXT,
    access_group     TEXT,
    protection_class INTEGER,
    created_utc      TEXT,
    modified_utc     TEXT,
    secret           TEXT,
    secret_error     TEXT
);

CREATE TABLE calendar_events (
    rowid     INTEGER PRIMARY KEY,
    calendar  TEXT,
    title     TEXT,
    location  TEXT,
    notes     TEXT,
    start_utc TEXT,
    end_utc   TEXT,
    all_day   INTEGER NOT NULL DEFAULT 0,
    invitees  TEXT
);
CREATE INDEX idx_calendar_events_start ON calendar_events(start_utc);

CREATE TABLE voicemail (
    rowid            INTEGER PRIMARY KEY,
    sender           TEXT,
    received_utc     TEXT,
    duration_seconds INTEGER NOT NULL DEFAULT 0,
    trashed          INTEGER NOT NULL DEFAULT 0,
    transcript       TEXT
);
CREATE INDEX idx_voicemail_received ON voicemail(received_utc);

-- A curated slice of knowledgeC: app usage / focus, backlight, notifications.
CREATE TABLE device_usage (
    rowid            INTEGER PRIMARY KEY,
    stream           TEXT,
    bundle_id        TEXT,
    value            TEXT,
    start_utc        TEXT,
    end_utc          TEXT,
    duration_seconds INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX idx_device_usage_start ON device_usage(start_utc);

CREATE TABLE accounts (
    rowid           INTEGER PRIMARY KEY,
    type            TEXT,
    identifier      TEXT,
    description     TEXT,
    username        TEXT,
    added_utc       TEXT,
    credential_type TEXT
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
