# pineapple (backend)

Python backend for the Pineapple iOS forensic analysis tool.

- `pineapple.devices` - async USB device access (`connected_devices`, `get_device_info`).
- `pineapple.api` - `Api`, the sync bridge exposed to the frontend as `window.pywebview.api`.
- `pineapple.app` - pywebview host window for the desktop UI.
- `pineapple.cli` - the `pineapple` console script.

## Setup

```bash
uv sync
```

## Run

```bash
# Print the connected devices and their info
uv run pineapple

# Desktop window (serves the production frontend build)
uv run pineapple-gui

# Desktop window against the Angular dev server (run `pnpm start` in ../frontend first)
uv run pineapple-gui --dev
```
