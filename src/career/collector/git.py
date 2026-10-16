"""Local Git intelligence. Uses the git CLI only; no GitHub/GitLab API is needed.

discover_repos()  finds repositories under the configured roots (metadata only)
GitWatcher        remembers each active repo's branch and HEAD and turns changes
                  into git_activity events: new commits (with changed files and
                  line counts) and branch switches.
"""

import logging
import os
import shutil
import subprocess
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from career.events.models import Event, EventType

log = logging.getLogger(__name__)

_SKIP_DIRS = {
    "node_modules", ".venv", "venv", "env", "__pycache__", ".cache", ".local", ".npm", ".cargo", ".rustup",
    "Library", "AppData", "snap", ".git", "site-packages", "dist", "build", ".tox", ".mypy_cache", "Trash",
}


def discover_repos(roots: list[str], depth: int = 4) -> list[Path]:
    found: list[Path] = []
    for root in roots:
        base = Path(os.path.expanduser(root))
        if not base.is_dir():
            continue
        _walk(base, depth, found)
    return sorted(set(found))


def _walk(path: Path, depth: int, found: list[Path]) -> None:
    try:
        entries = list(os.scandir(path))
    except OSError:
        return
    if any(e.name == ".git" for e in entries):
        found.append(path)
        return  # don't descend into a repo (submodules are part of it)
    if depth <= 0:
        return
    for entry in entries:
        if entry.is_dir(follow_symlinks=False) and entry.name not in _SKIP_DIRS and not entry.name.startswith("."):
            _walk(Path(entry.path), depth - 1, found)


@dataclass
class Commit:
    hash: str
    message: str
    author: str
    timestamp: datetime
    files: list[str] = field(default_factory=list)
    added: int = 0
    removed: int = 0


class Git:
    """Thin wrapper over the git CLI for one repository."""

    def __init__(self, repo: Path, binary: str | None = None):
        self.repo = repo
        self.binary = binary or shutil.which("git")

    def _run(self, *args: str) -> str | None:
        if not self.binary:
            return None
        try:
            result = subprocess.run(
                [self.binary, "-C", str(self.repo), *args],
                capture_output=True, text=True, timeout=10, check=False, encoding="utf-8", errors="replace",
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            log.debug("git %s failed in %s: %s", args[0], self.repo, exc)
            return None
        return result.stdout if result.returncode == 0 else None

    def head(self) -> str | None:
        out = self._run("rev-parse", "HEAD")
        return out.strip() if out else None

    def branch(self) -> str | None:
        out = self._run("rev-parse", "--abbrev-ref", "HEAD")
        return out.strip() if out else None

    def changed_files(self) -> list[str]:
        out = self._run("status", "--porcelain")
        return [line[3:].strip() for line in (out or "").splitlines() if len(line) > 3]

    def commits_since(self, since_hash: str | None, limit: int = 20) -> list[Commit]:
        rng = f"{since_hash}..HEAD" if since_hash else "-1"
        args = ["log", "--numstat", "--no-merges", "--date=iso-strict", "--format=\x1e%H\x1f%an\x1f%aI\x1f%s"]
        args += [rng] if since_hash else ["-1"]
        args += [f"--max-count={limit}"]
        out = self._run(*args)
        return parse_log(out or "")


def parse_log(output: str) -> list[Commit]:
    commits: list[Commit] = []
    for chunk in output.split("\x1e"):
        lines = [line for line in chunk.strip("\n").split("\n")]
        if not lines or "\x1f" not in lines[0]:
            continue
        hash_, author, ts, message = lines[0].split("\x1f", 3)
        commit = Commit(hash=hash_, message=message, author=author, timestamp=datetime.fromisoformat(ts))
        for line in lines[1:]:
            parts = line.split("\t")
            if len(parts) != 3:
                continue
            added, removed, path = parts
            commit.files.append(path)
            commit.added += int(added) if added.isdigit() else 0
            commit.removed += int(removed) if removed.isdigit() else 0
        commits.append(commit)
    return commits


class GitWatcher:
    def __init__(self, repos: list[Path]):
        from datetime import timedelta

        from career.events.models import utc_now

        self.repos = {r.name: r for r in repos}
        self._state: dict[Path, tuple[str | None, str | None]] = {}
        self._since = utc_now() - timedelta(minutes=2)  # git times have 1 s resolution

    def repo_for(self, name_or_path: str) -> Path | None:
        p = Path(name_or_path)
        if p.is_absolute():
            for repo in self.repos.values():
                if p == repo or repo in p.parents:
                    return repo
            return None
        return self.repos.get(name_or_path)

    def check(self, repo: Path) -> list[Event]:
        git = Git(repo)
        head, branch = git.head(), git.branch()
        if head is None:
            return []
        previous = self._state.get(repo)
        self._state[repo] = (branch, head)
        if previous is None:
            return []  # first look: remember, don't report history as new work
        events: list[Event] = []
        old_branch, old_head = previous
        if branch != old_branch:
            events.append(Event(type=EventType.GIT_ACTIVITY, application="Git", metadata={
                "kind": "branch_switch", "repository": repo.name, "path": str(repo), "branch": branch, "from_branch": old_branch,
            }))
        if head != old_head:
            # only commits made while the agent was watching (a branch switch can
            # otherwise surface someone else's history as "new")
            new = [c for c in git.commits_since(old_head) if c.timestamp >= self._since]
            for c in reversed(new):
                events.append(Event(
                    timestamp=c.timestamp, type=EventType.GIT_ACTIVITY, application="Git", window_title=c.message,
                    metadata={
                        "kind": "commit", "repository": repo.name, "path": str(repo), "branch": branch, "hash": c.hash[:12],
                        "message": c.message, "files": c.files[:50], "added": c.added, "removed": c.removed,
                    },
                ))
        return events
