"""Tests for :mod:`pineapple.analysis.descriptor`."""

from __future__ import annotations

from pathlib import Path

import pytest

from pineapple.analysis.descriptor import (
    CaseDescriptor,
    descriptor_path,
    find_descriptor,
    read_descriptor,
    safe_filename,
    tool_version,
    write_descriptor,
)
from pineapple.analysis.errors import AnalysisError
from pineapple.analysis.schema import SCHEMA_VERSION


def _descriptor(title: str = "case-1") -> CaseDescriptor:
    return CaseDescriptor(
        title=title,
        device={"serial": "ABC123"},
        source={"path": "x.pineapple", "sha256": "deadbeef", "is_encrypted": False},
        parse={"status": "done", "counts": {"messages": 2}},
    )


def test_safe_filename_strips_unsafe_chars_and_uses_the_fallback() -> None:
    assert safe_filename('a/b:c*?"<>|d') == "a_b_c______d"
    assert safe_filename("   ") == "analysis"
    assert safe_filename("", fallback="device") == "device"


def test_tool_version_is_a_string() -> None:
    assert isinstance(tool_version(), str)
    assert tool_version()  # non-empty


def test_descriptor_path_is_the_safe_title_json(tmp_path: Path) -> None:
    assert descriptor_path(tmp_path, "My Case/1") == tmp_path / "My Case_1.json"


def test_round_trip_through_the_file(tmp_path: Path) -> None:
    path = descriptor_path(tmp_path, "case-1")
    write_descriptor(path, _descriptor())

    loaded = read_descriptor(path)
    assert loaded.title == "case-1"
    assert loaded.device == {"serial": "ABC123"}
    assert loaded.schema_version == SCHEMA_VERSION


def test_read_descriptor_rejects_non_json(tmp_path: Path) -> None:
    path = tmp_path / "case.json"
    path.write_text("{ not json", encoding="utf-8")

    with pytest.raises(AnalysisError, match="Cannot read"):
        read_descriptor(path)


def test_read_descriptor_rejects_a_non_object(tmp_path: Path) -> None:
    path = tmp_path / "case.json"
    path.write_text("[1, 2, 3]", encoding="utf-8")

    with pytest.raises(AnalysisError, match="unexpected shape"):
        read_descriptor(path)


def test_from_dict_requires_a_title() -> None:
    with pytest.raises(AnalysisError, match="missing"):
        CaseDescriptor.from_dict({"device": {}, "source": {}})


def test_find_descriptor_none_one_and_many(tmp_path: Path) -> None:
    assert find_descriptor(tmp_path) is None

    (tmp_path / "only.json").write_text("{}", encoding="utf-8")
    assert find_descriptor(tmp_path) == tmp_path / "only.json"

    (tmp_path / "second.json").write_text("{}", encoding="utf-8")
    with pytest.raises(AnalysisError, match="more than one"):
        find_descriptor(tmp_path)
