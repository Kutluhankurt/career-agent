"""Turns periodic collector samples into normalized events.

This is shared by every platform: collectors only answer "what is focused?" and
"how long since input?"; deciding when something is an event happens here.

    focus changes            → window_focus
    idle crosses threshold   → idle_started (timestamped when input actually stopped)
    input resumes            → idle_ended (and the current window is re-emitted)
    sampling stalled         → idle_started + idle_ended around the gap (laptop sleep,
                               suspended VM), so sleeping time never counts as work
"""

import logging
import re
from collections.abc import Callable
from datetime import datetime, timedelta

from career.collector.base import ActiveWindow, ActivityCollector
from career.events.models import Event, EventType, utc_now
from career.events.normalizer import normalize_application

log = logging.getLogger(__name__)

BROWSERS = {"Chrome", "Chromium", "Firefox", "Edge", "Safari", "Brave", "Opera", "Vivaldi", "Arc"}
PRIVATE_APP = "Private"

# Things that look like credentials never reach the database, even inside window titles.
_SECRET_PATTERNS = [
    re.compile(r"\b(sk-[A-Za-z0-9_\-]{16,}|sk-ant-[A-Za-z0-9_\-]{16,}|gh[pousr]_[A-Za-z0-9]{20,}|xox[abprs]-[A-Za-z0-9-]{10,}|AKIA[0-9A-Z]{16}|AIza[0-9A-Za-z_\-]{30,})"),
    re.compile(r"(?i)\b(password|passwd|pwd|token|secret|api[_-]?key)\s*[=:]\s*\S+"),
]
_PRIVATE_TITLE_RE = re.compile(r"(?i)(incognito|inprivate|private browsing|1password|bitwarden|keepass|lastpass|keychain access)")


# Spinners and status marks that tools put in front of titles ("✳ Task", "◐ Task", "⠋ npm",
# "● file.py" for unsaved). They change every second and would turn one window into hundreds
# of events. Letters (including Turkish ones) and ASCII are never stripped.
_LEADING_GLYPHS_RE = re.compile(r"^(?:[^\w\s\x00-\x7F]+\s*)+")


def clean_title(title: str | None) -> str | None:
    if not title:
        return title
    cleaned = _LEADING_GLYPHS_RE.sub("", title).strip()
    return cleaned or title


def redact(title: str | None) -> str | None:
    if not title:
        return title
    for pattern in _SECRET_PATTERNS:
        title = pattern.sub("[redacted]", title)
    return title


class EventProcessor:
    def __init__(
        self,
        collector: ActivityCollector,
        idle_threshold: float = 300.0,
        clock: Callable[[], datetime] = utc_now,
        suspend_gap: float = 90.0,
        excluded_apps: list[str] | None = None,
        browser_tracking: bool = True,
    ):
        self.collector = collector
        self.excluded_apps = {a.casefold() for a in (excluded_apps or [])}
        self.browser_tracking = browser_tracking
        self.idle_threshold = idle_threshold
        self.clock = clock
        self.suspend_gap = suspend_gap
        self.is_idle = False
        self._last_focus: tuple[str | None, str | None] | None = None
        self._last_tick: datetime | None = None

    def tick(self) -> list[Event]:
        now = self.clock()
        events: list[Event] = []

        last, self._last_tick = self._last_tick, now
        if last is not None and (now - last).total_seconds() >= self.suspend_gap:
            if not self.is_idle:
                events.append(self._event(EventType.IDLE_STARTED, last, reason="suspended"))
            events.append(self._event(EventType.IDLE_ENDED, now, reason="resumed"))
            self.is_idle = False
            self._last_focus = None

        idle = self._safe(self.collector.get_idle_time)
        if idle is not None:
            if not self.is_idle and idle >= self.idle_threshold:
                self.is_idle = True
                events.append(self._event(EventType.IDLE_STARTED, now - timedelta(seconds=idle), idle_seconds=round(idle, 1)))
            elif self.is_idle and idle < self.idle_threshold:
                self.is_idle = False
                self._last_focus = None  # re-emit focus so the new activity has a start
                events.append(self._event(EventType.IDLE_ENDED, now - timedelta(seconds=idle)))

        if not self.is_idle:
            window = self._safe(self.collector.get_active_window)
            if window is not None:
                focus_event = self._focus_event(window, now)
                if focus_event:
                    events.append(focus_event)
        return events

    def _focus_event(self, window: ActiveWindow, now: datetime) -> Event | None:
        app = normalize_application(window.application) or normalize_application(window.process)
        title = redact(clean_title(window.title))
        private = bool(app and app.casefold() in self.excluded_apps) or bool(title and _PRIVATE_TITLE_RE.search(title))
        if private:
            app, title = PRIVATE_APP, None  # time is accounted for, but nothing about it is kept
        elif app in BROWSERS and not self.browser_tracking:
            title = None
        key = (app, title)
        if key == self._last_focus or (app is None and title is None):
            return None
        self._last_focus = key
        meta = {} if private else {
            k: v for k, v in {"pid": window.pid, "process": window.process, **window.extra}.items() if v is not None
        }
        return Event(
            timestamp=now,
            type=EventType.WINDOW_FOCUS,
            application=app,
            window_title=title,
            source=self.collector.source,
            metadata=meta,
        )

    def _event(self, type: EventType, timestamp: datetime, **meta) -> Event:
        return Event(timestamp=timestamp, type=type, source=self.collector.source, metadata=meta)

    @staticmethod
    def _safe(probe):
        # One failing probe must never stop collection.
        try:
            return probe()
        except Exception:  # noqa: BLE001
            log.exception("Collector probe %s failed", getattr(probe, "__name__", probe))
            return None
