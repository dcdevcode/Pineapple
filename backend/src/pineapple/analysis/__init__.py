"""Offline analysis of a ``.pineapple`` logical image.

The :class:`~pineapple.backup.DeviceBackup` feature produces a ``.pineapple``
archive -- an uncompressed zip of a MobileBackup2 backup. This package opens one
of those archives (encrypted or not), extracts and decrypts what it needs, and
parses it into a per-case SQLite database (``analysis.db``) plus a human-facing
JSON descriptor. The frontend's Analysis tab browses the result.

Everything a *case* needs lives in one folder the user picks:

``<case>/<title>.json``
    The case descriptor -- device metadata, the source archive path/hash, and
    the parse outcome. Source of truth for reopening a case.
``<case>/backup/<udid>/``
    The archive extracted as-is (encrypted blobs stay encrypted on disk).
``<case>/decrypted/``
    ``Manifest.db`` and the source databases the parsers needed, decrypted.
``<case>/analysis.db``
    The results database (see :mod:`pineapple.analysis.schema`).
"""

from pineapple.analysis.errors import AnalysisError

__all__ = ["AnalysisError"]
