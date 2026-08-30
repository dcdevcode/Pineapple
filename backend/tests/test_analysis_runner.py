"""Tests for :mod:`pineapple.analysis.runner` (the end-to-end parse)."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import pytest

from analysis_support import (
    ATTRIBUTED_BODY_TEXT,
    BACKUP_FILE_COUNT,
    SERIAL,
    FakeEncryptedBackup,
    build_backup,
    file_id,
    make_pineapple,
)
from pineapple.analysis import reader as reader_module
from pineapple.analysis.case import load_case
from pineapple.analysis.runner import AnalysisRun
from pineapple.session import DeviceSession


@pytest.fixture(autouse=True)
def _fake_library(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(reader_module, "EncryptedBackup", FakeEncryptedBackup)


def _image(tmp_path: Path, *, encrypted: bool = False, **kw: object) -> Path:
    root = build_backup(tmp_path / "src", encrypted=encrypted, **kw)  # type: ignore[arg-type]
    return make_pineapple(root, tmp_path / "image.pineapple")


def _wait(run: AnalysisRun, phases: set[str], timeout: float = 5.0) -> dict[str, Any]:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        state = run.progress()
        if state["phase"] in phases:
            return state
        time.sleep(0.01)
    raise AssertionError(f"stuck at {run.progress()}")


def test_full_run_on_an_unencrypted_image(
    device_session: DeviceSession, tmp_path: Path
) -> None:
    image = _image(tmp_path)
    case_dir = tmp_path / "case"

    run = AnalysisRun(device_session)
    run.start(str(image), str(case_dir), "", "")
    state = _wait(run, {"done", "error"})

    assert state["phase"] == "done", state
    assert state["counts"]["messages"] == 3
    assert state["counts"]["calls"] == 3
    assert state["counts"]["contacts"] == 2
    assert state["counts"]["notes"] == 1
    assert state["counts"]["files"] == BACKUP_FILE_COUNT

    assert (case_dir / "analysis.db").is_file()
    assert (case_dir / f"{SERIAL}.json").is_file()
    assert (case_dir / "backup" / "00008110-000A1B2C3D4E001E").is_dir()

    descriptor = json.loads((case_dir / f"{SERIAL}.json").read_text())
    assert descriptor["title"] == SERIAL
    assert descriptor["device"]["serial"] == SERIAL
    assert descriptor["source"]["is_encrypted"] is False
    assert descriptor["parse"]["counts"]["messages"] == 3

    # The iOS 16+ row whose body lived only in attributedBody is recovered.
    handle = load_case(case_dir)
    try:
        texts = [row["text"] for row in handle.messages()["rows"]]
    finally:
        handle.close()
    assert ATTRIBUTED_BODY_TEXT in texts


def test_full_run_on_an_encrypted_image(
    device_session: DeviceSession, tmp_path: Path
) -> None:
    image = _image(tmp_path, encrypted=True)
    case_dir = tmp_path / "case"

    run = AnalysisRun(device_session)
    run.start(str(image), str(case_dir), "my case", FakeEncryptedBackup.PASSWORD)
    state = _wait(run, {"done", "error"})

    assert state["phase"] == "done", state
    assert (case_dir / "my case.json").is_file()
    handle = load_case(case_dir)
    try:
        assert handle.summary()["counts"]["messages"] == 3
    finally:
        handle.close()


def test_wrong_password_ends_in_error(
    device_session: DeviceSession, tmp_path: Path
) -> None:
    image = _image(tmp_path, encrypted=True)
    case_dir = tmp_path / "case"

    run = AnalysisRun(device_session)
    run.start(str(image), str(case_dir), "", "nope")
    state = _wait(run, {"done", "error"})

    assert state["phase"] == "error"
    assert "password" in str(state["error"]).lower()
    assert not (case_dir / "analysis.db").exists()
    assert not list(case_dir.glob("*.json"))


def test_missing_source_db_is_skipped_not_fatal(
    device_session: DeviceSession, tmp_path: Path
) -> None:
    image = _image(tmp_path, include_sources=False)
    case_dir = tmp_path / "case"

    run = AnalysisRun(device_session)
    run.start(str(image), str(case_dir), "", "")
    state = _wait(run, {"done", "error"})

    assert state["phase"] == "done", state
    assert state["counts"].get("messages", 0) == 0
    assert any("messages" in note for note in state["skipped"])


def test_absent_calls_db_is_explained_for_an_unencrypted_backup(
    device_session: DeviceSession, tmp_path: Path
) -> None:
    """CallHistory.storedata is only in encrypted backups; the skip note says so."""
    root = build_backup(tmp_path / "src")
    fid = file_id("HomeDomain", "Library/CallHistoryDB/CallHistory.storedata")
    (root / fid[:2] / fid).unlink()  # drop only the call-history blob
    image = make_pineapple(root, tmp_path / "image.pineapple")

    run = AnalysisRun(device_session)
    run.start(str(image), str(tmp_path / "case"), "", "")
    state = _wait(run, {"done", "error"})

    assert state["phase"] == "done", state
    assert state["counts"]["messages"] == 3
    calls_note = next(n for n in state["skipped"] if n.startswith("calls:"))
    assert "encrypted" in calls_note


def test_refuses_a_folder_that_already_holds_an_analysis(
    device_session: DeviceSession, tmp_path: Path
) -> None:
    image = _image(tmp_path)
    case_dir = tmp_path / "case"
    case_dir.mkdir()
    (case_dir / "old.json").write_text("{}")

    run = AnalysisRun(device_session)
    with pytest.raises(Exception, match="already holds an analysis"):
        run.start(str(image), str(case_dir), "", "")
