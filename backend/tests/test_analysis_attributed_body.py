"""Tests for :mod:`pineapple.analysis.parsers.attributed_body`."""

from __future__ import annotations

from analysis_support import ATTRIBUTED_BODY_SAMPLE, ATTRIBUTED_BODY_TEXT
from pineapple.analysis.parsers.attributed_body import decode_attributed_body


def test_decodes_a_real_attributed_body() -> None:
    assert decode_attributed_body(ATTRIBUTED_BODY_SAMPLE) == ATTRIBUTED_BODY_TEXT


def test_none_and_empty_yield_none() -> None:
    assert decode_attributed_body(None) is None
    assert decode_attributed_body(b"") is None


def test_junk_yields_none_not_an_error() -> None:
    assert decode_attributed_body(b"not a typedstream at all") is None
    assert decode_attributed_body(b"\x04\x0bstreamtyped\x00\x00garbage") is None
