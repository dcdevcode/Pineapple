"""Parse the camera roll from ``Photos.sqlite`` (Core Data, ``Z``-prefixed).

Source: ``CameraRollDomain/Media/PhotoData/Photos.sqlite``. ``ZASSET`` is one row
per photo or video (``ZGENERICASSET`` on iOS <= 13); ``ZGENERICALBUM`` is one row
per album. Dates are Cocoa absolute time; a latitude/longitude of ``-180`` means
"no location".

One parser fills ``photos`` + ``photo_albums`` and returns the photo count. Each
asset row also carries the Manifest file id of the image itself (domain + relative
path hashed the way iOS names backup blobs) so the browser can preview it.
"""

from __future__ import annotations

import hashlib
import sqlite3
from pathlib import Path

from pineapple.analysis.parsers._common import (
    as_text,
    mac_absolute_to_iso,
    read_source,
)

_ASSET_DOMAIN = "CameraRollDomain"
_NO_LOCATION = -180.0
_ALBUM_KINDS = {2: "user", 4000: "folder"}

_ALBUMS_QUERY = """
SELECT ZTITLE AS title, ZKIND AS kind, ZCACHEDCOUNT AS count,
       ZSTARTDATE AS start_date, ZENDDATE AS end_date
FROM ZGENERICALBUM
WHERE ZTITLE IS NOT NULL AND ZTITLE <> ''
"""


def _assets_query(table: str) -> str:
    return f"""
SELECT Z_PK AS rowid, ZFILENAME AS filename, ZDIRECTORY AS directory,
       ZKIND AS kind, ZDATECREATED AS created, ZADDEDDATE AS added,
       ZWIDTH AS width, ZHEIGHT AS height, ZFAVORITE AS favorite,
       ZHIDDEN AS hidden, ZTRASHEDSTATE AS trashed,
       ZLATITUDE AS latitude, ZLONGITUDE AS longitude
FROM {table}
"""


def _asset_table(source: sqlite3.Connection) -> str:
    names = {
        row[0]
        for row in source.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
    }
    for candidate in ("ZASSET", "ZGENERICASSET"):
        if candidate in names:
            return candidate
    raise sqlite3.OperationalError("no ZASSET / ZGENERICASSET table")


def _file_id(directory: object, filename: object) -> str | None:
    if not directory or not filename:
        return None
    relative_path = f"Media/{directory}/{filename}"
    return hashlib.sha1(f"{_ASSET_DOMAIN}-{relative_path}".encode()).hexdigest()


def _coordinate(value: object) -> float | None:
    if not isinstance(value, (int, float)) or value == _NO_LOCATION:
        return None
    return float(value)


def _kind(value: object) -> str:
    return "video" if value == 1 else "image"


def parse_photos(source_db: Path, conn: sqlite3.Connection) -> int:
    """Fill ``photos`` + ``photo_albums`` from ``Photos.sqlite``; return the photo
    count."""
    with read_source(source_db, "Photos.sqlite") as source:
        assets = source.execute(_assets_query(_asset_table(source))).fetchall()
        albums = source.execute(_ALBUMS_QUERY).fetchall()

    conn.executemany(
        "INSERT OR REPLACE INTO photos"
        "(rowid, file_id, filename, directory, kind, created_utc, added_utc, "
        "width, height, favorite, hidden, trashed, latitude, longitude) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [
            (
                row["rowid"],
                _file_id(row["directory"], row["filename"]),
                as_text(row["filename"]),
                as_text(row["directory"]),
                _kind(row["kind"]),
                mac_absolute_to_iso(row["created"]),
                mac_absolute_to_iso(row["added"]),
                row["width"],
                row["height"],
                1 if row["favorite"] else 0,
                1 if row["hidden"] else 0,
                1 if row["trashed"] else 0,
                _coordinate(row["latitude"]),
                _coordinate(row["longitude"]),
            )
            for row in assets
        ],
    )
    conn.executemany(
        "INSERT INTO photo_albums(title, kind, count, start_utc, end_utc) "
        "VALUES (?, ?, ?, ?, ?)",
        [
            (
                as_text(row["title"]),
                _ALBUM_KINDS.get(row["kind"], "smart"),
                row["count"] or 0,
                mac_absolute_to_iso(row["start_date"]),
                mac_absolute_to_iso(row["end_date"]),
            )
            for row in albums
        ],
    )
    return len(assets)
