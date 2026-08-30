"""Tests for :class:`pineapple.session.DeviceSession` (the shared asyncio loop)."""

import asyncio
import threading

import pytest

from pineapple.session import DeviceSession
from support import settle


def test_run_returns_the_coroutine_result(device_session: DeviceSession) -> None:
    async def compute() -> int:
        await asyncio.sleep(0)
        return 42

    assert device_session.run(compute()) == 42


def test_run_propagates_exceptions(device_session: DeviceSession) -> None:
    async def boom() -> None:
        raise ValueError("nope")

    with pytest.raises(ValueError, match="nope"):
        device_session.run(boom())


def test_spawn_runs_on_the_loop_and_cancel_stops_it(
    device_session: DeviceSession,
) -> None:
    started = threading.Event()
    cancelled = threading.Event()

    async def worker() -> None:
        started.set()
        try:
            await asyncio.sleep(30)
        except asyncio.CancelledError:
            cancelled.set()
            raise

    task = device_session.spawn(worker())
    assert started.wait(timeout=1)

    device_session.cancel(task)
    device_session.run(settle(task))

    assert cancelled.wait(timeout=1)
    assert task.cancelled()


def test_the_loop_runs_on_a_daemon_thread(device_session: DeviceSession) -> None:
    assert device_session._thread.daemon
    assert device_session._thread.is_alive()


def test_close_stops_the_loop_thread() -> None:
    session = DeviceSession()
    assert session.run(_return_one()) == 1

    session.close()

    assert not session._thread.is_alive()


async def _return_one() -> int:
    return 1
