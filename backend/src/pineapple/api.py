"""JS <-> Python bridge exposed to the Angular frontend via pywebview's js_api.

The methods here are thin wrappers over :mod:`pineapple.main` that return plain
JSON-serializable values. Method names stay in snake_case because they appear
verbatim as ``window.pywebview.api.<name>`` in the frontend.
"""

from typing import Any

from pineapple.main import get_device_info, list_devices


class Api:
    """Object bound to ``window.pywebview.api`` in the frontend."""

    def list_devices(self) -> list[dict[str, Any]]:
        """Return connected USB devices (usbmuxd only). Cheap enough to poll."""
        return list_devices()

    def get_device_info(self, udid: str) -> dict[str, Any]:
        """Return the full information for one device.

        ``{"ok": True, "info": {...}}`` on success, or
        ``{"ok": False, "error": "<message>"}`` when the device is not paired
        ("Trust this computer"), was unplugged, or is otherwise unreachable.
        """
        try:
            info = get_device_info(udid)
        except Exception as error:  # not paired, trust denied, disconnected, ...
            return {"ok": False, "error": str(error)}
        return {"ok": True, "info": info}
