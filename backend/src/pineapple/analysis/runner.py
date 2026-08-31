"""``AnalysisRun``: parse one ``.pineapple`` image into a case folder.

Long-lived, CPU- and IO-heavy work (unzip, PBKDF2 key derivation, SQLite
parsing), so -- like :class:`pineapple.backup.DeviceBackup` -- it runs as a task
on :data:`pineapple.session.session` while the frontend polls :meth:`progress`.
The actual pipeline runs in a worker thread and checks a cancellation event
between phases; on cancel or failure it rolls back the partial ``analysis.db``
and descriptor.
"""

from __future__ import annotations

import asyncio
import contextlib
import sqlite3
import threading
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

from pineapple.analysis import archive
from pineapple.analysis.archive import ArchiveCancelled
from pineapple.analysis.case import ANALYSIS_DB
from pineapple.analysis.descriptor import (
    CaseDescriptor,
    descriptor_path,
    find_descriptor,
    sha256_file,
    write_descriptor,
)
from pineapple.analysis.errors import AnalysisError, ArtifactUnreadable
from pineapple.analysis.metadata import BackupMetadata
from pineapple.analysis.parsers import (
    ARTIFACT_PARSERS,
    ParseFn,
    ReaderParseFn,
    index_apps,
    index_backup_info,
    index_files,
)
from pineapple.analysis.reader import BackupReader, open_reader
from pineapple.analysis.schema import initialize
from pineapple.session import DeviceSession

TEARDOWN_TIMEOUT = 10.0

# Percent at the end of each phase; parsers share the span up to PARSING_END.
_EXTRACT_END = 40.0
_OPEN_END = 55.0
_INDEX_END = 70.0
_PARSING_END = 95.0


class _Cancelled(Exception):
    """Raised inside the pipeline thread when cancellation is requested."""


@dataclass
class _Progress:
    phase: str = "idle"
    percent: float = 0.0
    note: str | None = None
    error: str | None = None
    title: str | None = None
    case_path: str | None = None
    counts: dict[str, int] = field(default_factory=dict)
    skipped: list[str] = field(default_factory=list)
    running: bool = False


@dataclass(frozen=True)
class _Params:
    pineapple_path: Path
    case_dir: Path
    title: str
    password: str
    metadata: BackupMetadata


class AnalysisRun:
    """One parse: :meth:`start` it, poll :meth:`progress`, optionally :meth:`cancel`."""

    def __init__(self, session: DeviceSession) -> None:
        self._session = session
        self._op_lock = threading.Lock()
        self._state_lock = threading.Lock()
        self._state = _Progress()
        self._task: asyncio.Task[Any] | None = None
        self._cancelled = threading.Event()

    @property
    def running(self) -> bool:
        return self._task is not None and not self._task.done()

    def start(
        self, pineapple_path: str, case_dir: str, title: str, password: str
    ) -> None:
        """Begin parsing ``pineapple_path`` into ``case_dir``.

        ``title`` empty ⇒ the device serial. Raises :class:`AnalysisError` when
        the archive is unreadable or the folder already holds an analysis.
        """
        with self._op_lock:
            self._teardown()
            case = Path(case_dir)
            case.mkdir(parents=True, exist_ok=True)
            if (case / ANALYSIS_DB).exists() or find_descriptor(case) is not None:
                raise AnalysisError(
                    "This folder already holds an analysis; open it instead."
                )
            metadata = archive.peek(pineapple_path)
            resolved = title.strip() or metadata.default_title
            params = _Params(Path(pineapple_path), case, resolved, password, metadata)
            self._cancelled = threading.Event()
            with self._state_lock:
                self._state = _Progress(
                    phase="extracting",
                    title=resolved,
                    case_path=str(case),
                    running=True,
                )
            self._task = self._session.spawn(self._run(params))

    def progress(self) -> dict[str, Any]:
        with self._state_lock:
            snapshot = asdict(self._state)
        snapshot["running"] = self.running and snapshot["running"]
        return snapshot

    def cancel(self) -> None:
        with self._op_lock:
            self._teardown()

    def _teardown(self) -> None:
        task, self._task = self._task, None
        if task is None:
            return
        self._cancelled.set()
        self._session.cancel(task)
        self._session.drain(task, TEARDOWN_TIMEOUT)

    # -- internals ------------------------------------------------------

    def _set(self, **fields: Any) -> None:
        with self._state_lock:
            for name, value in fields.items():
                setattr(self._state, name, value)

    async def _run(self, params: _Params) -> None:
        loop = asyncio.get_running_loop()
        future = loop.run_in_executor(None, self._pipeline, params)
        try:
            await asyncio.shield(future)
        except asyncio.CancelledError:
            # Let the worker thread notice the event and roll back before we go.
            # Any exception it raises during that unwind is deliberately dropped
            # here -- `_pipeline` has already recorded the outcome and cleaned
            # up the partial case.
            self._cancelled.set()
            with contextlib.suppress(Exception):
                await future
            raise

    def _check(self) -> None:
        if self._cancelled.is_set():
            raise _Cancelled

    def _pipeline(self, params: _Params) -> None:
        reader = None
        conn: sqlite3.Connection | None = None
        try:
            backup_root = self._extract(params)
            reader = self._open(params, backup_root)

            conn = sqlite3.connect(str(params.case_dir / ANALYSIS_DB))
            initialize(conn)

            counts, skipped = self._index(params, reader, conn)
            self._run_parsers(params, reader, conn, counts, skipped)

            self._check()
            self._set(phase="writing_descriptor", note="Writing the case descriptor.")
            self._write_descriptor(params, conn, counts, skipped)
            conn.commit()

            self._set(
                phase="done",
                percent=100.0,
                note=None,
                error=None,
                counts=dict(counts),
                skipped=list(skipped),
                running=False,
            )
        except _Cancelled, ArchiveCancelled:
            self._cleanup_partial(params)
            self._set(phase="cancelled", note=None, running=False)
        except AnalysisError as error:
            self._cleanup_partial(params)
            self._set(phase="error", error=str(error), note=None, running=False)
        except Exception as error:  # surfaced to the UI, never silently swallowed
            self._cleanup_partial(params)
            self._set(
                phase="error",
                error=f"{type(error).__name__}: {error}",
                note=None,
                running=False,
            )
        finally:
            if reader is not None:
                reader.close()
            if conn is not None:
                conn.close()

    def _extract(self, params: _Params) -> Path:
        self._check()
        self._set(phase="extracting", note="Unpacking the archive.")
        root = archive.extract(
            params.pineapple_path, params.case_dir / "backup", self._cancelled
        )
        self._set(percent=_EXTRACT_END)
        return root

    def _open(self, params: _Params, backup_root: Path) -> BackupReader:
        self._check()
        self._set(
            phase="opening",
            note=(
                "Deriving the decryption key."
                if params.metadata.is_encrypted
                else "Opening the backup."
            ),
        )
        reader = open_reader(
            backup_root,
            params.metadata,
            params.password,
            params.case_dir / "decrypted",
        )
        self._set(percent=_OPEN_END)
        return reader

    def _index(
        self, params: _Params, reader: BackupReader, conn: sqlite3.Connection
    ) -> tuple[dict[str, int], list[str]]:
        self._check()
        self._set(phase="indexing", note="Indexing device info and files.")
        index_backup_info(params.metadata, conn)
        apps = index_apps(params.metadata, conn)
        files = index_files(reader.manifest_connection(), conn)
        conn.commit()
        counts = {"apps": apps, "files": files}
        self._set(percent=_INDEX_END, counts=dict(counts))
        return counts, []

    def _run_parsers(
        self,
        params: _Params,
        reader: BackupReader,
        conn: sqlite3.Connection,
        counts: dict[str, int],
        skipped: list[str],
    ) -> None:
        self._set(phase="parsing")
        span = _PARSING_END - _INDEX_END
        for index, spec in enumerate(ARTIFACT_PARSERS):
            self._check()
            self._set(
                note=f"Parsing {spec.name}.",
                percent=_INDEX_END + span * index / len(ARTIFACT_PARSERS),
            )
            source = reader.extract_db(
                spec.relative_path, spec.domain, params.case_dir / "decrypted"
            )
            if source is None:
                if spec.encrypted_only and not params.metadata.is_encrypted:
                    skipped.append(
                        f"{spec.name}: not in this backup — only included when the "
                        "backup is encrypted"
                    )
                else:
                    skipped.append(f"{spec.name}: not present in the backup")
                continue
            try:
                if spec.needs_reader:
                    parse_with_reader = cast(ReaderParseFn, spec.parse)
                    counts[spec.counts_as] = parse_with_reader(source, conn, reader)
                else:
                    parse = cast(ParseFn, spec.parse)
                    counts[spec.counts_as] = parse(source, conn)
                conn.commit()
            except ArtifactUnreadable as error:
                skipped.append(str(error))
            self._set(counts=dict(counts), skipped=list(skipped))
        self._set(percent=_PARSING_END)

    def _write_descriptor(
        self,
        params: _Params,
        conn: sqlite3.Connection,
        counts: dict[str, int],
        skipped: list[str],
    ) -> None:
        source = {
            "path": str(params.pineapple_path),
            "sha256": sha256_file(params.pineapple_path),
            "is_encrypted": params.metadata.is_encrypted,
        }
        parse = {
            "status": "done",
            "finished_at": datetime.now(UTC).isoformat(),
            "counts": dict(counts),
            "skipped": list(skipped),
        }
        descriptor = CaseDescriptor(
            title=params.title,
            device=params.metadata.device_dict(),
            source=source,
            parse=parse,
        )
        write_descriptor(descriptor_path(params.case_dir, params.title), descriptor)
        conn.executemany(
            "INSERT OR REPLACE INTO case_meta(key, value) VALUES (?, ?)",
            [
                ("title", params.title),
                ("source_path", source["path"]),
                ("source_sha256", source["sha256"]),
                ("parsed_at", parse["finished_at"]),
            ],
        )

    def _cleanup_partial(self, params: _Params) -> None:
        (params.case_dir / ANALYSIS_DB).unlink(missing_ok=True)
        descriptor_path(params.case_dir, params.title).unlink(missing_ok=True)
