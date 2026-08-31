"""Tests for :mod:`pineapple.analysis.keychain` (plist walk + secret decryption)."""

from __future__ import annotations

import plistlib

import pytest

from analysis_support import FakeKeychainReader, keychain_item_blob
from pineapple.analysis.keychain import decrypt_item_secret, parse_keychain_plist

_UNWRAP = FakeKeychainReader().unwrap_keychain_key


def _plist(**groups: list[dict[str, object]]) -> bytes:
    base: dict[str, list[dict[str, object]]] = {
        "genp": [],
        "inet": [],
        "cert": [],
        "keys": [],
    }
    base.update(groups)
    return plistlib.dumps(base, fmt=plistlib.FMT_BINARY)


def test_parse_keychain_plist_reads_metadata_and_protection_class() -> None:
    raw = _plist(
        genp=[
            {
                "acct": "wifi",
                "svce": "AirPort",
                "agrp": "apple",
                "v_Data": keychain_item_blob("pw", protection_class=6),
            }
        ]
    )

    items = parse_keychain_plist(raw)

    assert len(items) == 1
    assert items[0].item_class == "genp"
    assert items[0].account == "wifi"
    assert items[0].service == "AirPort"
    assert items[0].protection_class == 6


def test_parse_keychain_plist_rejects_a_non_dict() -> None:
    with pytest.raises(ValueError, match="dictionary"):
        parse_keychain_plist(plistlib.dumps([1, 2, 3], fmt=plistlib.FMT_BINARY))


def test_decrypt_item_secret_round_trips_through_the_keybag() -> None:
    items = parse_keychain_plist(
        _plist(inet=[{"acct": "a", "v_Data": keychain_item_blob("hunter2")}])
    )

    secret, error = decrypt_item_secret(items[0], _UNWRAP)

    assert secret == "hunter2"
    assert error is None


def test_decrypt_item_secret_reports_an_unopenable_class() -> None:
    items = parse_keychain_plist(
        _plist(
            genp=[{"acct": "a", "v_Data": keychain_item_blob("x", protection_class=6)}]
        )
    )

    # A reader whose keybag never unwraps anything.
    secret, error = decrypt_item_secret(items[0], lambda _c, _w: None)

    assert secret is None
    assert error is not None
    assert "unwrap" in error


def test_decrypt_item_secret_handles_a_missing_secret() -> None:
    items = parse_keychain_plist(_plist(genp=[{"acct": "a"}]))

    secret, error = decrypt_item_secret(items[0], _UNWRAP)

    assert secret is None
    assert error == "no secret data in the backup"
