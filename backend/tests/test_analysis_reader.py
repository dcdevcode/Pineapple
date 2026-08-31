"""Tests for :mod:`pineapple.analysis.reader`."""

from __future__ import annotations

from pathlib import Path

import pytest

from analysis_support import FakeEncryptedBackup, build_backup, file_id
from pineapple.analysis import reader as reader_module
from pineapple.analysis.errors import AnalysisError
from pineapple.analysis.metadata import BackupMetadata
from pineapple.analysis.reader import BackupReader, open_reader


@pytest.fixture(autouse=True)
def _fake_library(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(reader_module, "EncryptedBackup", FakeEncryptedBackup)


def _sms_path(work: Path, reader: BackupReader) -> Path | None:
    return reader.extract_db("Library/SMS/sms.db", "HomeDomain", work / "decrypted")


def test_plain_and_encrypted_readers_agree(tmp_path: Path) -> None:
    plain_root = build_backup(tmp_path / "plain", udid="udid-plain")
    enc_root = build_backup(tmp_path / "enc", udid="udid-enc", encrypted=True)

    plain = open_reader(
        plain_root, BackupMetadata(is_encrypted=False), "", tmp_path / "wp"
    )
    encrypted = open_reader(
        enc_root,
        BackupMetadata(is_encrypted=True),
        FakeEncryptedBackup.PASSWORD,
        tmp_path / "we",
    )
    try:
        plain_rows = (
            plain.manifest_connection()
            .execute("SELECT COUNT(*) FROM Files")
            .fetchone()[0]
        )
        enc_rows = (
            encrypted.manifest_connection()
            .execute("SELECT COUNT(*) FROM Files")
            .fetchone()[0]
        )
        assert plain_rows == enc_rows

        plain_db = _sms_path(tmp_path / "wp", plain)
        enc_db = _sms_path(tmp_path / "we", encrypted)
        assert plain_db is not None
        assert enc_db is not None
        assert plain_db.read_bytes() == enc_db.read_bytes()
    finally:
        plain.close()
        encrypted.close()


def test_unwrap_keychain_key_plain_returns_none(tmp_path: Path) -> None:
    root = build_backup(tmp_path / "src")
    plain = open_reader(root, BackupMetadata(), "", tmp_path / "w")
    try:
        assert plain.unwrap_keychain_key(6, b"whatever") is None
    finally:
        plain.close()


def test_unwrap_keychain_key_encrypted_uses_the_keybag(tmp_path: Path) -> None:
    from cryptography.hazmat.primitives.keywrap import aes_key_wrap

    from analysis_support import _FakeKeybag

    root = build_backup(tmp_path / "src", encrypted=True)
    reader = open_reader(
        root,
        BackupMetadata(is_encrypted=True),
        FakeEncryptedBackup.PASSWORD,
        tmp_path / "w",
    )
    data_key = b"\x11" * 32
    wrapped = aes_key_wrap(_FakeKeybag.CLASS_KEYS[6], data_key)
    try:
        assert reader.unwrap_keychain_key(6, wrapped) == data_key
        assert reader.unwrap_keychain_key(99, wrapped) is None  # unknown class
        assert reader.unwrap_keychain_key(6, b"too short") is None
    finally:
        reader.close()


def test_encrypted_reader_rejects_a_wrong_password(tmp_path: Path) -> None:
    root = build_backup(tmp_path / "enc", encrypted=True)

    with pytest.raises(AnalysisError, match="password"):
        open_reader(root, BackupMetadata(is_encrypted=True), "wrong", tmp_path / "w")


def test_extract_db_returns_none_when_absent(tmp_path: Path) -> None:
    root = build_backup(tmp_path / "src", include_sources=False)
    plain = open_reader(root, BackupMetadata(), "", tmp_path / "w")
    try:
        assert _sms_path(tmp_path, plain) is None
    finally:
        plain.close()


@pytest.mark.parametrize("encrypted", [False, True])
def test_extract_file_and_read_bytes_by_file_id(
    tmp_path: Path, encrypted: bool
) -> None:
    root = build_backup(tmp_path / "src", encrypted=encrypted)
    reader = open_reader(
        root,
        BackupMetadata(is_encrypted=encrypted),
        FakeEncryptedBackup.PASSWORD if encrypted else "",
        tmp_path / "w",
    )
    fid = file_id("HomeDomain", "Library/SMS/sms.db")
    try:
        head = reader.read_bytes(fid, "Library/SMS/sms.db", "HomeDomain", 16)
        assert head is not None
        assert head.startswith(b"SQLite format 3")

        dest = tmp_path / "out" / "sms.db"
        written = reader.extract_file(fid, "Library/SMS/sms.db", "HomeDomain", dest)
        assert written == dest
        assert dest.read_bytes()[:16] == head

        missing = file_id("HomeDomain", "nope")
        assert reader.read_bytes(missing, "nope", "HomeDomain", 16) is None
        assert (
            reader.extract_file(missing, "nope", "HomeDomain", tmp_path / "z") is None
        )
    finally:
        reader.close()
