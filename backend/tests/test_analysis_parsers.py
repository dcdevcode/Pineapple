"""Tests for the artifact parsers in :mod:`pineapple.analysis.parsers`."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from analysis_support import (
    ATTRIBUTED_BODY_TEXT,
    BACKUP_FILE_COUNT,
    NOTE_BODY_TEXT,
    build_backup,
    file_id,
)
from pineapple.analysis.errors import ArtifactUnreadable
from pineapple.analysis.parsers.calls import parse_calls
from pineapple.analysis.parsers.contacts import parse_contacts
from pineapple.analysis.parsers.files import index_files
from pineapple.analysis.parsers.messages import parse_messages
from pineapple.analysis.parsers.notes import parse_notes, walk_protobuf_string
from pineapple.analysis.schema import initialize


@pytest.fixture
def conn() -> sqlite3.Connection:
    connection = sqlite3.connect(":memory:")
    initialize(connection)
    connection.row_factory = sqlite3.Row
    return connection


@pytest.fixture
def backup(tmp_path: Path) -> Path:
    return build_backup(tmp_path / "src")


def _source(backup: Path, domain: str, relative_path: str) -> Path:
    fid = file_id(domain, relative_path)
    return backup / fid[:2] / fid


def test_parse_messages(conn: sqlite3.Connection, backup: Path) -> None:
    written = parse_messages(_source(backup, "HomeDomain", "Library/SMS/sms.db"), conn)

    assert written == 3
    rows = conn.execute("SELECT * FROM messages ORDER BY rowid").fetchall()
    assert rows[0]["address"] == "+15551234567"
    assert rows[0]["is_from_me"] == 0
    assert rows[1]["is_from_me"] == 1
    assert rows[0]["date_utc"].startswith("2023-")
    # Row 3 had no plain text -- recovered from attributedBody.
    assert rows[2]["text"] == ATTRIBUTED_BODY_TEXT
    assert rows[2]["attachments"] == 1
    assert rows[0]["chat_id"] == 7


def test_parse_notes_reads_title_folder_snippet_and_body(
    conn: sqlite3.Connection, backup: Path
) -> None:
    written = parse_notes(
        _source(backup, "AppDomainGroup-group.com.apple.notes", "NoteStore.sqlite"),
        conn,
    )

    assert written == 1
    note = conn.execute("SELECT * FROM notes").fetchone()
    assert note["title"] == "Shopping list"
    assert note["folder"] == "Notes"
    assert note["snippet"] == "Shopping list: pineapples"
    assert note["body"] == NOTE_BODY_TEXT
    assert note["created_utc"].startswith("2023-")


def test_walk_protobuf_string_returns_none_off_path() -> None:
    assert walk_protobuf_string(b"\x12\x02hi", (9,)) is None
    assert walk_protobuf_string(b"garbage", (2, 3, 2)) is None


def test_parse_calls_maps_direction_and_service(
    conn: sqlite3.Connection, backup: Path
) -> None:
    written = parse_calls(
        _source(backup, "HomeDomain", "Library/CallHistoryDB/CallHistory.storedata"),
        conn,
    )

    assert written == 3
    rows = conn.execute("SELECT * FROM calls ORDER BY rowid").fetchall()
    assert rows[0]["direction"] == "outgoing"
    assert rows[0]["duration_seconds"] == 42
    assert rows[0]["service"] == "Phone"
    assert rows[1]["direction"] == "missed"
    assert rows[2]["direction"] == "incoming"
    assert rows[2]["service"] == "FaceTime"


def test_parse_contacts_flattens_multivalues(
    conn: sqlite3.Connection, backup: Path
) -> None:
    written = parse_contacts(
        _source(backup, "HomeDomain", "Library/AddressBook/AddressBook.sqlitedb"),
        conn,
    )

    assert written == 2
    ada = conn.execute("SELECT * FROM contacts WHERE rowid = 1").fetchone()
    assert ada["first"] == "Ada"
    assert ada["organization"] == "Analytical Engines"
    assert ada["phones"] == "+15551234567; +15550000000"
    assert ada["emails"] == "ada@example.com"
    hopper = conn.execute("SELECT * FROM contacts WHERE rowid = 2").fetchone()
    assert hopper["phones"] is None


def test_parser_raises_artifact_unreadable_on_a_bad_db(
    conn: sqlite3.Connection, tmp_path: Path
) -> None:
    broken = tmp_path / "sms.db"
    broken.write_bytes(b"SQLite format 3\x00 but not really")

    with pytest.raises(ArtifactUnreadable):
        parse_messages(broken, conn)


def test_index_files_records_dirs_sizes_and_symlink_targets(
    conn: sqlite3.Connection, backup: Path
) -> None:
    manifest = sqlite3.connect(backup / "Manifest.db")
    try:
        written = index_files(manifest, conn)
    finally:
        manifest.close()

    assert written == BACKUP_FILE_COUNT
    link = conn.execute(
        "SELECT * FROM files WHERE relative_path = 'Library/link'"
    ).fetchone()
    assert link["target"] == "SMS/sms.db"
    directory = conn.execute(
        "SELECT is_dir FROM files WHERE relative_path = 'Library/SMS'"
    ).fetchone()
    assert directory["is_dir"] == 1
    sms = conn.execute(
        "SELECT size FROM files WHERE relative_path = 'Library/SMS/sms.db'"
    ).fetchone()
    assert sms["size"] > 0
