"""pywebview host window for the Pineapple desktop UI.

Opens the window, points it at the Angular frontend, and exposes the
:class:`~pineapple.api.Api` bridge as ``window.pywebview.api``.
"""

import argparse
import sys
from pathlib import Path

import webview

from pineapple.api import Api

# Repo layout: <repo>/backend/src/pineapple/app.py -> parents[3] == <repo>
REPO_ROOT = Path(__file__).resolve().parents[3]
FRONTEND_DIST = REPO_ROOT / "frontend" / "dist" / "pineapple-frontend" / "browser"
DEV_URL = "http://localhost:4200"

WINDOW_TITLE = "Pineapple"
WINDOW_BACKGROUND = "#121212"


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="pineapple-gui",
        description="Open the Pineapple desktop window.",
    )
    parser.add_argument(
        "--dev",
        action="store_true",
        help=f"Load the Angular dev server ({DEV_URL}) instead of the build.",
    )
    return parser.parse_args(argv)


def _resolve_url(dev: bool) -> str:
    if dev:
        return DEV_URL

    index = FRONTEND_DIST / "index.html"
    if not index.is_file():
        sys.exit(
            f"Frontend build not found at {index}\n"
            "Run `pnpm install && pnpm run build` in the frontend/ directory "
            "first, or start `pnpm start` there and launch with `--dev`."
        )
    return str(index)


def run(argv: list[str] | None = None) -> None:
    args = _parse_args(argv)
    url = _resolve_url(args.dev)

    webview.create_window(
        WINDOW_TITLE,
        url,
        js_api=Api(),
        width=1024,
        height=720,
        min_size=(900, 600),
        background_color=WINDOW_BACKGROUND,
    )
    webview.start(http_server=not args.dev)


if __name__ == "__main__":
    run()
