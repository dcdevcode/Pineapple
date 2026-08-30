"""Parse Safari history and bookmarks (both under ``HomeDomain/Library/Safari``).

``History.db`` is two tables -- ``history_items`` (one row per URL) and
``history_visits`` (one row per visit, with the page title and a Cocoa
absolute-time ``visit_time``). iOS keeps it out of *unencrypted* backups.

``Bookmarks.db`` is a single self-referential ``bookmarks`` table; ``type`` 1 is
a bookmark, ``type`` 0 a folder.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from pineapple.analysis.parsers._common import (
    as_text,
    mac_absolute_to_iso,
    read_source,
)

_HISTORY_QUERY = """
SELECT hi.url AS url, hv.title AS title, hv.visit_time AS visit_time,
       hi.visit_count AS visit_count
FROM history_visits hv
JOIN history_items hi ON hi.id = hv.history_item
ORDER BY hv.visit_time
"""

_BOOKMARKS_QUERY = """
SELECT b.title AS title, b.url AS url, p.title AS folder
FROM bookmarks b
LEFT JOIN bookmarks p ON p.id = b.parent
WHERE b.type = 1 AND b.url IS NOT NULL
"""


def parse_safari_history(source_db: Path, conn: sqlite3.Connection) -> int:
    """Load ``History.db`` into the ``safari_history`` table; return the count.

    Plain ``INSERT`` (not ``INSERT OR REPLACE``): a visit has no stable source
    id to carry over, so rows get fresh autoincrement rowids. One analysis per
    case folder, so this is never run twice against the same DB.
    """
    with read_source(source_db, "History.db") as source:
        rows = source.execute(_HISTORY_QUERY).fetchall()

    conn.executemany(
        "INSERT INTO safari_history(url, title, visit_utc, visit_count) "
        "VALUES (?, ?, ?, ?)",
        [
            (
                as_text(row["url"]),
                as_text(row["title"]),
                mac_absolute_to_iso(row["visit_time"]),
                row["visit_count"] or 0,
            )
            for row in rows
        ],
    )
    return len(rows)


def parse_safari_bookmarks(source_db: Path, conn: sqlite3.Connection) -> int:
    """Load ``Bookmarks.db`` into the ``safari_bookmarks`` table; return the count."""
    with read_source(source_db, "Bookmarks.db") as source:
        rows = source.execute(_BOOKMARKS_QUERY).fetchall()

    conn.executemany(
        "INSERT INTO safari_bookmarks(title, url, folder) VALUES (?, ?, ?)",
        [
            (as_text(row["title"]), as_text(row["url"]), as_text(row["folder"]))
            for row in rows
        ],
    )
    return len(rows)
