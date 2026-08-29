"""Tests for :mod:`pineapple.syslog` (the live system-log stream)."""

from __future__ import annotations

import asyncio
import time
from collections.abc import AsyncIterator
from datetime import datetime

import pytest
from pymobiledevice3.services.os_trace import SyslogEntry, SyslogLabel, SyslogLogLevel

from pineapple.session import DeviceSession
from pineapple.syslog import SyslogLine, SyslogStream, _to_line
from support import FakeLockdown


def make_entry(**overrides: object) -> SyslogEntry:
    fields: dict[str, object] = {
        "pid": 42,
        "timestamp": datetime(2026, 8, 29, 12, 0, 0),
        "level": SyslogLogLevel.NOTICE,
        "image_name": "SpringBoard",
        "image_offset": 0,
        "filename": "/usr/libexec/SpringBoard",
        "message": "hello",
        "label": None,
    }
    fields.update(overrides)
    return SyslogEntry(**fields)  # type: ignore[arg-type]


def make_line(**overrides: object) -> SyslogLine:
    fields: dict[str, object] = {
        "timestamp": "2026-08-29T12:00:00",
        "process": "SpringBoard",
        "pid": 1,
        "level": "NOTICE",
        "label": None,
        "message": "m",
    }
    fields.update(overrides)
    return SyslogLine(**fields)  # type: ignore[arg-type]


class FakeTrace:
    """Async-context / async-iterator stand-in for ``OsTraceService``."""

    def __init__(self, entries: list[SyslogEntry], *, forever: bool = False) -> None:
        self._entries = entries
        self._forever = forever

    async def __aenter__(self) -> FakeTrace:
        return self

    async def __aexit__(self, *exc: object) -> bool:
        return False

    async def syslog(self) -> AsyncIterator[SyslogEntry]:
        for entry in self._entries:
            yield entry
        while self._forever:
            await asyncio.sleep(0.02)


def wait_until_stopped(stream: SyslogStream, timeout: float = 2.0) -> None:
    deadline = time.monotonic() + timeout
    while stream.running and time.monotonic() < deadline:
        time.sleep(0.01)
    assert not stream.running


def patch_single_device(monkeypatch: pytest.MonkeyPatch, udid: str | None) -> None:
    async def fake() -> str | None:
        return udid

    monkeypatch.setattr("pineapple.devices.single_device_udid", fake)


def test_to_line_flattens_an_entry() -> None:
    line = _to_line(make_entry(filename="/a/b/mediaserverd", message="tick"))

    assert line == SyslogLine(
        timestamp="2026-08-29T12:00:00",
        process="mediaserverd",
        pid=42,
        level="NOTICE",
        label=None,
        message="tick",
    )


def test_to_line_joins_label_subsystem_and_category() -> None:
    entry = make_entry(label=SyslogLabel(category="net", subsystem="com.apple.foo"))

    assert _to_line(entry).label == "com.apple.foo/net"


def test_start_raises_without_a_single_device(
    device_session: DeviceSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    patch_single_device(monkeypatch, None)
    stream = SyslogStream(device_session)

    with pytest.raises(RuntimeError, match="no single device connected"):
        stream.start()


def test_append_counts_dropped_lines_and_read_resets(
    device_session: DeviceSession,
) -> None:
    stream = SyslogStream(device_session, buffer_size=2)

    for index in range(5):
        stream._append(make_line(message=str(index)))

    first = stream.read()
    assert [line["message"] for line in first["lines"]] == ["3", "4"]
    assert first["dropped"] == 3

    second = stream.read()
    assert second["lines"] == []
    assert second["dropped"] == 0


def test_streams_entries_into_the_buffer(
    device_session: DeviceSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    entries = [make_entry(message="one"), make_entry(message="two")]
    monkeypatch.setattr(
        "pineapple.syslog.OsTraceService", lambda lockdown: FakeTrace(entries)
    )

    async def fake_create(udid: str, autopair: bool) -> FakeLockdown:
        return FakeLockdown()

    monkeypatch.setattr("pineapple.syslog.create_using_usbmux", fake_create)
    patch_single_device(monkeypatch, "udid-1")

    stream = SyslogStream(device_session)
    stream.start()
    wait_until_stopped(stream)

    result = stream.read()
    assert [line["message"] for line in result["lines"]] == ["one", "two"]
    assert result["error"] is None


def test_read_reports_an_unpaired_device(
    device_session: DeviceSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def fake_create(udid: str, autopair: bool) -> FakeLockdown:
        raise RuntimeError("device not paired")

    monkeypatch.setattr("pineapple.syslog.create_using_usbmux", fake_create)
    patch_single_device(monkeypatch, "udid-1")

    stream = SyslogStream(device_session)
    stream.start()
    wait_until_stopped(stream)

    result = stream.read()
    assert result["error"] == "device not paired"
    assert result["running"] is False


def test_stop_closes_the_device_connection(
    device_session: DeviceSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    lockdown = FakeLockdown()
    monkeypatch.setattr(
        "pineapple.syslog.OsTraceService",
        lambda lockdown: FakeTrace([], forever=True),
    )

    async def fake_create(udid: str, autopair: bool) -> FakeLockdown:
        return lockdown

    monkeypatch.setattr("pineapple.syslog.create_using_usbmux", fake_create)
    patch_single_device(monkeypatch, "udid-1")

    stream = SyslogStream(device_session)
    stream.start()
    time.sleep(0.1)
    assert stream.running

    stream.stop()
    assert not stream.running
    assert lockdown.closed
