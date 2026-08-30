"""Tests for :mod:`pineapple.analysis.archive`."""

from __future__ import annotations

import threading
import zipfile
from pathlib import Path

import pytest

from analysis_support import SERIAL, UDID, build_backup, make_pineapple
from pineapple.analysis.archive import ArchiveCancelled, extract, peek
from pineapple.analysis.errors import AnalysisError


@pytest.fixture
def pineapple(tmp_path: Path) -> Path:
    root = build_backup(tmp_path / "src")
    return make_pineapple(root, tmp_path / "image.pineapple")


def test_peek_reads_metadata_without_unpacking(pineapple: Path) -> None:
    metadata = peek(pineapple)

    assert metadata.serial == SERIAL
    assert metadata.product_name == "iPhone 13"
    assert metadata.product_version == "17.5.1"
    assert metadata.udid == UDID
    assert metadata.is_encrypted is False
    assert metadata.default_title == SERIAL


def test_peek_reports_encryption(tmp_path: Path) -> None:
    root = build_backup(tmp_path / "src", encrypted=True)
    archive = make_pineapple(root, tmp_path / "enc.pineapple")

    assert peek(archive).is_encrypted is True


def test_peek_rejects_a_non_archive(tmp_path: Path) -> None:
    junk = tmp_path / "image.pineapple"
    junk.write_bytes(b"not a zip")

    with pytest.raises(AnalysisError):
        peek(junk)


def test_extract_returns_the_backup_root(pineapple: Path, tmp_path: Path) -> None:
    root = extract(pineapple, tmp_path / "out", threading.Event())

    assert root == tmp_path / "out" / UDID
    assert (root / "Manifest.db").is_file()


def test_extract_honours_cancellation(pineapple: Path, tmp_path: Path) -> None:
    cancelled = threading.Event()
    cancelled.set()

    with pytest.raises(ArchiveCancelled):
        extract(pineapple, tmp_path / "out", cancelled)


def test_peek_rejects_multiple_top_level_folders(tmp_path: Path) -> None:
    archive_path = tmp_path / "weird.pineapple"
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr("a/Info.plist", b"x")
        archive.writestr("b/Info.plist", b"x")

    with pytest.raises(AnalysisError, match="single top-level folder"):
        peek(archive_path)
