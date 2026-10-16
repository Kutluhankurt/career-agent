from datetime import datetime, timedelta, timezone

from career.collector import MockCollector, Sample
from career.events.models import EventType
from career.events.processor import EventProcessor


class Clock:
    def __init__(self):
        self.now = datetime(2026, 10, 16, 9, 0, tzinfo=timezone.utc)

    def __call__(self):
        return self.now

    def step(self, seconds=5):
        self.now += timedelta(seconds=seconds)


def run(samples, threshold=300):
    collector, clock = MockCollector(samples), Clock()
    proc = EventProcessor(collector, idle_threshold=threshold, clock=clock)
    events = []
    for _ in samples:
        events += proc.tick()
        collector.advance()
        clock.step()
    return events


def test_focus_changes_produce_events_and_repeats_are_ignored():
    events = run([
        Sample("code", "temperature_test.py"),
        Sample("code", "temperature_test.py"),
        Sample("Google-chrome", "AI-1842 Temperature Test - Jira"),
        Sample("code", "temperature_test.py"),
    ])
    assert [e.type for e in events] == [EventType.WINDOW_FOCUS] * 3
    assert [e.application for e in events] == ["VS Code", "Chrome", "VS Code"]
    assert events[1].window_title == "AI-1842 Temperature Test - Jira"
    assert all(e.source == "mock" for e in events)


def test_title_change_in_same_app_is_a_new_focus():
    events = run([Sample("code", "a.py"), Sample("code", "b.py")])
    assert [e.window_title for e in events] == ["a.py", "b.py"]


def test_idle_start_and_end():
    events = run([
        Sample("code", "a.py", idle=0),
        Sample("code", "a.py", idle=400),
        Sample("code", "a.py", idle=405),
        Sample("code", "a.py", idle=1),
    ])
    types = [e.type for e in events]
    assert types == [EventType.WINDOW_FOCUS, EventType.IDLE_STARTED, EventType.IDLE_ENDED, EventType.WINDOW_FOCUS]
    started = events[1]
    # idle_started is backdated to when input actually stopped
    assert started.timestamp == datetime(2026, 10, 16, 9, 0, 5, tzinfo=timezone.utc) - timedelta(seconds=400)
    assert started.metadata["idle_seconds"] == 400


def test_no_focus_events_while_idle():
    events = run([
        Sample("code", "a.py", idle=500),
        Sample("Google-chrome", "Jira", idle=510),
    ])
    assert [e.type for e in events] == [EventType.IDLE_STARTED]


def test_unknown_idle_never_triggers_idle():
    class NoIdle(MockCollector):
        def get_idle_time(self):
            return None

    proc = EventProcessor(NoIdle([Sample("code", "a.py")]))
    assert [e.type for e in proc.tick()] == [EventType.WINDOW_FOCUS]


def test_failing_probe_does_not_raise():
    class Broken(MockCollector):
        def get_active_window(self):
            raise RuntimeError("display gone")

    proc = EventProcessor(Broken([Sample("code", "a.py")]))
    assert proc.tick() == []


def test_no_window_no_event():
    assert run([Sample(None)]) == []


def test_sleep_gap_becomes_idle():
    collector, clock = MockCollector([Sample("code", "a.py")]), Clock()
    proc = EventProcessor(collector, clock=clock, suspend_gap=90)
    assert [e.type for e in proc.tick()] == [EventType.WINDOW_FOCUS]
    before = clock.now
    clock.step(3600)  # laptop lid closed for an hour
    events = proc.tick()
    assert [e.type for e in events] == [EventType.IDLE_STARTED, EventType.IDLE_ENDED, EventType.WINDOW_FOCUS]
    assert events[0].timestamp == before
    assert events[0].metadata["reason"] == "suspended"
    assert events[1].timestamp == clock.now
