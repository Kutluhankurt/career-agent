import sqlite3
from datetime import date

from career.analysis.service import rebuild_day
from career.config import Settings
from career.database.database import Database
from career.database.migrations import SCHEMA_VERSION
from tests.fixtures import day


def test_rebuild_is_idempotent_and_roundtrips(tmp_path):
    db = Database(tmp_path / "c.db")
    db.add_events(day.generate())
    n1, first = rebuild_day(db, Settings(), day.DAY)
    n2, second = rebuild_day(db, Settings(), day.DAY)
    assert n1 == n2 > 400
    assert [s.id for s in first] == [s.id for s in second]
    stored = db.list_sessions()
    assert len(stored) == len(first) == db.count_sessions()
    assert stored[1].model_dump() == first[1].model_dump()
    assert stored[1].files and stored[1].event_ids


def test_rebuild_only_touches_that_day(tmp_path):
    db = Database(tmp_path / "c.db")
    db.add_events(day.generate())
    rebuild_day(db, Settings(), day.DAY)
    rebuild_day(db, Settings(), date(2026, 10, 17))  # empty day
    assert db.count_sessions() == len(day.PLAN)


def test_upgrade_from_v1_database(tmp_path):
    path = tmp_path / "old.db"
    conn = sqlite3.connect(path)
    conn.executescript(
        "CREATE TABLE events (id VARCHAR(36) PRIMARY KEY, timestamp DATETIME, type VARCHAR(32), application VARCHAR(255),"
        " title TEXT, metadata JSON, source VARCHAR(32)); PRAGMA user_version = 1;"
    )
    conn.close()
    db = Database(path)
    with db.engine.connect() as c:
        assert c.exec_driver_sql("PRAGMA user_version").scalar() == SCHEMA_VERSION
    assert db.count_sessions() == 0
