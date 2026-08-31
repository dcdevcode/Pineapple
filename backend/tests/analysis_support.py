"""Fixtures for the analysis tests: build a real (tiny) iOS backup on disk.

Nothing here is encrypted. An "encrypted" backup is just one whose
``Manifest.plist`` says ``IsEncrypted`` -- :class:`FakeEncryptedBackup` stands in
for the real decryption library and serves the cleartext fixtures.
"""

from __future__ import annotations

import base64
import datetime as dt
import gzip
import hashlib
import plistlib
import shutil
import sqlite3
import struct
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.keywrap import aes_key_unwrap, aes_key_wrap

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


class _FakeKeybag:
    """Minimal stand-in for ``google_iphone_dataprotection.Keybag``.

    Holds one AES key-wrapping key per keychain protection class the fixtures
    build items for; :meth:`unwrapKeyForClass` mirrors the real method's name and
    RFC 3394 behaviour (``KeyError`` for an unknown class, ``InvalidUnwrap`` for
    a bad blob -- both of which the reader treats as "cannot unwrap").
    """

    CLASS_KEYS: ClassVar[dict[int, bytes]] = {6: b"\x06" * 32, 11: b"\x0b" * 32}

    def unwrapKeyForClass(self, protection_class: int, wrapped: bytes) -> bytes:
        return aes_key_unwrap(self.CLASS_KEYS[protection_class], wrapped)


class FakeKeychainReader:
    """A ``SupportsKeychainUnwrap`` stub for testing the keychain parser without
    building a whole encrypted backup."""

    def unwrap_keychain_key(
        self, protection_class: int, wrapped: bytes
    ) -> bytes | None:
        try:
            return _FakeKeybag().unwrapKeyForClass(protection_class, wrapped)
        except Exception:
            return None


def keychain_item_blob(
    secret: str, *, protection_class: int = 6, version: int = 4
) -> bytes:
    """A ``v_Data`` blob the keychain decoder can round-trip via :class:`_FakeKeybag`.

    Layout: ``[version u32-le][class u32-le][wrapped-key-len u32-le][wrapped key]
    [AES-GCM ciphertext + 16-byte tag]`` over a ``{"v_Data": <secret>}`` plist,
    IV = 16 zero bytes (Apple's ``SecAESGCM``).
    """
    data_key = hashlib.sha256(f"{protection_class}:{secret}".encode()).digest()
    wrapped = aes_key_wrap(_FakeKeybag.CLASS_KEYS[protection_class], data_key)
    inner = plistlib.dumps({"v_Data": secret.encode()}, fmt=plistlib.FMT_BINARY)
    encryptor = Cipher(algorithms.AES(data_key), modes.GCM(b"\x00" * 16)).encryptor()
    ciphertext = encryptor.update(inner) + encryptor.finalize()
    header = struct.pack("<III", version, protection_class, len(wrapped))
    return header + wrapped + ciphertext + encryptor.tag


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


def _pb_varint(value: int) -> bytes:
    out = bytearray()
    while True:
        byte = value & 0x7F
        value >>= 7
        out.append(byte | (0x80 if value else 0))
        if not value:
            return bytes(out)


def _pb_len_field(field: int, payload: bytes) -> bytes:
    """One length-delimited protobuf field (wire type 2)."""
    return _pb_varint(field << 3 | 2) + _pb_varint(len(payload)) + payload


NOTE_BODY_TEXT = "Shopping list:\n- pineapples\n- forensics tooling"


def _note_proto(text: str) -> bytes:
    """A NoteStore ``ZDATA`` payload: gzip of Document(2) -> Note(3) -> text(2)."""
    note = _pb_len_field(2, text.encode())
    document = _pb_len_field(3, note)
    return gzip.compress(_pb_len_field(2, document))


def _note_store(path: Path) -> None:
    conn = sqlite3.connect(path)
    try:
        conn.executescript(
            """
CREATE TABLE ZICCLOUDSYNCINGOBJECT (
    Z_PK INTEGER PRIMARY KEY, ZTITLE1 TEXT, ZTITLE2 TEXT, ZSNIPPET TEXT,
    ZFOLDER INTEGER, ZCREATIONDATE1 REAL, ZMODIFICATIONDATE1 REAL
);
CREATE TABLE ZICNOTEDATA (Z_PK INTEGER PRIMARY KEY, ZNOTE INTEGER, ZDATA BLOB);
INSERT INTO ZICCLOUDSYNCINGOBJECT (Z_PK, ZTITLE2) VALUES (1, 'Notes');
INSERT INTO ZICCLOUDSYNCINGOBJECT
    (Z_PK, ZTITLE1, ZSNIPPET, ZFOLDER, ZCREATIONDATE1, ZMODIFICATIONDATE1)
VALUES (2, 'Shopping list', 'Shopping list: pineapples', 1, 700000000.0, 700000500.0);
            """
        )
        conn.execute(
            "INSERT INTO ZICNOTEDATA (Z_PK, ZNOTE, ZDATA) VALUES (1, 2, ?)",
            (_note_proto(NOTE_BODY_TEXT),),
        )
        conn.commit()
    finally:
        conn.close()


def _safari_history(path: Path) -> None:
    _script(
        path,
        """
CREATE TABLE history_items (id INTEGER PRIMARY KEY, url TEXT, visit_count INTEGER);
CREATE TABLE history_visits (
    id INTEGER PRIMARY KEY, history_item INTEGER, visit_time REAL, title TEXT
);
INSERT INTO history_items VALUES (1, 'https://apple.com/', 3);
INSERT INTO history_items VALUES (2, 'https://example.com/news', 1);
INSERT INTO history_visits VALUES (1, 1, 700000000.0, 'Apple');
INSERT INTO history_visits VALUES (2, 2, 700000300.0, 'Example News');
        """,
    )


def _safari_bookmarks(path: Path) -> None:
    _script(
        path,
        """
CREATE TABLE bookmarks (
    id INTEGER PRIMARY KEY, parent INTEGER, type INTEGER, title TEXT, url TEXT
);
INSERT INTO bookmarks VALUES (1, NULL, 0, 'Favorites', NULL);
INSERT INTO bookmarks VALUES (2, 1, 1, 'Apple', 'https://apple.com/');
INSERT INTO bookmarks VALUES (3, 1, 0, 'Empty folder', NULL);
        """,
    )


def _whatsapp(path: Path) -> None:
    _script(
        path,
        """
CREATE TABLE ZWACHATSESSION (
    Z_PK INTEGER PRIMARY KEY, ZCONTACTJID TEXT, ZPARTNERNAME TEXT,
    ZLASTMESSAGEDATE REAL, ZMESSAGECOUNTER INTEGER
);
CREATE TABLE ZWAMESSAGE (
    Z_PK INTEGER PRIMARY KEY, ZCHATSESSION INTEGER, ZISFROMME INTEGER,
    ZFROMJID TEXT, ZMESSAGEDATE REAL, ZTEXT TEXT, ZMESSAGETYPE INTEGER
);
INSERT INTO ZWACHATSESSION VALUES (1, '1555000@s.whatsapp.net', 'Alice', 7e8, 2);
INSERT INTO ZWAMESSAGE VALUES (1, 1, 0, '1555000@s.whatsapp.net', 700000100.0, 'hi', 0);
INSERT INTO ZWAMESSAGE VALUES (2, 1, 1, NULL, 700000200.0, NULL, 1);
        """,
    )


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


def _photos(path: Path) -> None:
    _script(
        path,
        """
CREATE TABLE ZASSET (
    Z_PK INTEGER PRIMARY KEY, ZFILENAME TEXT, ZDIRECTORY TEXT, ZKIND INTEGER,
    ZDATECREATED REAL, ZADDEDDATE REAL, ZWIDTH INTEGER, ZHEIGHT INTEGER,
    ZFAVORITE INTEGER, ZHIDDEN INTEGER, ZTRASHEDSTATE INTEGER,
    ZLATITUDE REAL, ZLONGITUDE REAL
);
CREATE TABLE ZGENERICALBUM (
    Z_PK INTEGER PRIMARY KEY, ZTITLE TEXT, ZKIND INTEGER, ZCACHEDCOUNT INTEGER,
    ZSTARTDATE REAL, ZENDDATE REAL
);
INSERT INTO ZASSET VALUES
    (1, 'IMG_0001.HEIC', 'DCIM/100APPLE', 0, 700000000.0, 700000050.0,
     4032, 3024, 1, 0, 0, 37.33, -122.03),
    (2, 'IMG_0002.MOV', 'DCIM/100APPLE', 1, 700000600.0, 700000650.0,
     1920, 1080, 0, 1, 0, -180.0, -180.0);
INSERT INTO ZGENERICALBUM VALUES (1, 'Holidays', 2, 12, 700000000.0, 700000600.0);
INSERT INTO ZGENERICALBUM VALUES (2, NULL, 2, 0, NULL, NULL);
        """,
    )


def _calendar(path: Path) -> None:
    _script(
        path,
        """
CREATE TABLE Calendar (ROWID INTEGER PRIMARY KEY, title TEXT);
CREATE TABLE Location (ROWID INTEGER PRIMARY KEY, title TEXT);
CREATE TABLE CalendarItem (
    ROWID INTEGER PRIMARY KEY, summary TEXT, calendar_id INTEGER,
    location_id INTEGER, description TEXT, start_date REAL, end_date REAL,
    all_day INTEGER
);
CREATE TABLE Participant (
    ROWID INTEGER PRIMARY KEY, owner_id INTEGER, email TEXT, name TEXT
);
INSERT INTO Calendar VALUES (1, 'Work');
INSERT INTO Location VALUES (1, 'Room 4');
INSERT INTO CalendarItem VALUES
    (1, 'Standup', 1, 1, 'Daily sync', 700000000.0, 700001800.0, 0),
    (2, 'Holiday', 1, NULL, NULL, 700100000.0, 700186400.0, 1);
INSERT INTO Participant VALUES (1, 1, 'ada@example.com', 'Ada');
INSERT INTO Participant VALUES (2, 1, 'grace@example.com', NULL);
        """,
    )


def _voicemail(path: Path) -> None:
    _script(
        path,
        """
CREATE TABLE voicemail (
    ROWID INTEGER PRIMARY KEY, sender TEXT, date INTEGER, duration INTEGER,
    trashed_date INTEGER, transcription TEXT
);
INSERT INTO voicemail VALUES (1, '+15551234567', 1600000000, 23, 0, 'Call me back');
INSERT INTO voicemail VALUES (2, '+15559998888', 1600100000, 8, 1600200000, NULL);
        """,
    )


def _accounts(path: Path) -> None:
    _script(
        path,
        """
CREATE TABLE ZACCOUNTTYPE (
    Z_PK INTEGER PRIMARY KEY, ZACCOUNTTYPEDESCRIPTION TEXT, ZIDENTIFIER TEXT
);
CREATE TABLE ZACCOUNT (
    Z_PK INTEGER PRIMARY KEY, ZACCOUNTTYPE INTEGER, ZIDENTIFIER TEXT,
    ZACCOUNTDESCRIPTION TEXT, ZUSERNAME TEXT, ZDATE REAL
);
INSERT INTO ZACCOUNTTYPE VALUES (1, 'IMAP', 'com.apple.account.IMAP');
INSERT INTO ZACCOUNT VALUES
    (1, 1, 'AAAA-1111', 'Work mail', 'ada@example.com', 700000000.0);
        """,
    )


def _knowledge_c(path: Path) -> None:
    _script(
        path,
        """
CREATE TABLE ZOBJECT (
    Z_PK INTEGER PRIMARY KEY, ZSTREAMNAME TEXT, ZVALUESTRING TEXT,
    ZVALUEINTEGER INTEGER, ZSTARTDATE REAL, ZENDDATE REAL
);
INSERT INTO ZOBJECT VALUES
    (1, '/app/usage', 'com.apple.mobilesafari', NULL, 700000000.0, 700000090.0),
    (2, '/app/inFocus', 'com.example.app', NULL, 700000200.0, 700000260.0),
    (3, '/display/isBacklit', NULL, 1, 700000300.0, 700000330.0),
    (4, '/nonsense/stream', 'ignored', NULL, 700000400.0, 700000401.0);
        """,
    )


# Naive on purpose: exercises the decoder's "assume UTC" path.
_KEYCHAIN_DATE = dt.datetime(2023, 6, 1, 12, 0, 0)


def _keychain(path: Path) -> None:
    plist = {
        "genp": [
            {
                "acct": "wifi-home",
                "svce": "AirPort",
                "agrp": "apple",
                "cdat": _KEYCHAIN_DATE,
                "mdat": _KEYCHAIN_DATE,
                "v_Data": keychain_item_blob("hunter2"),
            }
        ],
        "inet": [
            {
                "acct": "ada@example.com",
                "srvr": "mail.example.com",
                "agrp": "com.apple.mail",
                "v_Data": keychain_item_blob("s3cr3t", protection_class=11),
            }
        ],
        "cert": [],
        "keys": [],
    }
    path.write_bytes(plistlib.dumps(plist, fmt=plistlib.FMT_BINARY))


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
    _SourceDb("AppDomainGroup-group.com.apple.notes", "NoteStore.sqlite", _note_store),
    _SourceDb("CameraRollDomain", "Media/PhotoData/Photos.sqlite", _photos),
    _SourceDb("HomeDomain", "Library/Calendar/Calendar.sqlitedb", _calendar),
    _SourceDb("HomeDomain", "Library/Voicemail/voicemail.db", _voicemail),
    _SourceDb("HomeDomain", "Library/Accounts/Accounts3.sqlite", _accounts),
    _SourceDb(
        "AppDomainGroup-group.com.apple.coreduet",
        "Library/CoreDuet/Knowledge/knowledgeC.db",
        _knowledge_c,
    ),
    _SourceDb("KeychainDomain", "keychain-backup.plist", _keychain),
    _SourceDb("HomeDomain", "Library/Safari/History.db", _safari_history),
    _SourceDb("HomeDomain", "Library/Safari/Bookmarks.db", _safari_bookmarks),
    _SourceDb(
        "AppDomainGroup-group.net.whatsapp.WhatsApp.shared",
        "ChatStorage.sqlite",
        _whatsapp,
    ),
)

UDID = "00008110-000A1B2C3D4E001E"
SERIAL = "F17ABC123DEF"

# Manifest ``Files`` rows a full ``build_backup`` writes: one per source DB plus
# the fixed directory + symlink rows.
BACKUP_FILE_COUNT = len(_SOURCES) + 2


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
        self._keybag = _FakeKeybag()

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

    def extract_file_as_bytes(
        self, relative_path: str, *, domain_like: str | None = None
    ) -> bytes:
        self.test_decryption()
        fid = file_id(domain_like or "HomeDomain", relative_path)
        blob = self._root / fid[:2] / fid
        if not blob.is_file():
            raise FileNotFoundError(relative_path)
        return blob.read_bytes()
