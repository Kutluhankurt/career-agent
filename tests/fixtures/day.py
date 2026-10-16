"""Deterministic synthetic work day (~500 raw events) for the Session Engine success test.

The plan below is the ground truth: each block is one real session. Within a block the
generator alt-tabs between that block's windows every 15–90 s and sometimes glances at
Slack or Teams, which must not split the session.
"""

import random
from datetime import date, timedelta

from career.events.models import Event, EventType
from tests.fixtures.loader import at

SUP = ["temperature_test.py — supervisor — Visual Studio Code", "AI-1842 Temperature Test - Jira - Google Chrome",
       "alex@nxp-lab: ~/work/supervisor", "Temperature_Result.xlsx - Excel"]
SUP_APPS = ["VS Code", "Chrome", "Terminal", "Excel"]
VU = ["version_updater.py — VersionUpdater_v2.3 — Visual Studio Code", "alex@desk: ~/VersionUpdater_v2.3",
      "devices.csv — VersionUpdater_v2.3 — Visual Studio Code"]
VU_APPS = ["VS Code", "Terminal", "VS Code"]
MAI = ["MAI-311 Camera freeze on boot - Jira - Google Chrome", "test_camera.py — mobilai — Visual Studio Code",
       "alex@desk: ~/work/mobilai"]
MAI_APPS = ["Chrome", "VS Code", "Terminal"]
LOG = ["parse.py — logParser_v2 — Visual Studio Code", "alex@desk: ~/logParser_v2", "device_0412.tm — logParser_v2 — Visual Studio Code"]
LOG_APPS = ["VS Code", "Terminal", "VS Code"]
MAIL = ["Inbox - alex@example.com - Outlook"]
MAIL_APPS = ["Outlook"]
DISTRACT = [("Slack", "Slack | #field-ops | Acme"), ("Teams", "Chat | Microsoft Teams")]

# (start, minutes, titles, apps, pause after in minutes)
PLAN = [
    ("08:55", 20, MAIL, MAIL_APPS, 3),
    ("09:18", 46, SUP, SUP_APPS, 0),
    ("10:04", 38, VU, VU_APPS, 12),
    ("10:54", 30, MAI, MAI_APPS, 0),
    ("11:24", 36, SUP, SUP_APPS, 55),
    ("12:55", 15, MAIL, MAIL_APPS, 0),
    ("13:10", 52, LOG, LOG_APPS, 4),
    ("14:06", 28, MAI, MAI_APPS, 0),
    ("14:34", 41, VU, VU_APPS, 18),
    ("15:33", 33, SUP, SUP_APPS, 0),
    ("16:06", 25, LOG, LOG_APPS, 7),
    ("16:38", 22, MAI, MAI_APPS, 0),
]
DAY = date(2026, 10, 16)


def generate(seed: int = 7) -> list[Event]:
    rng = random.Random(seed)
    events: list[Event] = []
    n = 0

    def emit(ts, type_, app=None, title=None):
        nonlocal n
        events.append(Event(id=f"day-{n}", timestamp=ts, type=type_, application=app, window_title=title, source="fixture"))
        n += 1

    for start, minutes, titles, apps, pause in PLAN:
        t = at(DAY, start + ":00")
        end = t + timedelta(minutes=minutes)
        while t < end:
            if rng.random() < 0.08:
                app, title = rng.choice(DISTRACT)
            else:
                i = rng.randrange(len(titles))
                app, title = apps[i], titles[i]
            emit(t, EventType.WINDOW_FOCUS, app, title)
            t += timedelta(seconds=rng.randint(15, 90))
        if pause >= 5:
            emit(end, EventType.IDLE_STARTED)
            emit(end + timedelta(minutes=pause), EventType.IDLE_ENDED)
    emit(events[-1].timestamp + timedelta(seconds=30), EventType.AGENT_STOPPED)
    return events
