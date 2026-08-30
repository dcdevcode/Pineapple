"""Synchronous bridge over :mod:`pineapple.devices`, bound to
``window.pywebview.api`` in the frontend.

pywebview calls these methods from a worker thread with no event loop. Short
calls run the async device layer with :func:`asyncio.run`; long-lived work
(syslog streaming) goes through :data:`pineapple.session.session` instead.
Method names are snake_case because they appear verbatim as
``window.pywebview.api.<name>``.
"""

import asyncio
from datetime import datetime
from pathlib import Path
from typing import Any

import webview

from pineapple import backup, devices
from pineapple.backup import DeviceBackup
from pineapple.session import session
from pineapple.syslog import SyslogStream

# Characters a device name may contain that must not reach a file name.
_UNSAFE_NAME_CHARS = set('/\\:*?"<>|')


class Api:
    def __init__(self) -> None:
        self._syslog = SyslogStream(session)
        self._backup = DeviceBackup(session)

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

    def backup_preflight(self) -> dict[str, Any]:
        """Whether the connected device already encrypts its backups.

        ``{"ok": True, "willEncrypt": bool}``, or ``{"ok": False, "error": ...}``
        when there is not exactly one device, or it is unpaired / unreachable.
        """
        udid = asyncio.run(devices.single_device_udid())
        if udid is None:
            return {"ok": False, "error": "no single device connected"}
        try:
            will_encrypt = asyncio.run(backup.will_encrypt_backups(udid))
        except Exception as error:
            return {"ok": False, "error": str(error)}
        return {"ok": True, "willEncrypt": will_encrypt}

    def choose_backup_path(self, device_name: str) -> dict[str, Any]:
        """Ask the user where to write the ``.pineapple`` archive.

        ``{"ok": True, "path": ...}``, or ``{"ok": False}`` when cancelled.
        """
        safe_name = (
            "".join(
                "_" if character in _UNSAFE_NAME_CHARS else character
                for character in device_name
            ).strip()
            or "device"
        )
        stamp = datetime.now().strftime("%Y-%m-%d %H%M%S")
        window = webview.windows[0]
        result = window.create_file_dialog(
            webview.FileDialog.SAVE,
            save_filename=f"{safe_name} {stamp}.pineapple",
        )
        if not result:
            return {"ok": False}
        path = result if isinstance(result, str) else result[0]
        return {"ok": True, "path": path}

    def start_backup(self, path: str, encrypt: bool, password: str) -> dict[str, Any]:
        """Begin the logical acquisition. ``password`` is ignored (may be empty)
        when ``encrypt`` is False.

        ``{"ok": True}``, or ``{"ok": False, "error": ...}``.
        """
        try:
            self._backup.start(path, encrypt, password)
        except Exception as error:
            return {"ok": False, "error": str(error)}
        return {"ok": True}

    def read_backup_progress(self) -> dict[str, Any]:
        """Snapshot of the running (or finished) acquisition."""
        return self._backup.progress()

    def cancel_backup(self) -> dict[str, Any]:
        """Cancel a running acquisition; safe to call when none is running."""
        self._backup.cancel()
        return {"ok": True}

    def save_syslog(self, content: str) -> dict[str, Any]:
        """Write captured log text to a file the user picks.

        ``{"ok": True, "path": ...}``, ``{"ok": False}`` when the save dialog is
        cancelled, or ``{"ok": False, "error": ...}`` when the write fails.
        """
        window = webview.windows[0]
        result = window.create_file_dialog(
            webview.FileDialog.SAVE, save_filename="syslog.txt"
        )
        if not result:
            return {"ok": False}
        path = Path(result if isinstance(result, str) else result[0])
        try:
            path.write_text(content, encoding="utf-8")
        except OSError as error:
            return {"ok": False, "error": str(error)}
        return {"ok": True, "path": str(path)}
