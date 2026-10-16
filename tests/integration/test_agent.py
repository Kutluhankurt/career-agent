from career.agent import Agent, read_agent_info
from career.collector import MockCollector, Sample
from career.config import Settings
from career.database.database import Database
from career.events.models import EventType


class SteppingMock(MockCollector):
    """Advances one sample per tick, like real time passing."""

    def get_active_window(self):
        window = super().get_active_window()
        self.advance()
        return window


def quiet_settings() -> Settings:
    settings = Settings()
    settings.collector.repo_roots = []  # never scan the real home folder in tests
    return settings


def test_agent_collects_into_database(home):
    settings = quiet_settings()
    settings.collector.interval = 0.01
    settings.collector.idle_threshold = 60
    collector = SteppingMock([
        Sample("code", "temperature_test.py"),
        Sample("Google-chrome", "AI-1842 - Jira"),
        Sample("Gnome-terminal-server", "pytest"),
        Sample("Gnome-terminal-server", "pytest"),
    ])
    db = Database(home.database)
    Agent(home, settings, collector=collector, db=db).run(max_ticks=4)

    events = db.list_events()
    assert events[0].type == EventType.AGENT_STARTED
    assert events[-1].type == EventType.AGENT_STOPPED
    focus = [e for e in events if e.type == EventType.WINDOW_FOCUS]
    assert [e.application for e in focus] == ["VS Code", "Chrome", "Terminal"]
    assert not home.pid_file.exists()
    assert read_agent_info(home) is None


def test_agent_stops_on_stop_file(home):
    settings = quiet_settings()
    settings.collector.interval = 0.01
    collector = MockCollector([Sample("code", "a.py")])

    class StopAfterFirst(Agent):
        def _tick(self):
            super()._tick()
            self.paths.stop_file.touch()

    StopAfterFirst(home, settings, collector=collector, db=Database(home.database)).run(max_ticks=1000)
    types = [e.type for e in Database(home.database).list_events()]
    assert types == [EventType.AGENT_STARTED, EventType.WINDOW_FOCUS, EventType.AGENT_STOPPED]
    assert not home.stop_file.exists()


def test_stale_pid_file_is_cleaned(home):
    home.pid_file.write_text('{"pid": 999999, "started_at": "2026-10-16T09:00:00+00:00", "platform": "Linux"}')
    assert read_agent_info(home) is None
    assert not home.pid_file.exists()


def test_pause_stops_collection_and_resume_continues(home):
    from career.agent import pause, read_pause, resume

    settings = quiet_settings()
    settings.collector.interval = 0.01
    collector = SteppingMock([Sample("code", "a.py"), Sample("code", "b.py"), Sample("code", "c.py")])
    db = Database(home.database)
    agent = Agent(home, settings, collector=collector, db=db)
    pause(home, 5)
    assert read_pause(home) is not None
    agent.run(max_ticks=2)
    types = [e.type for e in db.list_events()]
    assert EventType.WINDOW_FOCUS not in types
    resume(home)
    assert read_pause(home) is None
