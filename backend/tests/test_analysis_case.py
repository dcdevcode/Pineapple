"""Tests for :mod:`pineapple.analysis.case`."""

from __future__ import annotations

import plistlib
import sqlite3
from pathlib import Path

import pytest

from analysis_support import SERIAL, build_backup, file_id
from pineapple.analysis.case import load_case
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
        assert summary["counts"]["files"] == 5
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


def test_load_case_rejects_a_plain_folder(tmp_path: Path) -> None:
    with pytest.raises(AnalysisError):
        load_case(tmp_path)


def test_load_case_rejects_a_schema_mismatch(case_dir: Path) -> None:
    path = descriptor_path(case_dir, SERIAL)
    data = path.read_text().replace('"schema_version": 1', '"schema_version": 99')
    path.write_text(data)

    with pytest.raises(AnalysisError, match="schema"):
        load_case(case_dir)
