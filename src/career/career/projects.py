"""Project Engine (roadmap §26): discovers projects and maps sessions to them.

Association sources, strongest first:
  aliases   workspace / repository names and ticket prefixes already linked to a project
  profile   project names the user gave during setup, fuzzily matched to folder names
  learning  ticket prefixes that keep appearing with a project's workspace (2+ sessions)
  discovery a workspace that recurs (2+ sessions or 20+ min) becomes an inferred project
"""

import re
from collections import defaultdict
from difflib import SequenceMatcher

from career.analysis.context import ContextPacket
from career.career.evidence import TruthState
from career.career.store import MemoryStore, new_id
from career.database.models import ProjectRow, ReviewRow

PALETTE_SIZE = 8
_GENERIC_WORKSPACES = {"home", "desktop", "downloads", "documents", "tmp", "src", "work", "projects", "code", "repos", "git"}


def norm(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.casefold())


def similar(a: str, b: str) -> bool:
    """'Mobile AI' ~ 'mobilai', 'Supervisor' ~ 'supervisor-fw', 'Log Parser' ~ 'logParser_v2'."""
    a, b = norm(a), norm(b)
    if not a or not b:
        return False
    if a == b or (min(len(a), len(b)) >= 4 and (a in b or b in a)):
        return True
    return SequenceMatcher(None, a, b).ratio() >= 0.85


def pretty(workspace: str) -> str:
    """'version_updater_v2.3' → 'Version Updater v2.3', 'supervisor' → 'Supervisor', 'logParser_v2' → 'Log Parser v2'."""
    words = re.sub(r"([a-z])([A-Z])", r"\1 \2", workspace).replace("_", " ").replace("-", " ").split()
    out = []
    for w in words:
        out.append(w if re.fullmatch(r"v\d[\d.]*", w, re.IGNORECASE) else (w if w.isupper() else w.capitalize()))
    return " ".join(out) or workspace


def ticket_prefix(ticket: str) -> str:
    return ticket.split("-")[0]


class ProjectEngine:
    def __init__(self, store: MemoryStore, learning: bool = False):
        self.store = store
        self.learning = learning
        self.projects = store.projects()
        self.profile = store.get_profile()
        self._cooc: dict[str, dict[str, int]] = store.get_state("ticket_cooccurrence", {})
        self._ws_seen: dict[str, float] = store.get_state("workspace_seconds", {})
        self._ws_sessions: dict[str, list[str]] = store.get_state("workspace_sessions", {})

    # lookups ------------------------------------------------------------------
    def by_alias(self, alias: str) -> ProjectRow | None:
        return next((p for p in self.projects if alias in (p.aliases or []) and p.state != TruthState.REJECTED), None)

    def by_id(self, project_id: str | None) -> ProjectRow | None:
        return next((p for p in self.projects if p.id == project_id), None)

    # main entry -----------------------------------------------------------------
    def resolve(self, ctx: ContextPacket, active_seconds: float) -> ProjectRow | None:
        workspaces = [w for w in ctx.workspaces if norm(w) not in _GENERIC_WORKSPACES]
        workspaces += [g.repository for g in ctx.git if g.repository not in workspaces]
        for ws in workspaces:
            sessions = self._ws_sessions.setdefault(ws.lower(), [])
            if ctx.session_id not in sessions:
                sessions.append(ctx.session_id)
                self._ws_seen[ws.lower()] = self._ws_seen.get(ws.lower(), 0) + active_seconds

        project = None
        for ws in workspaces:
            project = self.by_alias(f"workspace:{ws.lower()}")
            if project:
                break
        if project is None:
            for ticket in ctx.tickets:
                project = self.by_alias(f"ticket:{ticket_prefix(ticket)}")
                if project:
                    break
        if project is None and workspaces:
            project = self._from_profile(workspaces[0]) or self._discover(workspaces[0])
        if project is None and ctx.tickets:
            project = self._from_cooccurrence(ctx.tickets)

        if project is not None and ctx.tickets and workspaces:
            self._learn_tickets(project, ctx.tickets)
        return project

    def save_state(self) -> None:
        self.store.set_state("ticket_cooccurrence", self._cooc)
        self.store.set_state("workspace_seconds", self._ws_seen)
        self.store.set_state("workspace_sessions", {k: v[-50:] for k, v in self._ws_sessions.items()})

    # strategies ---------------------------------------------------------------------
    def _from_profile(self, workspace: str) -> ProjectRow | None:
        for name in self.profile.projects:
            n = norm(name)
            if n and similar(name, workspace):
                project = next((p for p in self.projects if norm(p.name) == n), None)
                if project is None:
                    project = self._create(name, TruthState.CONFIRMED, [])
                self._add_alias(project, f"workspace:{workspace.lower()}")
                self._ask(f"alias:{project.id}:{workspace.lower()}", "question",
                          f"Is the {workspace} folder part of your {project.name} project?", project,
                          {"project_id": project.id, "alias": f"workspace:{workspace.lower()}"})
                return project
        return None

    def _discover(self, workspace: str) -> ProjectRow | None:
        key = workspace.lower()
        if len(self._ws_sessions.get(key, [])) < 2 and self._ws_seen.get(key, 0) < 1200:
            return None
        rejected = next((p for p in self.projects if f"workspace:{key}" in (p.aliases or [])), None)
        if rejected is not None:
            return None  # the user said no to this one
        project = self._create(pretty(workspace), TruthState.INFERRED, [f"workspace:{key}"])
        self._ask(f"project:{project.id}", "project", f"Is {project.name} a project you work on?", project,
                  {"project_id": project.id})
        return project

    def _from_cooccurrence(self, tickets: list[str]) -> ProjectRow | None:
        for ticket in tickets:
            counts = self._cooc.get(ticket_prefix(ticket), {})
            if counts:
                pid, n = max(counts.items(), key=lambda kv: kv[1])
                project = self.by_id(pid)
                if project and n >= 2:
                    self._add_alias(project, f"ticket:{ticket_prefix(ticket)}")
                    return project
        return None

    def _learn_tickets(self, project: ProjectRow, tickets: list[str]) -> None:
        for ticket in tickets:
            counts = self._cooc.setdefault(ticket_prefix(ticket), {})
            counts[project.id] = counts.get(project.id, 0) + 1
            if counts[project.id] >= 2 and max(counts.values()) == counts[project.id]:
                self._add_alias(project, f"ticket:{ticket_prefix(ticket)}")

    # mutations ---------------------------------------------------------------------
    def _create(self, name: str, state: TruthState, aliases: list[str]) -> ProjectRow:
        row = ProjectRow(id=new_id(), name=name, state=state.value, color=len(self.store.projects(include_merged=True)) % PALETTE_SIZE,
                         aliases=aliases, created_at=self.store.now())
        self.store.save(row)
        self.projects.append(row)
        return row

    def _add_alias(self, project: ProjectRow, alias: str) -> None:
        if alias not in (project.aliases or []):
            project.aliases = [*(project.aliases or []), alias]
            self.store.save(project)

    def _ask(self, ref: str, kind: str, title: str, project: ProjectRow, data: dict) -> None:
        if kind == "question" and not self.learning:
            return
        existing = self.store.all(ReviewRow, ReviewRow.kind == kind, ReviewRow.ref_id == ref)
        if existing:
            return
        self.store.save(ReviewRow(id=new_id(), kind=kind, ref_id=ref, status="pending", created_at=self.store.now(),
                                  data={"title": title, "project_id": project.id,
                                        "options": ["Yes", "No"], **data}))


def ensure_profile_projects(store: MemoryStore) -> None:
    """Projects named during setup exist as confirmed projects from day one."""
    existing = {norm(p.name) for p in store.projects()}
    count = len(store.projects(include_merged=True))
    for name in store.get_profile().projects:
        if name.strip() and norm(name) not in existing:
            store.save(ProjectRow(id=new_id(), name=name.strip(), state=TruthState.CONFIRMED.value, color=count % PALETTE_SIZE,
                                  aliases=[], created_at=store.now()))
            existing.add(norm(name))
            count += 1


def merge_projects(store: MemoryStore, source_id: str, target_id: str) -> ProjectRow:
    from career.database.models import AchievementRow, AnalysisRow, CVBulletRow

    source, target = store.get(ProjectRow, source_id), store.get(ProjectRow, target_id)
    if source is None or target is None or source_id == target_id:
        raise ValueError("Pick two different existing projects to merge.")
    target.aliases = list(dict.fromkeys([*(target.aliases or []), *(source.aliases or [])]))
    source.merged_into = target.id
    store.save(target, source)
    for model in (AnalysisRow, AchievementRow, CVBulletRow):
        rows = store.all(model, model.project_id == source_id)
        for row in rows:
            row.project_id = target_id
        store.save(*rows)
    return target


def project_seconds(store: MemoryStore) -> dict[str, float]:
    totals: dict[str, float] = defaultdict(float)
    for a in store.analyses():
        if a.project_id and a.state != TruthState.REJECTED:
            totals[a.project_id] += a.active_seconds
    return totals
