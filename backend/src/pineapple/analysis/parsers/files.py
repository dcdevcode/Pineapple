"""Index the backup's file inventory: ``Manifest.db`` ``Files`` -> ``files``."""

from __future__ import annotations

import sqlite3

from pineapple.analysis.mbfile import decode_mbfile
from pineapple.analysis.parsers._common import unix_to_iso

_DIR_FLAG = 2


def index_files(manifest: sqlite3.Connection, conn: sqlite3.Connection) -> int:
    """Copy every ``Manifest.db`` ``Files`` row into ``files``, decoding the
    ``MBFile`` blob for size / timestamps / mode / symlink target. Returns the
    row count."""
    rows = manifest.execute(
        "SELECT fileID, domain, relativePath, flags, file FROM Files"
    ).fetchall()

    def record(row: tuple[object, ...]) -> tuple[object, ...]:
        file_id, domain, relative_path, flags, blob = row
        meta = decode_mbfile(blob if isinstance(blob, bytes) else None)
        is_dir = flags == _DIR_FLAG or meta.is_dir
        return (
            file_id,
            domain,
            relative_path,
            flags,
            1 if is_dir else 0,
            meta.size,
            unix_to_iso(meta.mtime),
            unix_to_iso(meta.ctime),
            unix_to_iso(meta.btime),
            meta.mode,
            meta.target,
        )

    conn.executemany(
        "INSERT OR REPLACE INTO files"
        "(file_id, domain, relative_path, flags, is_dir, size, "
        " mtime, ctime, btime, mode, target) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [record(row) for row in rows],
    )
    return len(rows)
