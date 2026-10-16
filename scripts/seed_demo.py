"""Fill a Career Agent home with 10 days of realistic synthetic work (for demos and UI work).

    CAREER_AGENT_HOME=/tmp/career-demo uv run python scripts/seed_demo.py
    CAREER_AGENT_HOME=/tmp/career-demo uv run career dashboard
"""

import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from career.career.memory import MemoryEngine  # noqa: E402
from career.career.store import MemoryStore  # noqa: E402
from career.config import Settings, get_paths  # noqa: E402
from career.database.database import Database  # noqa: E402
from career.events.models import Event, EventType, utc_now  # noqa: E402
from career.profile.models import Profile  # noqa: E402
from tests.fixtures import day as synthetic  # noqa: E402

DAYS = 10


def main() -> None:
    paths = get_paths().ensure()
    if paths.database.exists():
        sys.exit(f"{paths.database} already exists; point CAREER_AGENT_HOME at an empty folder.")
    db = Database(paths.database)
    store = MemoryStore(db)
    today = date.today()
    store.save_profile(Profile(name="Alex Morgan", job_title="Test Engineer", focus="Edge AI device testing",
                               projects=["Supervisor", "Mobile AI"], tools=["Jira", "VS Code", "Git", "Python"],
                               setup_at=utc_now() - timedelta(days=DAYS - 4)))
    events: list[Event] = []
    workdays = [today - timedelta(days=i) for i in range(DAYS - 1, -1, -1) if (today - timedelta(days=i)).weekday() < 5]
    for n, d in enumerate(workdays):
        shift = d - synthetic.DAY
        for e in synthetic.generate(seed=100 + n):
            events.append(e.model_copy(update={"id": f"{e.id}-{n}", "timestamp": e.timestamp + shift}))
        # a commit and some saved files each day, like the real collectors produce
        t = synthetic.at(d, "11:40:00")  # inside the late-morning Supervisor block
        events.append(Event(id=f"git-{n}", timestamp=t, type=EventType.GIT_ACTIVITY, application="Git",
                            window_title="Fix temperature validation", metadata={
                                "kind": "commit", "repository": "supervisor", "branch": "feature/temperature-test",
                                "hash": f"abc{n:03d}def456", "message": "Fix temperature validation" if n % 2 == 0 else "Tighten temperature limits",
                                "files": ["temperature_test.py", "config.yaml"], "added": 12 + n, "removed": 3}))
        saves = [("09:30:00", "temperature_test.py", "supervisor"), ("11:45:00", "Temperature_Result.xlsx", "supervisor"),
                 ("11:05:00", "test_camera.py", "mobilai"), ("10:20:00", "version_updater.py", "VersionUpdater_v2.3"),
                 ("13:40:00", "parse.py", "logParser_v2")]
        for k, (at, name, repo) in enumerate(saves):
            events.append(Event(id=f"file-{n}-{k}", timestamp=synthetic.at(d, at), type=EventType.FILE_CHANGED,
                                window_title=name, metadata={"action": "modified", "name": name,
                                                             "extension": name.rsplit(".", 1)[-1], "repository": repo}))
    db.add_events(events)
    engine = MemoryEngine(db, Settings())
    for d in workdays:
        engine.update_day(d)
    print(f"Seeded {len(events):,} events over {len(workdays)} workdays into {paths.home}")


if __name__ == "__main__":
    main()
