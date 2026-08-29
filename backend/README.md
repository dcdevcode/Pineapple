# pineapple (backend)

Python backend for the Pineapple iOS forensic analysis tool.

- `pineapple.main` - USB device detection and lockdown info (`detect_devices`, `get_device_info`).
- `pineapple.app` - pywebview host window for the desktop UI.

## Setup

```bash
uv sync
```

## Run

```bash
# Device detection helpers
uv run python src/pineapple/main.py

# Desktop window (serves the production frontend build)
uv run pineapple-gui

# Desktop window against the Angular dev server (run `npm start` in ../frontend first)
uv run pineapple-gui --dev
```
