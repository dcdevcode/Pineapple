"""Decode one ``Manifest.db`` ``Files.file`` BLOB.

Each row of the ``Files`` table carries a ``file`` column: an ``NSKeyedArchiver``
binary plist describing the backed-up item (size, timestamps, mode, symlink
target). This unwraps the ``$objects`` graph into a flat record.
"""

from __future__ import annotations

import plistlib
import stat
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class MbFile:
    """The fields of an ``MBFile`` record we keep."""

    size: int = 0
    mode: int | None = None
    mtime: int | None = None
    ctime: int | None = None
    btime: int | None = None
    target: str | None = None

    @property
    def is_dir(self) -> bool:
        return self.mode is not None and stat.S_ISDIR(self.mode)

    @property
    def is_symlink(self) -> bool:
        return self.mode is not None and stat.S_ISLNK(self.mode)


def _int(value: Any) -> int | None:
    return value if isinstance(value, int) else None


def decode_mbfile(blob: bytes | None) -> MbFile:
    """Best-effort decode; returns an empty :class:`MbFile` on anything unexpected."""
    if not blob:
        return MbFile()
    try:
        plist = plistlib.loads(blob)
        objects = plist["$objects"]
        root_uid = plist["$top"]["root"]
        record = objects[root_uid.data]

        def deref(value: Any) -> Any:
            return objects[value.data] if isinstance(value, plistlib.UID) else value

        mode = _int(record.get("Mode"))
        target = deref(record.get("Target"))
        return MbFile(
            size=_int(record.get("Size")) or 0,
            mode=mode,
            mtime=_int(record.get("LastModified")),
            ctime=_int(record.get("LastStatusChange")),
            btime=_int(record.get("Birth")),
            target=target if isinstance(target, str) and target else None,
        )
    except Exception:
        return MbFile()
