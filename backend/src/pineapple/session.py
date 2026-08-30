"""A background asyncio loop for long-lived device work.

The :class:`~pineapple.api.Api` bridge answers each frontend call on a pywebview
worker thread with no event loop, so short calls just use :func:`asyncio.run`.
Streaming features (syslog, and more later) instead need a connection that
outlives a single call: they run as tasks on the one loop owned here.

This module deliberately stays small -- it is the shared *connector* to the
device in use, not a service registry. Consumers open their own lockdown
connections on the loop and manage their own tasks.
"""

import asyncio
import threading
from collections.abc import Coroutine
from typing import Any, TypeVar

T = TypeVar("T")


class DeviceSession:
    """Owns one asyncio event loop running on a daemon thread."""

    def __init__(self) -> None:
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(
            target=self._loop.run_forever,
            name="device-session",
            daemon=True,
        )
        self._thread.start()

    def run(self, coro: Coroutine[Any, Any, T]) -> T:
        """Run ``coro`` on the loop and block until it returns."""
        return asyncio.run_coroutine_threadsafe(coro, self._loop).result()

    def spawn(self, coro: Coroutine[Any, Any, Any]) -> asyncio.Task[Any]:
        """Schedule ``coro`` as a background task and return the task.

        The task is created on the loop thread; cancel it with
        :meth:`cancel` (calling ``Task.cancel`` directly from another thread is
        not safe).
        """
        created: threading.Event = threading.Event()
        task: list[asyncio.Task[Any]] = []

        def _create() -> None:
            task.append(self._loop.create_task(coro))
            created.set()

        self._loop.call_soon_threadsafe(_create)
        created.wait()
        return task[0]

    def cancel(self, task: asyncio.Task[Any]) -> None:
        """Request cancellation of a task created by :meth:`spawn`."""
        self._loop.call_soon_threadsafe(task.cancel)

    def drain(self, task: asyncio.Task[Any], timeout: float) -> None:
        """Block until ``task`` finishes or ``timeout`` elapses, ignoring its
        outcome.

        Used after :meth:`cancel` so a slow or failing teardown cannot hang the
        caller. ``asyncio.wait`` neither re-cancels the task nor re-raises its
        exception.
        """
        self.run(asyncio.wait({task}, timeout=timeout))

    def close(self) -> None:
        """Stop the loop and join its thread. For tests / a clean shutdown; the
        process-wide singleton normally runs for the process lifetime."""
        self._loop.call_soon_threadsafe(self._loop.stop)
        self._thread.join(timeout=5.0)


# One session for the whole process; imported by the Api bridge.
session = DeviceSession()
