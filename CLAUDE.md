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
  Ask when something is unclear.
- **Backend** (`backend/`): Python, [`uv`](https://docs.astral.sh/uv/) +
  `uv_build`, Python `>=3.14`. Device access via
  [`pymobiledevice3`](https://github.com/doronz88/pymobiledevice3); desktop window
  via [`pywebview`](https://pywebview.flowrl.com/).
- **Frontend** (`frontend/`): Angular + Angular Material, **`pnpm` only**
  (never `npm`/`yarn`). Rendered inside the pywebview window.

## Layout

| Path | Purpose |
| --- | --- |
| `backend/pyproject.toml` | uv project: deps, `pineapple` and `pineapple-gui` entry points. |
| `backend/src/pineapple/devices.py` | Async USB device access (`connected_devices`, `single_device_udid`, `get_device_info`, `INFO_FIELDS`). |
| `backend/src/pineapple/session.py` | `DeviceSession`: one background asyncio loop for long-lived device work. Module singleton `session`. |
| `backend/src/pineapple/syslog.py` | `SyslogStream`: live `com.apple.os_trace_relay` stream into a bounded buffer the frontend drains. |
| `backend/src/pineapple/api.py` | `Api`: the sync bridge over `devices` / `syslog`, bound to `window.pywebview.api`. |
| `backend/src/pineapple/cli.py` | `pineapple` console script: print the connected devices and their info. |
| `backend/src/pineapple/app.py` | pywebview host window; wires `js_api=Api()`. No device logic of its own. |
| `frontend/src/app/app.*` | Shell: `mat-tab-group` with the **Device** and **Analysis** tabs; starts device polling. |
| `frontend/src/app/device/` | Device tab: `DeviceService` (polls the bridge) + the empty / connected views. `phone-outline/` holds the iPhone SVG. |
| `frontend/src/app/syslog/` | Syslog viewer: `SyslogService` (polls the bridge) + `SyslogDialog`, the live-log modal opened from the Device tab. |
| `frontend/src/app/analysis/` | Analysis tab: intentionally empty for now. |
| `frontend/src/styles.scss` | Global Angular Material theme (dark, yellow accent — a nod to the pineapple). |

## Common commands

```bash
# Backend
cd backend
uv sync
uv run pineapple                           # print connected devices + info
uv run pineapple-gui                        # desktop window, serves frontend/dist
uv run pineapple-gui --dev                  # desktop window against the Angular dev server

# Frontend (pnpm only)
cd frontend
pnpm install
pnpm run build                              # -> dist/pineapple-frontend/browser/
pnpm start                                  # ng serve on http://localhost:4200
pnpm test                                   # vitest
```

Typical dev loop: `pnpm start` in `frontend/`, then `uv run pineapple-gui --dev` in `backend/`.

## UI / design system

Target: **Material Design 3**, restrained and functional. Explicitly **not** the
"generic AI" aesthetic.

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
  a native save dialog.
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

## Git workflow

- Work happens on the **`development`** branch. `main` holds the baseline.
- Commit every logical step. Commit messages in English.
- Push / open PRs only when the user asks.

## Conventions

- Type hints on public functions; short docstrings.
- Keep code simple and readable — no premature abstraction.
- Backend deps: `uv add` (keep `backend/uv.lock` committed).
- Frontend deps: `pnpm add` (keep `frontend/pnpm-lock.yaml` committed; no `package-lock.json`).
