# Pineapple

An iOS forensic analysis tool. Desktop application that inspects Apple devices
connected over USB.

Early stage — currently the UI shell only, no analysis functionality yet.

## Structure

| Folder | Stack |
| --- | --- |
| `backend/` | Python (`uv`), `pymobiledevice3` for device access, `pywebview` for the window. |
| `frontend/` | Angular + Angular Material, dark theme. Package manager: **`pnpm`**. |

## Requirements

- Python `>=3.14` and [`uv`](https://docs.astral.sh/uv/)
- Node.js and [`pnpm`](https://pnpm.io/) (never `npm`)

## Setup

```bash
# Backend
cd backend && uv sync

# Frontend
cd frontend && pnpm install
```

## Run

```bash
# Build the UI once
cd frontend && pnpm run build

# Open the desktop window (serves the production build)
cd backend && uv run pineapple-gui
```

Development loop with hot reload:

```bash
cd frontend && pnpm start                 # terminal 1: ng serve on :4200
cd backend && uv run pineapple-gui --dev   # terminal 2: window against the dev server
```

## Development

Work happens on the `development` branch. See `CLAUDE.md` for the design system and conventions.
