"""File hashing shared by the acquisition and analysis sides.

Kept in its own module so :mod:`pineapple.backup` does not have to import from
:mod:`pineapple.analysis`.
"""

from __future__ import annotations

import hashlib
import threading
from pathlib import Path


class HashingCancelled(Exception):
    """Raised inside :func:`sha256_file` when its cancellation event is set."""


def sha256_file(path: Path, *, cancelled: threading.Event | None = None) -> str:
    """The SHA-256 hex digest of a file, read in 1 MiB chunks.

    When ``cancelled`` is given, it is checked between chunks so a large file can
    be interrupted; a set event raises :class:`HashingCancelled`.
    """
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            if cancelled is not None and cancelled.is_set():
                raise HashingCancelled
            digest.update(chunk)
    return digest.hexdigest()
