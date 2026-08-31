"""Tests for :mod:`pineapple.hashing`."""

from __future__ import annotations

import hashlib
import threading
from pathlib import Path

import pytest

from pineapple.hashing import HashingCancelled, sha256_file


def test_sha256_file_matches_hashlib(tmp_path: Path) -> None:
    target = tmp_path / "blob"
    target.write_bytes(b"pineapple" * 1000)

    assert sha256_file(target) == hashlib.sha256(target.read_bytes()).hexdigest()


def test_sha256_file_raises_when_the_cancel_event_is_set(tmp_path: Path) -> None:
    target = tmp_path / "blob"
    target.write_bytes(b"pineapple" * 1000)

    cancelled = threading.Event()
    cancelled.set()

    with pytest.raises(HashingCancelled):
        sha256_file(target, cancelled=cancelled)
