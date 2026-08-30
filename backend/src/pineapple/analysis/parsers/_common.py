"""Helpers shared by the artifact parsers."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path

from pineapple.analysis.errors import ArtifactUnreadable

# Cocoa / Mac "absolute time": seconds since 2001-01-01 UTC. iOS 11+ stores some
# of these columns in nanoseconds instead, hence the magnitude check below.
_APPLE_EPOCH = datetime(2001, 1, 1, tzinfo=UTC)
_NANOSECOND_CUTOFF = 1e11


def mac_absolute_to_iso(value: object) -> str | None:
    """ISO-8601 UTC string for a Cocoa absolute-time value, or ``None``."""
    try:
        seconds = float(value)  # type: ignore[arg-type]
    except TypeError, ValueError:
        return None
    if seconds == 0:
        return None
    if abs(seconds) > _NANOSECOND_CUTOFF:
        seconds /= 1e9
    try:
        return (_APPLE_EPOCH + timedelta(seconds=seconds)).isoformat()
    except OverflowError, OSError:
        return None


def unix_to_iso(value: object) -> str | None:
    """ISO-8601 UTC string for a Unix epoch-seconds value, or ``None``."""
    if not isinstance(value, (int, float)) or value <= 0:
        return None
    try:
        return datetime.fromtimestamp(value, tz=UTC).isoformat()
    except OverflowError, OSError, ValueError:
        return None


def as_text(value: object) -> str | None:
    """Decode a value that iOS may store as ``TEXT`` or as a UTF-8 ``BLOB``."""
    if value is None:
        return None
    if isinstance(value, bytes):
        return value.decode("utf-8", "replace") or None
    return str(value) or None


def open_source(path: Path) -> sqlite3.Connection:
    """Open an extracted source database read-only, rows as :class:`sqlite3.Row`."""
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


@contextmanager
def read_source(path: Path, label: str) -> Iterator[sqlite3.Connection]:
    """Open a source database read-only for the duration of the block.

    Any :class:`sqlite3.Error` raised while opening or querying is turned into
    an :class:`ArtifactUnreadable` tagged with ``label`` (a damaged or
    unexpected schema is recorded as skipped, not fatal).
    """
    try:
        conn = open_source(path)
        try:
            yield conn
        finally:
            conn.close()
    except sqlite3.Error as error:
        raise ArtifactUnreadable(f"{label}: {error}") from error
