"""Synchronous bridge over :mod:`pineapple.devices`, bound to
``window.pywebview.api`` in the frontend.

pywebview calls these methods from a worker thread with no event loop, so this
is the one place the async device layer is run. Method names are snake_case
because they appear verbatim as ``window.pywebview.api.<name>``.
"""

import asyncio
from typing import Any

from pineapple import devices


class Api:
    def list_devices(self) -> list[dict[str, str]]:
        return asyncio.run(devices.list_devices())

    def get_device_info(self, udid: str) -> dict[str, Any]:
        """``{"ok": True, "info": {...}}``, or ``{"ok": False, "error": ...}``
        when the device is unpaired or unreachable."""
        try:
            info = asyncio.run(devices.get_device_info(udid))
        except Exception as error:
            return {"ok": False, "error": str(error)}
        return {"ok": True, "info": info}
