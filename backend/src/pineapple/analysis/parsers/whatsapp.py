"""Parse WhatsApp chats and messages.

Source: ``AppDomainGroup-group.net.whatsapp.WhatsApp.shared/ChatStorage.sqlite``
(Core Data, so tables are ``Z``-prefixed). ``ZWACHATSESSION`` is one row per
conversation; ``ZWAMESSAGE`` one row per message, linked by ``ZCHATSESSION``.
Dates are Cocoa absolute time. One parser fills both ``whatsapp_*`` tables and
returns the message count.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from pineapple.analysis.parsers._common import (
    as_text,
    mac_absolute_to_iso,
    read_source,
)

_MEDIA_TYPES = {
    0: "text",
    1: "image",
    2: "video",
    3: "audio",
    4: "contact",
    5: "location",
    7: "url",
    8: "document",
}

_CHATS_QUERY = """
SELECT ZCONTACTJID AS jid, ZPARTNERNAME AS name,
       ZLASTMESSAGEDATE AS last_date, ZMESSAGECOUNTER AS message_count
FROM ZWACHATSESSION
"""

_MESSAGES_QUERY = """
SELECT m.Z_PK AS rowid, s.ZCONTACTJID AS chat_jid, s.ZPARTNERNAME AS chat_name,
       m.ZISFROMME AS from_me, m.ZFROMJID AS sender, m.ZMESSAGEDATE AS date,
       m.ZTEXT AS text, m.ZMESSAGETYPE AS message_type
FROM ZWAMESSAGE m
LEFT JOIN ZWACHATSESSION s ON s.Z_PK = m.ZCHATSESSION
ORDER BY m.ZMESSAGEDATE
"""


def _media_type(value: object) -> str:
    if not isinstance(value, int):
        return "other"
    return _MEDIA_TYPES.get(value, "other")


def parse_whatsapp(source_db: Path, conn: sqlite3.Connection) -> int:
    """Fill both ``whatsapp_*`` tables from ``ChatStorage.sqlite``; return the
    message count."""
    with read_source(source_db, "ChatStorage.sqlite") as source:
        chats = source.execute(_CHATS_QUERY).fetchall()
        messages = source.execute(_MESSAGES_QUERY).fetchall()

    conn.executemany(
        "INSERT INTO whatsapp_chats(jid, name, last_message_utc, message_count) "
        "VALUES (?, ?, ?, ?)",
        [
            (
                as_text(chat["jid"]),
                as_text(chat["name"]),
                mac_absolute_to_iso(chat["last_date"]),
                chat["message_count"] or 0,
            )
            for chat in chats
        ],
    )
    conn.executemany(
        "INSERT OR REPLACE INTO whatsapp_messages"
        "(rowid, chat_jid, chat_name, from_me, sender, date_utc, text, media_type) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        [
            (
                msg["rowid"],
                as_text(msg["chat_jid"]),
                as_text(msg["chat_name"]),
                1 if msg["from_me"] else 0,
                as_text(msg["sender"]),
                mac_absolute_to_iso(msg["date"]),
                as_text(msg["text"]),
                _media_type(msg["message_type"]),
            )
            for msg in messages
        ],
    )
    return len(messages)
