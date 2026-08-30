"""Parse ``HomeDomain/Library/Calendar/Calendar.sqlitedb`` into ``calendar_events``.

``CalendarItem`` is one row per event; ``Calendar`` names the calendar it belongs
to and ``Location`` its place. ``Participant`` rows (keyed by ``owner_id``) are the
invitees, flattened into one ``"; "``-joined string per event. Dates are Cocoa
absolute time.
"""

from __future__ import annotations

import sqlite3
from collections import defaultdict
from pathlib import Path

from pineapple.analysis.parsers._common import (
    as_text,
    mac_absolute_to_iso,
    read_source,
)

_EVENTS_QUERY = """
SELECT ci.ROWID AS rowid, ci.summary AS title, cal.title AS calendar,
       loc.title AS location, ci.description AS notes,
       ci.start_date AS start_date, ci.end_date AS end_date,
       ci.all_day AS all_day
FROM CalendarItem ci
LEFT JOIN Calendar cal ON cal.ROWID = ci.calendar_id
LEFT JOIN Location loc ON loc.ROWID = ci.location_id
ORDER BY ci.start_date
"""

_PARTICIPANTS_QUERY = """
SELECT owner_id AS event_id, COALESCE(name, email) AS who
FROM Participant
WHERE owner_id IS NOT NULL AND COALESCE(name, email) IS NOT NULL
"""


def parse_calendar(source_db: Path, conn: sqlite3.Connection) -> int:
    """Load ``Calendar.sqlitedb`` into ``calendar_events``; return the count."""
    with read_source(source_db, "Calendar.sqlitedb") as source:
        events = source.execute(_EVENTS_QUERY).fetchall()
        participants = source.execute(_PARTICIPANTS_QUERY).fetchall()

    invitees: dict[int, list[str]] = defaultdict(list)
    for row in participants:
        who = as_text(row["who"])
        if who is not None:
            invitees[row["event_id"]].append(who)

    conn.executemany(
        "INSERT OR REPLACE INTO calendar_events"
        "(rowid, calendar, title, location, notes, start_utc, end_utc, all_day, "
        "invitees) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [
            (
                row["rowid"],
                as_text(row["calendar"]),
                as_text(row["title"]),
                as_text(row["location"]),
                as_text(row["notes"]),
                mac_absolute_to_iso(row["start_date"]),
                mac_absolute_to_iso(row["end_date"]),
                1 if row["all_day"] else 0,
                "; ".join(invitees[row["rowid"]]) or None,
            )
            for row in events
        ],
    )
    return len(events)
