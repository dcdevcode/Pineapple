"""Parse ``HomeDomain/Library/AddressBook/AddressBook.sqlitedb`` into ``contacts``.

``ABPerson`` holds the names; phone numbers and e-mail addresses are rows in
``ABMultiValue`` keyed by ``property`` (3 = phone, 4 = e-mail).
"""

from __future__ import annotations

import sqlite3
from collections import defaultdict
from pathlib import Path

from pineapple.analysis.errors import ArtifactUnreadable
from pineapple.analysis.parsers._common import as_text, open_source

_PHONE_PROPERTY = 3
_EMAIL_PROPERTY = 4


def parse_contacts(source_db: Path, conn: sqlite3.Connection) -> int:
    try:
        source = open_source(source_db)
        try:
            people = source.execute(
                "SELECT ROWID AS rowid, First AS first, Last AS last, "
                "Organization AS organization FROM ABPerson"
            ).fetchall()
            multivalues = source.execute(
                "SELECT record_id, property, value FROM ABMultiValue "
                "WHERE property IN (?, ?)",
                (_PHONE_PROPERTY, _EMAIL_PROPERTY),
            ).fetchall()
        finally:
            source.close()
    except sqlite3.Error as error:
        raise ArtifactUnreadable(f"AddressBook.sqlitedb: {error}") from error

    phones: dict[int, list[str]] = defaultdict(list)
    emails: dict[int, list[str]] = defaultdict(list)
    for row in multivalues:
        value = as_text(row["value"])
        if value is None:
            continue
        bucket = phones if row["property"] == _PHONE_PROPERTY else emails
        bucket[row["record_id"]].append(value)

    conn.executemany(
        "INSERT OR REPLACE INTO contacts"
        "(rowid, first, last, organization, phones, emails) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        [
            (
                person["rowid"],
                person["first"],
                person["last"],
                person["organization"],
                "; ".join(phones[person["rowid"]]) or None,
                "; ".join(emails[person["rowid"]]) or None,
            )
            for person in people
        ],
    )
    return len(people)
