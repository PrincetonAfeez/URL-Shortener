"""SQLite storage implementation. """

from __future__ import annotations

import json
import sqlite3
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sniplink.core.lifecycle import ensure_click_quota_available, ensure_link_available
from sniplink.exceptions import AliasTaken, CodeExpired, CodeNotFound, StorageError
from sniplink.models import HealthCheckResult, Link, utc_now


def _dt_to_db(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat()


def _dt_from_db(value: str | None) -> datetime | None:
    if value is None:
        return None
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _is_unique_constraint(exc: sqlite3.IntegrityError) -> bool:
    """Distinguish UNIQUE violations from other IntegrityErrors.

    Without the disambiguation, a future NOT NULL / CHECK constraint would
    be mis-reported as ``AliasTaken``. Python 3.11+ exposes ``sqlite_errorname``
    on ``sqlite3.Error``; falling back to substring matching when the
    attribute is missing keeps the code working on older interpreters.
    """

    name = getattr(exc, "sqlite_errorname", "") or ""
    if name:
        return name == "SQLITE_CONSTRAINT_UNIQUE"
    # Pre-3.11 fallback: the message contains "UNIQUE constraint failed".
    return "UNIQUE constraint failed" in str(exc)


class SQLiteStorage:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def initialize(self) -> None:
        if self.path.parent != Path("."):
            self.path.parent.mkdir(parents=True, exist_ok=True)
        schema_path = Path(__file__).with_name("schema.sql")
        # WAL is sticky on the database file — set it once at init so the
        # per-request _connect() doesn't pay the brief writer-lock cost on
        # every call (bug #17 in the third-pass review).
        with self._connect() as conn:
            conn.execute("PRAGMA journal_mode = WAL")
            conn.executescript(schema_path.read_text(encoding="utf-8"))

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        """Open a connection, run as a transaction, close on exit.

        ``sqlite3.Connection`` does NOT close itself when used as a context
        manager — the context manager only commits / rolls back. Without
        wrapping in ``contextlib.closing`` (or this combined manager), every
        call site would leak a connection until Python's garbage collector
        ran.
        """

        conn = sqlite3.connect(self.path, timeout=30, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            with conn:
                yield conn
        finally:
            conn.close()

    def insert_link(
        self,
        *,
        short_code: str,
        destination_url: str,
        redirect_status: int,
        expires_at: datetime | None = None,
        max_clicks: int | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Link:
        return self._insert(
            short_code=short_code,
            destination_url=destination_url,
            redirect_status=redirect_status,
            expires_at=expires_at,
            max_clicks=max_clicks,
            metadata=metadata,
        )

    def insert_pending_link(
        self,
        *,
        destination_url: str,
        redirect_status: int,
        expires_at: datetime | None = None,
        max_clicks: int | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Link:
        return self._insert(
            short_code=f"__pending_{uuid.uuid4().hex}",
            destination_url=destination_url,
            redirect_status=redirect_status,
            expires_at=expires_at,
            max_clicks=max_clicks,
            metadata=metadata,
        )

    def _insert(
        self,
        *,
        short_code: str,
        destination_url: str,
        redirect_status: int,
        expires_at: datetime | None,
        max_clicks: int | None,
        metadata: dict[str, Any] | None,
    ) -> Link:
        created_at = utc_now()
        try:
            with self._connect() as conn:
                cursor = conn.execute(
                    """
                    INSERT INTO links (
                        short_code, destination_url, redirect_status, created_at,
                        expires_at, max_clicks, click_count, metadata
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        short_code,
                        destination_url,
                        redirect_status,
                        _dt_to_db(created_at),
                        _dt_to_db(expires_at),
                        max_clicks,
                        0,
                        json.dumps(metadata or {}, sort_keys=True),
                    ),
                )
                link_id = cursor.lastrowid
            return self.get_link_by_id(link_id)
        except sqlite3.IntegrityError as exc:
            if _is_unique_constraint(exc):
                raise AliasTaken(f"short code already exists: {short_code}") from exc
            raise StorageError(str(exc)) from exc
        except sqlite3.Error as exc:
            raise StorageError(str(exc)) from exc

    def update_short_code(self, link_id: int, short_code: str) -> Link:
        try:
            with self._connect() as conn:
                cursor = conn.execute(
                    "UPDATE links SET short_code = ? WHERE id = ?",
                    (short_code, link_id),
                )
                if cursor.rowcount == 0:
                    raise CodeNotFound(f"link id not found: {link_id}")
            return self.get_link_by_id(link_id)
        except sqlite3.IntegrityError as exc:
            if _is_unique_constraint(exc):
                raise AliasTaken(f"short code already exists: {short_code}") from exc
            raise StorageError(str(exc)) from exc
        except sqlite3.Error as exc:
            raise StorageError(str(exc)) from exc

    def delete_pending_link(self, link_id: int) -> None:
        with self._connect() as conn:
            cursor = conn.execute(
                "DELETE FROM links WHERE id = ? AND short_code LIKE '__pending_%'",
                (link_id,),
            )
            if cursor.rowcount == 0:
                raise CodeNotFound(f"pending link id not found: {link_id}")

    def cleanup_stale_pending_links(self, *, max_age_hours: int = 24) -> int:
        """Remove abandoned ``__pending_*`` placeholder rows."""

        cutoff = utc_now().replace(microsecond=0)
        from datetime import timedelta

        threshold = _dt_to_db(cutoff - timedelta(hours=max_age_hours))
        with self._connect() as conn:
            cursor = conn.execute(
                "DELETE FROM links WHERE short_code LIKE '__pending_%' AND created_at < ?",
                (threshold,),
            )
            return int(cursor.rowcount)

    def get_link(self, short_code: str) -> Link:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM links WHERE short_code = ?",
                (short_code,),
            ).fetchone()
        if row is None:
            raise CodeNotFound(f"short code not found: {short_code}")
        return self._row_to_link(row)

    def get_link_by_id(self, link_id: int) -> Link:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM links WHERE id = ?", (link_id,)).fetchone()
        if row is None:
            raise CodeNotFound(f"link id not found: {link_id}")
        return self._row_to_link(row)

    def list_links(self, include_deleted: bool = False) -> list[Link]:
        where = "" if include_deleted else "WHERE deleted_at IS NULL"
        with self._connect() as conn:
            rows = conn.execute(
                f"SELECT * FROM links {where} ORDER BY created_at DESC, id DESC"
            ).fetchall()
        return [self._row_to_link(row) for row in rows]

    def mark_disabled(self, short_code: str) -> Link:
        return self._touch_lifecycle(short_code, "disabled_at")

    def mark_deleted(self, short_code: str) -> Link:
        return self._touch_lifecycle(short_code, "deleted_at")

    def set_expiry(self, short_code: str, expires_at: datetime) -> Link:
        with self._connect() as conn:
            cursor = conn.execute(
                "UPDATE links SET expires_at = ? WHERE short_code = ?",
                (_dt_to_db(expires_at), short_code),
            )
            if cursor.rowcount == 0:
                raise CodeNotFound(f"short code not found: {short_code}")
        return self.get_link(short_code)

    def _touch_lifecycle(self, short_code: str, column: str) -> Link:
        if column not in {"disabled_at", "deleted_at"}:
            raise ValueError("unsupported lifecycle column")
        with self._connect() as conn:
            cursor = conn.execute(
                f"UPDATE links SET {column} = ? WHERE short_code = ?",
                (_dt_to_db(utc_now()), short_code),
            )
            if cursor.rowcount == 0:
                raise CodeNotFound(f"short code not found: {short_code}")
        return self.get_link(short_code)

    def record_click(
        self,
        link_id: int,
        *,
        referrer: str | None = None,
        user_agent: str | None = None,
    ) -> Link:
        """Atomically gate on ``max_clicks`` and record the click row.

        The conditional UPDATE is the entire race fix: if the link has
        already reached its cap, ``rowcount`` is 0 and we raise
        ``CodeExpired`` *before* inserting a click row. Two concurrent
        requests cannot both pass a "check then increment" pattern because
        the check IS the increment.
        """

        clicked_at = utc_now()
        now_db = _dt_to_db(clicked_at)
        with self._connect() as conn:
            cursor = conn.execute(
                """
                UPDATE links
                SET click_count = click_count + 1
                WHERE id = ?
                  AND disabled_at IS NULL
                  AND deleted_at IS NULL
                  AND (expires_at IS NULL OR expires_at > ?)
                  AND (max_clicks IS NULL OR click_count < max_clicks)
                """,
                (link_id, now_db),
            )
            if cursor.rowcount == 0:
                link = self.get_link_by_id(link_id)
                ensure_link_available(link)
                ensure_click_quota_available(link)
                raise CodeExpired(f"link reached max_clicks: {link_id}")
            conn.execute(
                """
                INSERT INTO clicks (link_id, clicked_at, referrer, user_agent)
                VALUES (?, ?, ?, ?)
                """,
                (link_id, _dt_to_db(clicked_at), referrer, user_agent),
            )
        return self.get_link_by_id(link_id)

    def stats(self, short_code: str) -> dict[str, Any]:
        link = self.get_link(short_code)
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT COUNT(*) AS total_clicks, MAX(clicked_at) AS last_clicked_at
                FROM clicks WHERE link_id = ?
                """,
                (link.id,),
            ).fetchone()
        return {
            "short_code": link.short_code,
            "destination_url": link.destination_url,
            "click_count": link.click_count,
            "recorded_clicks": int(row["total_clicks"] or 0),
            "last_clicked_at": _dt_to_db(_dt_from_db(row["last_clicked_at"])),
            "disabled": link.disabled_at is not None,
            "deleted": link.deleted_at is not None,
            "expires_at": _dt_to_db(link.expires_at),
        }

    def save_health_result(self, result: HealthCheckResult) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO health_check_results (
                    link_id, checked_at, status_code, error, elapsed_ms, redirect_count
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    result.link_id,
                    _dt_to_db(result.checked_at),
                    result.status_code,
                    result.error,
                    result.elapsed_ms,
                    result.redirect_count,
                ),
            )

    def _row_to_link(self, row: sqlite3.Row) -> Link:
        return Link(
            id=int(row["id"]),
            short_code=row["short_code"],
            destination_url=row["destination_url"],
            redirect_status=int(row["redirect_status"]),
            created_at=_dt_from_db(row["created_at"]) or utc_now(),
            expires_at=_dt_from_db(row["expires_at"]),
            disabled_at=_dt_from_db(row["disabled_at"]),
            deleted_at=_dt_from_db(row["deleted_at"]),
            max_clicks=row["max_clicks"],
            click_count=int(row["click_count"]),
            metadata=json.loads(row["metadata"] or "{}"),
        )
