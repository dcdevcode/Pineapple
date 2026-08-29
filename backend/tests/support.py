"""Shared fakes for the backend tests.

The tests never touch a real device: they replace the boundary with
``pymobiledevice3`` (lockdown connections, the os_trace service) and with
``webview``. These helpers stand in for the objects those libraries return.
"""

import asyncio
import contextlib
from types import SimpleNamespace


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


def mux_device(serial: str, connection_type: str = "USB") -> SimpleNamespace:
    """A ``MuxDevice`` as far as :mod:`pineapple.devices` cares about it."""
    return SimpleNamespace(serial=serial, connection_type=connection_type)


async def settle(task: asyncio.Task[object]) -> None:
    """Await a task that is expected to be cancelled, swallowing the outcome."""
    with contextlib.suppress(asyncio.CancelledError):
        await task
