"""Open a parsed case folder and answer the frontend's read-only queries.

Each query opens its own short-lived ``sqlite3`` connection: pywebview answers
bridge calls on a small thread pool, and a SQLite connection may only be used on
the thread that created it, so a persistent connection would break as soon as a
second call landed on a different worker thread.

A :class:`CaseHandle` also lends read access to the backup itself -- extracting
one file, or a size-capped preview of its contents. That needs the decryption
password for an encrypted backup; it is supplied at load time or later via
:meth:`CaseHandle.set_password`, and is held only in memory.
"""

from __future__ import annotations

import base64
import datetime as dt
import plistlib
import sqlite3
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from pathlib import Path
from typing import Any, TypeVar

from pineapple.analysis.descriptor import (
    CaseDescriptor,
    find_descriptor,
    read_descriptor,
)
from pineapple.analysis.errors import AnalysisError
from pineapple.analysis.reader import (
    BackupReader,
    EncryptedBackupReader,
    PlainBackupReader,
)
from pineapple.analysis.schema import SCHEMA_VERSION

_T = TypeVar("_T")

ANALYSIS_DB = "analysis.db"
DEFAULT_PAGE = 200
MAX_PAGE = 2000
PREVIEW_MAX_BYTES = 5 * 1024 * 1024

_COUNT_TABLES = (
    "apps",
    "files",
    "messages",
    "calls",
    "contacts",
    "notes",
    "safari_history",
    "safari_bookmarks",
    "whatsapp_chats",
    "whatsapp_messages",
    "photos",
    "calendar_events",
    "voicemail",
    "device_usage",
    "accounts",
)

_IMAGE_SIGNATURES: tuple[tuple[bytes, str], ...] = (
    (b"\x89PNG\r\n\x1a\n", "image/png"),
    (b"\xff\xd8\xff", "image/jpeg"),
    (b"GIF87a", "image/gif"),
    (b"GIF89a", "image/gif"),
)


def _page(limit: int, offset: int) -> tuple[int, int]:
    """Clamp a caller-supplied ``(limit, offset)`` to ``1..MAX_PAGE`` / ``>= 0``."""
    return max(1, min(int(limit), MAX_PAGE)), max(0, int(offset))


def _json_safe(value: Any) -> Any:
    """Make a ``plistlib`` result JSON-serialisable for the bridge envelope."""
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    if isinstance(value, bytes):
        return base64.b64encode(value).decode("ascii")
    if isinstance(value, (dt.datetime, dt.date)):
        return value.isoformat()
    if isinstance(value, plistlib.UID):
        return value.data
    return value


def _image_mime(data: bytes) -> str | None:
    for signature, mime in _IMAGE_SIGNATURES:
        if data.startswith(signature):
            return mime
    # HEIC/HEIF: an ISO base-media file whose `ftyp` box (bytes 4..12, after the
    # 4-byte box length) carries one of these brands.
    if data[4:12] in {b"ftypheic", b"ftypheix", b"ftypmif1"}:
        return "image/heic"
    return None


def _as_plist_json(data: bytes) -> Any | None:
    looks_like_plist = data.startswith(b"bplist00") or (
        data.lstrip().startswith(b"<?xml") and b"<plist" in data[:512]
    )
    if not looks_like_plist:
        return None
    try:
        return _json_safe(plistlib.loads(data))
    except plistlib.InvalidFileException, ValueError, OverflowError:
        return None


def _sniff(data: bytes, truncated: bool) -> dict[str, Any]:
    """Classify a file preview payload: image / plist / text / binary."""
    mime = _image_mime(data)
    if mime is not None:
        return {
            "kind": "image",
            "mime": mime,
            "data_base64": base64.b64encode(data).decode("ascii"),
            "truncated": truncated,
        }
    if not truncated:
        plist_json = _as_plist_json(data)
        if plist_json is not None:
            return {"kind": "plist", "json": plist_json}
    try:
        return {"kind": "text", "text": data.decode("utf-8"), "truncated": truncated}
    except UnicodeDecodeError:
        return {"kind": "binary", "size": len(data), "truncated": truncated}


class CaseHandle:
    """A loaded case: its descriptor, read access to ``analysis.db`` and (on
    demand) to the backup files themselves."""

    def __init__(
        self,
        case_dir: Path,
        descriptor: CaseDescriptor,
        database: Path,
        backup_root: Path,
        is_encrypted: bool,
        password: str | None = None,
    ) -> None:
        self.case_dir = case_dir
        self._descriptor = descriptor
        self._database = database
        self._backup_root = backup_root
        self._is_encrypted = is_encrypted
        self._password = password
        self._reader: BackupReader | None = None
        # The backup reader -- and the SQLite connections it (and
        # `iphone_backup_decrypt`) hold -- must stay on one thread, but pywebview
        # answers bridge calls on a pool of workers. Every reader touch is routed
        # through this single-worker executor so it always runs on that thread.
        self._reader_pool = ThreadPoolExecutor(
            max_workers=1, thread_name_prefix="pineapple-case-reader"
        )

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(f"file:{self._database}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        return conn

    # -- descriptor / summary ---------------------------------------------

    @staticmethod
    def _search_where(search: str | None, *columns: str) -> tuple[str, list[Any]]:
        """A ``WHERE col LIKE ? OR …`` fragment over ``columns`` (or ``""`` when
        ``search`` is empty), plus the ``%search%`` params it binds."""
        if not search:
            return "", []
        clause = " OR ".join(f"{column} LIKE ?" for column in columns)
        return f"WHERE {clause}", [f"%{search}%"] * len(columns)

    def descriptor(self) -> dict[str, Any]:
        """The case descriptor (device, source archive, parse outcome) as a dict."""
        return self._descriptor.to_dict()

    def summary(self) -> dict[str, Any]:
        """Descriptor essentials plus a per-table row count and the encryption /
        files-unlocked state the browser switches on."""
        with closing(self._connect()) as conn:
            row = conn.execute("SELECT * FROM backup_info LIMIT 1").fetchone()
            counts = {
                table: conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                for table in _COUNT_TABLES
            }
        return {
            "title": self._descriptor.title,
            "device": dict(row) if row else self._descriptor.device,
            "source": self._descriptor.source,
            "parse": self._descriptor.parse,
            "counts": counts,
            "is_encrypted": self._is_encrypted,
            "files_unlocked": self.files_unlocked(),
        }

    # -- artifact queries ------------------------------------------------

    def apps(self) -> list[dict[str, Any]]:
        """Every installed app (bundle id, name, version), ordered by bundle id."""
        with closing(self._connect()) as conn:
            return [
                dict(row)
                for row in conn.execute(
                    "SELECT bundle_id, name, version FROM apps ORDER BY bundle_id"
                )
            ]

    def domains(self) -> list[dict[str, Any]]:
        """Each backup domain and its file count, for the Files filter."""
        with closing(self._connect()) as conn:
            return [
                {"domain": row[0], "count": row[1]}
                for row in conn.execute(
                    "SELECT domain, COUNT(*) FROM files GROUP BY domain ORDER BY domain"
                )
            ]

    def files(
        self,
        domain: str | None = None,
        search: str | None = None,
        limit: int = DEFAULT_PAGE,
        offset: int = 0,
    ) -> dict[str, Any]:
        """One page of the file index, optionally scoped to a domain and/or a
        relative-path substring."""
        where, params = self._files_where(domain, search)
        return self._page_query(
            "SELECT file_id, domain, relative_path, is_dir, size, mtime, btime, target "
            f"FROM files {where} ORDER BY domain, relative_path",
            f"SELECT COUNT(*) FROM files {where}",
            params,
            limit,
            offset,
        )

    def messages(
        self,
        search: str | None = None,
        limit: int = DEFAULT_PAGE,
        offset: int = 0,
    ) -> dict[str, Any]:
        """One page of SMS / iMessage rows, oldest first; ``search`` matches text
        or address."""
        where, params = self._search_where(search, "text", "address")
        return self._page_query(
            "SELECT rowid, chat_id, address, service, is_from_me, date_utc, text, "
            f"attachments FROM messages {where} ORDER BY date_utc",
            f"SELECT COUNT(*) FROM messages {where}",
            params,
            limit,
            offset,
        )

    def calls(self, limit: int = DEFAULT_PAGE, offset: int = 0) -> dict[str, Any]:
        """One page of call-history rows, most recent first."""
        return self._page_query(
            "SELECT rowid, address, service, direction, date_utc, duration_seconds "
            "FROM calls ORDER BY date_utc DESC",
            "SELECT COUNT(*) FROM calls",
            [],
            limit,
            offset,
        )

    def contacts(
        self,
        search: str | None = None,
        limit: int = DEFAULT_PAGE,
        offset: int = 0,
    ) -> dict[str, Any]:
        """One page of contacts, by last then first name; ``search`` matches any
        name, organization, phone or email."""
        where, params = self._search_where(
            search, "first", "last", "organization", "phones", "emails"
        )
        return self._page_query(
            "SELECT rowid, first, last, organization, phones, emails "
            f"FROM contacts {where} ORDER BY last, first",
            f"SELECT COUNT(*) FROM contacts {where}",
            params,
            limit,
            offset,
        )

    def notes(
        self,
        search: str | None = None,
        limit: int = DEFAULT_PAGE,
        offset: int = 0,
    ) -> dict[str, Any]:
        """One page of notes, most recently modified first; ``search`` matches
        title, snippet or body."""
        where, params = self._search_where(search, "title", "snippet", "body")
        return self._page_query(
            "SELECT rowid, folder, title, snippet, body, created_utc, modified_utc "
            f"FROM notes {where} ORDER BY modified_utc DESC",
            f"SELECT COUNT(*) FROM notes {where}",
            params,
            limit,
            offset,
        )

    def safari_history(
        self,
        search: str | None = None,
        limit: int = DEFAULT_PAGE,
        offset: int = 0,
    ) -> dict[str, Any]:
        """One page of Safari history, most recent visit first; ``search`` matches
        URL or page title."""
        where, params = self._search_where(search, "url", "title")
        return self._page_query(
            "SELECT rowid, url, title, visit_utc, visit_count "
            f"FROM safari_history {where} ORDER BY visit_utc DESC",
            f"SELECT COUNT(*) FROM safari_history {where}",
            params,
            limit,
            offset,
        )

    def safari_bookmarks(
        self,
        search: str | None = None,
        limit: int = DEFAULT_PAGE,
        offset: int = 0,
    ) -> dict[str, Any]:
        """One page of Safari bookmarks, by folder then title; ``search`` matches
        title, URL or folder."""
        where, params = self._search_where(search, "title", "url", "folder")
        return self._page_query(
            "SELECT rowid, title, url, folder "
            f"FROM safari_bookmarks {where} ORDER BY folder, title",
            f"SELECT COUNT(*) FROM safari_bookmarks {where}",
            params,
            limit,
            offset,
        )

    def whatsapp_chats(
        self, limit: int = DEFAULT_PAGE, offset: int = 0
    ) -> dict[str, Any]:
        """One page of WhatsApp conversations, most recently active first."""
        return self._page_query(
            "SELECT rowid, jid, name, last_message_utc, message_count "
            "FROM whatsapp_chats ORDER BY last_message_utc DESC",
            "SELECT COUNT(*) FROM whatsapp_chats",
            [],
            limit,
            offset,
        )

    def whatsapp_messages(
        self,
        chat_jid: str | None = None,
        search: str | None = None,
        limit: int = DEFAULT_PAGE,
        offset: int = 0,
    ) -> dict[str, Any]:
        """One page of WhatsApp messages, oldest first; optionally scoped to one
        chat and/or a text substring."""
        clauses: list[str] = []
        params: list[Any] = []
        if chat_jid:
            clauses.append("chat_jid = ?")
            params.append(chat_jid)
        if search:
            clauses.append("text LIKE ?")
            params.append(f"%{search}%")
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        return self._page_query(
            "SELECT rowid, chat_jid, chat_name, from_me, sender, date_utc, text, "
            f"media_type FROM whatsapp_messages {where} ORDER BY date_utc",
            f"SELECT COUNT(*) FROM whatsapp_messages {where}",
            params,
            limit,
            offset,
        )

    def photos(
        self,
        search: str | None = None,
        limit: int = DEFAULT_PAGE,
        offset: int = 0,
    ) -> dict[str, Any]:
        """One page of camera-roll assets, newest first; ``search`` matches the
        filename or directory."""
        where, params = self._search_where(search, "filename", "directory")
        return self._page_query(
            "SELECT rowid, file_id, filename, directory, kind, created_utc, "
            "added_utc, width, height, favorite, hidden, trashed, latitude, "
            f"longitude FROM photos {where} ORDER BY created_utc DESC",
            f"SELECT COUNT(*) FROM photos {where}",
            params,
            limit,
            offset,
        )

    def photo_albums(
        self, limit: int = DEFAULT_PAGE, offset: int = 0
    ) -> dict[str, Any]:
        """One page of photo albums, by title."""
        return self._page_query(
            "SELECT rowid, title, kind, count, start_utc, end_utc "
            "FROM photo_albums ORDER BY title",
            "SELECT COUNT(*) FROM photo_albums",
            [],
            limit,
            offset,
        )

    def calendar_events(
        self,
        search: str | None = None,
        limit: int = DEFAULT_PAGE,
        offset: int = 0,
    ) -> dict[str, Any]:
        """One page of calendar events, most recent start first; ``search``
        matches the title, location or notes."""
        where, params = self._search_where(search, "title", "location", "notes")
        return self._page_query(
            "SELECT rowid, calendar, title, location, notes, start_utc, end_utc, "
            f"all_day, invitees FROM calendar_events {where} "
            "ORDER BY start_utc DESC",
            f"SELECT COUNT(*) FROM calendar_events {where}",
            params,
            limit,
            offset,
        )

    def voicemail(
        self,
        search: str | None = None,
        limit: int = DEFAULT_PAGE,
        offset: int = 0,
    ) -> dict[str, Any]:
        """One page of voicemails, most recent first; ``search`` matches the
        caller or the transcript."""
        where, params = self._search_where(search, "sender", "transcript")
        return self._page_query(
            "SELECT rowid, sender, received_utc, duration_seconds, trashed, "
            f"transcript FROM voicemail {where} ORDER BY received_utc DESC",
            f"SELECT COUNT(*) FROM voicemail {where}",
            params,
            limit,
            offset,
        )

    def accounts(
        self,
        search: str | None = None,
        limit: int = DEFAULT_PAGE,
        offset: int = 0,
    ) -> dict[str, Any]:
        """One page of configured accounts, by type then identifier; ``search``
        matches the type, identifier or username."""
        where, params = self._search_where(search, "type", "identifier", "username")
        return self._page_query(
            "SELECT rowid, type, identifier, description, username, added_utc, "
            f"credential_type FROM accounts {where} ORDER BY type, identifier",
            f"SELECT COUNT(*) FROM accounts {where}",
            params,
            limit,
            offset,
        )

    def device_usage(
        self,
        search: str | None = None,
        limit: int = DEFAULT_PAGE,
        offset: int = 0,
    ) -> dict[str, Any]:
        """One page of knowledgeC events, most recent first; ``search`` matches
        the stream or bundle id."""
        where, params = self._search_where(search, "stream", "bundle_id")
        return self._page_query(
            "SELECT rowid, stream, bundle_id, value, start_utc, end_utc, "
            f"duration_seconds FROM device_usage {where} ORDER BY start_utc DESC",
            f"SELECT COUNT(*) FROM device_usage {where}",
            params,
            limit,
            offset,
        )

    # -- backup file access -------------------------------------------------

    def files_unlocked(self) -> bool:
        """Whether the backup files can be read (an encrypted case needs a key)."""
        if not self._is_encrypted:
            return True
        try:
            self._on_reader_thread(self._backup_reader)
        except AnalysisError:
            return False
        return True

    def set_password(self, password: str) -> None:
        """Supply (or replace) the decryption key for an encrypted backup."""

        def swap() -> None:
            if self._reader is not None:
                self._reader.close()
                self._reader = None
            self._password = password
            self._backup_reader()  # validate now; raises AnalysisError on a bad key

        self._on_reader_thread(swap)

    def file_name(self, file_id: str) -> str:
        """The basename of one backup file (raises if the id is unknown)."""
        return Path(self._file_row(file_id)["relative_path"]).name

    def extract_file(self, file_id: str, dest: Path) -> Path:
        """Copy/decrypt one backup file to ``dest``. Regular files only."""
        row = self._file_row(file_id)
        if row["is_dir"] or row["target"]:
            raise AnalysisError("Only regular files can be extracted.")
        out = self._on_reader_thread(
            lambda: self._backup_reader().extract_file(
                file_id, row["relative_path"], row["domain"], dest
            )
        )
        if out is None:
            raise AnalysisError("The backup does not contain this file's data.")
        return out

    def preview_file(self, file_id: str) -> dict[str, Any]:
        """A size-capped, classified preview of one backup file's contents."""
        row = self._file_row(file_id)
        name = Path(row["relative_path"]).name
        if row["is_dir"]:
            return {"kind": "unavailable", "reason": "directory", "name": name}
        if row["target"]:
            return {
                "kind": "unavailable",
                "reason": "symlink",
                "name": name,
                "target": row["target"],
            }
        data = self._on_reader_thread(
            lambda: self._backup_reader().read_bytes(
                file_id, row["relative_path"], row["domain"], PREVIEW_MAX_BYTES + 1
            )
        )
        if data is None:
            return {"kind": "unavailable", "reason": "not-in-backup", "name": name}
        truncated = len(data) > PREVIEW_MAX_BYTES
        result = _sniff(data[:PREVIEW_MAX_BYTES], truncated)
        result["name"] = name
        result["size"] = row["size"]
        return result

    def close(self) -> None:
        reader, self._reader = self._reader, None
        if reader is not None:
            self._on_reader_thread(reader.close)
        self._reader_pool.shutdown(wait=True)

    # -- internals ------------------------------------------------------

    def _on_reader_thread(self, fn: Callable[[], _T]) -> _T:
        """Run ``fn`` on the one thread the backup reader is confined to."""
        return self._reader_pool.submit(fn).result()

    def _backup_reader(self) -> BackupReader:
        if self._reader is None:
            work_dir = self.case_dir / "decrypted"
            if self._is_encrypted:
                self._reader = EncryptedBackupReader(
                    self._backup_root, self._password or "", work_dir
                )
            else:
                self._reader = PlainBackupReader(self._backup_root, work_dir)
        return self._reader

    def _file_row(self, file_id: str) -> dict[str, Any]:
        with closing(self._connect()) as conn:
            row = conn.execute(
                "SELECT relative_path, domain, is_dir, size, target "
                "FROM files WHERE file_id = ?",
                (file_id,),
            ).fetchone()
        if row is None:
            raise AnalysisError("No such file in this backup.")
        return dict(row)

    @staticmethod
    def _files_where(domain: str | None, search: str | None) -> tuple[str, list[Any]]:
        clauses: list[str] = []
        params: list[Any] = []
        if domain:
            clauses.append("domain = ?")
            params.append(domain)
        if search:
            clauses.append("relative_path LIKE ?")
            params.append(f"%{search}%")
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        return where, params

    def _page_query(
        self,
        rows_sql: str,
        count_sql: str,
        params: list[Any],
        limit: int,
        offset: int,
    ) -> dict[str, Any]:
        limit, offset = _page(limit, offset)
        with closing(self._connect()) as conn:
            total = conn.execute(count_sql, params).fetchone()[0]
            rows = conn.execute(
                f"{rows_sql} LIMIT ? OFFSET ?", [*params, limit, offset]
            ).fetchall()
        return {
            "rows": [dict(row) for row in rows],
            "total": total,
            "limit": limit,
            "offset": offset,
        }


def load_case(case_dir: str | Path, password: str | None = None) -> CaseHandle:
    """Open an existing case folder. Raises :class:`AnalysisError` when it is
    not a case, or was written by an incompatible schema version."""
    path = Path(case_dir)
    descriptor_file = find_descriptor(path)
    if descriptor_file is None:
        raise AnalysisError(f"{path} does not contain a case descriptor (.json).")
    descriptor = read_descriptor(descriptor_file)
    if descriptor.schema_version != SCHEMA_VERSION:
        raise AnalysisError(
            f"Case was written by schema v{descriptor.schema_version}; "
            f"this build expects v{SCHEMA_VERSION}."
        )
    database = path / ANALYSIS_DB
    if not database.is_file():
        raise AnalysisError(f"{path} has a descriptor but no {ANALYSIS_DB}.")
    with closing(sqlite3.connect(f"file:{database}?mode=ro", uri=True)) as conn:
        version = conn.execute(
            "SELECT value FROM case_meta WHERE key = 'schema_version'"
        ).fetchone()
        udid_row = conn.execute("SELECT udid FROM backup_info LIMIT 1").fetchone()
    if version is not None and int(version[0]) != SCHEMA_VERSION:
        raise AnalysisError(
            f"{ANALYSIS_DB} was written by schema v{version[0]}; "
            f"this build expects v{SCHEMA_VERSION}."
        )
    udid = udid_row[0] if udid_row and udid_row[0] else None
    backup_root = path / "backup" / udid if udid else path / "backup"
    is_encrypted = bool(descriptor.source.get("is_encrypted"))
    return CaseHandle(path, descriptor, database, backup_root, is_encrypted, password)
