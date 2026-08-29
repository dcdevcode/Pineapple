"""Detect Apple devices connected over USB and read basic device information."""

import asyncio
from typing import Any

from pymobiledevice3 import usbmux
from pymobiledevice3.exceptions import ConnectionFailedToUsbmuxdError
from pymobiledevice3.lockdown import create_using_usbmux

# "Typical" fields pulled from lockdownd to describe a device.
DEVICE_INFO_FIELDS = [
    "DeviceName",
    "DeviceClass",
    "ProductType",
    "ProductName",
    "ProductVersion",
    "BuildVersion",
    "ModelNumber",
    "HardwareModel",
    "RegionInfo",
    "SerialNumber",
    "UniqueDeviceID",
    "WiFiAddress",
    "BluetoothAddress",
    "CPUArchitecture",
    "TotalDiskCapacity",
    "TimeZone",
    "PasswordProtected",
]


async def _detect_devices() -> list[dict[str, Any]]:
    try:
        mux_devices = await usbmux.list_devices()
    except ConnectionFailedToUsbmuxdError:
        return []

    devices: list[dict[str, Any]] = []
    for device in mux_devices:
        if not device.is_usb:
            continue

        try:
            lockdown = await create_using_usbmux(
                device.serial,
                autopair=False,
                connection_type=device.connection_type,
            )
        except Exception as error:  # not paired, trust not granted, etc.
            devices.append(
                {
                    "Udid": device.serial,
                    "ConnectionType": device.connection_type,
                    "Error": str(error),
                }
            )
            continue

        try:
            info = dict(lockdown.short_info)
            info["Udid"] = device.serial
            info["ConnectionType"] = device.connection_type
            devices.append(info)
        finally:
            await lockdown.close()

    return devices


async def _list_devices() -> list[dict[str, Any]]:
    try:
        mux_devices = await usbmux.list_devices()
    except ConnectionFailedToUsbmuxdError:
        return []

    return [
        {"Udid": device.serial, "ConnectionType": device.connection_type}
        for device in mux_devices
        if device.is_usb
    ]


def list_devices() -> list[dict[str, Any]]:
    """Return the USB devices reported by the local usbmuxd daemon.

    This never talks to the device itself, so it is cheap enough to call on a
    poll. Each item has ``Udid`` and ``ConnectionType``. The list is empty when
    no device is connected or usbmuxd is unavailable. Use :func:`get_device_info`
    to read the full details of a device.
    """
    return asyncio.run(_list_devices())


def detect_devices() -> list[dict[str, Any]]:
    """Return the list of Apple devices connected over USB.

    Each item is a dict with a device summary (``DeviceName``, ``ProductType``,
    ``ProductVersion``, ...) plus ``Udid`` and ``ConnectionType``. The list is
    empty when no device is connected or usbmuxd is unavailable.
    """
    return asyncio.run(_detect_devices())


async def _get_device_info(udid: str) -> dict[str, Any]:
    lockdown = await create_using_usbmux(udid, autopair=False)
    try:
        values = lockdown.all_values
    finally:
        await lockdown.close()
    return {key: values.get(key) for key in DEVICE_INFO_FIELDS}


def get_device_info(device: str | dict[str, Any]) -> dict[str, Any]:
    """Return the typical information for a device.

    ``device`` can be a UDID string or an item returned by :func:`detect_devices`.
    """
    udid = device if isinstance(device, str) else device["Udid"]
    return asyncio.run(_get_device_info(udid))


def main() -> None:
    devices = detect_devices()
    if not devices:
        print("No devices connected over USB were detected.")
        return

    device_info = get_device_info(devices[0])
    print(device_info)


if __name__ == "__main__":
    main()
