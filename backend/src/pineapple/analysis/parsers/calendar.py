"""Parse ``HomeDomain/Library/Calendar/Calendar.sqlitedb`` into ``calendar_events``.

``CalendarItem`` is one row per event; ``Calendar`` names the calendar it belongs
to and ``Location`` its place. Invitees come from ``Participant`` rows (keyed by
``owner_id``), flattened into one ``"; "``-joined string per event -- but the
``Participant`` schema drifts between iOS releases (older builds keep a display
name on the row, newer ones only an ``identity_id`` into ``Identity``), so that
part is introspected and best-effort: it never fails the event parse. Dates are
Cocoa absolute time.
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


def _columns(source: sqlite3.Connection, table: str) -> set[str]:
    return {row["name"] for row in source.execute(f"PRAGMA table_info({table})")}


def _invitees(source: sqlite3.Connection) -> dict[int, list[str]]:
    """Map each event id to its invitee display names / addresses.

    Built from whatever the ``Participant`` (and, when present, ``Identity``)
    schema on this backup actually offers; an empty map when it offers nothing
    usable or the query fails.
    """
    tables = {
        row["name"]
        for row in source.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
    }
    if "Participant" not in tables:
        return {}
    participant_cols = _columns(source, "Participant")
    if "owner_id" not in participant_cols:
        return {}

    who_parts: list[str] = []
    join = ""
    if "name" in participant_cols:  # older iOS keeps the name on the row
        who_parts.append("p.name")
    if "identity_id" in participant_cols and "Identity" in tables:
        join = " LEFT JOIN Identity idn ON idn.ROWID = p.identity_id"
        identity_cols = _columns(source, "Identity")
        who_parts += [
            f"idn.{col}" for col in ("display_name", "address") if col in identity_cols
        ]
    if "email" in participant_cols:
        who_parts.append("p.email")
    if not who_parts:
        return {}

    who = "COALESCE(" + ", ".join(f"NULLIF({part}, '')" for part in who_parts) + ")"
    query = (
        f"SELECT p.owner_id AS event_id, {who} AS who "
        f"FROM Participant p{join} WHERE p.owner_id IS NOT NULL"
    )
    try:
        rows = source.execute(query).fetchall()
    except sqlite3.OperationalError:
        return {}

    invitees: dict[int, list[str]] = defaultdict(list)
    for row in rows:
        person = as_text(row["who"])
        if person is not None:
            invitees[row["event_id"]].append(person.removeprefix("mailto:"))
    return invitees


def parse_calendar(source_db: Path, conn: sqlite3.Connection) -> int:
    """Load ``Calendar.sqlitedb`` into ``calendar_events``; return the count."""
    with read_source(source_db, "Calendar.sqlitedb") as source:
        events = source.execute(_EVENTS_QUERY).fetchall()
        invitees = _invitees(source)

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
                "; ".join(invitees.get(row["rowid"], [])) or None,
            )
            for row in events
        ],
    )
    return len(events)
