"""Synchronous bridge over :mod:`pineapple.devices`, bound to
``window.pywebview.api`` in the frontend.

pywebview calls these methods from a worker thread with no event loop. Short
calls run the async device layer with :func:`asyncio.run`; long-lived work
(syslog streaming) goes through :data:`pineapple.session.session` instead.
Method names are snake_case because they appear verbatim as
``window.pywebview.api.<name>``.
"""

import asyncio
import contextlib
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any

import webview

from pineapple import backup, devices
from pineapple.analysis import archive as analysis_archive
from pineapple.analysis.case import CaseHandle, load_case
from pineapple.analysis.errors import AnalysisError
from pineapple.analysis.runner import AnalysisRun
from pineapple.backup import DeviceBackup
from pineapple.session import session
from pineapple.syslog import SyslogStream

# Characters a device name may contain that must not reach a file name.
_UNSAFE_NAME_CHARS = set('/\\:*?"<>|')


class Api:
    def __init__(self) -> None:
        self._syslog = SyslogStream(session)
        self._backup = DeviceBackup(session)
        self._analysis = AnalysisRun(session)
        self._case: CaseHandle | None = None
        # Decryption key for the open case's backup files. In memory only.
        self._case_password: str | None = None

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

    # -- analysis (offline .pineapple parsing) -----------------------------

    def choose_pineapple_file(self) -> dict[str, Any]:
        """Ask the user to pick a ``.pineapple`` image to analyse."""
        window = webview.windows[0]
        result = window.create_file_dialog(
            webview.FileDialog.OPEN,
            file_types=("Pineapple image (*.pineapple)", "All files (*.*)"),
        )
        if not result:
            return {"ok": False}
        path = result if isinstance(result, str) else result[0]
        return {"ok": True, "path": path}

    def choose_case_folder(self) -> dict[str, Any]:
        """Ask the user for the folder the analysis will live in."""
        window = webview.windows[0]
        result = window.create_file_dialog(webview.FileDialog.FOLDER)
        if not result:
            return {"ok": False}
        path = result if isinstance(result, str) else result[0]
        return {"ok": True, "path": path}

    def analysis_peek(self, pineapple_path: str) -> dict[str, Any]:
        """Device and encryption facts from the archive, before parsing.

        ``{"ok": True, "encrypted": bool, "device": {...}, "default_title": str}``
        or ``{"ok": False, "error": ...}``.
        """
        try:
            metadata = analysis_archive.peek(pineapple_path)
        except AnalysisError as error:
            return {"ok": False, "error": str(error)}
        return {
            "ok": True,
            "encrypted": metadata.is_encrypted,
            "device": metadata.device_dict(),
            "default_title": metadata.default_title,
        }

    def start_analysis(
        self, pineapple_path: str, case_dir: str, title: str, password: str
    ) -> dict[str, Any]:
        """Begin parsing. ``title`` empty ⇒ the device serial; ``password`` is
        ignored for an unencrypted image."""
        try:
            self._analysis.start(pineapple_path, case_dir, title, password)
        except Exception as error:
            return {"ok": False, "error": str(error)}
        # Keep the key so the finished case can read its own backup files.
        self._case_password = password or None
        return {"ok": True}

    def read_analysis_progress(self) -> dict[str, Any]:
        """Snapshot of the running (or finished) parse; opens the case on ``done``."""
        snapshot = self._analysis.progress()
        if snapshot["phase"] == "done" and self._case is None and snapshot["case_path"]:
            with contextlib.suppress(AnalysisError):
                self._case = load_case(snapshot["case_path"], self._case_password)
        return snapshot

    def cancel_analysis(self) -> dict[str, Any]:
        """Cancel a running parse; safe to call when none is running."""
        self._analysis.cancel()
        return {"ok": True}

    def open_case(self, case_dir: str, password: str = "") -> dict[str, Any]:
        """Load an existing case folder for browsing. ``password`` is optional and
        only used to unlock file extraction/preview for an encrypted backup.

        ``{"ok": True, "descriptor": {...}, "summary": {...}}`` or
        ``{"ok": False, "error": ...}``.
        """
        if self._case is not None:
            self._case.close()
            self._case = None
        self._case_password = password or None
        try:
            self._case = load_case(case_dir, self._case_password)
        except AnalysisError as error:
            return {"ok": False, "error": str(error)}
        return {
            "ok": True,
            "descriptor": self._case.descriptor(),
            "summary": self._case.summary(),
        }

    def analysis_unlock(self, password: str) -> dict[str, Any]:
        """Supply the decryption key for the open (encrypted) case's backup files."""
        if self._case is None:
            return {"ok": False, "error": "No analysis is open."}
        try:
            self._case.set_password(password)
        except AnalysisError as error:
            return {"ok": False, "error": str(error)}
        self._case_password = password
        return {"ok": True, "summary": self._case.summary()}

    def analysis_summary(self) -> dict[str, Any]:
        return self._case_query(lambda case: case.summary())

    def analysis_apps(self) -> dict[str, Any]:
        return self._case_query(lambda case: case.apps())

    def analysis_domains(self) -> dict[str, Any]:
        return self._case_query(lambda case: case.domains())

    def analysis_files(
        self,
        domain: str | None = None,
        search: str | None = None,
        limit: int = 200,
        offset: int = 0,
    ) -> dict[str, Any]:
        return self._case_query(lambda case: case.files(domain, search, limit, offset))

    def analysis_messages(
        self, search: str | None = None, limit: int = 200, offset: int = 0
    ) -> dict[str, Any]:
        return self._case_query(lambda case: case.messages(search, limit, offset))

    def analysis_calls(self, limit: int = 200, offset: int = 0) -> dict[str, Any]:
        return self._case_query(lambda case: case.calls(limit, offset))

    def analysis_contacts(
        self, search: str | None = None, limit: int = 200, offset: int = 0
    ) -> dict[str, Any]:
        return self._case_query(lambda case: case.contacts(search, limit, offset))

    def analysis_notes(
        self, search: str | None = None, limit: int = 200, offset: int = 0
    ) -> dict[str, Any]:
        return self._case_query(lambda case: case.notes(search, limit, offset))

    def analysis_safari_history(
        self, search: str | None = None, limit: int = 200, offset: int = 0
    ) -> dict[str, Any]:
        return self._case_query(lambda case: case.safari_history(search, limit, offset))

    def analysis_safari_bookmarks(
        self, search: str | None = None, limit: int = 200, offset: int = 0
    ) -> dict[str, Any]:
        return self._case_query(
            lambda case: case.safari_bookmarks(search, limit, offset)
        )

    def analysis_whatsapp_chats(
        self, limit: int = 200, offset: int = 0
    ) -> dict[str, Any]:
        return self._case_query(lambda case: case.whatsapp_chats(limit, offset))

    def analysis_whatsapp_messages(
        self,
        chat_jid: str | None = None,
        search: str | None = None,
        limit: int = 200,
        offset: int = 0,
    ) -> dict[str, Any]:
        return self._case_query(
            lambda case: case.whatsapp_messages(chat_jid, search, limit, offset)
        )

    def analysis_preview_file(self, file_id: str) -> dict[str, Any]:
        """A size-capped, classified preview of one backup file's contents."""
        return self._case_query(lambda case: case.preview_file(file_id))

    def analysis_extract_file(self, file_id: str) -> dict[str, Any]:
        """Save one backup file to a path the user picks.

        ``{"ok": True, "path": ...}``, ``{"ok": False}`` when the dialog is
        cancelled, or ``{"ok": False, "error": ...}``.
        """
        if self._case is None:
            return {"ok": False, "error": "No analysis is open."}
        try:
            suggested = self._case.file_name(file_id)
        except AnalysisError as error:
            return {"ok": False, "error": str(error)}
        window = webview.windows[0]
        result = window.create_file_dialog(
            webview.FileDialog.SAVE, save_filename=suggested
        )
        if not result:
            return {"ok": False}
        dest = Path(result if isinstance(result, str) else result[0])
        try:
            self._case.extract_file(file_id, dest)
        except AnalysisError as error:
            return {"ok": False, "error": str(error)}
        return {"ok": True, "path": str(dest)}

    def _case_query(self, run: Callable[[CaseHandle], Any]) -> dict[str, Any]:
        if self._case is None:
            return {"ok": False, "error": "No analysis is open."}
        try:
            return {"ok": True, "result": run(self._case)}
        except Exception as error:  # a corrupt analysis.db surfaces here
            return {"ok": False, "error": str(error)}
