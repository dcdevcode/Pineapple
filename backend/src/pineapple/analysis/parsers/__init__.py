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

from pineapple.analysis.parsers.accounts import parse_accounts
from pineapple.analysis.parsers.apps import index_apps, index_backup_info
from pineapple.analysis.parsers.calendar import parse_calendar
from pineapple.analysis.parsers.calls import parse_calls
from pineapple.analysis.parsers.contacts import parse_contacts
from pineapple.analysis.parsers.device_usage import parse_device_usage
from pineapple.analysis.parsers.files import index_files
from pineapple.analysis.parsers.keychain import (
    SupportsKeychainUnwrap,
    parse_keychain,
)
from pineapple.analysis.parsers.messages import parse_messages
from pineapple.analysis.parsers.notes import parse_notes
from pineapple.analysis.parsers.photos import parse_photos
from pineapple.analysis.parsers.safari import (
    parse_safari_bookmarks,
    parse_safari_history,
)
from pineapple.analysis.parsers.voicemail import parse_voicemail
from pineapple.analysis.parsers.whatsapp import parse_whatsapp

# Most parsers take (source, analysis.db). A few need the backup reader too --
# to unwrap keychain item keys -- and set `needs_reader` so the runner passes it
# (the reader satisfies `SupportsKeychainUnwrap`).
ParseFn = Callable[[Path, sqlite3.Connection], int]
ReaderParseFn = Callable[[Path, sqlite3.Connection, SupportsKeychainUnwrap], int]


@dataclass(frozen=True)
class ParserSpec:
    """One artifact: where its source DB lives and how to parse it."""

    name: str
    relative_path: str
    domain: str
    parse: ParseFn | ReaderParseFn
    # iOS keeps some files (call history, keychain, Safari, Health) out of
    # *unencrypted* backups; when one of those is missing and the backup is not
    # encrypted, that is expected rather than an anomaly.
    encrypted_only: bool = False
    # `analysis.db` table the parser's return count belongs to, when it differs
    # from `name` (whatsapp fills whatsapp_chats + whatsapp_messages).
    count_key: str | None = None
    # When True the runner calls `parse(source, conn, reader)` instead of
    # `parse(source, conn)`.
    needs_reader: bool = False

    @property
    def counts_as(self) -> str:
        """The count key for this parser -- ``count_key`` or, by default, ``name``."""
        return self.count_key or self.name


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
        "photos",
        "Media/PhotoData/Photos.sqlite",
        "CameraRollDomain",
        parse_photos,
    ),
    ParserSpec(
        "calendar",
        "Library/Calendar/Calendar.sqlitedb",
        "HomeDomain",
        parse_calendar,
        count_key="calendar_events",
    ),
    ParserSpec(
        "voicemail",
        "Library/Voicemail/voicemail.db",
        "HomeDomain",
        parse_voicemail,
    ),
    ParserSpec(
        "accounts",
        "Library/Accounts/Accounts3.sqlite",
        "HomeDomain",
        parse_accounts,
    ),
    ParserSpec(
        "safari_history",
        "Library/Safari/History.db",
        "HomeDomain",
        parse_safari_history,
        encrypted_only=True,
    ),
    ParserSpec(
        # Verify against a real Manifest.db if the file comes back skipped:
        # the CoreDuet domain / path has moved between iOS releases.
        "device_usage",
        "Library/CoreDuet/Knowledge/knowledgeC.db",
        "AppDomainGroup-group.com.apple.coreduet",
        parse_device_usage,
        encrypted_only=True,
    ),
    ParserSpec(
        "keychain",
        "keychain-backup.plist",
        "KeychainDomain",
        parse_keychain,
        encrypted_only=True,
        needs_reader=True,
    ),
    ParserSpec(
        "safari_bookmarks",
        "Library/Safari/Bookmarks.db",
        "HomeDomain",
        parse_safari_bookmarks,
    ),
    ParserSpec(
        "whatsapp",
        "ChatStorage.sqlite",
        "AppDomainGroup-group.net.whatsapp.WhatsApp.shared",
        parse_whatsapp,
        count_key="whatsapp_messages",
    ),
]

__all__ = [
    "ARTIFACT_PARSERS",
    "ParseFn",
    "ParserSpec",
    "ReaderParseFn",
    "index_apps",
    "index_backup_info",
    "index_files",
]
