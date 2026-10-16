from datetime import datetime, timedelta, timezone

from career.database.database import Database
from career.database.migrations import SCHEMA_VERSION, current_version
from career.events.models import Event, EventType


def make(minutes, type=EventType.WINDOW_FOCUS, app="VS Code"):
    ts = datetime(2026, 10, 16, 9, 0, tzinfo=timezone.utc) + timedelta(minutes=minutes)
    return Event(timestamp=ts, type=type, application=app, window_title=f"t{minutes}", metadata={"pid": 1})


def test_schema_version(tmp_path):
    db = Database(tmp_path / "c.db")
    with db.engine.connect() as conn:
        assert current_version(conn) == SCHEMA_VERSION
    # reopening doesn't re-run migrations
    Database(tmp_path / "c.db")


def test_add_and_list_roundtrip(tmp_path):
    db = Database(tmp_path / "c.db")
    events = [make(0), make(5, EventType.IDLE_STARTED, None), make(10)]
    assert db.add_events(events) == 3
    out = db.list_events()
    assert [e.id for e in out] == [e.id for e in events]
    assert out[0].timestamp == events[0].timestamp
    assert out[0].timestamp.tzinfo is not None
    assert out[0].metadata == {"pid": 1}
    assert out[1].type == EventType.IDLE_STARTED


def test_filters_and_counts(tmp_path):
    db = Database(tmp_path / "c.db")
    db.add_events([make(0), make(5), make(10, EventType.IDLE_STARTED, None)])
    since = datetime(2026, 10, 16, 9, 4, tzinfo=timezone.utc)
    assert db.count_events() == 3
    assert db.count_events(since=since) == 2
    assert [e.window_title for e in db.list_events(limit=2, newest_first=True)] == ["t10", "t5"]
    assert db.last_event().type == EventType.IDLE_STARTED
    assert db.last_event(EventType.WINDOW_FOCUS).window_title == "t5"


def test_empty_add(tmp_path):
    assert Database(tmp_path / "c.db").add_events([]) == 0
