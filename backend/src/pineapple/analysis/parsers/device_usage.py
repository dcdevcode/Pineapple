"""Parse a curated slice of ``knowledgeC.db`` into ``device_usage``.

``knowledgeC.db`` (CoreDuet) records a great many event streams; this parser keeps
only the four most useful for a timeline -- app usage, app in-focus, display
backlight and notification delivery -- and caps the row count so a busy device
does not blow up ``analysis.db``. iOS keeps this file out of *unencrypted*
backups. Dates are Cocoa absolute time.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from pineapple.analysis.parsers._common import (
    as_text,
    mac_absolute_to_iso,
    read_source,
)

# Streams that name an app in ZVALUESTRING vs. those that carry a bare state.
_APP_STREAMS = ("/app/usage", "/app/inFocus", "/notification/usage")
_STATE_STREAMS = ("/display/isBacklit",)
_STREAMS = _APP_STREAMS + _STATE_STREAMS
_ROW_CAP = 50_000

_QUERY = f"""
SELECT Z_PK AS rowid, ZSTREAMNAME AS stream, ZVALUESTRING AS value_string,
       ZVALUEINTEGER AS value_integer, ZSTARTDATE AS start_date,
       ZENDDATE AS end_date
FROM ZOBJECT
WHERE ZSTREAMNAME IN ({", ".join("?" for _ in _STREAMS)})
ORDER BY ZSTARTDATE DESC
LIMIT {_ROW_CAP}
"""


def _duration(start: object, end: object) -> int:
    if (
        isinstance(start, (int, float))
        and isinstance(end, (int, float))
        and end > start
    ):
        return int(end - start)
    return 0


def parse_device_usage(source_db: Path, conn: sqlite3.Connection) -> int:
    """Load the curated ``knowledgeC.db`` streams into ``device_usage``; return
    the row count."""
    with read_source(source_db, "knowledgeC.db") as source:
        rows = source.execute(_QUERY, _STREAMS).fetchall()

    records = []
    for row in rows:
        is_app = row["stream"] in _APP_STREAMS
        value_integer = row["value_integer"]
        records.append(
            (
                row["rowid"],
                row["stream"],
                as_text(row["value_string"]) if is_app else None,
                None if is_app else _state_text(value_integer),
                mac_absolute_to_iso(row["start_date"]),
                mac_absolute_to_iso(row["end_date"]),
                _duration(row["start_date"], row["end_date"]),
            )
        )

    conn.executemany(
        "INSERT OR REPLACE INTO device_usage"
        "(rowid, stream, bundle_id, value, start_utc, end_utc, duration_seconds) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        records,
    )
    return len(rows)


def _state_text(value: object) -> str | None:
    return str(value) if isinstance(value, int) else None
