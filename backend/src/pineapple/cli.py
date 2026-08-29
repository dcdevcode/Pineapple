"""``pineapple`` console script: print the connected devices and their info."""

import asyncio

from pineapple import devices


async def _run() -> None:
    connected = await devices.connected_devices()
    if not connected:
        print("No USB devices detected.")
        return

    for device in connected:
        udid = device["Udid"]
        print(udid)
        try:
            info = await devices.get_device_info(udid)
        except Exception as error:
            print(f"  unavailable: {error}")
            continue
        for field, value in info.items():
            print(f"  {field}: {value}")


def main() -> None:
    asyncio.run(_run())


if __name__ == "__main__":
    main()
