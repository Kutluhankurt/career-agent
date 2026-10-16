from datetime import timedelta

import pytest

from career.config import get_paths


@pytest.fixture
def home(tmp_path, monkeypatch):
    """Isolated CAREER_AGENT_HOME for each test."""
    monkeypatch.setenv("CAREER_AGENT_HOME", str(tmp_path / "home"))
    return get_paths().ensure()


@pytest.fixture
def seeded(home):
    """A home with a profile and three analysed synthetic work days."""
    from career.career.memory import MemoryEngine
    from career.career.store import MemoryStore
    from career.config import Settings
    from career.database.database import Database
    from career.events.models import utc_now
    from career.profile.models import Profile
    from tests.fixtures import day

    db = Database(home.database)
    store = MemoryStore(db)
    store.save_profile(Profile(name="Alex Morgan", job_title="Test Engineer", focus="Edge AI device testing",
                               projects=["Supervisor", "Mobile AI"], setup_at=utc_now() - timedelta(days=2)))
    events = []
    for n in range(3):
        for e in day.generate(seed=7 + n):
            events.append(e.model_copy(update={"id": f"{e.id}-{n}", "timestamp": e.timestamp - timedelta(days=2 - n)}))
    db.add_events(events)
    engine = MemoryEngine(db, Settings())
    for n in range(3):
        engine.update_day(day.DAY - timedelta(days=2 - n))
    return db
