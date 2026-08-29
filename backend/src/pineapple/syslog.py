"""Live system-log streaming for the connected device.

``pymobiledevice3``'s :class:`OsTraceService` yields structured log entries over
``com.apple.os_trace_relay`` (the same feed Console.app shows). The stream is
long-lived, so it runs as a task on :data:`pineapple.session.session` and pushes
lines into a bounded buffer; the frontend drains that buffer by polling
:meth:`SyslogStream.read`.
"""

import asyncio
import posixpath
import threading
from collections import deque
from dataclasses import asdict, dataclass
from typing import Any

from pymobiledevice3.lockdown import create_using_usbmux
from pymobiledevice3.services.os_trace import OsTraceService, SyslogEntry

from pineapple import devices
from pineapple.session import DeviceSession

BUFFER_SIZE = 5000

# How long stop() waits for the reader task to close its connections.
TEARDOWN_TIMEOUT = 5.0


async def _drain(task: asyncio.Task[Any]) -> None:
    """Wait for a cancelled task to finish its cleanup, swallowing the outcome."""
    try:
        await asyncio.wait_for(asyncio.shield(task), TEARDOWN_TIMEOUT)
    except BaseException:
        pass


@dataclass(frozen=True)
class SyslogLine:
    """One decoded syslog entry, flattened for the frontend."""

    timestamp: str
    process: str
    pid: int
    level: str
    label: str | None
    message: str


def _to_line(entry: SyslogEntry) -> SyslogLine:
    label = None
    if entry.label is not None:
        label = f"{entry.label.subsystem}/{entry.label.category}"
    return SyslogLine(
        timestamp=entry.timestamp.isoformat(),
        process=posixpath.basename(entry.filename),
        pid=entry.pid,
        level=entry.level.name,
        label=label,
        message=entry.message,
    )


class SyslogStream:
    """A single syslog session: start it, poll :meth:`read`, then :meth:`stop`."""

    def __init__(self, session: DeviceSession, buffer_size: int = BUFFER_SIZE) -> None:
        self._session = session
        # Serialises start/stop so a reopen cannot race a previous teardown.
        self._op_lock = threading.Lock()
        # Filled on the session loop thread, drained on a pywebview worker
        # thread -- every buffer access is under _buffer_lock.
        self._buffer_lock = threading.Lock()
        self._buffer: deque[SyslogLine] = deque(maxlen=buffer_size)
        self._dropped = 0
        self._error: str | None = None
        self._task: asyncio.Task[Any] | None = None

    @property
    def running(self) -> bool:
        return self._task is not None and not self._task.done()

    def start(self) -> None:
        """(Re)start streaming for the single connected device.

        Any previous reader is fully torn down first, so this is safe to call
        again after :meth:`stop`.
        """
        with self._op_lock:
            self._teardown()
            udid = self._session.run(devices.single_device_udid())
            if udid is None:
                raise RuntimeError("no single device connected")
            with self._buffer_lock:
                self._buffer.clear()
                self._dropped = 0
            self._error = None
            self._task = self._session.spawn(self._read(udid))

    def stop(self) -> None:
        """Cancel the reader task and wait for it to close its connections."""
        with self._op_lock:
            self._teardown()

    def _teardown(self) -> None:
        """Cancel the current reader task and block until it has finished."""
        task, self._task = self._task, None
        if task is not None:
            self._session.cancel(task)
            self._session.run(_drain(task))

    def read(self) -> dict[str, Any]:
        """Drain buffered lines and report stream status."""
        with self._buffer_lock:
            drained = list(self._buffer)
            self._buffer.clear()
            dropped, self._dropped = self._dropped, 0
        return {
            "lines": [asdict(line) for line in drained],
            "dropped": dropped,
            "running": self.running,
            "error": self._error,
        }

    async def _read(self, udid: str) -> None:
        try:
            lockdown = await create_using_usbmux(udid, autopair=False)
        except Exception as error:  # unpaired / unreachable
            self._error = str(error)
            return
        try:
            # `async with` guarantees the os_trace_relay service socket is
            # closed on exit -- including on cancellation. Leaking it makes the
            # device refuse the next stream.
            async with OsTraceService(lockdown=lockdown) as trace:
                async for entry in trace.syslog():
                    self._append(_to_line(entry))
        except asyncio.CancelledError:
            raise
        except Exception as error:  # device disconnected mid-stream
            self._error = str(error)
        finally:
            await lockdown.close()

    def _append(self, line: SyslogLine) -> None:
        with self._buffer_lock:
            if len(self._buffer) == self._buffer.maxlen:
                self._dropped += 1  # deque will evict the oldest line
            self._buffer.append(line)
