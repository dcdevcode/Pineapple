"""Access to Apple devices connected over USB, via pymobiledevice3 (async)."""

from typing import Any

from pymobiledevice3 import usbmux
from pymobiledevice3.exceptions import ConnectionFailedToUsbmuxdError
from pymobiledevice3.lockdown import create_using_usbmux

INFO_FIELDS = [
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


async def connected_devices() -> list[dict[str, str]]:
    """Return the USB devices known to the local usbmuxd daemon.

    Does not contact the devices themselves, so it is cheap enough to poll.
    Each item has ``Udid`` and ``ConnectionType``. Empty when nothing is
    connected or usbmuxd is unavailable.
    """
    try:
        attached = await usbmux.select_devices_by_connection_type("USB")
    except ConnectionFailedToUsbmuxdError:
        return []
    return [
        {"Udid": device.serial, "ConnectionType": device.connection_type}
        for device in attached
    ]


async def get_device_info(udid: str) -> dict[str, Any]:
    """Return the ``INFO_FIELDS`` values for one device.

    Opens a lockdown connection, so the device must be paired ("Trust this
    computer"). Raises when the device is unpaired or unreachable.
    """
    lockdown = await create_using_usbmux(udid, autopair=False)
    try:
        values = lockdown.all_values
    finally:
        await lockdown.close()
    return {field: values.get(field) for field in INFO_FIELDS}
