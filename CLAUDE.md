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
| `backend/src/pineapple/main.py` | USB device detection / info helpers (`detect_devices`, `get_device_info`). |
| `backend/src/pineapple/app.py` | pywebview host window (no device logic, no JS↔Python bridge yet). |
| `frontend/src/app/app.*` | Shell: `mat-tab-group` with the **Device** and **Analysis** tabs. |
| `frontend/src/app/device/` | Device tab: centered iPhone SVG + "Connect a device to get started". |
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
  SVG in `device/device.html`) — no photos, no 3D, no glow.

## `backend/src/pineapple` notes

- `main.py`: `pymobiledevice3` v11 is **async**; the public helpers are
  **synchronous** wrappers around private coroutines (`_detect_devices`,
  `_get_device_info`). `detect_devices()` returns `[]` when usbmuxd is
  unavailable and an `Error` entry for unreachable devices. Full info needs the
  device paired ("Trust this computer"). Always close lockdown connections.
- `app.py`: resolves `FRONTEND_DIST` relative to the repo root; `--dev` loads
  `http://localhost:4200`, otherwise serves the production build with pywebview's
  built-in HTTP server. Exits with a clear message if the build is missing.

## Git workflow

- Work happens on the **`Dev`** branch. `main` holds the baseline.
- Commit every logical step. Commit messages in English.
- Push / open PRs only when the user asks.

## Conventions

- Type hints on public functions; short docstrings.
- Keep code simple and readable — no premature abstraction.
- Backend deps: `uv add` (keep `backend/uv.lock` committed).
- Frontend deps: `pnpm add` (keep `frontend/pnpm-lock.yaml` committed; no `package-lock.json`).
