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
    file_id,
    make_pineapple,
)
from pineapple.analysis import reader as reader_module
from pineapple.api import Api


def _run_to_done(api: Api, image: Path, case_dir: Path, password: str = "") -> None:
    assert api.start_analysis(str(image), str(case_dir), "", password)["ok"]
    deadline = time.monotonic() + 5.0
    snapshot = api.read_analysis_progress()
    while snapshot["phase"] not in {"done", "error"} and time.monotonic() < deadline:
        time.sleep(0.02)
        snapshot = api.read_analysis_progress()
    assert snapshot["phase"] == "done", snapshot


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


def test_new_artifact_queries_answer_from_the_case(image: Path, tmp_path: Path) -> None:
    api = Api()
    _run_to_done(api, image, tmp_path / "case")

    assert api.analysis_notes()["result"]["total"] == 1
    assert api.analysis_photos()["result"]["total"] == 2
    assert api.analysis_photo_albums()["result"]["total"] == 1
    assert api.analysis_calendar()["result"]["total"] == 2
    assert api.analysis_safari_history()["result"]["total"] == 2
    assert api.analysis_safari_bookmarks()["result"]["total"] == 1
    assert api.analysis_whatsapp_chats()["result"]["total"] == 1
    scoped = api.analysis_whatsapp_messages(chat_jid="1555000@s.whatsapp.net")
    assert scoped["result"]["total"] == 2


def test_apps_domains_calls_contacts_queries(image: Path, tmp_path: Path) -> None:
    api = Api()
    _run_to_done(api, image, tmp_path / "case")

    apps = api.analysis_apps()
    assert apps["ok"] is True
    assert any(row["bundle_id"] == "com.example.app" for row in apps["result"])

    domains = api.analysis_domains()
    assert {d["domain"] for d in domains["result"]} >= {"HomeDomain"}
    assert all(d["count"] >= 1 for d in domains["result"])

    assert api.analysis_calls()["result"]["total"] == 3
    contacts = api.analysis_contacts(search="Ada")
    assert contacts["result"]["total"] == 1
    assert contacts["result"]["rows"][0]["first"] == "Ada"


def test_preview_and_extract_a_file(
    image: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    api = Api()
    _run_to_done(api, image, tmp_path / "case")
    sms_id = file_id("HomeDomain", "Library/SMS/sms.db")

    preview = api.analysis_preview_file(sms_id)
    assert preview["ok"] is True
    assert preview["result"]["name"] == "sms.db"

    dest = tmp_path / "saved.db"
    window = FakeDialogWindow([str(dest)])
    monkeypatch.setattr("pineapple.api.webview.windows", [window])
    result = api.analysis_extract_file(sms_id)

    assert result == {"ok": True, "path": str(dest)}
    assert dest.is_file()
    assert window.calls[0][1]["save_filename"] == "sms.db"


def test_extract_file_dialog_cancelled(
    image: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    api = Api()
    _run_to_done(api, image, tmp_path / "case")
    monkeypatch.setattr("pineapple.api.webview.windows", [FakeDialogWindow(None)])
    assert api.analysis_extract_file(file_id("HomeDomain", "Library/SMS/sms.db")) == {
        "ok": False
    }


def test_unlock_rejects_a_wrong_key_for_an_encrypted_case(
    tmp_path: Path,
) -> None:
    root = build_backup(tmp_path / "src", encrypted=True)
    image = make_pineapple(root, tmp_path / "image.pineapple")
    api = Api()
    _run_to_done(api, image, tmp_path / "case", password=FakeEncryptedBackup.PASSWORD)

    # Parsed with the right key; the case starts unlocked.
    assert api.analysis_summary()["result"]["files_unlocked"] is True
    assert api.analysis_unlock("wrong")["ok"] is False
    assert api.analysis_unlock(FakeEncryptedBackup.PASSWORD)["ok"] is True


def test_reopening_the_just_analysed_encrypted_case_keeps_the_key(
    tmp_path: Path,
) -> None:
    root = build_backup(tmp_path / "src", encrypted=True)
    image = make_pineapple(root, tmp_path / "image.pineapple")
    case_dir = tmp_path / "case"
    api = Api()
    _run_to_done(api, image, case_dir, password=FakeEncryptedBackup.PASSWORD)

    # The tab re-opens the case with no password -- the retained key must hold.
    reopened = api.open_case(str(case_dir))
    assert reopened["ok"] is True
    assert reopened["summary"]["files_unlocked"] is True

    # Opening a different folder with no password drops the stale key.
    api.open_case(str(tmp_path / "not-a-case"))
    assert api._case_password is None


def test_start_analysis_wraps_a_refusal() -> None:
    result = Api().start_analysis("/no/such.pineapple", "/tmp/case", "", "")
    assert result["ok"] is False


def test_case_queries_without_an_open_case() -> None:
    assert Api().analysis_summary() == {"ok": False, "error": "No analysis is open."}
