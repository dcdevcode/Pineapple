"""Parse ``HomeDomain/Library/SMS/sms.db`` into the ``messages`` table.

iOS 16+ leaves ``message.text`` NULL for some rows and keeps the body in an
``attributedBody`` typedstream archive instead; :func:`decode_attributed_body`
recovers those.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from pineapple.analysis.parsers._common import mac_absolute_to_iso, read_source
from pineapple.analysis.parsers.attributed_body import decode_attributed_body

_QUERY = """
SELECT
    m.ROWID                                   AS rowid,
    m.text                                    AS text,
    m.attributedBody                          AS attributed_body,
    m.is_from_me                              AS is_from_me,
    m.date                                    AS date,
    m.service                                 AS service,
    h.id                                      AS address,
    (SELECT cmj.chat_id FROM chat_message_join cmj
        WHERE cmj.message_id = m.ROWID LIMIT 1) AS chat_id,
    (SELECT COUNT(*) FROM message_attachment_join maj
        WHERE maj.message_id = m.ROWID)          AS attachments
FROM message m
LEFT JOIN handle h ON h.ROWID = m.handle_id
"""


def parse_messages(source_db: Path, conn: sqlite3.Connection) -> int:
    """Load ``sms.db`` into the ``messages`` table; return the row count."""
    with read_source(source_db, "sms.db") as source:
        rows = source.execute(_QUERY).fetchall()

    def body(row: sqlite3.Row) -> str | None:
        if row["text"] is not None:
            return str(row["text"])
        return decode_attributed_body(row["attributed_body"])

    conn.executemany(
        "INSERT OR REPLACE INTO messages"
        "(rowid, chat_id, address, service, is_from_me, date_utc, text, attachments) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        [
            (
                row["rowid"],
                row["chat_id"],
                row["address"],
                row["service"],
                1 if row["is_from_me"] else 0,
                mac_absolute_to_iso(row["date"]),
                body(row),
                row["attachments"] or 0,
            )
            for row in rows
        ],
    )
    return len(rows)
