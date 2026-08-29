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
| `backend/src/pineapple/main.py` | USB device helpers (`list_devices`, `detect_devices`, `get_device_info`). |
| `backend/src/pineapple/api.py` | `Api` class exposed to the frontend as `window.pywebview.api`. |
| `backend/src/pineapple/app.py` | pywebview host window; wires `js_api=Api()`. No device logic of its own. |
| `frontend/src/app/app.*` | Shell: `mat-tab-group` with the **Device** and **Analysis** tabs; starts device polling. |
| `frontend/src/app/device/` | Device tab: `DeviceService` (polls the bridge) + the empty / connected views. `phone-outline/` holds the iPhone SVG. |
| `frontend/src/app/analysis/` | Analysis tab: intentionally empty for now. |
| `frontend/src/styles.scss` | Global Angular Material theme (dark, red accent). |

## Common commands

```bash
# Backend
cd backend
uv sync
uv run python src/pineapple/main.py        # device detection helpers
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

- **Dark theme**, red as an **accent only** (`mat.$red-palette` as `primary`):
  active tab indicator, focus rings, later the primary button. Never large red
  fills or red gradients.
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

- `main.py`: `pymobiledevice3` v11 is **async**; the public helpers are
  **synchronous** wrappers around private coroutines (`_list_devices`,
  `_detect_devices`, `_get_device_info`). `list_devices()` talks only to the
  local usbmuxd daemon (no device contact — safe to poll); `detect_devices()`
  and `get_device_info()` open a lockdown connection. All return `[]` / raise
  when usbmuxd is unavailable. Full info needs the device paired ("Trust this
  computer"). Always close lockdown connections.
- `api.py`: `Api.get_device_info()` wraps `main.get_device_info()` in an
  `{"ok": True, "info": ...}` / `{"ok": False, "error": ...}` envelope so the
  frontend can tell "needs trust" from "ready". `Api.list_devices()` passes
  through. Each method runs on a pywebview worker thread.
- `app.py`: resolves `FRONTEND_DIST` relative to the repo root; `--dev` loads
  `http://localhost:4200`, otherwise serves the production build with pywebview's
  built-in HTTP server. Exits with a clear message if the build is missing.
- frontend `DeviceService`: polls `window.pywebview.api.list_devices()` every 2s,
  fetches full info once per device (retrying while `unpaired`), exposes a
  `DeviceState` signal. Idle no-op when `window.pywebview` is absent (plain
  browser).

## Git workflow

- Work happens on the **`Dev`** branch. `main` holds the baseline.
- Commit every logical step. Commit messages in English.
- Push / open PRs only when the user asks.

## Conventions

- Type hints on public functions; short docstrings.
- Keep code simple and readable — no premature abstraction.
- Backend deps: `uv add` (keep `backend/uv.lock` committed).
- Frontend deps: `pnpm add` (keep `frontend/pnpm-lock.yaml` committed; no `package-lock.json`).
