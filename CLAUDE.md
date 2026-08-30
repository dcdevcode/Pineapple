# CLAUDE.md

Guidance for Claude Code when working in this repository.

## Language policy

**All code and documentation must be written in English** — comments, variable and
function names, docstrings, commit messages, and every `.md` file. This is a hard
requirement. Conversation with the user happens in Spanish, but nothing that lands
in the repo is in Spanish.

## Project overview

`pineapple` is an **iOS forensic analysis tool** — a desktop application that
inspects Apple devices connected over USB.

- Built **incrementally**; the user orchestrates the project and reviews every
  change. Do not add scope, features, or "nice to haves" that were not requested.
  Ask when something is unclear. Never pick between real alternatives (a library,
  a data shape, an API surface, a UX behaviour) on your own — ask the user
  explicitly. Defaults are only for things with one obvious answer.
- **Backend** (`backend/`): Python, [`uv`](https://docs.astral.sh/uv/) +
  `uv_build`, Python `>=3.14`. Device access via
  [`pymobiledevice3`](https://github.com/doronz88/pymobiledevice3); desktop window
  via [`pywebview`](https://pywebview.flowrl.com/); encrypted-backup decryption
  via [`iphone_backup_decrypt`](https://github.com/jsharkey13/iphone_backup_decrypt).
- **Frontend** (`frontend/`): Angular + Angular Material, **`pnpm` only**
  (never `npm`/`yarn`). Rendered inside the pywebview window.

## Layout

| Path | Purpose |
| --- | --- |
| `backend/pyproject.toml` | uv project: deps, `pineapple` and `pineapple-gui` entry points. |
| `backend/src/pineapple/devices.py` | Async USB device access (`connected_devices`, `single_device_udid`, `get_device_info`, `INFO_FIELDS`). |
| `backend/src/pineapple/session.py` | `DeviceSession`: one background asyncio loop for long-lived device work. Module singleton `session`. |
| `backend/src/pineapple/syslog.py` | `SyslogStream`: live `com.apple.os_trace_relay` stream into a bounded buffer the frontend drains. |
| `backend/src/pineapple/backup.py` | `DeviceBackup`: a full MobileBackup2 acquisition packaged as one uncompressed `.pineapple` zip; runs on `session`, progress polled by the frontend. |
| `backend/src/pineapple/analysis/` | Offline `.pineapple` parsing: `archive` (peek/extract the zip), `metadata` (the three plists), `reader` (uniform access, encrypted via `iphone_backup_decrypt`), `schema` + `parsers/` (messages / calls / contacts / file index → `analysis.db`), `runner` (`AnalysisRun`, runs on `session`), `descriptor` + `case` (the `<title>.json` case folder and its read queries). |
| `backend/src/pineapple/api.py` | `Api`: the sync bridge over `devices` / `syslog` / `backup` / `analysis`, bound to `window.pywebview.api`. |
| `backend/src/pineapple/cli.py` | `pineapple` console script: print the connected devices and their info. |
| `backend/src/pineapple/app.py` | pywebview host window; wires `js_api=Api()`. No device logic of its own. |
| `backend/tests/` | `pytest` suite; the `pymobiledevice3` / `webview` boundary is faked (`support.py`), no hardware needed. `analysis_support.py` builds a tiny real on-disk backup + `.pineapple` and fakes `iphone_backup_decrypt`. |
| `frontend/src/app/app.*` | Shell: `mat-tab-group` with the **Device** and **Analysis** tabs; starts device polling. |
| `frontend/src/app/device/` | Device tab: `DeviceService` (polls the bridge) + the empty / connected views. `phone-outline/` holds the iPhone SVG. |
| `frontend/src/app/syslog/` | Syslog viewer: `SyslogService` (polls the bridge) + `SyslogDialog`, the live-log modal opened from the Device tab. |
| `frontend/src/app/backup/` | Logical acquisition: `BackupService` (polls the bridge) + `BackupDialog`, the confirm → password → progress modal opened by the **Create Pineapple Logical Image** button. |
| `frontend/src/app/settings/` | Settings: floating gear (`SettingsButton`) opens `SettingsDialog` (nav-rail shell); each section is its own component (`ThemeSettings`). `ThemeService` owns the light/dark/system preference. |
| `frontend/src/app/analysis/` | Analysis tab: `AnalysisService` (parse polling + case queries) + `AnalysisDialog` (pick → configure → progress wizard) + the case browser (nav-rail over `Overview` / `Files` sections + the generic `ArtifactTable` for apps / messages / calls / contacts). |
| `frontend/src/styles.scss` | Global Angular Material theme (dark, yellow accent — a nod to the pineapple). |
| `.github/workflows/ci.yml` | CI: backend (ruff / mypy / pytest) and frontend (prettier / test / build) on every push and PR. |

## Common commands

```bash
# Backend
cd backend
uv sync
uv run pineapple                           # print connected devices + info
uv run pineapple-gui                        # desktop window, serves frontend/dist
uv run pineapple-gui --dev                  # desktop window against the Angular dev server
uv run ruff check . && uv run ruff format --check .
uv run mypy                                 # strict
uv run pytest

# Frontend (pnpm only)
cd frontend
pnpm install
pnpm run build                              # -> dist/pineapple-frontend/browser/
pnpm start                                  # ng serve on http://localhost:4200
pnpm test                                   # vitest
pnpm exec prettier --check "src/**/*.{ts,html,scss}"
```

Typical dev loop: `pnpm start` in `frontend/`, then `uv run pineapple-gui --dev` in `backend/`.

## UI / design system

Target: **Material Design 3**, restrained and functional. Explicitly **not** the
"generic AI" aesthetic. Every screen must look deliberately designed for *this*
tool — never the default "AI assistant" look (centered hero text, gradient
buttons, emoji, purple, glassmorphism).

- **Dark theme**, a muted yellow as an **accent only** (`mat.$yellow-palette` as
  `primary`, a nod to the pineapple): active tab indicator, focus rings, later the
  primary button. Never large yellow fills or yellow gradients.
- Surfaces from `styles.scss` tokens: `--app-bg: #121212`, `--app-surface: #1e1e1e`.
  Not pure black. Depth comes from Material elevation, not custom shadows or glow.
- Typeface: **Roboto**, self-hosted via `@fontsource/roboto` (weights 400/500).
  No Google Fonts / CDN links — the app must work offline.
- Material 8dp spacing grid and the standard Material type scale
  (`var(--mat-sys-*)`).
- **Forbidden**: gradients, glassmorphism / blur panels, neon glow, emoji, purple,
  decorative hero art, marketing-style layouts.
- Illustrations are clean monochrome line-art of the real object (see the iPhone
  SVG in `device/phone-outline/phone-outline.html`) — no photos, no 3D, no glow.

## `backend/src/pineapple` notes

- `devices.py`: `pymobiledevice3` v11 is **async**, and so is this module — no
  sync wrappers here. `connected_devices()` talks only to the local usbmuxd
  daemon (no device contact — safe to poll) and returns `[]` when it is
  unavailable; `get_device_info()` opens a lockdown connection (device must be
  paired — "Trust this computer") and raises when the device is unpaired or
  unreachable.
- `api.py`: the sync/async boundary, called on a pywebview worker thread. Short
  calls use `asyncio.run()` over `devices`; long-lived work (syslog) goes through
  `session` instead. `connected_device()` applies the single-device policy:
  `{"status": "none" | "one" | "multiple"}` (several devices are never
  auto-picked — wrong-device risk). `get_device_info()` wraps the result in an
  `{"ok": True, "info": ...}` / `{"ok": False, "error": ...}` envelope so the
  frontend can tell "needs trust" from "ready". `start_syslog` / `read_syslog` /
  `stop_syslog` drive one `SyslogStream`; `save_syslog` writes captured text via
  a native save dialog. `backup_preflight` / `choose_backup_path` (native save
  dialog) / `start_backup` / `read_backup_progress` / `cancel_backup` drive one
  `DeviceBackup`.
- `session.py`: one `asyncio` loop on a daemon thread, shared by streaming
  features. `run(coro)` blocks for a result; `spawn(coro)` / `cancel(task)`
  manage a background task from another thread. Deliberately minimal — it is the
  shared connector, not a service registry.
- `syslog.py`: `SyslogStream.start()` resolves the single device and spawns an
  `OsTraceService.syslog()` reader on `session`; entries land in a
  `deque(maxlen=5000)` under a lock. `read()` drains it and reports
  `running` / `dropped` / `error` (unpaired or mid-stream disconnect). Same
  "Trust this computer" requirement as `get_device_info`. `start`/`stop` hold an
  op lock and `stop` blocks until the reader has closed its connections
  (`async with OsTraceService`) — leaking that socket makes the device refuse
  the next stream, so reopening the viewer would silently fail.
- `backup.py`: `DeviceBackup.start()` spawns a full `Mobilebackup2Service.backup`
  on `session` into a temp staging dir, then packs `staging/<udid>/` into the
  chosen path as an **uncompressed** (`ZIP_STORED`) zip named `*.pineapple`.
  Encryption is a *device* setting: for an encrypted backup on a device that does
  not already encrypt, it calls `change_password(new=…)` first and always
  restores the original state (`change_password(old=…)`) afterwards — on success,
  failure and cancel alike (shielded so a cancel still runs it). Each device
  operation (enable / backup / restore) opens its **own** `Mobilebackup2Service`
  context: the `com.apple.mobilebackup2` session is single-use (one DeviceLink
  operation, then `DLMessageDisconnect`), so reusing one instance runs the
  second operation on a dead session. `progress()` reports `phase` (`preparing` /
  `backing_up` / `packaging` / `restoring_encryption` / `done` / `error` /
  `cancelled`), `percent`, `note`, `output_path`. Same "Trust this computer"
  requirement as `get_device_info`.
- `analysis/`: offline analysis of a saved `.pineapple` image (no device needed).
  `archive.peek()` reads the three root plists straight from the zip (never
  encrypted) for the device facts shown before parsing; `archive.extract()`
  unpacks the whole archive as-is (encrypted blobs stay encrypted on disk).
  `reader.open_reader()` returns a `PlainBackupReader` or, when `Manifest.plist`
  says `IsEncrypted`, an `EncryptedBackupReader` wrapping
  `iphone_backup_decrypt.EncryptedBackup` — a wrong password raises `AnalysisError`.
  `runner.AnalysisRun` mirrors `DeviceBackup`: it runs on `session`, the pipeline
  is a worker thread checking a cancellation `Event` between phases (`extracting`
  / `opening` / `indexing` / `parsing` / `writing_descriptor` / `done` / `error`
  / `cancelled`), and on cancel or failure it rolls back the partial
  `analysis.db` and `<title>.json`. Only `Manifest.db` and the source DBs the
  parsers need are decrypted (into `<case>/decrypted/`) — no bulk file
  extraction yet. One analysis per case folder: `<title>.json` (the descriptor
  the frontend lists / reopens; `<title>` defaults to the device serial),
  `backup/<udid>/`, `decrypted/`, `analysis.db`. `case.load_case()` reopens a
  folder and answers paginated read queries. Parsers (`messages` = `sms.db`,
  `calls` = `CallHistory.storedata`, `contacts` = `AddressBook.sqlitedb`) are
  tolerant: a missing or damaged source DB is recorded as skipped, not fatal.
  All timestamps are stored as ISO-8601 UTC.
- `api.py` analysis bridge: `choose_pineapple_file` / `choose_case_folder`
  (native dialogs), `analysis_peek`, `start_analysis` / `read_analysis_progress`
  / `cancel_analysis` drive one `AnalysisRun` (and load the case on `done`),
  `open_case` loads an existing folder, and `analysis_summary` / `analysis_apps`
  / `analysis_domains` / `analysis_files` / `analysis_messages` / `analysis_calls`
  / `analysis_contacts` answer from the open `CaseHandle` in an
  `{"ok": …, "result": …}` envelope.
- `app.py`: resolves `FRONTEND_DIST` relative to the repo root; `--dev` loads
  `http://localhost:4200`, otherwise serves the production build with pywebview's
  built-in HTTP server. Exits with a clear message if the build is missing.
- frontend `DeviceService`: polls `window.pywebview.api.connected_device()` every
  2s, fetches full info once per device (retrying while `unpaired`), exposes a
  `DeviceState` signal. Idle no-op when `window.pywebview` is absent (plain
  browser).
- frontend `SyslogService`: while the `SyslogDialog` is open, polls
  `read_syslog()` every 400ms into a `lines` signal (capped, drop-oldest);
  stops when the backend reports the stream ended. `SyslogDialog` adds
  text/process filters, pause, clear and export over a `cdk-virtual-scroll`
  list. Same idle no-op without the bridge.
- frontend `BackupService` / `BackupDialog`: the dialog steps confirm → options
  (encrypted / unencrypted, or the existing password when the device already
  encrypts) → native path picker → progress. `BackupService` polls
  `read_backup_progress()` every 500ms into a `progress` signal until the run
  stops. While a phase in `RUNNING_PHASES` is active the dialog is `disableClose`
  — only the explicit Cancel button stops the acquisition.
- frontend `AnalysisService` / `AnalysisDialog` / Analysis tab: the dialog steps
  pick (native `.pineapple` picker → `analysis_peek`) → configure (device facts,
  a name prefilled with the serial, a password field only when encrypted) →
  native folder picker → progress (`disableClose` while running). `AnalysisService`
  polls `read_analysis_progress()` every 500ms and, on `done`, calls `open_case`
  so the tab flips to the browser; `summary()` non-null is what the `Analysis`
  component switches on (launcher vs browser). The browser is a nav-rail
  (`Overview`, `Apps`, `Files`, `Messages`, `Calls`, `Contacts`). `ArtifactTable`
  is a generic `mat-table` + `mat-paginator` that owns its fetch loop; the
  service's query wrappers unwrap the `{ok, result}` envelope and throw on
  `{ok:false}`. Re-opening a case is manual (the launcher's "Open existing
  analysis"); nothing is persisted locally. Idle no-op without the bridge.

## Git workflow

- Work happens on the **`development`** branch. `main` holds the baseline.
- Commit every logical step. Commit messages in English.
- Push / open PRs only when the user asks.

## Conventions

- Type hints on public functions; short docstrings.
- Code is written to be read by humans first: clear names, small functions, the
  simplest approach that works. No premature abstraction, no cleverness that
  needs a comment to survive.
- Every new function with non-trivial behaviour ships with its test in the same
  change — backend in `backend/tests/` (`uv run pytest`), frontend in a
  `*.spec.ts` (`pnpm test`). Pure glue and one-liners are exempt.
- `ruff`, `mypy` (strict) and the test suites must stay green; CI enforces this.
- Backend deps: `uv add` (dev tools via `uv add --dev`; keep `backend/uv.lock` committed).
- Frontend deps: `pnpm add` (keep `frontend/pnpm-lock.yaml` committed; no `package-lock.json`).
