"""Fixtures shared across the backend tests."""

from collections.abc import Iterator

import pytest

from pineapple.session import DeviceSession


@pytest.fixture
def device_session() -> Iterator[DeviceSession]:
    session = DeviceSession()
    yield session
    session._loop.call_soon_threadsafe(session._loop.stop)
    session._thread.join(timeout=1)
