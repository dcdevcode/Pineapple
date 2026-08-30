"""Tests for :mod:`pineapple.analysis.metadata`."""

from __future__ import annotations

from datetime import UTC, datetime

from pineapple.analysis.metadata import AppInfo, from_plists


def test_from_plists_pulls_device_and_apps() -> None:
    info = {
        "Device Name": "My iPhone",
        "Product Type": "iPhone14,5",
        "Product Version": "17.5.1",
        "Serial Number": "ABC123",
        "Target Identifier": "udid-1",
        "Last Backup Date": datetime(2026, 8, 1, 12, 0, tzinfo=UTC),
        "Applications": {
            "com.example.app": {
                "CFBundleDisplayName": "Example",
                "CFBundleShortVersionString": "3.0",
            }
        },
    }
    manifest = {"IsEncrypted": True, "WasPasscodeSet": True}

    metadata = from_plists(info, manifest, {})

    assert metadata.device_name == "My iPhone"
    assert metadata.serial == "ABC123"
    assert metadata.udid == "udid-1"
    assert metadata.is_encrypted is True
    assert metadata.last_backup_date == "2026-08-01T12:00:00+00:00"
    assert metadata.apps == [AppInfo("com.example.app", "Example", "3.0")]


def test_from_plists_falls_back_to_installed_list_and_status_date() -> None:
    info = {"Installed Applications": ["com.b", "com.a"]}
    status = {"Date": datetime(2026, 1, 1, tzinfo=UTC)}

    metadata = from_plists(info, {}, status)

    assert [app.bundle_id for app in metadata.apps] == ["com.a", "com.b"]
    assert metadata.last_backup_date == "2026-01-01T00:00:00+00:00"
    assert metadata.is_encrypted is False
    assert metadata.default_title == "analysis"
