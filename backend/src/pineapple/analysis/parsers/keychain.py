"""Parse ``KeychainDomain/keychain-backup.plist`` into the ``keychain`` table.

Not a SQLite source -- a binary plist, so this parser reads bytes directly rather
than through ``_common.read_source``. Metadata always lands; each item's secret
is decrypted through the backup keybag (``reader.unwrap_keychain_key``) when it
can be, otherwise ``secret`` is NULL and ``secret_error`` explains. iOS keeps the
keychain out of *unencrypted* backups (this ``ParserSpec`` is ``encrypted_only``).
"""

from __future__ import annotations

import plistlib
import sqlite3
from pathlib import Path
from typing import Protocol

from pineapple.analysis.errors import ArtifactUnreadable
from pineapple.analysis.keychain import decrypt_item_secret, parse_keychain_plist


class SupportsKeychainUnwrap(Protocol):
    """The one thing the keychain parser needs from the backup reader."""

    def unwrap_keychain_key(
        self, protection_class: int, wrapped: bytes
    ) -> bytes | None: ...


def parse_keychain(
    source_db: Path, conn: sqlite3.Connection, reader: SupportsKeychainUnwrap
) -> int:
    """Load ``keychain-backup.plist`` into ``keychain``; return the item count."""
    try:
        items = parse_keychain_plist(source_db.read_bytes())
    except (plistlib.InvalidFileException, ValueError) as error:
        raise ArtifactUnreadable(f"keychain-backup.plist: {error}") from error

    rows = []
    for rowid, item in enumerate(items, start=1):
        secret, secret_error = decrypt_item_secret(item, reader.unwrap_keychain_key)
        rows.append(
            (
                rowid,
                item.item_class,
                item.account,
                item.service,
                item.server,
                item.access_group,
                item.protection_class,
                item.created,
                item.modified,
                secret,
                secret_error,
            )
        )

    conn.executemany(
        "INSERT OR REPLACE INTO keychain"
        "(rowid, item_class, account, service, server, access_group, "
        "protection_class, created_utc, modified_utc, secret, secret_error) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        rows,
    )
    return len(rows)
