"""Reading and unpacking a ``.pineapple`` archive.

A ``.pineapple`` file is an uncompressed zip whose entries are rooted at the
device UDID: ``<udid>/Info.plist``, ``<udid>/Manifest.db``, ``<udid>/aa/aa11..``.
"""

from __future__ import annotations

import plistlib
import threading
import zipfile
from pathlib import Path
from typing import Any

from pineapple.analysis.errors import AnalysisError
from pineapple.analysis.metadata import BackupMetadata, from_plists

_ROOT_PLISTS = ("Info.plist", "Manifest.plist", "Status.plist")


class ArchiveCancelled(Exception):
    """Raised out of :func:`extract` when its ``cancelled`` event is set."""


def _backup_root(names: list[str]) -> str:
    """The single top-level directory every entry sits under (the UDID)."""
    tops = {name.split("/", 1)[0] for name in names if name}
    if len(tops) != 1:
        raise AnalysisError(
            "This does not look like a .pineapple image: expected a single "
            f"top-level folder, found {len(tops)}."
        )
    return tops.pop()


def _load_plist(raw: bytes, name: str) -> dict[str, Any]:
    try:
        value = plistlib.loads(raw)
    except Exception as error:
        raise AnalysisError(f"{name} is not a readable plist ({error}).") from error
    if not isinstance(value, dict):
        raise AnalysisError(f"{name} has an unexpected shape.")
    return value


def peek(pineapple_path: str | Path) -> BackupMetadata:
    """Device and backup facts from the archive's plists, without unpacking it.

    Raises :class:`AnalysisError` when the file is missing, not a zip, or does
    not carry the three root plists.
    """
    path = Path(pineapple_path)
    if not path.is_file():
        raise AnalysisError(f"No file at {path}.")
    try:
        with zipfile.ZipFile(path) as archive:
            names = archive.namelist()
            root = _backup_root(names)
            plists = {}
            for plist_name in _ROOT_PLISTS:
                member = f"{root}/{plist_name}"
                if member not in names:
                    raise AnalysisError(f"The archive is missing {plist_name}.")
                plists[plist_name] = _load_plist(archive.read(member), plist_name)
    except zipfile.BadZipFile as error:
        raise AnalysisError(f"{path.name} is not a valid zip archive.") from error
    return from_plists(
        plists["Info.plist"], plists["Manifest.plist"], plists["Status.plist"]
    )


def extract(
    pineapple_path: str | Path,
    dest_dir: str | Path,
    cancelled: threading.Event,
) -> Path:
    """Unpack the archive into ``dest_dir``; return the ``<udid>`` backup root.

    Checks ``cancelled`` between members and raises :class:`ArchiveCancelled`
    when it is set.
    """
    path = Path(pineapple_path)
    dest = Path(dest_dir)
    with zipfile.ZipFile(path) as archive:
        root = _backup_root(archive.namelist())
        for member in archive.infolist():
            if cancelled.is_set():
                raise ArchiveCancelled
            archive.extract(member, dest)
    backup_root = dest / root
    if not (backup_root / "Manifest.db").is_file():
        raise AnalysisError("The extracted archive has no Manifest.db.")
    return backup_root
