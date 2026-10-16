"""Read models shared by the CLI and the dashboard API (shapes follow docs/API.md)."""

from collections import Counter, defaultdict
from datetime import date, datetime, timedelta
from typing import Any

from career.analysis.models import WorkSession
from career.analysis.service import day_bounds
from career.career.evidence import TruthState
from career.career.review import describe
from career.career.skills import category_of, score_skills
from career.career.store import MemoryStore
from career.database.database import Database
from career.database.models import AchievementRow, AnalysisRow, ProjectRow

STEP_NAMES = ["problem", "investigation", "implementation", "testing", "verification"]


def iso(value: datetime | None) -> str | None:
    return value.astimezone().isoformat() if value else None


class Reports:
    def __init__(self, db: Database):
        self.db = db
        self.store = MemoryStore(db)
        self._projects = {p.id: p for p in self.store.all(ProjectRow)}

    # refs ---------------------------------------------------------------------------
    def project_ref(self, project_id: str | None) -> dict | None:
        p = self._projects.get(project_id) if project_id else None
        while p is not None and p.merged_into:
            p = self._projects.get(p.merged_into)
        if p is None or p.state == TruthState.REJECTED:
            return None
        return {"id": p.id, "name": p.name, "color": p.color}

    # sessions -------------------------------------------------------------------------
    def session(self, s: WorkSession, a: AnalysisRow | None = None) -> dict:
        a = a if a is not None else self.store.get(AnalysisRow, s.id)
        return {
            "id": s.id, "start": iso(s.start), "end": iso(s.end), "active_seconds": s.active_seconds,
            "idle_seconds": s.idle_seconds, "is_open": s.is_open, "label": s.label,
            "activity": a.activity if a else s.label, "category": a.category if a else "Other",
            "project": self.project_ref(a.project_id) if a else None,
            "state": a.state if a else TruthState.INFERRED.value,
            "confidence": a.confidence if a else s.score, "score": s.score,
            "skills": (a.skills if a else []) or [], "evidence": (a.evidence if a else []) or [],
            "applications": s.applications, "files": list(s.files), "tickets": list(s.tickets),
            "workspaces": list(s.workspaces), "analyzed_by": a.provider if a else None,
        }

    def sessions(self, day: date) -> list[dict]:
        since, until = day_bounds(day)
        rows = self.db.list_sessions(since=since, until=until)
        analyses = {a.session_id: a for a in self.store.analyses(since_day=day.isoformat(), until_day=day.isoformat())}
        return [self.session(s, analyses.get(s.id)) for s in rows]

    def session_detail(self, session_id: str) -> dict | None:
        s = next((x for x in self.db.list_sessions() if x.id == session_id), None)
        if s is None:
            return None
        events = self.db.list_events(since=s.start, until=s.end + timedelta(seconds=1))
        ids = set(s.event_ids)
        raw = [{"timestamp": iso(e.timestamp), "type": e.type.value, "application": e.application, "title": e.window_title}
               for e in events if e.id in ids or e.type.value in ("file_changed", "git_activity", "idle_started", "idle_ended")]
        return {**self.session(s), "raw_events": raw}

    # today -----------------------------------------------------------------------------
    def today(self, day: date) -> dict:
        sessions = self.sessions(day)
        meaningful = [s for s in sessions if s["state"] != TruthState.REJECTED]
        monday = day - timedelta(days=day.weekday())
        week = []
        for i in range(7):
            d = monday + timedelta(days=i)
            since, until = day_bounds(d)
            week.append({"date": d.isoformat(), "active_seconds": round(sum(
                s.active_seconds for s in self.db.list_sessions(since=since, until=until)))})
        skills = self.skill_summaries(day)[:4]
        potential = [self.achievement(a) for a in self.store.achievements()
                     if a.state in (TruthState.INFERRED, TruthState.CONFIRMED)][-3:]
        return {
            "date": day.isoformat(), "name": self.store.get_profile().first_name,
            "active_seconds": round(sum(s["active_seconds"] for s in meaningful)),
            "session_count": len(meaningful),
            "project_count": len({s["project"]["id"] for s in meaningful if s["project"]}),
            "ribbon": [{"start": s["start"], "end": s["end"], "label": s["activity"],
                        "color": s["project"]["color"] if s["project"] else None} for s in meaningful],
            "current_session": next((s for s in sessions if s["is_open"]), None),
            "review_count": len(self.review_items()),
            "top_skills": skills,
            "week": week, "week_total_seconds": sum(w["active_seconds"] for w in week),
            "potential_achievements": potential,
        }

    # skills ---------------------------------------------------------------------------
    def _scores(self, as_of: date):
        return score_skills(self.store.analyses(), {s.name: s.state for s in self.store.skills()}, as_of)

    def skill_summaries(self, day: date) -> list[dict]:
        now, before = self._scores(day), self._scores(day - timedelta(days=7))
        out = [{"name": n, "score": s.score, "delta": s.score - (before[n].score if n in before else 0)} for n, s in now.items()]
        return sorted(out, key=lambda x: -x["score"])

    def skills(self, day: date) -> list[dict]:
        from career.career.skills import skill_history

        rows = {s.name: s for s in self.store.skills()}
        now, before = self._scores(day), self._scores(day - timedelta(days=7))
        history = skill_history(self.store, day, 30)
        out = []
        for name, s in now.items():
            row = rows.get(name)
            out.append({
                "id": row.id if row else name, "name": name, "category": row.category if row else category_of(name),
                "state": row.state if row else TruthState.INFERRED.value, "score": s.score,
                "previous_score": before[name].score if name in before else 0, "factors": s.factors,
                "history": self._full_history(history.get(name, []), day),
                "projects": [self._projects[p].name for p in s.projects if p in self._projects],
                "evidence_count": s.evidence_count, "active_seconds": round(s.active_seconds),
            })
        return sorted(out, key=lambda x: -x["score"])

    @staticmethod
    def _full_history(points: list[tuple[str, float]], day: date) -> list[dict]:
        known = dict(points)
        days = [(day - timedelta(days=29 - i)).isoformat() for i in range(30)]
        return [{"date": d, "score": known.get(d, 0)} for d in days]

    # achievements ------------------------------------------------------------------------
    def achievement(self, a: AchievementRow) -> dict:
        steps = a.steps or {}
        return {
            "id": a.id, "title": a.title, "project": self.project_ref(a.project_id), "ticket": a.ticket,
            "state": a.state, "confidence": a.confidence,
            "steps": [{"name": n, "done": bool(steps.get(n)), "evidence": steps.get(n, [])} for n in STEP_NAMES],
            "impact": a.impact, "on_cv": a.on_cv, "created_at": iso(a.created_at),
        }

    def achievements(self) -> list[dict]:
        return [self.achievement(a) for a in reversed(self.store.achievements()) if a.state != TruthState.REJECTED]

    # projects ------------------------------------------------------------------------------
    def project(self, p: ProjectRow, today: date | None = None) -> dict:
        today = today or date.today()
        rows = [a for a in self.store.analyses() if a.project_id == p.id and a.state != TruthState.REJECTED]
        daily = defaultdict(float)
        for a in rows:
            daily[a.day] += a.active_seconds
        sparkline = [round(daily.get((today - timedelta(days=29 - i)).isoformat(), 0)) for i in range(30)]
        tickets = sorted({e["value"] for a in rows for e in (a.evidence or []) if e["type"] == "ticket"})
        skills = Counter(s for a in rows for s in (a.skills or []))
        return {
            "id": p.id, "name": p.name, "state": p.state, "color": p.color, "aliases": p.aliases or [],
            "active_seconds": round(sum(a.active_seconds for a in rows)), "session_count": len(rows),
            "tickets": tickets,
            "repos": sorted({al.split(":", 1)[1] for al in (p.aliases or []) if al.startswith(("workspace:", "repo:"))}),
            "skills": [s for s, _ in skills.most_common(6)],
            "achievement_count": sum(1 for a in self.store.achievements() if a.project_id == p.id and a.state != TruthState.REJECTED),
            "sparkline": sparkline, "last_active": max((a.day for a in rows), default=None),
        }

    def projects(self) -> list[dict]:
        out = [self.project(p) for p in self.store.projects() if p.state != TruthState.REJECTED]
        return sorted(out, key=lambda x: -x["active_seconds"])

    def project_detail(self, project_id: str) -> dict | None:
        p = self._projects.get(project_id)
        if p is None:
            return None
        days = sorted({a.day for a in self.store.analyses() if a.project_id == p.id}, reverse=True)[:7]
        sessions = [s for d in days for s in self.sessions(date.fromisoformat(d)) if s["project"] and s["project"]["id"] == p.id]
        achievements = [self.achievement(a) for a in self.store.achievements() if a.project_id == p.id]
        return {**self.project(p), "sessions": sessions[:30], "achievements": achievements}

    # review ----------------------------------------------------------------------------------
    def review_items(self) -> list[dict]:
        items = []
        for r in self.store.reviews():
            d = describe(r, self.store)
            if d is None:
                continue
            subtitle = d["subtitle"]
            if r.kind == "session" and d.get("sessions"):
                first = min(d["sessions"], key=lambda a: a.created_at)
                subtitle = f"{subtitle} · {date.fromisoformat(first.day):%a %d %b}"
            items.append({
                "id": r.id, "kind": r.kind, "ref_id": r.ref_id, "title": d["title"], "subtitle": subtitle,
                "project": self.project_ref(d["project_id"]), "confidence": d["confidence"], "skills": d["skills"],
                "evidence": d["evidence"], "options": d["options"], "created_at": iso(r.created_at),
            })
        return items

    # memory ------------------------------------------------------------------------------------
    def memory(self, type_: str | None = None, state: str | None = None) -> dict:
        items: list[dict[str, Any]] = []
        for p in self.projects():
            items.append({"id": p["id"], "type": "project", "name": p["name"], "state": p["state"], "project": None,
                          "detail": f"{round(p['active_seconds'] / 3600, 1)}h · {p['session_count']} sessions",
                          "updated_at": p["last_active"] or ""})
        for s in self.skills(date.today()):
            items.append({"id": s["id"], "type": "skill" if s["category"] != "Tool" else "technology", "name": s["name"],
                          "state": s["state"], "project": None, "detail": f"{s['category']} · {s['score']}", "updated_at": ""})
        for a in self.achievements():
            items.append({"id": a["id"], "type": "achievement", "name": a["title"], "state": a["state"],
                          "project": a["project"]["name"] if a["project"] else None,
                          "detail": f"{sum(st['done'] for st in a['steps'])} of 5 steps", "updated_at": a["created_at"] or ""})
        for a in reversed(self.store.analyses()[-200:]):
            ref = self.project_ref(a.project_id)
            items.append({"id": a.session_id, "type": "session", "name": a.activity, "state": a.state,
                          "project": ref["name"] if ref else None, "detail": f"{a.day} · {round(a.active_seconds / 60)} min",
                          "updated_at": iso(a.updated_at)})
        counts = Counter(i["state"] for i in items)
        if type_:
            items = [i for i in items if i["type"] == type_]
        if state:
            items = [i for i in items if i["state"] == state]
        return {"items": items, "counts": {s.value: counts.get(s.value, 0) for s in TruthState}}

    # insights -------------------------------------------------------------------------------------
    def insights(self, period: str, today: date | None = None) -> dict:
        today = today or date.today()
        if period == "month":
            start = today.replace(day=1)
            prev_start = (start - timedelta(days=1)).replace(day=1)
        else:
            start = today - timedelta(days=today.weekday())
            prev_start = start - timedelta(days=7)
        rows = [a for a in self.store.analyses(since_day=start.isoformat(), until_day=today.isoformat())
                if a.state != TruthState.REJECTED]
        prev = [a for a in self.store.analyses(since_day=prev_start.isoformat(), until_day=(start - timedelta(days=1)).isoformat())
                if a.state != TruthState.REJECTED]
        total = sum(a.active_seconds for a in rows) or 0
        per_project = defaultdict(float)
        for a in rows:
            per_project[a.project_id] += a.active_seconds
        projects = []
        for pid, sec in sorted(per_project.items(), key=lambda kv: -kv[1]):
            ref = self.project_ref(pid)
            projects.append({"name": ref["name"] if ref else "No project", "color": ref["color"] if ref else -1,
                             "seconds": round(sec), "share": round(sec / total, 3) if total else 0})
        acts = defaultdict(lambda: [0.0, 0])
        for a in rows:
            acts[a.activity][0] += a.active_seconds
            acts[a.activity][1] += 1
        top = [{"name": n, "seconds": round(v[0]), "count": v[1]} for n, v in sorted(acts.items(), key=lambda kv: -kv[1][0])[:6]]
        now, before = self._scores(today), self._scores(start - timedelta(days=1))
        deltas = [{"name": n, "score": s.score, "delta": s.score - (before[n].score if n in before else 0)} for n, s in now.items()]
        cats = Counter((a.category, a.project_id) for a in rows)
        repeated = []
        for (cat, pid), n in cats.most_common(4):
            if n >= 3 and cat not in ("Other", "Communication"):
                ref = self.project_ref(pid)
                repeated.append(f"{n} {cat.lower()} sessions" + (f" on {ref['name']}" if ref else ""))
        recent_projects = {a.project_id for a in rows}
        stopped = []
        for pid in {a.project_id for a in prev} - recent_projects:
            ref = self.project_ref(pid)
            if ref:
                last = max(a.day for a in prev if a.project_id == pid)
                stopped.append(f"No {ref['name']} work since {date.fromisoformat(last):%d %b}")
        by_day = []
        d = start
        while d <= today:
            by_day.append({"date": d.isoformat(), "active_seconds": round(sum(a.active_seconds for a in rows if a.day == d.isoformat()))})
            d += timedelta(days=1)
        achievements = [self.achievement(a) for a in self.store.achievements()
                        if a.state != TruthState.REJECTED and a.updated_at.astimezone().date() >= start]
        cv_keys = {b.key for b in self.store.cv_bullets()}
        return {
            "period": period, "start": start.isoformat(), "end": today.isoformat(), "active_seconds": round(total),
            "session_count": len(rows), "projects": projects, "top_activities": top,
            "skills_up": sorted([x for x in deltas if x["delta"] > 0], key=lambda x: -x["delta"])[:5],
            "skills_down": sorted([x for x in deltas if x["delta"] < 0], key=lambda x: x["delta"])[:5],
            "achievements": achievements, "repeated": repeated, "stopped": stopped,
            "cv_candidates": sum(1 for a in achievements if a["state"] == "confirmed" and not a["on_cv"]) + (0 if cv_keys else len(projects)),
            "by_day": by_day,
        }


__all__ = ["Reports"]
