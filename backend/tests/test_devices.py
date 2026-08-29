"""Tests for :mod:`pineapple.devices` (the async usbmux / lockdown layer)."""

import pytest
from pymobiledevice3.exceptions import ConnectionFailedToUsbmuxdError

from pineapple import devices
from support import FakeLockdown, mux_device

SELECT = "pymobiledevice3.usbmux.select_devices_by_connection_type"


def patch_attached(monkeypatch: pytest.MonkeyPatch, *serials: str) -> None:
    async def fake_select(connection_type: str) -> list[object]:
        assert connection_type == "USB"
        return [mux_device(serial) for serial in serials]

    monkeypatch.setattr(SELECT, fake_select)


async def test_connected_devices_maps_udid_and_connection_type(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    patch_attached(monkeypatch, "aaaa", "bbbb")

    assert await devices.connected_devices() == [
        {"Udid": "aaaa", "ConnectionType": "USB"},
        {"Udid": "bbbb", "ConnectionType": "USB"},
    ]


async def test_connected_devices_empty_when_usbmuxd_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_select(connection_type: str) -> list[object]:
        raise ConnectionFailedToUsbmuxdError

    monkeypatch.setattr(SELECT, fake_select)

    assert await devices.connected_devices() == []


@pytest.mark.parametrize(
    ("serials", "expected"),
    [
        ((), None),
        (("only-one",), "only-one"),
        (("first", "second"), None),
    ],
)
async def test_single_device_udid_only_picks_a_lone_device(
    monkeypatch: pytest.MonkeyPatch, serials: tuple[str, ...], expected: str | None
) -> None:
    patch_attached(monkeypatch, *serials)

    assert await devices.single_device_udid() == expected


async def test_get_device_info_projects_only_info_fields(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    values: dict[str, object] = {
        field: f"value-{field}" for field in devices.INFO_FIELDS
    }
    values["SomethingElse"] = "ignored"
    lockdown = FakeLockdown(values)
    seen: dict[str, object] = {}

    async def fake_create(udid: str, autopair: bool) -> FakeLockdown:
        seen["udid"] = udid
        seen["autopair"] = autopair
        return lockdown

    monkeypatch.setattr(devices, "create_using_usbmux", fake_create)

    info = await devices.get_device_info("udid-1")

    assert set(info) == set(devices.INFO_FIELDS)
    assert info["DeviceName"] == "value-DeviceName"
    assert seen == {"udid": "udid-1", "autopair": False}
    assert lockdown.closed


async def test_get_device_info_closes_the_lockdown_even_on_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    lockdown = FakeLockdown(fail=True)

    async def fake_create(udid: str, autopair: bool) -> FakeLockdown:
        return lockdown

    monkeypatch.setattr(devices, "create_using_usbmux", fake_create)

    with pytest.raises(RuntimeError, match="cannot read lockdown values"):
        await devices.get_device_info("udid-1")
    assert lockdown.closed
