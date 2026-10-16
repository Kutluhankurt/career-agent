"""Career Memory Engine: the pipeline from a day's events to remembered career facts.

    events → sessions → context → project → analysis (rules / AI) → skills
           → achievements → review queue

Running it again is safe: user decisions (confirmed, rejected, edited) are never
overwritten, and AI is only re-asked when a session actually changed.
"""

import logging
from dataclasses import dataclass
from datetime import date, timedelta

from career.ai.base import AIProvider
from career.analysis.analyzer import AI_FAILED, analyze
from career.analysis.context import ProfileContext, build_context
from career.analysis.models import WorkSession
from career.analysis.service import day_bounds, rebuild_day
from career.career.achievements import detect_achievements
from career.career.evidence import EvidenceType, TruthState, make_evidence
from career.career.projects import ProjectEngine, ensure_profile_projects
from career.career.review import learning_day, sync_review
from career.career.skills import update_skills
from career.career.store import MemoryStore
from career.config.settings import Settings
from career.database.database import Database
from career.database.models import AnalysisRow

log = logging.getLogger(__name__)


@dataclass
class UpdateResult:
    day: date
    events: int
    sessions: int
    analyzed: int
    ai_analyzed: int
    pending_ai: int
    review_count: int


def _evidence_for(session: WorkSession, ctx, values: list[str]) -> list[dict]:
    tickets, files, commands = set(ctx.tickets), set(ctx.files), set(ctx.commands)
    commits = {c.hash: c for g in ctx.git for c in g.commits}
    out = []
    for v in values:
        if v in tickets:
            t = EvidenceType.TICKET
        elif v in commits:
            t, v = EvidenceType.GIT, f"{v} {commits[v].message}".strip()
        elif v in files:
            t = EvidenceType.FILE
        elif v in commands:
            t = EvidenceType.COMMAND
        elif v in ctx.sites:
            t = EvidenceType.BROWSER
        elif v in ctx.applications:
            t = EvidenceType.APPLICATION
        else:
            t = EvidenceType.WINDOW
        out.append(make_evidence(t, v, session.id, session.start).model_dump(mode="json"))
    return out


class MemoryEngine:
    def __init__(self, db: Database, settings: Settings, provider: AIProvider | None = None):
        self.db = db
        self.settings = settings
        self.provider = provider
        self.store = MemoryStore(db)

    def update_day(self, day: date, open_until=None, use_ai: bool = True, deep: bool = False) -> UpdateResult:
        n_events, sessions = rebuild_day(self.db, self.settings, day, open_until=open_until)
        since, until = day_bounds(day)
        events = self.db.list_events(since=since, until=until)
        profile = self.store.get_profile()
        ensure_profile_projects(self.store)
        learning = learning_day(self.store, day) is not None
        projects = ProjectEngine(self.store, learning=learning)
        pctx = ProfileContext(job_title=profile.job_title, focus=profile.focus, projects=profile.projects, tools=profile.tools)
        provider = self.provider if use_ai else None

        analyzed = ai_count = pending_ai = 0
        for session in sessions:
            ctx = build_context(session, events, pctx)
            project = projects.resolve(ctx, session.active_seconds)
            if project:
                ctx.projects = [project.name]
            row = self.store.get(AnalysisRow, session.id)
            if row and (row.edited or row.state in (TruthState.CONFIRMED, TruthState.REJECTED)):
                # the user decided: keep their answer, only refresh the measured facts
                row.active_seconds = session.active_seconds
                if not row.edited and project and row.project_id is None:
                    row.project_id = project.id
                self.store.save(row)
                continue
            # re-analyze only when the session grew or nothing exists yet; never re-ask the AI
            # for an unchanged session it already analyzed
            unchanged = row is not None and row.session_events == session.event_count
            if unchanged and not deep and (row.provider != "rules" or row.model == AI_FAILED or session.is_open or not provider):
                continue
            # AI looks at finished sessions only; open ones get rules for now
            use_provider = provider if not session.is_open else None
            result, by, model = analyze(ctx, project.name if project else None, use_provider, deep=deep)
            if provider and by == "rules" and model != AI_FAILED and not session.is_open and result.confidence < 0.8:
                pending_ai += 1  # the AI wasn't reachable: these wait for the next run
            now = self.store.now()
            self.store.save(AnalysisRow(
                session_id=session.id, day=day.isoformat(), activity=result.activity, category=result.category,
                project_id=project.id if project else None, confidence=result.confidence, skills=result.skills,
                evidence=_evidence_for(session, ctx, result.evidence), state=TruthState.INFERRED.value,
                provider=by, model=model, session_events=session.event_count, active_seconds=session.active_seconds,
                edited=False, created_at=row.created_at if row else now, updated_at=now,
            ))
            analyzed += 1
            ai_count += by != "rules"

        projects.save_state()
        update_skills(self.store, day)
        session_map = {s.id: s for s in self.db.list_sessions(since=day_bounds(day - timedelta(days=60))[0])}
        detect_achievements(self.store, session_map, day)
        review_count = sync_review(self.store, day)
        self.store.set_state("last_update", {"day": day.isoformat(), "at": self.store.now().isoformat(),
                                             "pending_ai": pending_ai})
        return UpdateResult(day, n_events, len(sessions), analyzed, ai_count, pending_ai, review_count)

    def update_range(self, start: date, end: date, **kwargs) -> list[UpdateResult]:
        out, day = [], start
        while day <= end:
            out.append(self.update_day(day, **kwargs))
            day += timedelta(days=1)
        return out


__all__ = ["MemoryEngine", "UpdateResult"]
