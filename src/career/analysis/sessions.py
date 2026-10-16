"""Session Engine: raw events → meaningful work sessions, with deterministic rules.

1. Spans    Each window_focus lasts until the next boundary event. Idle, sleep and
            agent shutdown end a span; time without a span is a pause.
2. Blocks   A pause of at least `split_gap` always starts a new session.
3. Context  Inside a block, work switches to a new session only when a different
            workspace or ticket holds for at least `switch_min`, or an app not yet
            used in the session holds for 3 × `switch_min`. Shorter excursions (a look
            at Slack, another repo, a docs page) stay in the current session.
4. Tidy     Sessions shorter than `min_session` merge into a neighbour.
5. Score    Coherence from project evidence, app consistency and length.

AI is never used here (roadmap §17); it later receives these sessions as input.
"""

import uuid
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from career.analysis import signals as sig
from career.analysis.models import WorkSession
from career.config.settings import SessionSettings
from career.events.models import Event, EventType

_NAMESPACE = uuid.UUID("6f1d1a7e-6c1b-4f7e-9a59-2b8f0c3e5d10")
_ENDS_SPAN = {EventType.IDLE_STARTED, EventType.IDLE_ENDED, EventType.AGENT_STARTED, EventType.AGENT_STOPPED}


@dataclass
class Span:
    start: datetime
    end: datetime
    application: str | None
    title: str | None
    event_id: str
    signals: sig.Signals

    @property
    def seconds(self) -> float:
        return (self.end - self.start).total_seconds()


@dataclass
class _Segment:
    spans: list[Span] = field(default_factory=list)
    workspaces: set[str] = field(default_factory=set)
    tickets: set[str] = field(default_factory=set)
    apps: set[str | None] = field(default_factory=set)

    def add(self, span: Span) -> None:
        self.spans.append(span)
        self.workspaces |= span.signals.workspaces
        self.tickets |= span.signals.tickets
        self.apps.add(span.application)

    def absorb(self, other: "_Segment") -> None:
        for span in other.spans:
            self.add(span)
        self.spans.sort(key=lambda s: s.start)

    @property
    def keyed(self) -> bool:
        return bool(self.workspaces or self.tickets)

    @property
    def active(self) -> float:
        return sum(s.seconds for s in self.spans)

    def compatible(self, span: Span, switch_min: float) -> bool:
        """Could `span` be part of the same work as this segment?"""
        if not self.spans:
            return True
        s = span.signals
        if s.keyed:
            if not self.keyed:
                # project work after an established stretch of unkeyed work (e.g. 20 min
                # of e-mail) is new work; right at the start it's just the warm-up.
                return self.active < switch_min
            if s.workspaces and self.workspaces and not (s.workspaces & self.workspaces):
                return False
            if s.tickets and self.tickets and not (s.tickets & self.tickets):
                return False
            if s.tickets and not self.tickets and self.active >= switch_min:
                # a ticket appearing in long-running ticketless work is more likely
                # another task than this one; it must hold to count (or return).
                return False
            return True
        # Unkeyed window: fine if this app is already part of the work.
        return span.application in self.apps


class SessionEngine:
    def __init__(self, settings: SessionSettings | None = None, idle_threshold: float = 300.0):
        self.settings = settings or SessionSettings()
        self.idle_threshold = idle_threshold

    # public --------------------------------------------------------------
    def build(self, events: list[Event], open_until: datetime | None = None) -> list[WorkSession]:
        """Build sessions. `open_until` is "now" while the agent is still running,
        so the current focus extends to the present; otherwise the last focus is
        assumed to have lasted at most `idle_threshold`."""
        spans = self.build_spans(events, open_until)
        sessions: list[WorkSession] = []
        for block in self._blocks(spans):
            for segment in self._tidy(self._segment(block)):
                sessions.append(self._to_session(segment))
        if open_until is not None and sessions:
            last = sessions[-1]
            last.is_open = (open_until - last.end).total_seconds() < self.settings.split_gap
        return sessions

    def build_spans(self, events: list[Event], open_until: datetime | None = None) -> list[Span]:
        spans: list[Span] = []
        current: Event | None = None
        idle = False
        for event in sorted(events, key=lambda e: e.timestamp):
            if event.type != EventType.WINDOW_FOCUS and event.type not in _ENDS_SPAN:
                continue  # file/git/browser events add context later; they don't move focus
            if event.type == EventType.IDLE_STARTED:
                idle = True
            elif event.type in (EventType.IDLE_ENDED, EventType.AGENT_STARTED):
                idle = False
            elif event.type == EventType.WINDOW_FOCUS and idle:
                continue  # a window that changed while nobody was at the keyboard
            if current is not None:
                end = event.timestamp
                if event.type == EventType.AGENT_STARTED:
                    # the agent restarted without a clean stop (crash, power loss):
                    # we don't know how long that last window really lasted
                    end = min(end, current.timestamp + timedelta(seconds=self.idle_threshold))
                self._close(spans, current, end)
                current = None
            if event.type == EventType.WINDOW_FOCUS:
                current = event
        if current is not None:
            limit = current.timestamp + timedelta(seconds=self.idle_threshold)
            end = open_until if open_until is not None and open_until > current.timestamp else limit
            self._close(spans, current, end)
        return spans

    # steps ---------------------------------------------------------------
    def _close(self, spans: list[Span], event: Event, end: datetime) -> None:
        end = min(end, event.timestamp + timedelta(seconds=self.settings.max_span))
        if end <= event.timestamp:
            return
        spans.append(
            Span(
                start=event.timestamp,
                end=end,
                application=event.application,
                title=event.window_title,
                event_id=event.id,
                signals=sig.extract(event.application, event.window_title),
            )
        )

    def _blocks(self, spans: list[Span]) -> list[list[Span]]:
        blocks: list[list[Span]] = []
        for span in spans:
            if blocks and (span.start - blocks[-1][-1].end).total_seconds() < self.settings.split_gap:
                blocks[-1].append(span)
            else:
                blocks.append([span])
        return blocks

    def _segment(self, block: list[Span]) -> list[_Segment]:
        switch_min = self.settings.switch_min
        done: list[_Segment] = []
        current = _Segment()
        pending: _Segment | None = None
        for span in block:
            if pending is None:
                if current.compatible(span, switch_min):
                    current.add(span)
                else:
                    pending = _Segment()
                    pending.add(span)
            elif span.signals.keyed:
                if current.compatible(span, switch_min):
                    # back to the original work before the switch held: an excursion
                    current.absorb(pending)
                    current.add(span)
                    pending = None
                elif pending.compatible(span, switch_min):
                    pending.add(span)
                else:
                    # a third project: the previous excursion didn't hold either
                    current.absorb(pending)
                    pending = _Segment()
                    pending.add(span)
            elif not pending.keyed and span.application in current.apps and span.application not in pending.apps:
                # the excursion was only a glance (chat, mail); work continues
                current.absorb(pending)
                current.add(span)
                pending = None
            else:
                # unkeyed windows while switching belong to the switch
                pending.add(span)

            if pending is not None and pending.active >= self._switch_after(pending):
                done.append(current)
                current, pending = pending, None
        if pending is not None:
            if pending.active >= self._switch_after(pending):
                done.append(current)
                current = pending
            else:
                current.absorb(pending)
        done.append(current)
        return done

    def _switch_after(self, pending: _Segment) -> float:
        # A different project is clear evidence; a different unkeyed app (docs, chat,
        # e-mail) has to hold three times as long before it counts as new work.
        return self.settings.switch_min if pending.keyed else self.settings.switch_min * 3

    def _tidy(self, segments: list[_Segment]) -> list[_Segment]:
        """Merge too-short segments into the previous one (or the next one)."""
        result: list[_Segment] = []
        carry: _Segment | None = None
        for seg in segments:
            if carry is not None:
                seg.absorb(carry)
                carry = None
            if seg.active >= self.settings.min_session:
                result.append(seg)
            elif result:
                result[-1].absorb(seg)
            else:
                carry = seg
        if carry is not None:
            if result:
                result[-1].absorb(carry)
            elif carry.active >= self.settings.min_session:
                result.append(carry)
        return [s for s in result if s.active >= self.settings.min_session]

    def _to_session(self, seg: _Segment) -> WorkSession:
        spans = seg.spans
        active = seg.active
        apps: dict[str, float] = defaultdict(float)
        workspaces: dict[str, float] = defaultdict(float)
        tickets: dict[str, float] = defaultdict(float)
        files: dict[str, float] = defaultdict(float)
        titles: Counter[str] = Counter()
        for s in spans:
            apps[s.application or "Unknown"] += s.seconds
            for w in s.signals.workspaces:
                workspaces[w] += s.seconds
            for t in s.signals.tickets:
                tickets[t] += s.seconds
            for f in s.signals.files:
                files[f] += s.seconds
            if s.title:
                titles[s.title] += s.seconds

        start, end = spans[0].start, spans[-1].end
        return WorkSession(
            id=str(uuid.uuid5(_NAMESPACE, spans[0].event_id)),
            start=start,
            end=end,
            active_seconds=round(active, 1),
            idle_seconds=round(max(0.0, (end - start).total_seconds() - active), 1),
            event_count=len(spans),
            label=self._label(apps, workspaces, tickets),
            score=self._score(spans, active, apps, _ranked(workspaces), _ranked(tickets)),
            applications=_ranked(apps),
            workspaces=_ranked(workspaces),
            tickets=_ranked(tickets),
            files=_ranked(files, limit=15),
            titles=[t for t, _ in titles.most_common(5)],
            event_ids=[s.event_id for s in spans],
        )

    @staticmethod
    def _label(apps, workspaces, tickets) -> str:
        parts = []
        if workspaces:
            parts.append(max(workspaces, key=workspaces.get))
        if tickets:
            parts.append(max(tickets, key=tickets.get))
        if parts:
            return " · ".join(parts)
        return max(apps, key=apps.get) if apps else "Unknown"

    @staticmethod
    def _score(spans, active, apps, workspaces, tickets) -> float:
        """Coherence of the session, from rules only:
        evidence     share of time whose window names this session's project/ticket
        consistency  share of time in the session's three main apps
        length       20 minutes or more earns full credit
        Without any project evidence a session tops out around 0.5 ("weak")."""
        if active <= 0:
            return 0.0
        keys_ws = set(list(workspaces)[:2])
        keys_t = set(list(tickets)[:2])
        evidence = sum(
            s.seconds for s in spans if (s.signals.workspaces & keys_ws) or (s.signals.tickets & keys_t)
        ) / active
        consistency = sum(sorted(apps.values(), reverse=True)[:3]) / active
        length = min(1.0, active / 1200.0)
        return round(min(1.0, 0.5 * evidence + 0.25 * consistency + 0.25 * length), 2)


def _ranked(values: dict[str, float], limit: int | None = None) -> dict[str, float]:
    items = sorted(values.items(), key=lambda kv: kv[1], reverse=True)
    return {k: round(v, 1) for k, v in items[:limit]}
