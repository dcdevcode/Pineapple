# CLAUDE.md

Guidance for Claude Code when working in this repository.

## Language policy

**All code and documentation must be written in English** — comments, variable and
function names, docstrings, commit messages, and every `.md` file. This is a hard
requirement. Conversation with the user happens in Spanish, but nothing that lands
in the repo is in Spanish.

## Project overview

`pineapple` is a Python project for talking to Apple devices (iPhone/iPad) over USB
using [`pymobiledevice3`](https://github.com/doronz88/pymobiledevice3).

- Package source: `src/pineapple/`
- Python: `>=3.14` (see `.python-version`)
- Dependency management / build: [`uv`](https://docs.astral.sh/uv/) with the
  `uv_build` backend (`pyproject.toml`, `uv.lock`).
- Single runtime dependency: `pymobiledevice3>=11.2.1`.

## Layout

| Path | Purpose |
| --- | --- |
| `src/pineapple/__init__.py` | Package init; defines the `pineapple` console-script entry point (`main`). |
| `src/pineapple/main.py` | Device detection and info helpers (`detect_devices`, `get_device_info`, `main`). |

## Common commands

```bash
# Install / sync the environment
uv sync

# Run the device script directly
.venv/bin/python src/pineapple/main.py

# Syntax check
.venv/bin/python -m py_compile src/pineapple/main.py

# Reference CLI from pymobiledevice3 (useful to cross-check output)
.venv/bin/python -m pymobiledevice3 usbmux list --usb
.venv/bin/python -m pymobiledevice3 lockdown info
```

## `src/pineapple/main.py` notes

- `pymobiledevice3` v11 exposes an **async** API. The public helpers here are
  **synchronous** wrappers that call `asyncio.run()` over private coroutines
  (`_detect_devices`, `_get_device_info`).
- `detect_devices()` lists usbmuxd devices, keeps the USB ones, and connects to
  lockdownd with `autopair=False` to read `lockdown.short_info`. It returns `[]`
  when usbmuxd is unavailable and adds an `Error` entry for a device that cannot
  be reached (e.g. not paired / trust not granted).
- `get_device_info()` accepts a UDID string or a dict from `detect_devices()` and
  returns a curated dict built from `lockdown.all_values` using
  `DEVICE_INFO_FIELDS`.
- Always close lockdown connections (`await lockdown.close()` in a `try/finally`).
- Full device info requires the device to be paired ("Trust this computer").

## Conventions

- Type hints on public functions; short docstrings.
- Keep code simple and readable — no premature abstraction.
- Only add dependencies through `uv add`; keep `uv.lock` committed.
