from datetime import datetime, timedelta

import pytest

from career.analysis.sessions import SessionEngine
from career.events.models import Event, EventType
from tests.fixtures import day
from tests.fixtures.loader import TZ, load


def engine():
    return SessionEngine(idle_threshold=300)


def focus(t: datetime, app: str, title: str) -> Event:
    return Event(timestamp=t, type=EventType.WINDOW_FOCUS, application=app, window_title=title)


T0 = datetime(2026, 10, 16, 9, 0, tzinfo=TZ)


def m(minutes: float) -> datetime:
    return T0 + timedelta(minutes=minutes)


# --- fixtures from roadmap §52 ------------------------------------------------
def test_supervisor_temperature_is_one_session():
    data, events = load("supervisor_temperature")
    sessions = engine().build(events)
    assert len(sessions) == data["expected"]["sessions"]
    s = sessions[0]
    assert s.label == data["expected"]["label"]
    assert {"VS Code", "Chrome", "Terminal", "Excel", "Slack"} <= set(s.applications)
    assert {"temperature_test.py", "Temperature_Result.xlsx", "config.yaml"} <= set(s.files)
    assert s.tickets == {"AI-1842": pytest.approx(s.tickets["AI-1842"])}
    assert s.start.astimezone(TZ).strftime("%H:%M") == "09:12"
    assert s.end.astimezone(TZ).strftime("%H:%M") == "10:04"
    assert s.score >= 0.8


def test_idle_period_splits():
    data, events = load("idle_period")
    sessions = engine().build(events)
    assert len(sessions) == data["expected"]["sessions"]
    assert [x.label for x in sessions] == ["logParser_v2", "logParser_v2"]
    assert sessions[1].end.astimezone(TZ).strftime("%H:%M") == "14:18"  # ends at agent_stopped


def test_short_excursion_stays_inside():
    data, events = load("python_development")
    sessions = engine().build(events)
    assert len(sessions) == 1
    assert sessions[0].label == data["expected"]["label"]
    assert "logParser_v2" in sessions[0].workspaces  # visible as context, not as its own session


def test_sustained_switch_splits():
    data, events = load("jira_investigation")
    sessions = engine().build(events)
    assert [s.label for s in sessions] == data["expected"]["labels"]
    assert sessions[1].start.astimezone(TZ).strftime("%H:%M") == "11:12"


# --- rules ----------------------------------------------------------------------
def test_slack_glance_does_not_split():
    events = [
        focus(m(0), "VS Code", "a.py — supervisor — Visual Studio Code"),
        focus(m(20), "Slack", "Slack | #general"),
        focus(m(22), "VS Code", "a.py — supervisor — Visual Studio Code"),
        Event(timestamp=m(40), type=EventType.IDLE_STARTED),
    ]
    assert len(engine().build(events)) == 1


def test_long_unkeyed_app_splits_after_three_switch_windows():
    events = [
        focus(m(0), "VS Code", "a.py — supervisor — Visual Studio Code"),
        focus(m(20), "Outlook", "Inbox - Outlook"),
        Event(timestamp=m(40), type=EventType.IDLE_STARTED),
    ]
    sessions = engine().build(events)
    assert [s.label for s in sessions] == ["supervisor", "Outlook"]


def test_email_then_project_work_splits():
    events = [
        focus(m(0), "Outlook", "Inbox - Outlook"),
        focus(m(20), "VS Code", "a.py — supervisor — Visual Studio Code"),
        Event(timestamp=m(45), type=EventType.IDLE_STARTED),
    ]
    assert [s.label for s in engine().build(events)] == ["Outlook", "supervisor"]


def test_short_pause_does_not_split_but_long_one_does():
    def events(pause):
        return [
            focus(m(0), "VS Code", "a.py — supervisor — Visual Studio Code"),
            Event(timestamp=m(10), type=EventType.IDLE_STARTED),
            Event(timestamp=m(10 + pause), type=EventType.IDLE_ENDED),
            focus(m(10 + pause), "VS Code", "a.py — supervisor — Visual Studio Code"),
            Event(timestamp=m(30 + pause), type=EventType.IDLE_STARTED),
        ]

    short = engine().build(events(6))
    assert len(short) == 1
    assert short[0].idle_seconds == pytest.approx(360)
    assert len(engine().build(events(40))) == 2


def test_tiny_sessions_merge_or_drop():
    lone_blip = [focus(m(0), "Chrome", "News"), Event(timestamp=m(1), type=EventType.IDLE_STARTED)]
    assert engine().build(lone_blip) == []


def test_last_focus_is_capped_unless_open():
    events = [focus(m(0), "VS Code", "a.py — supervisor — Visual Studio Code")]
    closed = engine().build(events)
    assert closed[0].active_seconds == 300  # idle_threshold
    live = engine().build(events, open_until=m(42))
    assert live[0].active_seconds == 42 * 60
    assert live[0].is_open


def test_max_span_caps_missing_markers():
    events = [
        focus(m(0), "VS Code", "a.py — supervisor — Visual Studio Code"),
        focus(m(600), "VS Code", "a.py — supervisor — Visual Studio Code"),  # 10 h later, no marker
        Event(timestamp=m(630), type=EventType.AGENT_STOPPED),
    ]
    sessions = engine().build(events)
    assert sessions[0].active_seconds == 7200
    assert len(sessions) == 2


def test_ids_are_stable_across_rebuilds():
    _, events = load("jira_investigation")
    assert [s.id for s in engine().build(events)] == [s.id for s in engine().build(events)]


def test_empty():
    assert engine().build([]) == []


# --- roadmap Sprint 3 success criterion ----------------------------------------
def test_full_day_500_events_become_10_to_20_sessions():
    events = day.generate()
    assert 450 <= len(events) <= 650
    sessions = engine().build(events)
    assert 10 <= len(sessions) <= 20
    # matches the ground-truth plan block for block
    assert len(sessions) == len(day.PLAN)
    # boundaries within 2 minutes of the truth (a glance at the switch can land on either side)
    for session, block in zip(sessions, day.PLAN):
        planned = datetime.combine(day.DAY, datetime.strptime(block[0], "%H:%M").time(), tzinfo=TZ)
        assert abs((session.start - planned).total_seconds()) <= 120, (session.label, block[0])
    labels = [s.label.split(" · ")[0] for s in sessions]
    assert labels == ["Outlook", "supervisor", "VersionUpdater_v2.3", "mobilai", "supervisor", "Outlook",
                      "logParser_v2", "mobilai", "VersionUpdater_v2.3", "supervisor", "logParser_v2", "mobilai"]


def test_restart_after_crash_caps_the_last_window():
    events = [
        focus(m(0), "VS Code", "a.py — supervisor — Visual Studio Code"),
        Event(timestamp=m(180), type=EventType.AGENT_STARTED),  # no agent_stopped: it crashed
        focus(m(180), "VS Code", "a.py — supervisor — Visual Studio Code"),
        Event(timestamp=m(200), type=EventType.AGENT_STOPPED),
    ]
    sessions = engine().build(events)
    assert [s.active_seconds for s in sessions] == [300, 1200]
