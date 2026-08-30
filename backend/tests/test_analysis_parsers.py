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
from pineapple.analysis.parsers.accounts import parse_accounts
from pineapple.analysis.parsers.calendar import parse_calendar
from pineapple.analysis.parsers.calls import parse_calls
from pineapple.analysis.parsers.contacts import parse_contacts
from pineapple.analysis.parsers.files import index_files
from pineapple.analysis.parsers.messages import parse_messages
from pineapple.analysis.parsers.notes import parse_notes, walk_protobuf_string
from pineapple.analysis.parsers.photos import parse_photos
from pineapple.analysis.parsers.safari import (
    parse_safari_bookmarks,
    parse_safari_history,
)
from pineapple.analysis.parsers.voicemail import parse_voicemail
from pineapple.analysis.parsers.whatsapp import parse_whatsapp
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


def test_parse_safari_history_joins_items_and_visits(
    conn: sqlite3.Connection, backup: Path
) -> None:
    written = parse_safari_history(
        _source(backup, "HomeDomain", "Library/Safari/History.db"), conn
    )

    assert written == 2
    rows = conn.execute("SELECT * FROM safari_history ORDER BY visit_utc").fetchall()
    assert rows[0]["url"] == "https://apple.com/"
    assert rows[0]["title"] == "Apple"
    assert rows[0]["visit_count"] == 3
    assert rows[0]["visit_utc"].startswith("2023-")


def test_parse_safari_bookmarks_keeps_leaves_with_folder(
    conn: sqlite3.Connection, backup: Path
) -> None:
    written = parse_safari_bookmarks(
        _source(backup, "HomeDomain", "Library/Safari/Bookmarks.db"), conn
    )

    assert written == 1
    row = conn.execute("SELECT * FROM safari_bookmarks").fetchone()
    assert row["title"] == "Apple"
    assert row["url"] == "https://apple.com/"
    assert row["folder"] == "Favorites"


def test_parse_whatsapp_fills_chats_and_messages(
    conn: sqlite3.Connection, backup: Path
) -> None:
    written = parse_whatsapp(
        _source(
            backup,
            "AppDomainGroup-group.net.whatsapp.WhatsApp.shared",
            "ChatStorage.sqlite",
        ),
        conn,
    )

    assert written == 2
    chat = conn.execute("SELECT * FROM whatsapp_chats").fetchone()
    assert chat["name"] == "Alice"
    assert chat["message_count"] == 2
    rows = conn.execute("SELECT * FROM whatsapp_messages ORDER BY rowid").fetchall()
    assert rows[0]["text"] == "hi"
    assert rows[0]["from_me"] == 0
    assert rows[0]["media_type"] == "text"
    assert rows[1]["from_me"] == 1
    assert rows[1]["media_type"] == "image"
    assert rows[1]["chat_name"] == "Alice"


def test_parse_photos_reads_assets_and_albums(
    conn: sqlite3.Connection, backup: Path
) -> None:
    written = parse_photos(
        _source(backup, "CameraRollDomain", "Media/PhotoData/Photos.sqlite"), conn
    )

    assert written == 2
    rows = conn.execute("SELECT * FROM photos ORDER BY rowid").fetchall()
    assert rows[0]["filename"] == "IMG_0001.HEIC"
    assert rows[0]["kind"] == "image"
    assert rows[0]["favorite"] == 1
    assert rows[0]["latitude"] == 37.33
    assert rows[0]["created_utc"].startswith("2023-")
    assert rows[0]["file_id"] == file_id(
        "CameraRollDomain", "Media/DCIM/100APPLE/IMG_0001.HEIC"
    )
    assert rows[1]["kind"] == "video"
    assert rows[1]["hidden"] == 1
    assert rows[1]["latitude"] is None

    albums = conn.execute("SELECT * FROM photo_albums").fetchall()
    assert [a["title"] for a in albums] == ["Holidays"]
    assert albums[0]["count"] == 12
    assert albums[0]["kind"] == "user"


def test_parse_calendar_joins_calendar_location_and_invitees(
    conn: sqlite3.Connection, backup: Path
) -> None:
    written = parse_calendar(
        _source(backup, "HomeDomain", "Library/Calendar/Calendar.sqlitedb"), conn
    )

    assert written == 2
    rows = conn.execute("SELECT * FROM calendar_events ORDER BY rowid").fetchall()
    assert rows[0]["title"] == "Standup"
    assert rows[0]["calendar"] == "Work"
    assert rows[0]["location"] == "Room 4"
    assert rows[0]["all_day"] == 0
    assert rows[0]["start_utc"].startswith("2023-")
    assert rows[0]["invitees"] == "Ada; grace@example.com"
    assert rows[1]["all_day"] == 1
    assert rows[1]["invitees"] is None


def test_parse_voicemail_reads_caller_duration_and_trashed(
    conn: sqlite3.Connection, backup: Path
) -> None:
    written = parse_voicemail(
        _source(backup, "HomeDomain", "Library/Voicemail/voicemail.db"), conn
    )

    assert written == 2
    rows = conn.execute("SELECT * FROM voicemail ORDER BY rowid").fetchall()
    assert rows[0]["sender"] == "+15551234567"
    assert rows[0]["duration_seconds"] == 23
    assert rows[0]["trashed"] == 0
    assert rows[0]["transcript"] == "Call me back"
    assert rows[0]["received_utc"].startswith("20")
    assert rows[1]["trashed"] == 1


def test_parse_accounts_joins_account_type(
    conn: sqlite3.Connection, backup: Path
) -> None:
    written = parse_accounts(
        _source(backup, "HomeDomain", "Library/Accounts/Accounts3.sqlite"), conn
    )

    assert written == 1
    row = conn.execute("SELECT * FROM accounts").fetchone()
    assert row["type"] == "IMAP"
    assert row["identifier"] == "AAAA-1111"
    assert row["description"] == "Work mail"
    assert row["username"] == "ada@example.com"
    assert row["credential_type"] == "com.apple.account.IMAP"
    assert row["added_utc"].startswith("2023-")


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


@pytest.mark.parametrize(
    "parser",
    [
        parse_messages,
        parse_notes,
        parse_photos,
        parse_calendar,
        parse_voicemail,
        parse_accounts,
        parse_calls,
        parse_contacts,
        parse_safari_history,
        parse_safari_bookmarks,
        parse_whatsapp,
    ],
)
def test_parser_raises_artifact_unreadable_on_a_bad_db(
    conn: sqlite3.Connection, tmp_path: Path, parser: object
) -> None:
    broken = tmp_path / "source.db"
    broken.write_bytes(b"SQLite format 3\x00 but not really")

    with pytest.raises(ArtifactUnreadable):
        parser(broken, conn)  # type: ignore[operator]


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
