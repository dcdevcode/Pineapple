# pineapple (backend)

Python backend for the Pineapple iOS forensic analysis tool. See
[`../ARCHITECTURE.md`](../ARCHITECTURE.md) for how the pieces fit together.

## Modules

| Module | Purpose |
| --- | --- |
| `pineapple.devices` | Async USB device access (`connected_devices`, `single_device_udid`, `get_device_info`). |
| `pineapple.session` | `DeviceSession`: one background asyncio loop for long-lived device work. |
| `pineapple.syslog` | `SyslogStream`: live `com.apple.os_trace_relay` stream into a bounded buffer. |
| `pineapple.backup` | `DeviceBackup`: a full MobileBackup2 acquisition packaged as one `.pineapple` zip. |
| `pineapple.analysis` | Offline `.pineapple` parsing: archive / metadata / reader, the artifact parsers, the run pipeline, and the `<title>.json` case folder. |
| `pineapple.api` | `Api`: the sync bridge over the above, bound to `window.pywebview.api`. |
| `pineapple.app` | pywebview host window (`pineapple-gui`). |
| `pineapple.cli` | `pineapple` console script: print the connected devices. |

## Setup

```bash
uv sync
```

## Run

```bash
uv run pineapple            # print the connected devices and their info
uv run pineapple-gui        # desktop window (serves the production frontend build)
uv run pineapple-gui --dev  # desktop window against the Angular dev server (pnpm start in ../frontend)
```

## Checks

```bash
uv run ruff check . && uv run ruff format --check .
uv run mypy          # strict
uv run pytest
```

Tests live in `tests/` and never touch a device: the `pymobiledevice3`,
`webview` and `iphone_backup_decrypt` boundaries are faked (`tests/support.py`
and `tests/analysis_support.py`, which also builds a tiny real on-disk backup
+ `.pineapple`). Every function with non-trivial behaviour ships its test in
the same change.
