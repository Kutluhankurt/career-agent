"""Skill Engine (roadmap §25). Scores come from evidence, not from time spent.

score = 100 × (0.20 frequency + 0.15 duration + 0.15 complexity
               + 0.15 diversity + 0.20 evidence + 0.15 confirmation)
"""

import math
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, timedelta

from career.analysis.classifier import _LANG_BY_EXT, _SKILL_BY_COMMAND
from career.career.evidence import TruthState
from career.career.store import MemoryStore, new_id
from career.database.models import AnalysisRow, SkillRow, SkillScoreRow

WEIGHTS = {"frequency": 0.20, "duration": 0.15, "complexity": 0.15, "diversity": 0.15, "evidence": 0.20, "confirmation": 0.15}
COMPLEXITY = {"Development": 1.0, "Testing": 0.9, "Analysis": 0.8, "Investigation": 0.7, "Operations": 0.7,
              "Design": 0.7, "Documentation": 0.5, "Planning": 0.5, "Learning": 0.5, "Communication": 0.3, "Other": 0.3}
LANGUAGES = set(_LANG_BY_EXT.values())
TOOLS = {s for v in _SKILL_BY_COMMAND.values() for s in v} | {"Excel", "Jira", "Confluence", "GitHub", "GitLab", "Grafana",
                                                                "Figma", "Kibana", "AWS", "Azure DevOps", "Git", "pytest"}
PRACTICES = {"Test automation", "Test analysis", "Debugging", "Log analysis", "Technical writing", "Data analysis",
             "Issue triage", "Test execution", "Presentations", "Code review"}


def category_of(skill: str) -> str:
    if skill in LANGUAGES:
        return "Language"
    if skill in TOOLS:
        return "Tool"
    if skill in PRACTICES:
        return "Practice"
    return "Domain"


@dataclass
class SkillScore:
    name: str
    score: float
    factors: dict[str, float]
    active_seconds: float = 0
    projects: list[str] = field(default_factory=list)
    evidence_count: int = 0


def score_skills(analyses: list[AnalysisRow], skill_states: dict[str, str], as_of: date) -> dict[str, SkillScore]:
    start = (as_of - timedelta(days=90)).isoformat()
    month = (as_of - timedelta(days=30)).isoformat()
    end = as_of.isoformat()
    usage: dict[str, list[AnalysisRow]] = defaultdict(list)
    for a in analyses:
        if a.state == TruthState.REJECTED or not (start <= a.day <= end):
            continue
        for s in a.skills or []:
            usage[s].append(a)
    scores: dict[str, SkillScore] = {}
    for name, rows in usage.items():
        if skill_states.get(name) == TruthState.REJECTED:
            continue
        days = {a.day for a in rows if a.day >= month}
        hours = sum(a.active_seconds for a in rows) / 3600
        projects = {a.project_id for a in rows if a.project_id}
        evidence = {e["value"] for a in rows for e in (a.evidence or [])}
        confirmed = sum(1 for a in rows if a.state == TruthState.CONFIRMED) / len(rows)
        has_commits = any(e.get("type") == "git" for a in rows for e in (a.evidence or []))
        factors = {
            "frequency": min(1.0, len(days) / 15),
            "duration": min(1.0, math.log1p(hours) / math.log1p(40)),
            "complexity": min(1.0, sum(COMPLEXITY.get(a.category, 0.3) for a in rows) / len(rows) + (0.1 if has_commits else 0)),
            "diversity": min(1.0, len(projects) / 3),
            "evidence": min(1.0, len(evidence) / 15),
            "confirmation": 1.0 if skill_states.get(name) == TruthState.CONFIRMED else 0.4 + 0.6 * confirmed,
        }
        factors = {k: round(v, 3) for k, v in factors.items()}
        scores[name] = SkillScore(
            name=name, score=round(100 * sum(WEIGHTS[k] * v for k, v in factors.items())), factors=factors,
            active_seconds=sum(a.active_seconds for a in rows), projects=sorted(projects), evidence_count=len(evidence),
        )
    return scores


def update_skills(store: MemoryStore, today: date) -> dict[str, SkillScore]:
    """Registers new skills, snapshots today's scores and returns them."""
    analyses = store.analyses()
    rows = {s.name: s for s in store.skills()}
    observed = {s for a in analyses if a.provider == "rules" for s in (a.skills or [])}
    for a in analyses:
        for name in a.skills or []:
            if name not in rows:
                state = TruthState.OBSERVED if name in observed else TruthState.INFERRED
                rows[name] = SkillRow(id=new_id(), name=name, category=category_of(name), state=state.value, created_at=store.now())
                store.save(rows[name])
    scores = score_skills(analyses, {n: r.state for n, r in rows.items()}, today)
    store.save(*[SkillScoreRow(skill_id=rows[n].id, day=today.isoformat(), score=s.score, factors=s.factors)
                 for n, s in scores.items()])
    return scores


def skill_history(store: MemoryStore, today: date, days: int = 30) -> dict[str, list[tuple[str, float]]]:
    """Daily scores for the last `days` days, recomputed from analyses (no gaps on days the agent was off)."""
    analyses = store.analyses()
    states = {s.name: s.state for s in store.skills()}
    history: dict[str, list[tuple[str, float]]] = defaultdict(list)
    for offset in range(days - 1, -1, -1):
        day = today - timedelta(days=offset)
        for name, s in score_skills(analyses, states, day).items():
            history[name].append((day.isoformat(), s.score))
    return history
