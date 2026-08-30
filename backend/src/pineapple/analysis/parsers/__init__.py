"""Artifact parsers.

Each artifact parser takes an extracted source database and an open
``analysis.db`` connection, and returns the number of rows it wrote. The runner
iterates :data:`ARTIFACT_PARSERS` in order; a parser that raises
:class:`~pineapple.analysis.errors.ArtifactUnreadable` is recorded as skipped.

``index_files`` / ``index_apps`` / ``index_backup_info`` are not in the list --
they read the manifest and the plists, not a source database, and run in the
indexing phase.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from pineapple.analysis.parsers.apps import index_apps, index_backup_info
from pineapple.analysis.parsers.calls import parse_calls
from pineapple.analysis.parsers.contacts import parse_contacts
from pineapple.analysis.parsers.files import index_files
from pineapple.analysis.parsers.messages import parse_messages
from pineapple.analysis.parsers.notes import parse_notes
from pineapple.analysis.parsers.safari import (
    parse_safari_bookmarks,
    parse_safari_history,
)

ParseFn = Callable[[Path, sqlite3.Connection], int]


@dataclass(frozen=True)
class ParserSpec:
    """One artifact: where its source DB lives and how to parse it."""

    name: str
    relative_path: str
    domain: str
    parse: ParseFn
    # iOS keeps some files (call history, keychain, Safari, Health) out of
    # *unencrypted* backups; when one of those is missing and the backup is not
    # encrypted, that is expected rather than an anomaly.
    encrypted_only: bool = False


ARTIFACT_PARSERS: list[ParserSpec] = [
    ParserSpec("messages", "Library/SMS/sms.db", "HomeDomain", parse_messages),
    ParserSpec(
        "calls",
        "Library/CallHistoryDB/CallHistory.storedata",
        "HomeDomain",
        parse_calls,
        encrypted_only=True,
    ),
    ParserSpec(
        "contacts",
        "Library/AddressBook/AddressBook.sqlitedb",
        "HomeDomain",
        parse_contacts,
    ),
    ParserSpec(
        "notes",
        "NoteStore.sqlite",
        "AppDomainGroup-group.com.apple.notes",
        parse_notes,
    ),
    ParserSpec(
        "safari_history",
        "Library/Safari/History.db",
        "HomeDomain",
        parse_safari_history,
        encrypted_only=True,
    ),
    ParserSpec(
        "safari_bookmarks",
        "Library/Safari/Bookmarks.db",
        "HomeDomain",
        parse_safari_bookmarks,
    ),
]

__all__ = [
    "ARTIFACT_PARSERS",
    "ParserSpec",
    "index_apps",
    "index_backup_info",
    "index_files",
]
