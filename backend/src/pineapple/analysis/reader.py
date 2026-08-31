"""Uniform read access to an extracted backup, encrypted or not.

An unencrypted backup is a plain SQLite ``Manifest.db`` plus file blobs named by
SHA-1. An encrypted backup keeps the same layout but every blob -- and
``Manifest.db`` itself -- is AES-encrypted with per-file keys wrapped in the
keybag from ``Manifest.plist``. :class:`EncryptedBackupReader` delegates that to
the ``iphone_backup_decrypt`` library; :class:`PlainBackupReader` just copies.
"""

from __future__ import annotations

import contextlib
import shutil
import sqlite3
from pathlib import Path, PurePosixPath
from typing import Protocol

from iphone_backup_decrypt import EncryptedBackup

from pineapple.analysis.errors import AnalysisError
from pineapple.analysis.metadata import BackupMetadata

# SQLite write-ahead-log companions: a parser that opens the main DB needs these
# alongside it or it sees a stale snapshot (recent rows live only in the WAL).
_SIDECAR_SUFFIXES = ("-wal", "-shm")


class BackupReader(Protocol):
    """What the parsers need from a backup, regardless of encryption."""

    def manifest_connection(self) -> sqlite3.Connection:
        """A read-only connection to the (decrypted) ``Manifest.db``."""

    def extract_db(
        self, relative_path: str, domain: str, dest_dir: Path
    ) -> Path | None:
        """Decrypt/copy one source database (with WAL sidecars) into ``dest_dir``.

        Returns the path to the extracted main file, or ``None`` when the backup
        does not contain it.
        """

    def extract_file(
        self, file_id: str, relative_path: str, domain: str, dest: Path
    ) -> Path | None:
        """Decrypt/copy one backup file to ``dest`` (a full path).

        Regular files only. Returns ``dest``, or ``None`` when the file's data is
        not in the backup.
        """

    def read_bytes(
        self, file_id: str, relative_path: str, domain: str, max_bytes: int
    ) -> bytes | None:
        """Return up to ``max_bytes`` of one backup file, or ``None`` if absent."""

    def unwrap_keychain_key(
        self, protection_class: int, wrapped: bytes
    ) -> bytes | None:
        """Unwrap a keychain item's data key with the backup keybag.

        Only an unlocked encrypted backup can do this; a plain backup (whose
        keychain is device-bound and not recoverable offline) returns ``None``,
        as does any item whose protection class the keybag cannot open.
        """

    def close(self) -> None:
        """Release the manifest connection and any temp state."""


def open_reader(
    backup_root: Path, metadata: BackupMetadata, password: str, work_dir: Path
) -> BackupReader:
    """Pick the reader for ``backup_root`` based on ``metadata.is_encrypted``."""
    work_dir.mkdir(parents=True, exist_ok=True)
    if metadata.is_encrypted:
        return EncryptedBackupReader(backup_root, password, work_dir)
    return PlainBackupReader(backup_root, work_dir)


def _open_readonly(path: Path) -> sqlite3.Connection:
    return sqlite3.connect(f"file:{path}?mode=ro", uri=True)


class PlainBackupReader:
    """Reader for an unencrypted backup: everything is already in the clear."""

    def __init__(self, backup_root: Path, work_dir: Path) -> None:
        self._root = backup_root
        self._work_dir = work_dir
        self._conn: sqlite3.Connection | None = None

    def manifest_connection(self) -> sqlite3.Connection:
        if self._conn is None:
            copy = self._work_dir / "Manifest.db"
            shutil.copyfile(self._root / "Manifest.db", copy)
            self._conn = _open_readonly(copy)
        return self._conn

    def _blob_path(self, file_id: str) -> Path:
        return self._root / file_id[:2] / file_id

    def _file_id(self, relative_path: str, domain: str) -> str | None:
        cursor = self.manifest_connection().execute(
            "SELECT fileID FROM Files "
            "WHERE relativePath = ? AND domain = ? AND flags = 1 LIMIT 1",
            (relative_path, domain),
        )
        row = cursor.fetchone()
        return row[0] if row else None

    def extract_db(
        self, relative_path: str, domain: str, dest_dir: Path
    ) -> Path | None:
        file_id = self._file_id(relative_path, domain)
        if file_id is None:
            return None
        blob = self._blob_path(file_id)
        if not blob.is_file():
            return None
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / PurePosixPath(relative_path).name
        shutil.copyfile(blob, dest)
        for suffix in _SIDECAR_SUFFIXES:
            sidecar_id = self._file_id(relative_path + suffix, domain)
            if sidecar_id is not None and self._blob_path(sidecar_id).is_file():
                shutil.copyfile(
                    self._blob_path(sidecar_id), dest.with_name(dest.name + suffix)
                )
        return dest

    def extract_file(
        self, file_id: str, relative_path: str, domain: str, dest: Path
    ) -> Path | None:
        blob = self._blob_path(file_id)
        if not blob.is_file():
            return None
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(blob, dest)
        return dest

    def read_bytes(
        self, file_id: str, relative_path: str, domain: str, max_bytes: int
    ) -> bytes | None:
        blob = self._blob_path(file_id)
        if not blob.is_file():
            return None
        with blob.open("rb") as handle:
            return handle.read(max_bytes)

    def unwrap_keychain_key(
        self, protection_class: int, wrapped: bytes
    ) -> bytes | None:
        return None  # a plain backup's keychain is not recoverable offline

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None


class EncryptedBackupReader:
    """Reader for an encrypted backup, backed by ``iphone_backup_decrypt``."""

    def __init__(self, backup_root: Path, password: str, work_dir: Path) -> None:
        self._work_dir = work_dir
        self._conn: sqlite3.Connection | None = None
        self._backup = EncryptedBackup(
            backup_directory=str(backup_root), passphrase=password
        )
        try:
            self._backup.test_decryption()
        except ValueError as error:
            raise AnalysisError("Incorrect or missing backup password.") from error
        except Exception as error:  # malformed keybag / manifest
            raise AnalysisError(
                f"Could not open the encrypted backup ({error})."
            ) from error

    def manifest_connection(self) -> sqlite3.Connection:
        if self._conn is None:
            copy = self._work_dir / "Manifest.db"
            self._backup.save_manifest_file(str(copy))
            self._conn = _open_readonly(copy)
        return self._conn

    def extract_db(
        self, relative_path: str, domain: str, dest_dir: Path
    ) -> Path | None:
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / PurePosixPath(relative_path).name
        try:
            self._backup.extract_file(
                relative_path=relative_path,
                domain_like=domain,
                output_filename=str(dest),
            )
        except FileNotFoundError:
            return None
        for suffix in _SIDECAR_SUFFIXES:
            with contextlib.suppress(FileNotFoundError):
                self._backup.extract_file(
                    relative_path=relative_path + suffix,
                    domain_like=domain,
                    output_filename=str(dest.with_name(dest.name + suffix)),
                )
        return dest

    def extract_file(
        self, file_id: str, relative_path: str, domain: str, dest: Path
    ) -> Path | None:
        dest.parent.mkdir(parents=True, exist_ok=True)
        try:
            self._backup.extract_file(
                relative_path=relative_path,
                domain_like=domain,
                output_filename=str(dest),
            )
        except FileNotFoundError:
            return None
        return dest

    def read_bytes(
        self, file_id: str, relative_path: str, domain: str, max_bytes: int
    ) -> bytes | None:
        try:
            data = self._backup.extract_file_as_bytes(relative_path, domain_like=domain)
        except FileNotFoundError:
            return None
        return bytes(data[:max_bytes])

    def unwrap_keychain_key(
        self, protection_class: int, wrapped: bytes
    ) -> bytes | None:
        # `iphone_backup_decrypt` unlocks the keybag in `test_decryption()` (run
        # in `__init__`); reach into it the same defensive way `close()` reaches
        # for `_cleanup`. `unwrapKeyForClass` raises for a class the keybag has
        # no key for (e.g. a passcode-protected class on a device with no
        # passcode) -- treated as "cannot unwrap".
        keybag = getattr(self._backup, "_keybag", None)
        unwrap = getattr(keybag, "unwrapKeyForClass", None)
        if unwrap is None:
            return None
        try:
            result = unwrap(protection_class, wrapped)
        except Exception:
            return None
        return result if isinstance(result, bytes) else None

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None
        # `iphone_backup_decrypt` extracts into a private temp dir and only
        # removes it in its own (private, undocumented) `_cleanup`. Call it if
        # present; tolerate its absence on a library upgrade.
        cleanup = getattr(self._backup, "_cleanup", None)
        if callable(cleanup):
            cleanup()
