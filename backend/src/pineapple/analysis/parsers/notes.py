"""Parse Apple Notes (``AppDomainGroup-group.com.apple.notes/NoteStore.sqlite``).

``ZICCLOUDSYNCINGOBJECT`` holds a note's title, snippet, folder and timestamps.
The body lives in ``ZICNOTEDATA.ZDATA`` -- a gzip-compressed protobuf. We only
need the plain text: it sits at ``Document (field 2) -> Note (field 3) ->
note_text (field 2)`` (see threeplanetssoftware/apple_cloud_notes_parser). The
protobuf walk is best-effort; the always-present ``ZSNIPPET`` is the fallback.
"""

from __future__ import annotations

import gzip
import sqlite3
from pathlib import Path

from pineapple.analysis.parsers._common import as_text, mac_absolute_to_iso, read_source

_LEN_WIRE_TYPE = 2
_NOTE_TEXT_PATH = (2, 3, 2)

_QUERY = """
SELECT
    o.Z_PK               AS rowid,
    o.ZTITLE1            AS title,
    o.ZSNIPPET           AS snippet,
    o.ZCREATIONDATE1     AS created,
    o.ZMODIFICATIONDATE1 AS modified,
    f.ZTITLE2            AS folder,
    d.ZDATA              AS data
FROM ZICCLOUDSYNCINGOBJECT o
LEFT JOIN ZICCLOUDSYNCINGOBJECT f ON f.Z_PK = o.ZFOLDER
LEFT JOIN ZICNOTEDATA d ON d.ZNOTE = o.Z_PK
WHERE o.ZTITLE1 IS NOT NULL OR d.ZDATA IS NOT NULL
"""


def _read_varint(data: bytes, pos: int) -> tuple[int, int]:
    result = shift = 0
    while True:
        byte = data[pos]
        pos += 1
        result |= (byte & 0x7F) << shift
        if not byte & 0x80:
            return result, pos
        shift += 7


def walk_protobuf_string(data: bytes, path: tuple[int, ...]) -> str | None:
    """Follow ``path`` (a chain of field numbers) through nested length-delimited
    protobuf messages and return the leaf as UTF-8 text, or ``None``."""
    try:
        target, rest = path[0], path[1:]
        pos = 0
        while pos < len(data):
            tag, pos = _read_varint(data, pos)
            field, wire = tag >> 3, tag & 0x07
            if wire != _LEN_WIRE_TYPE:
                _, pos = _read_varint(data, pos)  # only LEN chains matter here
                continue
            length, pos = _read_varint(data, pos)
            chunk = data[pos : pos + length]
            pos += length
            if field != target:
                continue
            return walk_protobuf_string(chunk, rest) if rest else chunk.decode("utf-8")
    except IndexError, UnicodeDecodeError:
        return None
    return None


def _body(blob: object) -> str | None:
    if not isinstance(blob, bytes):
        return None
    try:
        return walk_protobuf_string(gzip.decompress(blob), _NOTE_TEXT_PATH)
    except OSError, EOFError:
        return None


def parse_notes(source_db: Path, conn: sqlite3.Connection) -> int:
    """Load ``NoteStore.sqlite`` into the ``notes`` table; return the row count."""
    with read_source(source_db, "NoteStore.sqlite") as source:
        rows = source.execute(_QUERY).fetchall()

    conn.executemany(
        "INSERT OR REPLACE INTO notes"
        "(rowid, folder, title, snippet, body, created_utc, modified_utc) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        [
            (
                row["rowid"],
                as_text(row["folder"]),
                as_text(row["title"]),
                as_text(row["snippet"]),
                _body(row["data"]),
                mac_absolute_to_iso(row["created"]),
                mac_absolute_to_iso(row["modified"]),
            )
            for row in rows
        ],
    )
    return len(rows)
