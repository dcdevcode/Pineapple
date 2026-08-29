"""Tests for :mod:`pineapple.app` argument parsing and URL resolution."""

from pathlib import Path

import pytest

from pineapple import app


def test_parse_args_reads_the_dev_flag() -> None:
    assert app._parse_args(["--dev"]).dev is True
    assert app._parse_args([]).dev is False


def test_resolve_url_dev_uses_the_dev_server() -> None:
    assert app._resolve_url(dev=True) == app.DEV_URL


def test_resolve_url_exits_when_the_build_is_missing(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(app, "FRONTEND_DIST", tmp_path / "missing")

    with pytest.raises(SystemExit, match="Frontend build not found"):
        app._resolve_url(dev=False)


def test_resolve_url_returns_the_index_when_the_build_exists(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    (tmp_path / "index.html").write_text("<html></html>", encoding="utf-8")
    monkeypatch.setattr(app, "FRONTEND_DIST", tmp_path)

    assert app._resolve_url(dev=False) == str(tmp_path / "index.html")
