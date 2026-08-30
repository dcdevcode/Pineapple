"""Parse ``HomeDomain/Library/Accounts/Accounts3.sqlite`` into ``accounts``.

Core Data, so tables are ``Z``-prefixed. ``ZACCOUNT`` is one row per configured
account (mail, social, iCloud, …); ``ZACCOUNTTYPE`` names the kind. Secrets are
not here -- they live in the keychain. ``ZDATE`` is Cocoa absolute time.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from pineapple.analysis.parsers._common import (
    as_text,
    mac_absolute_to_iso,
    read_source,
)

_QUERY = """
SELECT a.Z_PK AS rowid, t.ZACCOUNTTYPEDESCRIPTION AS type,
       a.ZIDENTIFIER AS identifier, a.ZACCOUNTDESCRIPTION AS description,
       a.ZUSERNAME AS username, a.ZDATE AS added, t.ZIDENTIFIER AS credential_type
FROM ZACCOUNT a
LEFT JOIN ZACCOUNTTYPE t ON t.Z_PK = a.ZACCOUNTTYPE
"""


def parse_accounts(source_db: Path, conn: sqlite3.Connection) -> int:
    """Load ``Accounts3.sqlite`` into the ``accounts`` table; return the count."""
    with read_source(source_db, "Accounts3.sqlite") as source:
        rows = source.execute(_QUERY).fetchall()

    conn.executemany(
        "INSERT OR REPLACE INTO accounts"
        "(rowid, type, identifier, description, username, added_utc, "
        "credential_type) VALUES (?, ?, ?, ?, ?, ?, ?)",
        [
            (
                row["rowid"],
                as_text(row["type"]),
                as_text(row["identifier"]),
                as_text(row["description"]),
                as_text(row["username"]),
                mac_absolute_to_iso(row["added"]),
                as_text(row["credential_type"]),
            )
            for row in rows
        ],
    )
    return len(rows)
