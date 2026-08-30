# Pineapple

An iOS forensic analysis tool. A desktop application that inspects Apple
devices over USB and analyses their backups offline.

## What it does

- **Device** — detects a connected iPhone/iPad (usbmuxd only, safe to poll),
  shows its lockdown info once "Trust this computer" is granted, and streams
  the live system log (`com.apple.os_trace_relay`).
- **Logical acquisition** — a full MobileBackup2 backup packaged as a single
  uncompressed `.pineapple` archive, encrypted or not (encryption is a device
  setting, enabled for the run and restored afterwards).
- **Analysis** — opens a `.pineapple` image with no device attached, decrypts
  what it needs, and parses it into a per-case SQLite database: the file
  index, installed apps, messages (with iOS 16+ `attributedBody` recovery),
  calls, contacts, notes, Safari history/bookmarks and WhatsApp. Individual
  backup files can be previewed and extracted.

## Structure

| Folder | Stack |
| --- | --- |
| `backend/` | Python `>=3.14` (`uv`). `pymobiledevice3` for device access, `pywebview` for the window, `iphone_backup_decrypt` for encrypted backups, `pytypedstream` for iMessage bodies. |
| `frontend/` | Angular + Angular Material, light theme, zoneless. Package manager: **`pnpm`** (never `npm`/`yarn`). Rendered inside the pywebview window. |

## Docs

- [`ARCHITECTURE.md`](ARCHITECTURE.md) — how everything works and why: the
  process model, the device read flow, backup creation, the analysis
  pipeline, the case-folder format, and how each third-party library is used.
- [`UI.md`](UI.md) — the UI design system (Material Design 3, light-only,
  goldenrod-amber accent, the component patterns).
- [`CLAUDE.md`](CLAUDE.md) — repository conventions.

## Requirements

- Python `>=3.14` and [`uv`](https://docs.astral.sh/uv/)
- Node.js and [`pnpm`](https://pnpm.io/) (never `npm`)

## Setup

```bash
cd backend && uv sync
cd frontend && pnpm install
```

## Run

```bash
# Build the UI once, then open the desktop window (serves the production build)
cd frontend && pnpm run build
cd backend && uv run pineapple-gui
```

Development loop with hot reload:

```bash
cd frontend && pnpm start                 # terminal 1: ng serve on :4200
cd backend && uv run pineapple-gui --dev   # terminal 2: window against the dev server
```

`uv run pineapple` prints the connected devices and their info without opening
the window.

## Checks

```bash
cd backend  && uv run ruff check . && uv run ruff format --check . && uv run mypy && uv run pytest
cd frontend && pnpm lint && pnpm exec prettier --check "src/**/*.{ts,html,scss}" && pnpm test && pnpm build
```

## Development

Work happens on the `development` branch; `main` holds the baseline. CI runs
both check suites on every push and PR.
