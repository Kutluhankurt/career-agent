import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from career.events.models import Event, EventType

FIXTURES = Path(__file__).parent
TZ = timezone(timedelta(hours=3))  # Europe/Istanbul, fixed so tests don't depend on the machine


def at(day: date, hhmmss: str) -> datetime:
    h, m, s = map(int, hhmmss.split(":"))
    return datetime(day.year, day.month, day.day, h, m, s, tzinfo=TZ)


def load(name: str) -> tuple[dict, list[Event]]:
    data = json.loads((FIXTURES / f"{name}.json").read_text(encoding="utf-8"))
    day = date.fromisoformat(data["date"])
    events = [
        Event(id=f"{name}-{i}", timestamp=at(day, t), type=EventType(type_), application=app, window_title=title, source="fixture")
        for i, (t, type_, app, title) in enumerate(data["events"])
    ]
    return data, events
