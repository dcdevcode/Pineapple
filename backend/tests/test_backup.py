"""Tests for :mod:`pineapple.backup` (the ``.pineapple`` logical acquisition)."""

from __future__ import annotations

import time
import zipfile
from pathlib import Path

import pytest

from pineapple.backup import DeviceBackup, _as_pineapple_path, will_encrypt_backups
from pineapple.session import DeviceSession
from support import FakeBackupServiceFactory, FakeLockdown

UDID = "udid-1"


def patch_single_device(monkeypatch: pytest.MonkeyPatch, udid: str | None) -> None:
    async def fake() -> str | None:
        return udid

    monkeypatch.setattr("pineapple.devices.single_device_udid", fake)


def patch_backend(
    monkeypatch: pytest.MonkeyPatch, factory: object, *, udid: str | None = UDID
) -> None:
    patch_single_device(monkeypatch, udid)

    async def fake_create(udid: str, autopair: bool) -> FakeLockdown:
        return FakeLockdown()

    monkeypatch.setattr("pineapple.backup.create_using_usbmux", fake_create)
    monkeypatch.setattr("pineapple.backup.Mobilebackup2Service", factory)


def wait_for_phase(
    backup: DeviceBackup, phases: set[str], timeout: float = 3.0
) -> dict[str, object]:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        state = backup.progress()
        if state["phase"] in phases:
            return state
        time.sleep(0.01)
    raise AssertionError(f"stuck at {backup.progress()}")


def leftover_dirs(path: Path) -> list[Path]:
    return [child for child in path.iterdir() if child.is_dir()]


def test_as_pineapple_path_forces_the_extension() -> None:
    assert _as_pineapple_path("/tmp/image") == Path("/tmp/image.pineapple")
    assert _as_pineapple_path("/tmp/image.zip") == Path("/tmp/image.zip.pineapple")
    assert _as_pineapple_path("/tmp/image.pineapple") == Path("/tmp/image.pineapple")


async def test_will_encrypt_backups_reports_the_device_setting(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_create(udid: str, autopair: bool) -> FakeLockdown:
        return FakeLockdown()

    monkeypatch.setattr("pineapple.backup.create_using_usbmux", fake_create)
    monkeypatch.setattr(
        "pineapple.backup.Mobilebackup2Service",
        FakeBackupServiceFactory(UDID, will_encrypt=True),
    )

    assert await will_encrypt_backups(UDID) is True


def test_unencrypted_backup_writes_a_stored_pineapple_archive(
    device_session: DeviceSession, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    factory = FakeBackupServiceFactory(UDID)
    patch_backend(monkeypatch, factory)

    backup = DeviceBackup(device_session)
    backup.start(str(tmp_path / "image"), encrypt=False, password="")

    state = wait_for_phase(backup, {"done", "error"})
    assert state["phase"] == "done"

    archive = tmp_path / "image.pineapple"
    assert state["output_path"] == str(archive)
    assert archive.exists()

    with zipfile.ZipFile(archive) as zf:
        names = zf.namelist()
        assert all(name.startswith(f"{UDID}/") for name in names)
        assert f"{UDID}/Info.plist" in names
        assert all(info.compress_type == zipfile.ZIP_STORED for info in zf.infolist())

    assert factory.calls == [("backup", True, "")]
    assert leftover_dirs(tmp_path) == []


def test_encrypted_backup_enables_then_restores_device_encryption(
    device_session: DeviceSession, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    factory = FakeBackupServiceFactory(UDID, will_encrypt=False)
    patch_backend(monkeypatch, factory)

    backup = DeviceBackup(device_session)
    backup.start(str(tmp_path / "image.pineapple"), encrypt=True, password="hunter2")

    state = wait_for_phase(backup, {"done", "error"})
    assert state["phase"] == "done"
    assert factory.calls == [
        ("change_password", "", "hunter2"),
        ("backup", True, "hunter2"),
        ("change_password", "hunter2", ""),
    ]
    assert "Restored" in str(state["note"])


def test_encrypted_backup_on_already_encrypting_device_skips_change_password(
    device_session: DeviceSession, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    factory = FakeBackupServiceFactory(UDID, will_encrypt=True)
    patch_backend(monkeypatch, factory)

    backup = DeviceBackup(device_session)
    backup.start(str(tmp_path / "image.pineapple"), encrypt=True, password="existing")

    wait_for_phase(backup, {"done", "error"})
    assert factory.calls == [("backup", True, "existing")]


def test_start_without_a_single_device_raises(
    device_session: DeviceSession, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    patch_backend(monkeypatch, FakeBackupServiceFactory(UDID), udid=None)
    backup = DeviceBackup(device_session)

    with pytest.raises(RuntimeError, match="no single device connected"):
        backup.start(str(tmp_path / "image"), encrypt=False, password="")


def test_backup_failure_is_reported_and_leaves_no_archive(
    device_session: DeviceSession, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    factory = FakeBackupServiceFactory(UDID, backup_error=RuntimeError("boom"))
    patch_backend(monkeypatch, factory)

    backup = DeviceBackup(device_session)
    backup.start(str(tmp_path / "image"), encrypt=False, password="")

    state = wait_for_phase(backup, {"error", "done"})
    assert state["phase"] == "error"
    assert state["error"] == "boom"
    assert not (tmp_path / "image.pineapple").exists()
    assert leftover_dirs(tmp_path) == []


def test_cancel_mid_backup_restores_encryption_and_removes_partials(
    device_session: DeviceSession, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    factory = FakeBackupServiceFactory(UDID, will_encrypt=False, hang=True)
    patch_backend(monkeypatch, factory)

    backup = DeviceBackup(device_session)
    backup.start(str(tmp_path / "image"), encrypt=True, password="pw")

    wait_for_phase(backup, {"backing_up"})
    assert backup.running

    backup.cancel()

    state = wait_for_phase(backup, {"cancelled", "error", "done"})
    assert state["phase"] == "cancelled"
    assert not backup.running
    assert ("change_password", "", "pw") in factory.calls
    assert ("change_password", "pw", "") in factory.calls
    assert not (tmp_path / "image.pineapple").exists()
    assert leftover_dirs(tmp_path) == []
