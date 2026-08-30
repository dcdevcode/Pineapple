"""Parse ``HomeDomain/Library/Voicemail/voicemail.db`` into ``voicemail``.

One ``voicemail`` row per message: caller, Unix-epoch ``date``, duration in
seconds and ``trashed_date`` (0 when the voicemail is still in the inbox). Some
iOS builds add a transcription column; it is picked up when present. The audio
itself stays a browsable file in the backup (``Library/Voicemail/<id>.amr``).
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from pineapple.analysis.parsers._common import as_text, read_source, unix_to_iso

_TRANSCRIPT_COLUMNS = ("transcription", "transcript")


def _transcript_column(source: sqlite3.Connection) -> str | None:
    columns = {row[1] for row in source.execute("PRAGMA table_info(voicemail)")}
    return next((name for name in _TRANSCRIPT_COLUMNS if name in columns), None)


def parse_voicemail(source_db: Path, conn: sqlite3.Connection) -> int:
    """Load ``voicemail.db`` into the ``voicemail`` table; return the count."""
    with read_source(source_db, "voicemail.db") as source:
        transcript = _transcript_column(source)
        select = "SELECT ROWID AS rowid, sender, date, duration, trashed_date"
        if transcript is not None:
            select += f", {transcript} AS transcript"
        rows = source.execute(f"{select} FROM voicemail").fetchall()

    conn.executemany(
        "INSERT OR REPLACE INTO voicemail"
        "(rowid, sender, received_utc, duration_seconds, trashed, transcript) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        [
            (
                row["rowid"],
                as_text(row["sender"]),
                unix_to_iso(row["date"]),
                int(row["duration"] or 0),
                1 if row["trashed_date"] else 0,
                as_text(row["transcript"]) if transcript is not None else None,
            )
            for row in rows
        ],
    )
    return len(rows)
