"""Full-device logical acquisition: a MobileBackup2 backup packaged as a single
``.pineapple`` archive.

Like :mod:`pineapple.syslog`, the work is long-lived and holds a device
connection, so it runs as a task on :data:`pineapple.session.session` while the
frontend polls :meth:`DeviceBackup.progress` for status.

An encrypted backup is only possible when the *device* is set to encrypt its
backups (``WillEncrypt``); passing a password to :meth:`Mobilebackup2Service.backup`
does not turn encryption on. So when the caller asks for encryption on a device
that does not already encrypt, this module enables it
(:meth:`Mobilebackup2Service.change_password`) before the backup and restores the
device's original setting afterwards -- including on failure or cancellation.
"""

import asyncio
import shutil
import threading
import zipfile
from dataclasses import asdict, dataclass
from pathlib import Path
from tempfile import mkdtemp
from typing import Any

from pymobiledevice3.lockdown import create_using_usbmux
from pymobiledevice3.services.mobilebackup2 import Mobilebackup2Service

from pineapple import devices
from pineapple.session import DeviceSession

PINEAPPLE_SUFFIX = ".pineapple"

# How long cancel() waits for the task to unwind before returning to the UI.
# Cleanup (restoring the device's encryption setting) is shielded, so it still
# finishes in the background; the frontend keeps polling until `running` is off.
TEARDOWN_TIMEOUT = 10.0


async def will_encrypt_backups(udid: str) -> bool:
    """Whether the device is configured to encrypt its backups.

    Opens a lockdown connection, so the device must be paired. Raises when it is
    unpaired or unreachable.
    """
    lockdown = await create_using_usbmux(udid, autopair=False)
    try:
        async with Mobilebackup2Service(lockdown) as service:
            return await service.get_will_encrypt()
    finally:
        await lockdown.close()


def _as_pineapple_path(raw: str) -> Path:
    """The chosen path with a ``.pineapple`` extension guaranteed."""
    path = Path(raw)
    if path.suffix == PINEAPPLE_SUFFIX:
        return path
    return path.with_name(path.name + PINEAPPLE_SUFFIX)


def _zip_stored(
    source_dir: Path, archive_path: Path, cancelled: threading.Event
) -> None:
    """Pack ``source_dir`` into ``archive_path`` as an uncompressed zip.

    Entries are rooted at ``source_dir.name`` (the device UDID) so the archive
    extracts back to a layout ``pymobiledevice3`` can restore from. Checks
    ``cancelled`` between files so a cancel during packaging is honoured.
    """
    files = sorted(p for p in source_dir.rglob("*") if p.is_file())
    root = source_dir.parent
    with zipfile.ZipFile(
        archive_path, "w", zipfile.ZIP_STORED, allowZip64=True
    ) as archive:
        for file in files:
            if cancelled.is_set():
                raise _PackagingCancelled
            archive.write(file, file.relative_to(root).as_posix())


class _PackagingCancelled(Exception):
    """Raised inside the packaging thread when a cancel is requested."""


@dataclass
class _Progress:
    phase: str = "idle"
    percent: float = 0.0
    output_path: str | None = None
    error: str | None = None
    note: str | None = None
    running: bool = False


class DeviceBackup:
    """A single acquisition: :meth:`start` it, poll :meth:`progress`, optionally
    :meth:`cancel`."""

    def __init__(self, session: DeviceSession) -> None:
        self._session = session
        # Serialises start/cancel so a new run cannot race a previous teardown.
        self._op_lock = threading.Lock()
        self._state_lock = threading.Lock()
        self._state = _Progress()
        self._task: asyncio.Task[Any] | None = None
        self._cancelled = threading.Event()
        # True once this run turned on the device's backup encryption; drives
        # the restore in _restore_encryption / _unwind.
        self._we_enabled_encryption = False

    @property
    def running(self) -> bool:
        return self._task is not None and not self._task.done()

    def start(self, output_path: str, encrypt: bool, password: str) -> None:
        """Begin a full backup of the single connected device.

        ``password`` is ``""`` for an unencrypted backup. Raises
        ``RuntimeError`` when there is not exactly one device connected.
        """
        with self._op_lock:
            self._teardown()
            udid = self._session.run(devices.single_device_udid())
            if udid is None:
                raise RuntimeError("no single device connected")
            target = _as_pineapple_path(output_path)
            self._cancelled = threading.Event()
            with self._state_lock:
                self._state = _Progress(phase="preparing", running=True)
            self._task = self._session.spawn(self._run(udid, target, encrypt, password))

    def progress(self) -> dict[str, Any]:
        """A JSON-friendly snapshot of the current acquisition state."""
        with self._state_lock:
            snapshot = asdict(self._state)
        snapshot["running"] = self.running and snapshot["running"]
        return snapshot

    def cancel(self) -> None:
        """Request cancellation and wait briefly for the task to unwind."""
        with self._op_lock:
            self._teardown()

    def _teardown(self) -> None:
        task, self._task = self._task, None
        if task is None:
            return
        self._cancelled.set()
        self._session.cancel(task)
        self._session.drain(task, TEARDOWN_TIMEOUT)

    # -- internals, all running on the session loop ------------------------

    def _set(self, **fields: Any) -> None:
        with self._state_lock:
            for name, value in fields.items():
                setattr(self._state, name, value)

    def _note(self) -> str | None:
        with self._state_lock:
            return self._state.note

    def _on_percent(self, value: Any) -> None:
        if not isinstance(value, (int, float)):
            return
        self._set(percent=max(0.0, min(100.0, float(value))))

    async def _run(
        self, udid: str, output_path: Path, encrypt: bool, password: str
    ) -> None:
        lockdown = None
        staging: Path | None = None
        self._we_enabled_encryption = False
        try:
            try:
                lockdown = await create_using_usbmux(udid, autopair=False)
            except Exception as error:  # unpaired / unreachable
                self._set(phase="error", error=str(error), note=None, running=False)
                return

            staging = Path(mkdtemp(prefix=".pineapple-", dir=output_path.parent))

            if encrypt:
                await self._enable_encryption_if_needed(lockdown, password)

            self._set(
                phase="backing_up",
                percent=0.0,
                note="Backing up the device. Keep it unlocked and connected.",
            )
            # A fresh Mobilebackup2Service: the com.apple.mobilebackup2 session
            # is single-use (one DeviceLink operation, then DLMessageDisconnect),
            # so the backup cannot share the "enable encryption" instance.
            async with Mobilebackup2Service(lockdown) as service:
                await service.backup(
                    full=True,
                    backup_directory=str(staging),
                    password=password,
                    progress_callback=self._on_percent,
                )

            self._set(phase="packaging", note="Packaging the .pineapple archive.")
            await asyncio.to_thread(
                _zip_stored, staging / udid, output_path, self._cancelled
            )

            note = None
            if self._we_enabled_encryption:
                await self._restore_encryption(lockdown, password)
                note = self._note()
            self._set(
                phase="done",
                percent=100.0,
                output_path=str(output_path),
                error=None,
                note=note,
                running=False,
            )
        except (asyncio.CancelledError, _PackagingCancelled) as exc:
            await asyncio.shield(
                self._unwind(lockdown, password, output_path, "cancelled")
            )
            if isinstance(exc, asyncio.CancelledError):
                raise
        except Exception as error:
            await asyncio.shield(
                self._unwind(lockdown, password, output_path, "error", str(error))
            )
        finally:
            if staging is not None:
                shutil.rmtree(staging, ignore_errors=True)
            if lockdown is not None:
                await lockdown.close()

    async def _enable_encryption_if_needed(self, lockdown: Any, password: str) -> None:
        """Turn on backup encryption when the device does not already encrypt.

        Its own Mobilebackup2Service (single-use session, see :meth:`_run`).
        ``_we_enabled_encryption`` is set *before* the call so a cancel
        mid-change still triggers the restore, even if the enable half-applied.
        """
        async with Mobilebackup2Service(lockdown) as prep:
            if await prep.get_will_encrypt():
                return
            self._set(
                phase="preparing",
                note="Enabling backup encryption on the device. Unlock it and "
                "enter the passcode if prompted.",
            )
            self._we_enabled_encryption = True
            await prep.change_password(new=password)

    async def _unwind(
        self,
        lockdown: Any,
        password: str,
        output_path: Path,
        phase: str,
        error: str | None = None,
    ) -> None:
        """Roll a failed / cancelled run back: drop the half-written archive and
        restore the device's original encryption setting."""
        output_path.unlink(missing_ok=True)
        if self._we_enabled_encryption:
            await self._restore_encryption(lockdown, password)
        self._set(phase=phase, error=error, running=False)

    async def _restore_encryption(self, lockdown: Any, password: str) -> None:
        """Turn off the backup encryption this run enabled on the device."""
        if lockdown is None:
            return
        self._set(
            phase="restoring_encryption",
            note="Restoring the device's original backup-encryption setting.",
        )
        try:
            async with Mobilebackup2Service(lockdown) as service:
                await service.change_password(old=password)
        except Exception as restore_error:
            self._set(
                note="Could not restore the device's backup-encryption setting "
                f"({restore_error}). The device still has backup encryption "
                "enabled with the password you chose.",
            )
        else:
            self._set(note="Restored the device's original backup-encryption setting.")
