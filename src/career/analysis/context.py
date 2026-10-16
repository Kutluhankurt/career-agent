"""Context Builder (roadmap §18): one structured packet per session.

This packet is the only thing an AI provider ever sees: names, titles and counts,
never file contents, keystrokes or screenshots.
"""

from collections import defaultdict
from datetime import timedelta

from pydantic import BaseModel, Field

from career.analysis import signals as sig
from career.analysis.models import WorkSession
from career.events.models import Event, EventType


class GitCommitContext(BaseModel):
    hash: str
    message: str
    files: list[str] = Field(default_factory=list)
    added: int = 0
    removed: int = 0


class GitContext(BaseModel):
    repository: str
    branch: str | None = None
    commits: list[GitCommitContext] = Field(default_factory=list)
    branch_switches: list[str] = Field(default_factory=list)


class ProfileContext(BaseModel):
    job_title: str = ""
    focus: str = ""
    projects: list[str] = Field(default_factory=list)
    tools: list[str] = Field(default_factory=list)


class ContextPacket(BaseModel):
    session_id: str
    date: str
    time: str                      # "10:14-10:46" local time
    active_minutes: int
    applications: dict[str, int]   # app -> minutes
    window_titles: list[str]
    sites: list[str]
    workspaces: list[str]
    projects: list[str] = Field(default_factory=list)   # known project names (filled by the project engine)
    files: list[str]
    file_actions: dict[str, int] = Field(default_factory=dict)  # extension -> number of saves
    commands: list[str]
    tickets: list[str]
    git: list[GitContext] = Field(default_factory=list)
    profile: ProfileContext = Field(default_factory=ProfileContext)

    def evidence_vocabulary(self) -> set[str]:
        """Everything an analysis may cite as evidence. Anything else is invented."""
        vocab = {*self.applications, *self.sites, *self.workspaces, *self.files, *self.commands, *self.tickets}
        for g in self.git:
            vocab.add(g.repository)
            for c in g.commits:
                vocab.update({c.hash, c.message, f"{c.hash} {c.message}", *c.files})
        return {v for v in vocab if v}


def build_context(session: WorkSession, events: list[Event], profile: ProfileContext | None = None) -> ContextPacket:
    """`events` = all events of the session's time window (focus, file, git...)."""
    start, end = session.start, session.end + timedelta(seconds=60)
    window = [e for e in events if start <= e.timestamp <= end]
    in_session = set(session.event_ids)

    sites: dict[str, float] = defaultdict(float)
    commands: set[str] = set()
    for e in window:
        if e.type == EventType.WINDOW_FOCUS and e.id in in_session:
            s = sig.extract(e.application, e.window_title)
            for site in s.sites:
                sites[site] += 1
            commands |= s.commands

    files = dict(session.files)
    file_actions: dict[str, int] = defaultdict(int)
    git: dict[str, GitContext] = {}
    for e in window:
        if e.type == EventType.FILE_CHANGED:
            repo = e.metadata.get("repository")
            if repo and session.workspaces and repo not in session.workspaces:
                continue  # a save in another repository (autosave, tooling) isn't this session's work
            name = e.metadata.get("name") or e.window_title
            if name:
                files.setdefault(name, 0)
                file_actions[e.metadata.get("extension") or "other"] += 1
        elif e.type == EventType.GIT_ACTIVITY:
            repo = e.metadata.get("repository") or "repository"
            if session.workspaces and repo not in session.workspaces:
                continue
            g = git.setdefault(repo, GitContext(repository=repo))
            g.branch = e.metadata.get("branch") or g.branch
            if e.metadata.get("kind") == "commit":
                g.commits.append(GitCommitContext(
                    hash=str(e.metadata.get("hash", ""))[:12], message=e.metadata.get("message", ""),
                    files=list(e.metadata.get("files", []))[:20], added=e.metadata.get("added", 0),
                    removed=e.metadata.get("removed", 0),
                ))
            elif e.metadata.get("kind") == "branch_switch" and g.branch:
                g.branch_switches.append(g.branch)

    local_start, local_end = session.start.astimezone(), session.end.astimezone()
    return ContextPacket(
        session_id=session.id,
        date=local_start.date().isoformat(),
        time=f"{local_start:%H:%M}-{local_end:%H:%M}",
        active_minutes=round(session.active_seconds / 60),
        applications={app: max(1, round(sec / 60)) for app, sec in session.applications.items()},
        window_titles=session.titles,
        sites=sorted(sites, key=sites.get, reverse=True),
        workspaces=list(session.workspaces),
        files=list(files)[:25],
        file_actions=dict(file_actions),
        commands=sorted(commands),
        tickets=list(session.tickets),
        git=list(git.values()),
        profile=profile or ProfileContext(),
    )
