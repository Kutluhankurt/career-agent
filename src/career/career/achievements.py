"""Achievement Engine (roadmap §27).

Looks for the shape of real accomplishments in a ticket's or a project-week's sessions:

    problem → investigation → implementation → testing → verification

Three or more steps backed by evidence make a *potential* achievement. Titles describe
what was done; impact (numbers, percentages, results) is never generated: only the
user can add it.
"""

import re
from collections import Counter, defaultdict
from datetime import date, timedelta

from career.analysis.classifier import _LANG_BY_EXT
from career.analysis.models import WorkSession
from career.career.evidence import TruthState
from career.career.store import MemoryStore, new_id
from career.career.topics import file_topics
from career.database.models import AchievementRow, AnalysisRow, ProjectRow

STEPS = ["problem", "investigation", "implementation", "testing", "verification"]
_PROBLEM_WORDS = re.compile(r"\b(bug|error|fail\w*|issue|freeze|crash\w*|broken|fix\w*|regression|timeout|leak)\b", re.I)
_RESULT_FILE = re.compile(r"(result|report|summary|\.xlsx$|\.csv$)", re.I)
_TEST_FILE = re.compile(r"(^test_|_test\.|\.spec\.|\.test\.)", re.I)
_SOURCE_EXT = set(_LANG_BY_EXT)
_HEX = re.compile(r"^[0-9a-f]{7,40}$")
_TITLE_NOISE = re.compile(r"\s+[—–-]\s+(Jira|Confluence|GitHub|GitLab|Google Chrome|Mozilla Firefox|Firefox|Microsoft Edge|Safari)\b.*$", re.I)


def _topic(ticket: str | None, titles: list[str], activities: list[str], project: str | None, rows=()) -> str:
    if ticket:
        for t in titles:
            if ticket in t:
                topic = _TITLE_NOISE.sub("", t.replace(ticket, "")).strip(" -—–:|")
                if 3 <= len(topic) <= 60:
                    # "Temperature Test" → "temperature test", but keep acronyms ("SSH timeout")
                    return " ".join(w if (w.isupper() and len(w) > 1) else w.lower() for w in topic.split())
    words = Counter()
    for a in activities:
        cleaned = a
        if project:
            cleaned = re.sub(re.escape(project), "", cleaned, flags=re.I)
        cleaned = re.sub(r"\b(testing|development|investigation|analysis|work|documentation|operations)\b", "", cleaned, flags=re.I)
        cleaned = cleaned.strip(" ·-")
        if cleaned:
            words[cleaned.lower()] += 1
    if words:
        return words.most_common(1)[0][0]
    from_files = file_topics(rows, 1)
    return f"{from_files[0]} handling" if from_files else "core functionality"


def _steps(rows: list[AnalysisRow], sessions: dict[str, WorkSession]) -> dict[str, list[dict]]:
    found: dict[str, list[dict]] = {s: [] for s in STEPS}
    ordered = sorted(rows, key=lambda a: a.created_at)
    tested_at = None
    for i, a in enumerate(ordered):
        ev = a.evidence or []
        session = sessions.get(a.session_id)
        titles = session.titles if session else []
        if any(e["type"] == "ticket" for e in ev) or any(_PROBLEM_WORDS.search(t) for t in titles):
            found["problem"] += [e for e in ev if e["type"] == "ticket"][:2] or ev[:1]
        if a.category in ("Investigation", "Analysis") or any(e["type"] == "browser" for e in ev):
            found["investigation"] += [e for e in ev if e["type"] in ("browser", "ticket", "file")][:2]
        commits = [e for e in ev if e["type"] == "git" or _HEX.match(e["value"])]
        sources = [e for e in ev if e["type"] == "file" and e["value"].rsplit(".", 1)[-1].lower() in _SOURCE_EXT
                   and not _TEST_FILE.search(e["value"])]
        if a.category == "Development" or commits or sources:
            found["implementation"] += (commits + sources)[:3] or ev[:1]
        tests = [e for e in ev if (e["type"] == "file" and _TEST_FILE.search(e["value"])) or e["value"] == "pytest"]
        if a.category == "Testing" or tests:
            found["testing"] += tests[:3] or ev[:1]
            tested_at = i
        results = [e for e in ev if e["type"] == "file" and _RESULT_FILE.search(e["value"])]
        if results and (a.category == "Testing" or tested_at is not None):
            found["verification"] += results[:2]
        elif tested_at is not None and i > tested_at and commits:
            found["verification"] += commits[:1]
    return {k: list({e["value"]: e for e in v}.values())[:4] for k, v in found.items()}


def _title(steps: dict[str, list], topic: str, project: str) -> str:
    done = {k for k, v in steps.items() if v}
    where = f" in {project}" if project else ""
    if {"implementation", "testing", "verification"} <= done:
        return f"Implemented and validated {topic}{where}"
    if {"investigation", "testing"} <= done:
        return f"Investigated and validated {topic}{where}"
    if {"problem", "implementation"} <= done:
        return f"Investigated and fixed {topic}{where}"
    if {"implementation", "testing"} <= done:
        return f"Implemented and tested {topic}{where}"
    return f"Worked through {topic}{where}"


def detect_achievements(store: MemoryStore, sessions: dict[str, WorkSession], today: date) -> list[AchievementRow]:
    since = (today - timedelta(days=60)).isoformat()
    analyses = [a for a in store.analyses(since_day=since) if a.state != TruthState.REJECTED]
    projects = {p.id: p for p in store.all(ProjectRow)}
    groups: dict[str, list[AnalysisRow]] = defaultdict(list)
    for a in analyses:
        tickets = [e["value"] for e in (a.evidence or []) if e["type"] == "ticket"]
        if tickets:
            groups[f"ticket:{tickets[0]}"].append(a)
        elif a.project_id:
            # without a ticket, the files worked on say what the effort was about
            topic = (file_topics([a], 1) or ["general"])[0]
            groups[f"project:{a.project_id}:{topic}"].append(a)

    existing = {r.key: r for r in store.achievements()}
    out: list[AchievementRow] = []
    for key, rows in groups.items():
        active = sum(a.active_seconds for a in rows)
        if len(rows) < 2 or active < 45 * 60:
            continue
        steps = _steps(rows, sessions)
        done = sum(1 for v in steps.values() if v)
        if done < 3:
            continue
        project_id = Counter(a.project_id for a in rows if a.project_id).most_common(1)
        project_id = project_id[0][0] if project_id else None
        project = projects.get(project_id)
        ticket = key.split(":", 1)[1] if key.startswith("ticket:") else None
        titles = [t for a in rows if a.session_id in sessions for t in sessions[a.session_id].titles]
        topic = _topic(ticket, titles, [a.activity for a in rows], project.name if project else None, rows)
        confidence = round(min(0.9, 0.5 + 0.08 * done + 0.05 * min(3, len(rows))), 2)
        row = existing.get(key)
        if row is None:
            row = AchievementRow(id=new_id(), key=key, title=_title(steps, topic, project.name if project else ""),
                                 state=TruthState.INFERRED.value, impact=None, on_cv=False, edited=False,
                                 created_at=store.now())
        elif not row.edited and row.state == TruthState.INFERRED:
            row.title = _title(steps, topic, project.name if project else "")
        row.project_id, row.ticket = project_id, ticket
        row.steps, row.confidence = steps, confidence
        row.session_ids = [a.session_id for a in rows]
        row.updated_at = store.now()
        store.save(row)
        out.append(row)
    return out
