"""Recover message text from an iMessage ``attributedBody`` blob.

iOS 16+ stores many message bodies only in ``message.attributedBody`` -- an
``NSMutableAttributedString`` serialised in Apple's legacy *typedstream* format
(``NSArchiver``, not a keyed archive or a plist). The plain string sits in the
first ``NSString`` of the archived object's contents; the rest is formatting.

Decoding is best-effort: any malformed or unexpected blob yields ``None`` so the
row simply lands without recovered text, mirroring :func:`decode_mbfile`.
"""

from __future__ import annotations

import typedstream
from typedstream.types.foundation import NSString


def decode_attributed_body(blob: bytes | None) -> str | None:
    """Return the plain message text inside an ``attributedBody`` blob, or ``None``."""
    if not blob:
        return None
    try:
        archived = typedstream.unarchive_from_data(blob)
        contents = getattr(archived, "contents", None) or []
        for item in contents:
            value = getattr(item, "value", None)
            if isinstance(value, NSString):
                return str(value.value)
    except Exception:  # malformed / unexpected stream -- treat as "no text"
        return None
    return None
