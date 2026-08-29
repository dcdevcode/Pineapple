"""Synchronous bridge over :mod:`pineapple.devices`, bound to
``window.pywebview.api`` in the frontend.

pywebview calls these methods from a worker thread with no event loop. Short
calls run the async device layer with :func:`asyncio.run`; long-lived work
(syslog streaming) goes through :data:`pineapple.session.session` instead.
Method names are snake_case because they appear verbatim as
``window.pywebview.api.<name>``.
"""

import asyncio
from pathlib import Path
from typing import Any

import webview

from pineapple import devices
from pineapple.session import session
from pineapple.syslog import SyslogStream


class Api:
    def __init__(self) -> None:
        self._syslog = SyslogStream(session)

    def connected_device(self) -> dict[str, Any]:
        """The single-device view the UI needs: ``{"status": "none"}``,
        ``{"status": "one", "device": {...}}``, or ``{"status": "multiple"}``.

        Several devices are reported as ``multiple`` rather than picking one --
        for forensics, guessing which device to act on is not acceptable.
        """
        attached = asyncio.run(devices.connected_devices())
        if not attached:
            return {"status": "none"}
        if len(attached) > 1:
            return {"status": "multiple"}
        return {"status": "one", "device": attached[0]}

    def get_device_info(self, udid: str) -> dict[str, Any]:
        """``{"ok": True, "info": {...}}``, or ``{"ok": False, "error": ...}``
        when the device is unpaired or unreachable."""
        try:
            info = asyncio.run(devices.get_device_info(udid))
        except Exception as error:
            return {"ok": False, "error": str(error)}
        return {"ok": True, "info": info}

    def start_syslog(self) -> dict[str, Any]:
        """Begin streaming the connected device's system log.

        ``{"ok": True}``, or ``{"ok": False, "error": ...}`` when there is not
        exactly one device. A device that turns out to be unpaired surfaces
        later via :meth:`read_syslog`'s ``error`` field.
        """
        try:
            self._syslog.start()
        except Exception as error:
            return {"ok": False, "error": str(error)}
        return {"ok": True}

    def read_syslog(self) -> dict[str, Any]:
        """Drain buffered lines: ``{"lines": [...], "dropped": N,
        "running": bool, "error": str | None}``."""
        return self._syslog.read()

    def stop_syslog(self) -> dict[str, Any]:
        """Stop the stream and close the connection."""
        self._syslog.stop()
        return {"ok": True}

    def save_syslog(self, content: str) -> dict[str, Any]:
        """Write captured log text to a file the user picks.

        ``{"ok": True, "path": ...}``, or ``{"ok": False}`` when the save
        dialog is cancelled.
        """
        window = webview.windows[0]
        result = window.create_file_dialog(
            webview.FileDialog.SAVE, save_filename="syslog.txt"
        )
        if not result:
            return {"ok": False}
        path = Path(result if isinstance(result, str) else result[0])
        path.write_text(content, encoding="utf-8")
        return {"ok": True, "path": str(path)}
