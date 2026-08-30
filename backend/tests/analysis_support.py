"""Fixtures for the analysis tests: build a real (tiny) iOS backup on disk.

Nothing here is encrypted. An "encrypted" backup is just one whose
``Manifest.plist`` says ``IsEncrypted`` -- :class:`FakeEncryptedBackup` stands in
for the real decryption library and serves the cleartext fixtures.
"""

from __future__ import annotations

import base64
import hashlib
import plistlib
import shutil
import sqlite3
import zipfile
from dataclasses import dataclass
from pathlib import Path

# 2001-01-01 in ns; add per-message offsets. (Cocoa absolute time, iOS 11+.)
_NS_2001 = 700_000_000 * 1_000_000_000

# A real iMessage ``attributedBody`` typedstream (an NSMutableAttributedString
# wrapping the text below). Source: ReagentX/imessage-exporter test data (MIT).
ATTRIBUTED_BODY_TEXT = "Noter test"
ATTRIBUTED_BODY_SAMPLE = base64.b64decode(
    "BAtzdHJlYW10eXBlZIHoA4QBQISEhBlOU011dGFibGVBdHRyaWJ1dGVkU3RyaW5nAISEEk5T"
    "QXR0cmlidXRlZFN0cmluZwCEhAhOU09iamVjdACFkoSEhA9OU011dGFibGVTdHJpbmcBhIQI"
    "TlNTdHJpbmcBlYQBKwpOb3RlciB0ZXN0hoQCaUkBCpKEhIQMTlNEaWN0aW9uYXJ5AJWEAWkB"
    "koSYmB1fX2tJTU1lc3NhZ2VQYXJ0QXR0cmlidXRlTmFtZYaShISECE5TTnVtYmVyAISEB05T"
    "VmFsdWUAlYQBKoSbmwCGhoY="
)


def file_id(domain: str, relative_path: str) -> str:
    return hashlib.sha1(f"{domain}-{relative_path}".encode()).hexdigest()


def mbfile_blob(
    *,
    size: int = 0,
    mode: int = 0o100644,
    mtime: int = 1_600_000_000,
    ctime: int = 1_600_000_000,
    btime: int = 1_599_000_000,
    target: str | None = None,
) -> bytes:
    record: dict[str, object] = {
        "Size": size,
        "Mode": mode,
        "LastModified": mtime,
        "LastStatusChange": ctime,
        "Birth": btime,
    }
    objects: list[object] = ["$null", record]
    if target is not None:
        record["Target"] = plistlib.UID(2)
        objects.append(target)
    plist = {
        "$version": 100000,
        "$archiver": "NSKeyedArchiver",
        "$top": {"root": plistlib.UID(1)},
        "$objects": objects,
    }
    return plistlib.dumps(plist, fmt=plistlib.FMT_BINARY)


def _script(path: Path, statements: str) -> None:
    conn = sqlite3.connect(path)
    try:
        conn.executescript(statements)
        conn.commit()
    finally:
        conn.close()


def _sms_db(path: Path) -> None:
    _script(
        path,
        """
CREATE TABLE handle (ROWID INTEGER PRIMARY KEY, id TEXT);
CREATE TABLE message (
    ROWID INTEGER PRIMARY KEY, text TEXT, attributedBody BLOB, handle_id INTEGER,
    is_from_me INTEGER, date INTEGER, service TEXT
);
CREATE TABLE chat_message_join (chat_id INTEGER, message_id INTEGER);
CREATE TABLE message_attachment_join (message_id INTEGER, attachment_id INTEGER);

INSERT INTO handle VALUES (1, '+15551234567');
INSERT INTO chat_message_join VALUES (7, 1), (7, 2), (7, 3);
INSERT INTO message_attachment_join VALUES (3, 99);
        """,
    )
    conn = sqlite3.connect(path)
    try:
        # Row 3 has no plain text -- its body lives only in attributedBody, the
        # iOS 16+ case the parser must recover.
        conn.executemany(
            "INSERT INTO message"
            "(ROWID, text, attributedBody, handle_id, is_from_me, date, service) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            [
                (1, "hello there", None, 1, 0, _NS_2001 + 10, "iMessage"),
                (2, "reply back", None, 1, 1, _NS_2001 + 20, "iMessage"),
                (3, None, ATTRIBUTED_BODY_SAMPLE, 1, 0, _NS_2001 + 30, "SMS"),
            ],
        )
        conn.commit()
    finally:
        conn.close()


def _call_history(path: Path) -> None:
    _script(
        path,
        """
CREATE TABLE ZCALLRECORD (
    Z_PK INTEGER PRIMARY KEY, ZDATE REAL, ZDURATION REAL, ZADDRESS BLOB,
    ZORIGINATED INTEGER, ZANSWERED INTEGER, ZSERVICE_PROVIDER TEXT
);
INSERT INTO ZCALLRECORD VALUES (1, 700000000.0, 42.0, '+15551234567', 1, 1, 'Phone');
INSERT INTO ZCALLRECORD VALUES (2, 700000100.0, 0.0, '+15559998888', 0, 0, 'Phone');
INSERT INTO ZCALLRECORD VALUES (3, 700000200.0, 65.0, 'a@b.com', 0, 1, 'FaceTime');
        """,
    )


def _address_book(path: Path) -> None:
    _script(
        path,
        """
CREATE TABLE ABPerson (
    ROWID INTEGER PRIMARY KEY, First TEXT, Last TEXT, Organization TEXT
);
CREATE TABLE ABMultiValue (
    UID INTEGER PRIMARY KEY, record_id INTEGER, property INTEGER, value
);
INSERT INTO ABPerson VALUES (1, 'Ada', 'Lovelace', 'Analytical Engines');
INSERT INTO ABPerson VALUES (2, 'Grace', 'Hopper', NULL);
INSERT INTO ABMultiValue VALUES (1, 1, 3, '+15551234567');
INSERT INTO ABMultiValue VALUES (2, 1, 4, 'ada@example.com');
INSERT INTO ABMultiValue VALUES (3, 1, 3, '+15550000000');
INSERT INTO ABMultiValue VALUES (4, 2, 4, 'grace@example.com');
        """,
    )


@dataclass(frozen=True)
class _SourceDb:
    domain: str
    relative_path: str
    build: object  # Callable[[Path], None]


_SOURCES = (
    _SourceDb("HomeDomain", "Library/SMS/sms.db", _sms_db),
    _SourceDb(
        "HomeDomain", "Library/CallHistoryDB/CallHistory.storedata", _call_history
    ),
    _SourceDb("HomeDomain", "Library/AddressBook/AddressBook.sqlitedb", _address_book),
)

UDID = "00008110-000A1B2C3D4E001E"
SERIAL = "F17ABC123DEF"


def build_backup(
    root: Path,
    *,
    udid: str = UDID,
    encrypted: bool = False,
    include_sources: bool = True,
    apps: dict[str, dict[str, str]] | None = None,
) -> Path:
    """Write a minimal MobileBackup2 backup under ``root/<udid>/``; return it."""
    backup = root / udid
    backup.mkdir(parents=True)

    manifest_files: list[tuple[str, str, str, int, bytes]] = []

    def add_blob(domain: str, relative_path: str, builder: object) -> None:
        fid = file_id(domain, relative_path)
        blob_dir = backup / fid[:2]
        blob_dir.mkdir(exist_ok=True)
        builder(blob_dir / fid)  # type: ignore[operator]
        size = (blob_dir / fid).stat().st_size
        manifest_files.append((fid, domain, relative_path, 1, mbfile_blob(size=size)))

    if include_sources:
        for source in _SOURCES:
            add_blob(source.domain, source.relative_path, source.build)

    # A directory row and a symlink row, so the file index has variety.
    manifest_files.append(
        (
            file_id("HomeDomain", "Library/SMS"),
            "HomeDomain",
            "Library/SMS",
            2,
            mbfile_blob(mode=0o040755),
        )
    )
    manifest_files.append(
        (
            file_id("HomeDomain", "Library/link"),
            "HomeDomain",
            "Library/link",
            4,
            mbfile_blob(mode=0o120777, target="SMS/sms.db"),
        )
    )

    manifest_db = backup / "Manifest.db"
    conn = sqlite3.connect(manifest_db)
    try:
        conn.execute(
            "CREATE TABLE Files (fileID TEXT PRIMARY KEY, domain TEXT, "
            "relativePath TEXT, flags INTEGER, file BLOB)"
        )
        conn.executemany("INSERT INTO Files VALUES (?, ?, ?, ?, ?)", manifest_files)
        conn.commit()
    finally:
        conn.close()

    info = {
        "Device Name": "Test iPhone",
        "Product Type": "iPhone14,5",
        "Product Name": "iPhone 13",
        "Product Version": "17.5.1",
        "Build Version": "21F90",
        "Serial Number": SERIAL,
        "Target Identifier": udid,
        "Unique Identifier": udid.replace("-", "").upper(),
        "Installed Applications": ["com.apple.mobilesafari"],
        "Applications": apps
        or {
            "com.example.app": {
                "CFBundleIdentifier": "com.example.app",
                "CFBundleDisplayName": "Example",
                "CFBundleShortVersionString": "2.1",
            }
        },
    }
    (backup / "Info.plist").write_bytes(plistlib.dumps(info))
    (backup / "Manifest.plist").write_bytes(
        plistlib.dumps(
            {
                "IsEncrypted": encrypted,
                "WasPasscodeSet": True,
                "BackupKeyBag": b"fake-keybag" if encrypted else b"",
                "Lockdown": {"ProductVersion": "17.5.1"},
            },
            fmt=plistlib.FMT_BINARY,
        )
    )
    (backup / "Status.plist").write_bytes(
        plistlib.dumps(
            {"IsFullBackup": True, "SnapshotState": "finished", "Version": "3.3"},
            fmt=plistlib.FMT_BINARY,
        )
    )
    return backup


def make_pineapple(backup_root: Path, dest: Path) -> Path:
    """Zip a ``build_backup`` result into a ``.pineapple`` archive at ``dest``."""
    with zipfile.ZipFile(dest, "w", zipfile.ZIP_STORED, allowZip64=True) as archive:
        for path in sorted(backup_root.rglob("*")):
            if path.is_file():
                archive.write(path, path.relative_to(backup_root.parent).as_posix())
    return dest


class FakeEncryptedBackup:
    """Stand-in for ``iphone_backup_decrypt.EncryptedBackup``.

    Serves the cleartext fixtures a :func:`build_backup` produced. ``passphrase``
    must equal :data:`PASSWORD` or :meth:`test_decryption` raises, mirroring the
    real library's ``ValueError`` on a wrong password.
    """

    PASSWORD = "correct horse"

    def __init__(self, *, backup_directory: str, passphrase: str) -> None:
        self._root = Path(backup_directory)
        self._passphrase = passphrase

    def test_decryption(self) -> bool:
        if self._passphrase != self.PASSWORD:
            raise ValueError("Failed to decrypt keys: incorrect passphrase?")
        return True

    def save_manifest_file(self, output_filename: str) -> None:
        self.test_decryption()
        shutil.copyfile(self._root / "Manifest.db", output_filename)

    def extract_file(
        self,
        *,
        relative_path: str,
        domain_like: str | None = None,
        output_filename: str,
    ) -> None:
        self.test_decryption()
        fid = file_id(domain_like or "HomeDomain", relative_path)
        blob = self._root / fid[:2] / fid
        if not blob.is_file():
            raise FileNotFoundError(relative_path)
        Path(output_filename).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(blob, output_filename)
