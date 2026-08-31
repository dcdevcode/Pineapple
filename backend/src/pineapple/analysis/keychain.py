"""Decode ``KeychainDomain/keychain-backup.plist`` from an encrypted backup.

The plist is a dict grouping items under ``genp`` (generic passwords), ``inet``
(internet passwords), ``cert`` (certificates) and ``keys``. Every item carries
its metadata -- account, service, dates, … -- in the clear; the secret itself is
in ``v_Data``, an encrypted blob laid out as::

    [version u32-le][protection class u32-le][wrapped key][ciphertext + 16-byte GCM tag]

Recovering a secret needs the unlocked backup keybag (reached through the reader's
``unwrap_keychain_key``) to unwrap the per-item key, then AES-GCM with a 16-byte
zero IV -- Apple's ``SecAESGCM``. Everything here is best-effort: an item that
will not decode keeps its metadata and records why.

Blob format and crypto follow the ``iphone-dataprotection`` reference
implementation; it has not been verified byte-for-byte against every iOS release.
"""

from __future__ import annotations

import datetime as dt
import plistlib
from collections.abc import Callable
from dataclasses import dataclass

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

from pineapple.analysis.parsers._common import as_text, mac_absolute_to_iso

# (protection_class, wrapped_key) -> unwrapped data key, or None.
UnwrapFn = Callable[[int, bytes], bytes | None]

_GROUPS = ("genp", "inet", "cert", "keys")
_WRAPPED_KEY_LEN = 0x28
_GCM_TAG_LEN = 16
_ZERO_IV = b"\x00" * 16


@dataclass(frozen=True)
class KeychainItem:
    """One keychain entry: cleartext metadata plus the still-wrapped secret."""

    item_class: str
    account: str | None
    service: str | None
    server: str | None
    access_group: str | None
    protection_class: int | None
    created: str | None
    modified: str | None
    wrapped_secret: bytes | None


def _date(value: object) -> str | None:
    if isinstance(value, dt.datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=dt.UTC)
        return value.astimezone(dt.UTC).isoformat()
    if isinstance(value, (int, float)):
        return mac_absolute_to_iso(value)
    return None


def parse_keychain_plist(raw: bytes) -> list[KeychainItem]:
    """Parse the plist into :class:`KeychainItem` records (no decryption yet).

    Raises ``plistlib.InvalidFileException`` / ``ValueError`` on a malformed
    plist -- the parser turns that into a skip note.
    """
    data = plistlib.loads(raw)
    if not isinstance(data, dict):
        raise ValueError("keychain plist is not a dictionary")

    items: list[KeychainItem] = []
    for group in _GROUPS:
        for entry in data.get(group, []):
            if not isinstance(entry, dict):
                continue
            secret = entry.get("v_Data")
            secret = secret if isinstance(secret, bytes) else None
            items.append(
                KeychainItem(
                    item_class=group,
                    account=as_text(entry.get("acct")),
                    service=as_text(entry.get("svce")),
                    server=as_text(entry.get("srvr")),
                    access_group=as_text(entry.get("agrp")),
                    protection_class=(
                        int.from_bytes(secret[4:8], "little")
                        if secret is not None and len(secret) >= 8
                        else None
                    ),
                    created=_date(entry.get("cdat")),
                    modified=_date(entry.get("mdat")),
                    wrapped_secret=secret,
                )
            )
    return items


def _split_blob(blob: bytes) -> tuple[int, bytes, bytes] | None:
    """``(protection_class, wrapped_key, ciphertext+tag)`` from a ``v_Data`` blob."""
    if len(blob) < 8 + _WRAPPED_KEY_LEN + _GCM_TAG_LEN:
        return None
    version = int.from_bytes(blob[0:4], "little")
    protection_class = int.from_bytes(blob[4:8], "little")

    if version >= 3 and len(blob) >= 12:
        declared = int.from_bytes(blob[8:12], "little")
        if declared and 12 + declared + _GCM_TAG_LEN <= len(blob):
            return protection_class, blob[12 : 12 + declared], blob[12 + declared :]

    body = 8 + _WRAPPED_KEY_LEN
    return protection_class, blob[8:body], blob[body:]


def _aes_gcm_decrypt(key: bytes, ciphertext_with_tag: bytes) -> bytes | None:
    ciphertext, tag = (
        ciphertext_with_tag[:-_GCM_TAG_LEN],
        ciphertext_with_tag[-_GCM_TAG_LEN:],
    )
    try:
        decryptor = Cipher(algorithms.AES(key), modes.GCM(_ZERO_IV, tag)).decryptor()
        return decryptor.update(ciphertext) + decryptor.finalize()
    except Exception:
        return None


def _secret_text(plaintext: bytes) -> str | None:
    """The decrypted secret: a plist of secret attributes (``v_Data`` is the
    password), or, failing that, the raw bytes as text."""
    try:
        parsed = plistlib.loads(plaintext)
    except plistlib.InvalidFileException, ValueError, OverflowError:
        parsed = None
    if isinstance(parsed, dict) and "v_Data" in parsed:
        value = parsed["v_Data"]
        return as_text(value) if isinstance(value, bytes) else str(value)
    return plaintext.decode("utf-8", "replace") or None


def decrypt_item_secret(
    item: KeychainItem, unwrap: UnwrapFn
) -> tuple[str | None, str | None]:
    """``(secret, None)`` on success, ``(None, reason)`` when it cannot be read."""
    if not item.wrapped_secret:
        return None, "no secret data in the backup"
    parsed = _split_blob(item.wrapped_secret)
    if parsed is None:
        return None, "unrecognised keychain blob format"
    protection_class, wrapped_key, ciphertext = parsed
    data_key = unwrap(protection_class, wrapped_key)
    if data_key is None:
        return None, f"keybag could not unwrap protection class {protection_class}"
    plaintext = _aes_gcm_decrypt(data_key, ciphertext)
    if plaintext is None:
        return None, "AES-GCM authentication failed"
    return _secret_text(plaintext), None
