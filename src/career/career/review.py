"""Review queue (roadmap §23, §28): what the user is asked to confirm, edit or reject."""

from datetime import date, timedelta

from career.career.evidence import TruthState
from career.career.store import MemoryStore, new_id
from career.database.models import AchievementRow, AnalysisRow, ProjectRow, ReviewRow, SkillRow

LEARNING_DAYS = 7


def learning_day(store: MemoryStore, today: date) -> int | None:
    """1..7 while Learning Mode is on (counted from setup), else None."""
    profile = store.get_profile()
    if profile.setup_at is None:
        return 1
    day = (today - profile.setup_at.astimezone().date()).days + 1
    return day if day <= LEARNING_DAYS else None


_NOT_REVIEWED = {"Communication", "Other"}  # not career evidence on their own


def _group_key(a: AnalysisRow) -> str:
    week = date.fromisoformat(a.day).isocalendar()
    return f"{week.year}-W{week.week:02d}|{a.project_id or '-'}|{a.activity.casefold()}"


def sync_review(store: MemoryStore, today: date) -> int:
    """Adds anything newly worth asking about. Returns the number of pending items.

    Sessions with the same week, project and activity become one card. Once the user has
    confirmed a project + activity pattern twice, new sessions like it aren't asked
    about again (Learning Mode: answers update the model)."""
    learning = learning_day(store, today) is not None
    threshold = 1.01 if learning else 0.8
    reviews = store.reviews(status=None)
    known = {(r.kind, r.ref_id) for r in reviews}
    since = (today - timedelta(days=7)).isoformat()
    analyses = store.analyses()
    confirmed_patterns: dict[tuple, int] = {}
    for a in analyses:
        if a.state == TruthState.CONFIRMED:
            key = (a.project_id, a.activity.casefold())
            confirmed_patterns[key] = confirmed_patterns.get(key, 0) + 1

    groups: dict[str, list[AnalysisRow]] = {}
    for a in analyses:
        if (a.day < since or a.state != TruthState.INFERRED or a.category in _NOT_REVIEWED
                or a.active_seconds < 600 or a.confidence >= threshold
                or confirmed_patterns.get((a.project_id, a.activity.casefold()), 0) >= 2):
            continue
        groups.setdefault(_group_key(a), []).append(a)

    new: list[ReviewRow] = []
    for key, rows in groups.items():
        if ("session", key) in known:
            # a card already exists for this group: make sure later sessions join it
            card = next(r for r in reviews if r.kind == "session" and r.ref_id == key)
            ids = sorted({*card.data.get("session_ids", []), *(a.session_id for a in rows)})
            if card.status == "pending" and ids != card.data.get("session_ids"):
                card.data = {**card.data, "session_ids": ids}
                store.save(card)
            continue
        new.append(ReviewRow(id=new_id(), kind="session", ref_id=key, status="pending", created_at=store.now(),
                             data={"session_ids": [a.session_id for a in rows]}))
    for ach in store.achievements():
        if ach.state == TruthState.INFERRED and ("achievement", ach.id) not in known:
            new.append(ReviewRow(id=new_id(), kind="achievement", ref_id=ach.id, status="pending", created_at=store.now(), data={}))
    store.save(*new)
    return len(store.reviews())


def resolve(store: MemoryStore, review_id: str, action: str, title: str | None = None, answer: str | None = None) -> int:
    review = store.get(ReviewRow, review_id)
    if review is None or review.status != "pending":
        raise KeyError(review_id)
    data = review.data or {}
    confirm = action == "confirm" or (action == "answer" and (answer or "").lower() in ("yes", "y"))
    reject = action == "reject" or (action == "answer" and (answer or "").lower() in ("no", "n"))

    if review.kind == "session":
        rows = [r for r in (store.get(AnalysisRow, sid) for sid in data.get("session_ids", [])) if r]
        for row in rows:
            if action == "edit" and title:
                row.activity, row.edited = title.strip()[:90], True
            row.state = (TruthState.REJECTED if reject else TruthState.CONFIRMED).value
            row.updated_at = store.now()
        store.save(*rows)
    elif review.kind == "achievement":
        row = store.get(AchievementRow, review.ref_id)
        if row:
            if action == "edit" and title:
                row.title, row.edited = title.strip()[:300], True
            row.state = (TruthState.REJECTED if reject else TruthState.CONFIRMED).value
            row.updated_at = store.now()
            store.save(row)
    elif review.kind == "project":
        row = store.get(ProjectRow, data.get("project_id"))
        if row:
            if action == "edit" and title:
                row.name = title.strip()[:120]
            row.state = (TruthState.REJECTED if reject else TruthState.CONFIRMED).value
            store.save(row)
    elif review.kind == "question":
        row = store.get(ProjectRow, data.get("project_id"))
        if row and reject and data.get("alias") in (row.aliases or []):
            row.aliases = [a for a in row.aliases if a != data["alias"]]
            store.save(row)
    elif review.kind == "skill":
        row = store.get(SkillRow, review.ref_id)
        if row:
            row.state = (TruthState.REJECTED if reject else TruthState.CONFIRMED).value
            store.save(row)

    review.status = "done"
    review.resolved_at = store.now()
    review.data = {**data, "action": action, "answer": answer, "confirmed": confirm}
    store.save(review)
    return len(store.reviews())


def describe(review: ReviewRow, store: MemoryStore) -> dict | None:
    """Human-facing fields for a review item, or None if its subject is gone."""
    data = review.data or {}
    if review.kind == "session":
        rows = [r for r in (store.get(AnalysisRow, sid) for sid in data.get("session_ids", [])) if r]
        if not rows:
            return None
        a = max(rows, key=lambda r: r.active_seconds)
        evidence = list({e["value"]: e for r in rows for e in (r.evidence or [])}.values())[:10]
        skills = list(dict.fromkeys(s for r in rows for s in (r.skills or [])))
        n = len(rows)
        return {"title": a.activity, "subtitle": "Session" if n == 1 else f"{n} sessions", "project_id": a.project_id,
                "confidence": round(sum(r.confidence for r in rows) / n, 2), "skills": skills, "evidence": evidence,
                "options": None, "sessions": rows}
    if review.kind == "achievement":
        ach = store.get(AchievementRow, review.ref_id)
        if ach is None:
            return None
        ev = [e for step in (ach.steps or {}).values() for e in step]
        return {"title": ach.title, "subtitle": "Possible achievement", "project_id": ach.project_id,
                "confidence": ach.confidence, "skills": [], "evidence": list({e["value"]: e for e in ev}.values())[:8],
                "options": None}
    if review.kind in ("project", "question"):
        return {"title": data.get("title", ""), "subtitle": "Question from Learning mode" if review.kind == "question"
                else "New project", "project_id": data.get("project_id"), "confidence": 0.7, "skills": [], "evidence": [],
                "options": data.get("options") or ["Yes", "No"]}
    return None


__all__ = ["describe", "learning_day", "resolve", "sync_review"]
