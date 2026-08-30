"""The ``<title>.json`` case descriptor: read, write, locate.

It is the human- and frontend-facing record of a case -- the device it came
from, the source archive, and how the parse went -- and the source of truth for
reopening a case folder.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any

from pineapple.analysis.errors import AnalysisError
from pineapple.analysis.schema import SCHEMA_VERSION

_UNSAFE_NAME_CHARS = set('/\\:*?"<>|')


def tool_version() -> str:
    try:
        return version("pineapple")
    except PackageNotFoundError:
        return "0.0.0"


def safe_filename(title: str) -> str:
    """A file-name-safe form of a case title (never a path, just a leaf name)."""
    cleaned = "".join(
        "_" if char in _UNSAFE_NAME_CHARS else char for char in title
    ).strip()
    return cleaned or "analysis"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


@dataclass
class CaseDescriptor:
    title: str
    device: dict[str, Any]
    source: dict[str, Any]
    parse: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    tool_version: str = field(default_factory=tool_version)
    schema_version: int = SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CaseDescriptor:
        try:
            return cls(
                title=data["title"],
                device=data.get("device", {}),
                source=data.get("source", {}),
                parse=data.get("parse", {}),
                created_at=data.get("created_at", ""),
                tool_version=data.get("tool_version", ""),
                schema_version=int(data.get("schema_version", 0)),
            )
        except KeyError as error:
            raise AnalysisError(f"Case descriptor is missing {error}.") from error


def descriptor_path(case_dir: Path, title: str) -> Path:
    return case_dir / f"{safe_filename(title)}.json"


def find_descriptor(case_dir: Path) -> Path | None:
    """The single ``*.json`` descriptor in ``case_dir``; ``None`` when there is none."""
    candidates = sorted(case_dir.glob("*.json"))
    if not candidates:
        return None
    if len(candidates) > 1:
        raise AnalysisError(
            f"{case_dir} holds more than one .json descriptor; "
            "expected one case per folder."
        )
    return candidates[0]


def write_descriptor(path: Path, descriptor: CaseDescriptor) -> None:
    path.write_text(
        json.dumps(descriptor.to_dict(), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def read_descriptor(path: Path) -> CaseDescriptor:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise AnalysisError(
            f"Cannot read case descriptor {path.name} ({error})."
        ) from error
    if not isinstance(data, dict):
        raise AnalysisError(f"Case descriptor {path.name} has an unexpected shape.")
    return CaseDescriptor.from_dict(data)
