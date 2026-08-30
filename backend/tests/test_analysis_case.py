"""Tests for :mod:`pineapple.analysis.case`."""

from __future__ import annotations

import base64
import datetime as dt
import plistlib
import shutil
import sqlite3
import threading
from pathlib import Path

import pytest

from analysis_support import (
    BACKUP_FILE_COUNT,
    SERIAL,
    UDID,
    build_backup,
    file_id,
)
from pineapple.analysis.case import _image_mime, _json_safe, _sniff, load_case
from pineapple.analysis.descriptor import (
    CaseDescriptor,
    descriptor_path,
    write_descriptor,
)
from pineapple.analysis.errors import AnalysisError
from pineapple.analysis.metadata import from_plists
from pineapple.analysis.parsers import index_apps, index_backup_info, index_files
from pineapple.analysis.parsers.messages import parse_messages
from pineapple.analysis.schema import initialize


@pytest.fixture
def case_dir(tmp_path: Path) -> Path:
    backup = build_backup(tmp_path / "src")
    case = tmp_path / "case"
    case.mkdir()
    shutil.copytree(backup, case / "backup" / UDID)

    info = plistlib.loads((backup / "Info.plist").read_bytes())
    manifest = plistlib.loads((backup / "Manifest.plist").read_bytes())
    metadata = from_plists(info, manifest, {})

    conn = sqlite3.connect(case / "analysis.db")
    initialize(conn)
    index_backup_info(metadata, conn)
    index_apps(metadata, conn)
    manifest_conn = sqlite3.connect(backup / "Manifest.db")
    index_files(manifest_conn, conn)
    manifest_conn.close()
    fid = file_id("HomeDomain", "Library/SMS/sms.db")
    parse_messages(backup / fid[:2] / fid, conn)
    conn.commit()
    conn.close()

    write_descriptor(
        descriptor_path(case, SERIAL),
        CaseDescriptor(
            title=SERIAL,
            device=metadata.device_dict(),
            source={"path": "x.pineapple", "sha256": "abc", "is_encrypted": False},
            parse={"status": "done", "counts": {"messages": 3}},
        ),
    )
    return case


def test_load_case_exposes_descriptor_and_summary(case_dir: Path) -> None:
    handle = load_case(case_dir)
    try:
        assert handle.descriptor()["title"] == SERIAL
        summary = handle.summary()
        assert summary["device"]["serial"] == SERIAL
        assert summary["counts"]["messages"] == 3
        assert summary["counts"]["files"] == BACKUP_FILE_COUNT
    finally:
        handle.close()


def test_queries_paginate_and_filter(case_dir: Path) -> None:
    handle = load_case(case_dir)
    try:
        page = handle.messages(limit=2, offset=0)
        assert page["total"] == 3
        assert len(page["rows"]) == 2
        assert page["limit"] == 2

        found = handle.messages(search="reply")
        assert found["total"] == 1
        assert found["rows"][0]["text"] == "reply back"

        files = handle.files(domain="HomeDomain", search="sms.db")
        assert files["total"] == 1
    finally:
        handle.close()


def test_queries_work_from_another_thread(case_dir: Path) -> None:
    """Regression: pywebview answers calls on a thread pool, so a CaseHandle
    must not pin a SQLite connection to the thread that opened it."""
    handle = load_case(case_dir)
    results: list[object] = []

    def query() -> None:
        results.append(handle.summary()["counts"]["messages"])
        results.append(handle.messages(limit=1)["total"])

    worker = threading.Thread(target=query)
    worker.start()
    worker.join()
    handle.close()

    assert results == [3, 3]


def test_load_case_rejects_a_plain_folder(tmp_path: Path) -> None:
    with pytest.raises(AnalysisError):
        load_case(tmp_path)


def test_load_case_rejects_a_schema_mismatch(case_dir: Path) -> None:
    path = descriptor_path(case_dir, SERIAL)
    data = path.read_text().replace('"schema_version": 2', '"schema_version": 99')
    path.write_text(data)

    with pytest.raises(AnalysisError, match="schema"):
        load_case(case_dir)


def test_extract_file_writes_the_blob(case_dir: Path, tmp_path: Path) -> None:
    handle = load_case(case_dir)
    dest = tmp_path / "out" / "sms.db"
    try:
        handle.extract_file(file_id("HomeDomain", "Library/SMS/sms.db"), dest)
    finally:
        handle.close()

    assert dest.is_file()
    assert sqlite3.connect(dest).execute("SELECT COUNT(*) FROM message").fetchone()[0]


def test_extract_file_refuses_a_directory_or_symlink(case_dir: Path) -> None:
    handle = load_case(case_dir)
    try:
        with pytest.raises(AnalysisError):
            handle.extract_file(
                file_id("HomeDomain", "Library/SMS"), handle.case_dir / "x"
            )
        with pytest.raises(AnalysisError):
            handle.extract_file(
                file_id("HomeDomain", "Library/link"), handle.case_dir / "y"
            )
    finally:
        handle.close()


def test_image_mime_recognises_signatures_and_heic() -> None:
    assert _image_mime(b"\x89PNG\r\n\x1a\n....") == "image/png"
    assert _image_mime(b"\xff\xd8\xff\xe0junk") == "image/jpeg"
    assert _image_mime(b"GIF89a...") == "image/gif"
    assert _image_mime(b"\x00\x00\x00\x18ftypheic....") == "image/heic"
    assert _image_mime(b"just some text") is None


def test_sniff_classifies_image_plist_text_and_binary() -> None:
    png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 8
    image = _sniff(png, truncated=False)
    assert image["kind"] == "image"
    assert image["mime"] == "image/png"
    assert base64.b64decode(image["data_base64"]) == png

    plist = plistlib.dumps({"a": 1}, fmt=plistlib.FMT_BINARY)
    assert _sniff(plist, truncated=False) == {"kind": "plist", "json": {"a": 1}}
    # A plist is only decoded when the payload is whole.
    assert _sniff(plist, truncated=True)["kind"] == "binary"

    sample = "a note with an em—dash and a ✓"
    text = _sniff(sample.encode(), truncated=False)
    assert text == {"kind": "text", "text": sample, "truncated": False}

    binary = _sniff(b"\xff\xfe\x00\x01\x02", truncated=False)
    assert binary == {"kind": "binary", "size": 5, "truncated": False}


def test_json_safe_coerces_bytes_dates_and_uids() -> None:
    value = {
        "blob": b"\x01\x02",
        "when": dt.datetime(2026, 1, 2, 3, 4, 5),
        "ref": plistlib.UID(7),
        "nested": [b"ab", 1],
    }
    assert _json_safe(value) == {
        "blob": base64.b64encode(b"\x01\x02").decode("ascii"),
        "when": "2026-01-02T03:04:05",
        "ref": 7,
        "nested": [base64.b64encode(b"ab").decode("ascii"), 1],
    }


def test_preview_file_classifies_content(case_dir: Path) -> None:
    handle = load_case(case_dir)
    try:
        sms = handle.preview_file(file_id("HomeDomain", "Library/SMS/sms.db"))
        assert sms["kind"] in {"binary", "text"}
        assert sms["name"] == "sms.db"

        directory = handle.preview_file(file_id("HomeDomain", "Library/SMS"))
        assert directory == {
            "kind": "unavailable",
            "reason": "directory",
            "name": "SMS",
        }
    finally:
        handle.close()
