"""Rebuilds the sessions of one local calendar day from stored events."""

from datetime import date, datetime, time, timedelta

from career.analysis.models import WorkSession
from career.analysis.sessions import SessionEngine
from career.config.settings import Settings
from career.database.database import Database


def day_bounds(day: date) -> tuple[datetime, datetime]:
    start = datetime.combine(day, time.min).astimezone()  # local midnight, tz-aware
    return start, start + timedelta(days=1)


def rebuild_day(db: Database, settings: Settings, day: date, open_until: datetime | None = None) -> tuple[int, list[WorkSession]]:
    """Returns (number of events used, sessions). Safe to run any number of times."""
    since, until = day_bounds(day)
    events = db.list_events(since=since, until=until)
    engine = SessionEngine(settings.sessions, idle_threshold=settings.collector.idle_threshold)
    sessions = engine.build(events, open_until=open_until)
    db.replace_sessions(since, until, sessions)
    return len(events), sessions
