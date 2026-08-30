"""Open a parsed case folder and answer the frontend's read-only queries."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from pineapple.analysis.descriptor import (
    CaseDescriptor,
    find_descriptor,
    read_descriptor,
)
from pineapple.analysis.errors import AnalysisError
from pineapple.analysis.schema import SCHEMA_VERSION

ANALYSIS_DB = "analysis.db"
DEFAULT_PAGE = 200
MAX_PAGE = 2000

_COUNT_TABLES = ("apps", "files", "messages", "calls", "contacts")


def _page(limit: int, offset: int) -> tuple[int, int]:
    return max(1, min(int(limit), MAX_PAGE)), max(0, int(offset))


class CaseHandle:
    """A loaded case: its descriptor plus a read-only ``analysis.db`` connection."""

    def __init__(
        self, case_dir: Path, descriptor: CaseDescriptor, conn: sqlite3.Connection
    ) -> None:
        self.case_dir = case_dir
        self._descriptor = descriptor
        self._conn = conn
        self._conn.row_factory = sqlite3.Row

    # -- descriptor / summary ---------------------------------------------

    def descriptor(self) -> dict[str, Any]:
        return self._descriptor.to_dict()

    def summary(self) -> dict[str, Any]:
        row = self._conn.execute("SELECT * FROM backup_info LIMIT 1").fetchone()
        counts = {
            table: self._conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in _COUNT_TABLES
        }
        return {
            "title": self._descriptor.title,
            "device": dict(row) if row else self._descriptor.device,
            "source": self._descriptor.source,
            "parse": self._descriptor.parse,
            "counts": counts,
        }

    # -- artifact queries ------------------------------------------------

    def apps(self) -> list[dict[str, Any]]:
        return [
            dict(row)
            for row in self._conn.execute(
                "SELECT bundle_id, name, version FROM apps ORDER BY bundle_id"
            )
        ]

    def files(
        self,
        domain: str | None = None,
        search: str | None = None,
        limit: int = DEFAULT_PAGE,
        offset: int = 0,
    ) -> dict[str, Any]:
        where, params = self._files_where(domain, search)
        return self._page_query(
            "SELECT file_id, domain, relative_path, is_dir, size, mtime, btime, target "
            f"FROM files {where} ORDER BY domain, relative_path",
            f"SELECT COUNT(*) FROM files {where}",
            params,
            limit,
            offset,
        )

    def domains(self) -> list[dict[str, Any]]:
        return [
            {"domain": row[0], "count": row[1]}
            for row in self._conn.execute(
                "SELECT domain, COUNT(*) FROM files GROUP BY domain ORDER BY domain"
            )
        ]

    def messages(
        self,
        search: str | None = None,
        limit: int = DEFAULT_PAGE,
        offset: int = 0,
    ) -> dict[str, Any]:
        where = ""
        params: list[Any] = []
        if search:
            where = "WHERE text LIKE ? OR address LIKE ?"
            params = [f"%{search}%"] * 2
        return self._page_query(
            "SELECT rowid, chat_id, address, service, is_from_me, date_utc, text, "
            f"attachments FROM messages {where} ORDER BY date_utc",
            f"SELECT COUNT(*) FROM messages {where}",
            params,
            limit,
            offset,
        )

    def calls(self, limit: int = DEFAULT_PAGE, offset: int = 0) -> dict[str, Any]:
        return self._page_query(
            "SELECT rowid, address, service, direction, date_utc, duration_seconds "
            "FROM calls ORDER BY date_utc DESC",
            "SELECT COUNT(*) FROM calls",
            [],
            limit,
            offset,
        )

    def contacts(
        self,
        search: str | None = None,
        limit: int = DEFAULT_PAGE,
        offset: int = 0,
    ) -> dict[str, Any]:
        where = ""
        params: list[Any] = []
        if search:
            where = (
                "WHERE first LIKE ? OR last LIKE ? OR organization LIKE ? "
                "OR phones LIKE ? OR emails LIKE ?"
            )
            params = [f"%{search}%"] * 5
        return self._page_query(
            "SELECT rowid, first, last, organization, phones, emails "
            f"FROM contacts {where} ORDER BY last, first",
            f"SELECT COUNT(*) FROM contacts {where}",
            params,
            limit,
            offset,
        )

    def close(self) -> None:
        self._conn.close()

    # -- internals ------------------------------------------------------

    @staticmethod
    def _files_where(domain: str | None, search: str | None) -> tuple[str, list[Any]]:
        clauses: list[str] = []
        params: list[Any] = []
        if domain:
            clauses.append("domain = ?")
            params.append(domain)
        if search:
            clauses.append("relative_path LIKE ?")
            params.append(f"%{search}%")
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        return where, params

    def _page_query(
        self,
        rows_sql: str,
        count_sql: str,
        params: list[Any],
        limit: int,
        offset: int,
    ) -> dict[str, Any]:
        limit, offset = _page(limit, offset)
        total = self._conn.execute(count_sql, params).fetchone()[0]
        rows = self._conn.execute(
            f"{rows_sql} LIMIT ? OFFSET ?", [*params, limit, offset]
        ).fetchall()
        return {
            "rows": [dict(row) for row in rows],
            "total": total,
            "limit": limit,
            "offset": offset,
        }


def load_case(case_dir: str | Path) -> CaseHandle:
    """Open an existing case folder. Raises :class:`AnalysisError` when it is
    not a case, or was written by an incompatible schema version."""
    path = Path(case_dir)
    descriptor_file = find_descriptor(path)
    if descriptor_file is None:
        raise AnalysisError(f"{path} does not contain a case descriptor (.json).")
    descriptor = read_descriptor(descriptor_file)
    if descriptor.schema_version != SCHEMA_VERSION:
        raise AnalysisError(
            f"Case was written by schema v{descriptor.schema_version}; "
            f"this build expects v{SCHEMA_VERSION}."
        )
    database = path / ANALYSIS_DB
    if not database.is_file():
        raise AnalysisError(f"{path} has a descriptor but no {ANALYSIS_DB}.")
    conn = sqlite3.connect(f"file:{database}?mode=ro", uri=True)
    return CaseHandle(path, descriptor, conn)
