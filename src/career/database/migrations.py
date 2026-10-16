"""Schema versioning via SQLite's user_version pragma.

Each migration is a function that takes a connection; they run in order once.
Each step creates only its own tables, so upgrading an old database is safe.
"""

from collections.abc import Callable

from sqlalchemy import Connection, Engine, text

from career.database.models import Base


def _v1_initial(conn: Connection) -> None:
    Base.metadata.tables["events"].create(conn, checkfirst=True)


def _v2_sessions(conn: Connection) -> None:
    Base.metadata.tables["sessions"].create(conn, checkfirst=True)


_MEMORY_TABLES = ("user_profile", "projects", "ai_analysis", "skills", "skill_scores", "achievements", "review_items",
                  "cv_bullets", "kv_state")


def _v3_career_memory(conn: Connection) -> None:
    for name in _MEMORY_TABLES:
        Base.metadata.tables[name].create(conn, checkfirst=True)


def _v4_indexes(conn: Connection) -> None:
    conn.execute(text("CREATE INDEX IF NOT EXISTS ix_events_type_timestamp ON events (type, timestamp)"))
    conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS ux_review_kind_ref ON review_items (kind, ref_id)"))


MIGRATIONS: list[Callable[[Connection], None]] = [_v1_initial, _v2_sessions, _v3_career_memory, _v4_indexes]
SCHEMA_VERSION = len(MIGRATIONS)


def current_version(conn: Connection) -> int:
    return conn.execute(text("PRAGMA user_version")).scalar_one()


def migrate(engine: Engine) -> int:
    with engine.begin() as conn:
        version = current_version(conn)
        for number, migration in enumerate(MIGRATIONS[version:], start=version + 1):
            migration(conn)
            conn.execute(text(f"PRAGMA user_version = {number}"))
        return current_version(conn)
