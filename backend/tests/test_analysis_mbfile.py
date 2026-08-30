"""Tests for :mod:`pineapple.analysis.mbfile`."""

from __future__ import annotations

from analysis_support import mbfile_blob
from pineapple.analysis.mbfile import decode_mbfile


def test_decode_reads_size_mode_and_timestamps() -> None:
    blob = mbfile_blob(
        size=4096, mode=0o100644, mtime=1_600_000_000, btime=1_500_000_000
    )

    meta = decode_mbfile(blob)

    assert meta.size == 4096
    assert meta.mode == 0o100644
    assert meta.mtime == 1_600_000_000
    assert meta.btime == 1_500_000_000
    assert not meta.is_dir
    assert not meta.is_symlink


def test_decode_recognises_directory_and_symlink() -> None:
    assert decode_mbfile(mbfile_blob(mode=0o040755)).is_dir
    link = decode_mbfile(mbfile_blob(mode=0o120777, target="SMS/sms.db"))
    assert link.is_symlink
    assert link.target == "SMS/sms.db"


def test_decode_is_tolerant_of_junk() -> None:
    assert decode_mbfile(None).size == 0
    assert decode_mbfile(b"not a plist").size == 0
