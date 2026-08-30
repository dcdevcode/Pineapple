"""Shared fakes for the backend tests.

The tests never touch a real device: they replace the boundary with
``pymobiledevice3`` (lockdown connections, the os_trace service) and with
``webview``. These helpers stand in for the objects those libraries return.
"""

import asyncio
import contextlib
from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace
from typing import Any


class FakeLockdown:
    """Stand-in for the object :func:`create_using_usbmux` returns."""

    def __init__(
        self, all_values: dict[str, object] | None = None, *, fail: bool = False
    ) -> None:
        self._all_values = all_values or {}
        self._fail = fail
        self.closed = False

    @property
    def all_values(self) -> dict[str, object]:
        if self._fail:
            raise RuntimeError("cannot read lockdown values")
        return self._all_values

    async def close(self) -> None:
        self.closed = True


class FakeMobilebackup2Service:
    """Stand-in for ``Mobilebackup2Service`` used by :mod:`pineapple.backup`.

    One ``calls`` list is shared across every instance a factory hands out, so a
    test can assert on both the backup call and the later encryption-restore
    call made from a fresh service instance.

    The real ``com.apple.mobilebackup2`` session is single-use -- one DeviceLink
    operation, then ``DLMessageDisconnect`` -- so this fake raises if a single
    instance is used for more than one of ``change_password`` / ``backup``.
    """

    def __init__(
        self,
        *,
        udid: str,
        calls: list[tuple[object, ...]],
        will_encrypt: bool = False,
        backup_error: BaseException | None = None,
        hang: bool = False,
        percentages: tuple[float, ...] = (10.0, 60.0, 100.0),
        files: tuple[str, ...] = ("Info.plist", "Manifest.plist", "Manifest.db"),
    ) -> None:
        self._udid = udid
        self._calls = calls
        self._will_encrypt = will_encrypt
        self._backup_error: BaseException | None = backup_error
        self._hang = hang
        self._percentages = percentages
        self._files = files
        self._link_used = False

    async def __aenter__(self) -> FakeMobilebackup2Service:
        return self

    async def __aexit__(self, *exc: object) -> bool:
        return False

    def _use_link(self) -> None:
        if self._link_used:
            raise RuntimeError("device link already disconnected")
        self._link_used = True

    async def get_will_encrypt(self) -> bool:
        return self._will_encrypt

    async def change_password(self, old: str = "", new: str = "") -> None:
        self._use_link()
        self._calls.append(("change_password", old, new))

    async def backup(
        self,
        *,
        full: bool,
        backup_directory: str,
        password: str,
        progress_callback: Callable[[float], None],
    ) -> None:
        self._use_link()
        self._calls.append(("backup", full, password))
        device_directory = Path(backup_directory) / self._udid
        device_directory.mkdir(parents=True, exist_ok=True)
        for name in self._files:
            (device_directory / name).write_bytes(b"payload")
        for percentage in self._percentages:
            progress_callback(percentage)
            await asyncio.sleep(0)
        if self._backup_error is not None:
            raise self._backup_error
        while self._hang:
            await asyncio.sleep(0.02)


class FakeBackupServiceFactory:
    """A ``Mobilebackup2Service`` replacement; ``calls`` records every call made
    across every service instance it hands out."""

    def __init__(self, udid: str, **kwargs: Any) -> None:
        self._udid = udid
        self._kwargs = kwargs
        self.calls: list[tuple[object, ...]] = []

    def __call__(self, _lockdown: object) -> FakeMobilebackup2Service:
        return FakeMobilebackup2Service(
            udid=self._udid, calls=self.calls, **self._kwargs
        )


def mux_device(serial: str, connection_type: str = "USB") -> SimpleNamespace:
    """A ``MuxDevice`` as far as :mod:`pineapple.devices` cares about it."""
    return SimpleNamespace(serial=serial, connection_type=connection_type)


async def settle(task: asyncio.Task[object]) -> None:
    """Await a task that is expected to be cancelled, swallowing the outcome."""
    with contextlib.suppress(asyncio.CancelledError):
        await task
