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


def test_backup_preflight_reports_encryption(monkeypatch: pytest.MonkeyPatch) -> None:
    async def one_device() -> str | None:
        return "udid-1"

    async def will_encrypt(udid: str) -> bool:
        return True

    monkeypatch.setattr("pineapple.devices.single_device_udid", one_device)
    monkeypatch.setattr("pineapple.backup.will_encrypt_backups", will_encrypt)
    assert Api().backup_preflight() == {"ok": True, "willEncrypt": True}


def test_backup_preflight_without_a_single_device(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def no_device() -> str | None:
        return None

    monkeypatch.setattr("pineapple.devices.single_device_udid", no_device)
    assert Api().backup_preflight() == {
        "ok": False,
        "error": "no single device connected",
    }


def test_backup_preflight_wraps_a_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    async def one_device() -> str | None:
        return "udid-1"

    async def boom(udid: str) -> bool:
        raise RuntimeError("unpaired")

    monkeypatch.setattr("pineapple.devices.single_device_udid", one_device)
    monkeypatch.setattr("pineapple.backup.will_encrypt_backups", boom)
    assert Api().backup_preflight() == {"ok": False, "error": "unpaired"}


def test_choose_backup_path_returns_the_pick(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    target = tmp_path / "My iPhone 2026-01-01 120000.pineapple"
    window = FakeWindow(str(target))
    monkeypatch.setattr("pineapple.api.webview.windows", [window])

    assert Api().choose_backup_path("Diego / iPhone") == {
        "ok": True,
        "path": str(target),
    }
    (_dialog, save_filename) = window.calls[0]
    assert save_filename.endswith(".pineapple")
    assert "/" not in save_filename


def test_choose_backup_path_returns_not_ok_when_cancelled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("pineapple.api.webview.windows", [FakeWindow(None)])
    assert Api().choose_backup_path("iPhone") == {"ok": False}


def test_start_backup_wraps_a_refusal(monkeypatch: pytest.MonkeyPatch) -> None:
    api = Api()

    def boom(path: str, encrypt: bool, password: str) -> None:
        raise RuntimeError("no single device connected")

    monkeypatch.setattr(api._backup, "start", boom)
    assert api.start_backup("/tmp/image", False, "") == {
        "ok": False,
        "error": "no single device connected",
    }


def test_cancel_backup_delegates(monkeypatch: pytest.MonkeyPatch) -> None:
    api = Api()
    calls: list[bool] = []
    monkeypatch.setattr(api._backup, "cancel", lambda: calls.append(True))
    assert api.cancel_backup() == {"ok": True}
    assert calls == [True]


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
