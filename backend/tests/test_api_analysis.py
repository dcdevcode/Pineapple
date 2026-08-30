"""Tests for the analysis methods on :class:`pineapple.api.Api`."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

import pytest

from analysis_support import (
    SERIAL,
    FakeEncryptedBackup,
    build_backup,
    make_pineapple,
)
from pineapple.analysis import reader as reader_module
from pineapple.api import Api


class FakeDialogWindow:
    def __init__(self, result: str | list[str] | None) -> None:
        self._result = result
        self.calls: list[tuple[Any, dict[str, Any]]] = []

    def create_file_dialog(self, dialog: object, **kwargs: Any) -> object:
        self.calls.append((dialog, kwargs))
        return self._result


@pytest.fixture(autouse=True)
def _fake_library(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(reader_module, "EncryptedBackup", FakeEncryptedBackup)


@pytest.fixture
def image(tmp_path: Path) -> Path:
    root = build_backup(tmp_path / "src")
    return make_pineapple(root, tmp_path / "image.pineapple")


def test_choose_pineapple_file_returns_the_pick(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    window = FakeDialogWindow(["/data/x.pineapple"])
    monkeypatch.setattr("pineapple.api.webview.windows", [window])

    assert Api().choose_pineapple_file() == {"ok": True, "path": "/data/x.pineapple"}


def test_choose_case_folder_cancelled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("pineapple.api.webview.windows", [FakeDialogWindow(None)])
    assert Api().choose_case_folder() == {"ok": False}


def test_analysis_peek_reports_device_and_default_title(image: Path) -> None:
    result = Api().analysis_peek(str(image))

    assert result["ok"] is True
    assert result["encrypted"] is False
    assert result["device"]["serial"] == SERIAL
    assert result["default_title"] == SERIAL


def test_analysis_peek_wraps_a_bad_file(tmp_path: Path) -> None:
    junk = tmp_path / "bad.pineapple"
    junk.write_bytes(b"nope")
    assert Api().analysis_peek(str(junk))["ok"] is False


def test_start_read_and_open_flow(image: Path, tmp_path: Path) -> None:
    api = Api()
    case_dir = tmp_path / "case"

    assert api.start_analysis(str(image), str(case_dir), "", "") == {"ok": True}

    deadline = time.monotonic() + 5.0
    snapshot = api.read_analysis_progress()
    while snapshot["phase"] not in {"done", "error"} and time.monotonic() < deadline:
        time.sleep(0.02)
        snapshot = api.read_analysis_progress()
    assert snapshot["phase"] == "done", snapshot

    summary = api.analysis_summary()
    assert summary["ok"] is True
    assert summary["result"]["counts"]["messages"] == 3

    messages = api.analysis_messages(limit=2)
    assert messages["result"]["total"] == 3
    assert len(messages["result"]["rows"]) == 2

    reopened = api.open_case(str(case_dir))
    assert reopened["ok"] is True
    assert reopened["descriptor"]["title"] == SERIAL


def test_start_analysis_wraps_a_refusal() -> None:
    result = Api().start_analysis("/no/such.pineapple", "/tmp/case", "", "")
    assert result["ok"] is False


def test_case_queries_without_an_open_case() -> None:
    assert Api().analysis_summary() == {"ok": False, "error": "No analysis is open."}
