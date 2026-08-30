"""The essential facts about a backup, read from its three plists.

``Info.plist``, ``Manifest.plist`` and ``Status.plist`` (each XML or binary --
:func:`plistlib.loads` handles both) sit at the root of every MobileBackup2
backup and are never encrypted, so this can run straight off the ``.pineapple``
zip -- see :func:`pineapple.analysis.archive.peek`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class AppInfo:
    """One installed application, as far as the backup plists describe it."""

    bundle_id: str
    name: str | None = None
    version: str | None = None


@dataclass(frozen=True)
class BackupMetadata:
    """Device and backup facts shown before and after parsing."""

    device_name: str | None = None
    product_type: str | None = None
    product_name: str | None = None
    product_version: str | None = None
    build_version: str | None = None
    serial: str | None = None
    udid: str | None = None
    last_backup_date: str | None = None
    is_encrypted: bool = False
    was_passcode_set: bool = False
    apps: list[AppInfo] = field(default_factory=list)

    @property
    def default_title(self) -> str:
        """The case title to offer when the user does not type one."""
        return self.serial or self.udid or "analysis"

    def device_dict(self) -> dict[str, Any]:
        """The device fields, JSON-friendly, for the case descriptor and the UI."""
        return {
            "name": self.device_name,
            "product_type": self.product_type,
            "product_name": self.product_name,
            "product_version": self.product_version,
            "build_version": self.build_version,
            "serial": self.serial,
            "udid": self.udid,
            "last_backup_date": self.last_backup_date,
            "was_passcode_set": self.was_passcode_set,
        }


def _isoformat(value: Any) -> str | None:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, str) and value:
        return value
    return None


def _apps(info: dict[str, Any]) -> list[AppInfo]:
    applications = info.get("Applications")
    if isinstance(applications, dict):
        apps = []
        for bundle_id, entry in sorted(applications.items()):
            details = entry if isinstance(entry, dict) else {}
            apps.append(
                AppInfo(
                    bundle_id=str(bundle_id),
                    name=details.get("CFBundleDisplayName")
                    or details.get("CFBundleName"),
                    version=(
                        details.get("CFBundleShortVersionString")
                        or details.get("CFBundleVersion")
                    ),
                )
            )
        return apps
    installed = info.get("Installed Applications")
    if isinstance(installed, list):
        return [AppInfo(bundle_id=str(bundle_id)) for bundle_id in sorted(installed)]
    return []


def from_plists(
    info: dict[str, Any],
    manifest: dict[str, Any],
    status: dict[str, Any],
) -> BackupMetadata:
    """Assemble :class:`BackupMetadata` from the three parsed plists."""
    lockdown = manifest.get("Lockdown")
    lockdown = lockdown if isinstance(lockdown, dict) else {}
    return BackupMetadata(
        device_name=info.get("Device Name") or lockdown.get("DeviceName"),
        product_type=info.get("Product Type") or lockdown.get("ProductType"),
        product_name=info.get("Product Name"),
        product_version=info.get("Product Version") or lockdown.get("ProductVersion"),
        build_version=info.get("Build Version") or lockdown.get("BuildVersion"),
        serial=info.get("Serial Number") or lockdown.get("SerialNumber"),
        udid=info.get("Target Identifier") or info.get("Unique Identifier"),
        last_backup_date=_isoformat(info.get("Last Backup Date"))
        or _isoformat(status.get("Date")),
        is_encrypted=bool(manifest.get("IsEncrypted", False)),
        was_passcode_set=bool(manifest.get("WasPasscodeSet", False)),
        apps=_apps(info),
    )
