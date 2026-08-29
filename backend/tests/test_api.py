"""Tests for :class:`pineapple.api.Api` (the sync bridge and its envelopes)."""

from pathlib import Path

import pytest

from pineapple.api import Api


def patch_connected(monkeypatch: pytest.MonkeyPatch, *devices_: dict[str, str]) -> None:
    async def fake() -> list[dict[str, str]]:
        return list(devices_)

    monkeypatch.setattr("pineapple.devices.connected_devices", fake)


class FakeWindow:
    def __init__(self, result: str | None) -> None:
        self._result = result
        self.calls: list[tuple[object, str]] = []

    def create_file_dialog(self, dialog: object, save_filename: str) -> str | None:
        self.calls.append((dialog, save_filename))
        return self._result


def test_connected_device_reports_none(monkeypatch: pytest.MonkeyPatch) -> None:
    patch_connected(monkeypatch)
    assert Api().connected_device() == {"status": "none"}


def test_connected_device_reports_the_lone_device(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    device = {"Udid": "a", "ConnectionType": "USB"}
    patch_connected(monkeypatch, device)
    assert Api().connected_device() == {"status": "one", "device": device}


def test_connected_device_reports_multiple_without_picking(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    patch_connected(
        monkeypatch,
        {"Udid": "a", "ConnectionType": "USB"},
        {"Udid": "b", "ConnectionType": "USB"},
    )
    assert Api().connected_device() == {"status": "multiple"}


def test_get_device_info_wraps_a_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    async def boom(udid: str) -> dict[str, object]:
        raise RuntimeError("unpaired")

    monkeypatch.setattr("pineapple.devices.get_device_info", boom)
    assert Api().get_device_info("x") == {"ok": False, "error": "unpaired"}


def test_get_device_info_wraps_a_success(monkeypatch: pytest.MonkeyPatch) -> None:
    async def ok(udid: str) -> dict[str, object]:
        return {"DeviceName": "iPhone"}

    monkeypatch.setattr("pineapple.devices.get_device_info", ok)
    assert Api().get_device_info("x") == {"ok": True, "info": {"DeviceName": "iPhone"}}


def test_start_syslog_wraps_a_refusal(monkeypatch: pytest.MonkeyPatch) -> None:
    api = Api()

    def boom() -> None:
        raise RuntimeError("no single device connected")

    monkeypatch.setattr(api._syslog, "start", boom)
    assert api.start_syslog() == {
        "ok": False,
        "error": "no single device connected",
    }


def test_save_syslog_returns_not_ok_when_cancelled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("pineapple.api.webview.windows", [FakeWindow(None)])
    assert Api().save_syslog("data") == {"ok": False}


def test_save_syslog_writes_the_chosen_file(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    target = tmp_path / "syslog.txt"
    monkeypatch.setattr("pineapple.api.webview.windows", [FakeWindow(str(target))])

    assert Api().save_syslog("hello") == {"ok": True, "path": str(target)}
    assert target.read_text(encoding="utf-8") == "hello"


def test_save_syslog_reports_a_write_error(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    unwritable = tmp_path / "missing-dir" / "syslog.txt"
    monkeypatch.setattr("pineapple.api.webview.windows", [FakeWindow(str(unwritable))])

    result = Api().save_syslog("hello")
    assert result["ok"] is False
    assert "error" in result
