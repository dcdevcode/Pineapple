"""Write the device facts and installed-app list into ``analysis.db``."""

from __future__ import annotations

import sqlite3

from pineapple.analysis.metadata import BackupMetadata


def index_backup_info(metadata: BackupMetadata, conn: sqlite3.Connection) -> None:
    """Write the single ``backup_info`` row from the parsed backup metadata."""
    conn.execute(
        "INSERT INTO backup_info"
        "(device_name, product_type, product_name, product_version, build_version, "
        " serial, udid, last_backup_date, is_encrypted, was_passcode_set) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            metadata.device_name,
            metadata.product_type,
            metadata.product_name,
            metadata.product_version,
            metadata.build_version,
            metadata.serial,
            metadata.udid,
            metadata.last_backup_date,
            1 if metadata.is_encrypted else 0,
            1 if metadata.was_passcode_set else 0,
        ),
    )


def index_apps(metadata: BackupMetadata, conn: sqlite3.Connection) -> int:
    """Write the installed-app list into ``apps``; return the app count."""
    conn.executemany(
        "INSERT OR REPLACE INTO apps(bundle_id, name, version) VALUES (?, ?, ?)",
        [(app.bundle_id, app.name, app.version) for app in metadata.apps],
    )
    return len(metadata.apps)
