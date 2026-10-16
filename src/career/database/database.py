"""SQLite access. The agent writes while the CLI reads, so WAL mode is enabled."""

import time
import logging
from collections.abc import Iterable
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import create_engine, delete, event, func, select
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session, sessionmaker

from career.database.migrations import migrate
from career.analysis.models import WorkSession
from career.database.models import EventRow, SessionRow
from career.events.models import Event, EventType

log = logging.getLogger(__name__)

_SESSION_DATA_FIELDS = {"applications", "workspaces", "tickets", "files", "titles", "event_ids"}


def _as_utc(value: datetime) -> datetime:
    # SQLite drops tzinfo; everything is stored as UTC, so restore it on read.
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


class Database:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        self.engine = create_engine(f"sqlite:///{path}", future=True, connect_args={"check_same_thread": False})
        event.listen(self.engine, "connect", self._on_connect)
        self._sessions = sessionmaker(self.engine, expire_on_commit=False)
        migrate(self.engine)

    @staticmethod
    def _on_connect(dbapi_conn, _record) -> None:
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA journal_mode=WAL")
        cur.execute("PRAGMA busy_timeout=5000")
        cur.close()

    def session(self) -> Session:
        return self._sessions()

    def add_events(self, events: Iterable[Event], retries: int = 3) -> int:
        rows = [
            EventRow(
                id=e.id,
                timestamp=_as_utc(e.timestamp),
                type=e.type.value,
                application=e.application,
                title=e.window_title,
                meta=e.metadata,
                source=e.source,
            )
            for e in events
        ]
        if not rows:
            return 0
        for attempt in range(1, retries + 1):
            try:
                with self.session() as s, s.begin():
                    s.add_all(rows)
                return len(rows)
            except OperationalError:
                if attempt == retries:
                    raise
                log.warning("Database busy, retrying write (%s/%s)", attempt, retries)
                time.sleep(0.5 * attempt)
        return 0

    def list_events(
        self,
        since: datetime | None = None,
        limit: int | None = None,
        newest_first: bool = False,
        until: datetime | None = None,
    ) -> list[Event]:
        stmt = select(EventRow)
        if since is not None:
            stmt = stmt.where(EventRow.timestamp >= _as_utc(since))
        if until is not None:
            stmt = stmt.where(EventRow.timestamp < _as_utc(until))
        stmt = stmt.order_by(EventRow.timestamp.desc() if newest_first else EventRow.timestamp)
        if limit is not None:
            stmt = stmt.limit(limit)
        with self.session() as s:
            return [self._to_event(r) for r in s.scalars(stmt)]

    def count_events(self, since: datetime | None = None) -> int:
        stmt = select(func.count()).select_from(EventRow)
        if since is not None:
            stmt = stmt.where(EventRow.timestamp >= _as_utc(since))
        with self.session() as s:
            return s.execute(stmt).scalar_one()

    def last_event(self, type: EventType | None = None) -> Event | None:
        stmt = select(EventRow).order_by(EventRow.timestamp.desc()).limit(1)
        if type is not None:
            stmt = stmt.where(EventRow.type == type.value)
        with self.session() as s:
            row = s.scalars(stmt).first()
            return self._to_event(row) if row else None

    @staticmethod
    def _to_event(row: EventRow) -> Event:
        return Event(
            id=row.id,
            timestamp=_as_utc(row.timestamp),
            type=EventType(row.type),
            application=row.application,
            window_title=row.title,
            source=row.source,
            metadata=row.meta or {},
        )

    # sessions ------------------------------------------------------------
    def replace_sessions(self, since: datetime, until: datetime, sessions: list[WorkSession]) -> None:
        """Atomically swap every session starting in [since, until) for `sessions`."""
        rows = [
            SessionRow(
                id=s.id,
                start=_as_utc(s.start),
                end=_as_utc(s.end),
                active_seconds=s.active_seconds,
                idle_seconds=s.idle_seconds,
                event_count=s.event_count,
                label=s.label,
                score=s.score,
                is_open=s.is_open,
                data=s.model_dump(mode="json", include=_SESSION_DATA_FIELDS),
            )
            for s in sessions
        ]
        with self.session() as db, db.begin():
            db.execute(delete(SessionRow).where(SessionRow.start >= _as_utc(since), SessionRow.start < _as_utc(until)))
            db.add_all(rows)

    def list_sessions(self, since: datetime | None = None, until: datetime | None = None) -> list[WorkSession]:
        stmt = select(SessionRow).order_by(SessionRow.start)
        if since is not None:
            stmt = stmt.where(SessionRow.start >= _as_utc(since))
        if until is not None:
            stmt = stmt.where(SessionRow.start < _as_utc(until))
        with self.session() as db:
            return [
                WorkSession(
                    id=r.id,
                    start=_as_utc(r.start),
                    end=_as_utc(r.end),
                    active_seconds=r.active_seconds,
                    idle_seconds=r.idle_seconds,
                    event_count=r.event_count,
                    label=r.label,
                    score=r.score,
                    is_open=r.is_open,
                    **(r.data or {}),
                )
                for r in db.scalars(stmt)
            ]

    def count_sessions(self, since: datetime | None = None) -> int:
        stmt = select(func.count()).select_from(SessionRow)
        if since is not None:
            stmt = stmt.where(SessionRow.start >= _as_utc(since))
        with self.session() as db:
            return db.execute(stmt).scalar_one()

    def close(self) -> None:
        self.engine.dispose()
