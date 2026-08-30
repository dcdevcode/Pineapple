"""Parse ``HomeDomain/Library/CallHistoryDB/CallHistory.storedata`` into ``calls``.

The store is Core Data: the ``ZCALLRECORD`` table holds one row per call.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from pineapple.analysis.parsers._common import as_text, mac_absolute_to_iso, read_source

_QUERY = """
SELECT
    Z_PK              AS rowid,
    ZDATE             AS date,
    ZDURATION         AS duration,
    ZADDRESS          AS address,
    ZORIGINATED       AS originated,
    ZANSWERED         AS answered,
    ZSERVICE_PROVIDER AS provider
FROM ZCALLRECORD
"""


def _direction(originated: object, answered: object) -> str:
    if originated:
        return "outgoing"
    return "incoming" if answered else "missed"


def _service(provider: object) -> str:
    text = as_text(provider) or ""
    return "FaceTime" if "FaceTime" in text else "Phone"


def parse_calls(source_db: Path, conn: sqlite3.Connection) -> int:
    """Load ``CallHistory.storedata`` into the ``calls`` table; return the count."""
    with read_source(source_db, "CallHistory.storedata") as source:
        rows = source.execute(_QUERY).fetchall()

    conn.executemany(
        "INSERT OR REPLACE INTO calls"
        "(rowid, address, service, direction, date_utc, duration_seconds) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        [
            (
                row["rowid"],
                as_text(row["address"]),
                _service(row["provider"]),
                _direction(row["originated"], row["answered"]),
                mac_absolute_to_iso(row["date"]),
                int(row["duration"] or 0),
            )
            for row in rows
        ],
    )
    return len(rows)
