"""The background agent: sample → events → SQLite, until asked to stop.

Process control is file based so it behaves the same on every OS:
  agent.pid   JSON {pid, started_at, platform} written on start, removed on exit
  agent.stop  created by `career stop`; the loop exits cleanly when it appears
"""

import json
import logging
import os
import signal
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import psutil

from career import __version__
from career.analysis import signals as sig
from career.collector import ActivityCollector, get_collector, platform_name
from career.collector.filesystem import FileActivity
from career.collector.git import GitWatcher, discover_repos
from career.config import Paths, Settings
from career.database.database import Database
from career.analysis.service import rebuild_day
from career.events.models import Event, EventType, utc_now
from career.events.processor import EventProcessor
from career.logging import setup_logging

log = logging.getLogger(__name__)


@dataclass
class AgentInfo:
    pid: int
    started_at: datetime
    platform: str


def read_agent_info(paths: Paths) -> AgentInfo | None:
    """Info about the running agent, or None (stale pid files are cleaned up)."""
    try:
        data = json.loads(paths.pid_file.read_text())
        info = AgentInfo(pid=int(data["pid"]), started_at=datetime.fromisoformat(data["started_at"]), platform=data["platform"])
    except (OSError, ValueError, KeyError):
        return None
    if not _is_agent_process(info.pid):
        paths.pid_file.unlink(missing_ok=True)
        return None
    return info


def _is_agent_process(pid: int) -> bool:
    try:
        proc = psutil.Process(pid)
        return proc.is_running() and proc.status() != psutil.STATUS_ZOMBIE
    except psutil.Error:
        return False


class Agent:
    def __init__(self, paths: Paths, settings: Settings, collector: ActivityCollector | None = None, db: Database | None = None):
        self.paths = paths
        self.settings = settings
        self.collector = collector or get_collector()
        self.db = db or Database(paths.database)
        self.processor = EventProcessor(
            self.collector,
            idle_threshold=settings.collector.idle_threshold,
            suspend_gap=max(90.0, settings.collector.interval * 3),
            excluded_apps=settings.collector.excluded_apps,
            browser_tracking=settings.privacy.browser_tracking,
        )
        self._running = False
        self._last_rebuild = 0.0
        self._last_git = 0.0
        self._last_memory = time.monotonic()  # first full analysis after one interval, not at boot
        self._memory_day = utc_now().astimezone().date()
        self._memory_thread: threading.Thread | None = None
        self.files: FileActivity | None = None
        self.git: GitWatcher | None = None
        self._active_repos: dict[Path, float] = {}  # repo -> last time it showed activity (monotonic)

    def run(self, max_ticks: int | None = None) -> None:
        self.paths.ensure()
        self.paths.stop_file.unlink(missing_ok=True)
        self.paths.pid_file.write_text(
            json.dumps({"pid": os.getpid(), "started_at": utc_now().isoformat(), "platform": platform_name()})
        )
        self._install_signal_handlers()
        self.collector.start()
        threading.Thread(target=self._start_context_sources, name="context-sources", daemon=True).start()
        log.info("Career Agent %s started (pid %s, collector %s)", __version__, os.getpid(), self.collector.name)
        self._store([Event(type=EventType.AGENT_STARTED, source=self.collector.source, metadata={"version": __version__})])
        self._running = True
        ticks = 0
        try:
            while self._running and not self.paths.stop_file.exists():
                self._tick()
                ticks += 1
                if max_ticks is not None and ticks >= max_ticks:
                    break
                self._sleep(self.settings.collector.interval)
        finally:
            self._store([Event(type=EventType.AGENT_STOPPED, source=self.collector.source)])
            self._rebuild_sessions(final=True)
            if self.files:
                self.files.stop()
            self.collector.stop()
            self.paths.pid_file.unlink(missing_ok=True)
            self.paths.stop_file.unlink(missing_ok=True)
            log.info("Career Agent stopped")

    def _start_context_sources(self) -> None:
        """Repo discovery can take a few seconds on a big home folder: do it off the loop."""
        try:
            repos = discover_repos(self.settings.collector.repo_roots, self.settings.collector.repo_scan_depth)
            log.info("Found %s Git repositories", len(repos))
            self.git = GitWatcher(repos)
            if self.settings.privacy.file_tracking and repos:
                # watching is recursive and OS watch handles are limited: follow the
                # repositories used most recently
                files = FileActivity(sorted(repos, key=_recent_activity, reverse=True)[:MAX_WATCHED_REPOS])
                files.start()
                self.files = files
        except Exception:  # noqa: BLE001
            log.exception("Context sources unavailable; window tracking continues")

    def _tick(self) -> None:
        if self.is_paused():
            return
        events = self.processor.tick()
        if self.files:
            events += self.files.drain()
        self._note_active_repos(events)
        self._store(events)
        now = time.monotonic()
        if self.git and now - self._last_git >= self.settings.collector.git_interval:
            self._last_git = now
            self._store(self._check_git())
        if now - self._last_rebuild >= self.settings.sessions.rebuild_interval:
            self._rebuild_sessions()
        if now - self._last_memory >= self.settings.ai.analysis_interval * 60:
            self._update_memory()

    def _update_memory(self) -> None:
        """Analysis can call an AI and take a while: run it beside collection, one at a time."""
        self._last_memory = time.monotonic()
        if self._memory_thread and self._memory_thread.is_alive():
            return
        today = utc_now().astimezone().date()
        days = [today] if today == self._memory_day else [self._memory_day, today]  # finish yesterday after midnight
        self._memory_day = today

        def work() -> None:
            from career.ai import get_provider
            from career.career.memory import MemoryEngine

            try:
                engine = MemoryEngine(self.db, self.settings, get_provider(self.settings.ai))
                for day in days:
                    result = engine.update_day(day, open_until=utc_now() if day == today else None)
                    log.info("Career Memory updated for %s: %s sessions, %s analyzed (%s by AI), %s to review",
                             day, result.sessions, result.analyzed, result.ai_analyzed, result.review_count)
            except Exception:  # noqa: BLE001
                log.exception("Career Memory update failed; collection continues")

        self._memory_thread = threading.Thread(target=work, name="career-memory", daemon=True)
        self._memory_thread.start()

    def is_paused(self) -> bool:
        until = read_pause(self.paths)
        if until is None:
            return False
        if not self.processor.is_idle:
            # close the current activity so paused time is never counted as work
            self._store([Event(type=EventType.IDLE_STARTED, source=self.collector.source, metadata={"reason": "paused"})])
            self.processor.is_idle = True
            self.processor._last_focus = None
        return True

    def _note_active_repos(self, events: list[Event]) -> None:
        if not self.git:
            return
        now = time.monotonic()
        for e in events:
            repo = None
            if e.type == EventType.FILE_CHANGED and e.metadata.get("folder"):
                repo = self.git.repo_for(e.metadata["folder"])
            elif e.type == EventType.WINDOW_FOCUS:
                for ws in sig.extract(e.application, e.window_title).workspaces:
                    repo = self.git.repo_for(ws) or repo
            if repo:
                self._active_repos[repo] = now

    def _check_git(self) -> list[Event]:
        now = time.monotonic()
        events: list[Event] = []
        for repo, seen in list(self._active_repos.items()):
            if now - seen > 3600:
                del self._active_repos[repo]
                continue
            try:
                events += self.git.check(repo)
            except Exception:  # noqa: BLE001
                log.exception("Git check failed for %s", repo)
        return events

    def _store(self, events: list[Event]) -> None:
        if not events:
            return
        try:
            self.db.add_events(events)
        except Exception:  # noqa: BLE001
            log.exception("Could not store %s events; they will be dropped", len(events))

    def _rebuild_sessions(self, final: bool = False) -> None:
        self._last_rebuild = time.monotonic()
        try:
            now = utc_now()
            count, sessions = rebuild_day(self.db, self.settings, now.astimezone().date(), open_until=None if final else now)
            log.debug("Rebuilt %s sessions from %s events", len(sessions), count)
        except Exception:  # noqa: BLE001
            log.exception("Session rebuild failed; collection continues")

    def _sleep(self, seconds: float) -> None:
        # Sleep in short steps so stop requests are noticed quickly.
        deadline = time.monotonic() + seconds
        while self._running and time.monotonic() < deadline:
            if self.paths.stop_file.exists():
                return
            time.sleep(min(0.25, max(0.0, deadline - time.monotonic())))

    def _install_signal_handlers(self) -> None:
        def _stop(_signum, _frame):
            self._running = False

        for signum in (signal.SIGINT, signal.SIGTERM):
            try:
                signal.signal(signum, _stop)
            except (ValueError, OSError):  # not on main thread / unsupported
                pass


MAX_WATCHED_REPOS = 25


def _recent_activity(repo: Path) -> float:
    for marker in (repo / ".git" / "index", repo / ".git" / "HEAD", repo):
        try:
            return marker.stat().st_mtime
        except OSError:
            continue
    return 0.0


def read_pause(paths: Paths) -> datetime | None:
    """When tracking is paused, the time it resumes; None when not paused."""
    try:
        until = datetime.fromisoformat(json.loads(paths.pause_file.read_text())["until"])
    except (OSError, ValueError, KeyError):
        return None
    if until <= utc_now():
        paths.pause_file.unlink(missing_ok=True)
        return None
    return until


def pause(paths: Paths, minutes: float) -> datetime:
    from datetime import timedelta

    until = utc_now() + timedelta(minutes=minutes)
    paths.ensure().pause_file.write_text(json.dumps({"until": until.isoformat()}))
    return until


def resume(paths: Paths) -> None:
    paths.pause_file.unlink(missing_ok=True)


def run_foreground(paths: Paths, settings: Settings, console: bool = False) -> None:
    setup_logging(paths.ensure().log_file, console=console)
    Agent(paths, settings).run()


def spawn_background(paths: Paths) -> int:
    """Start `career start --foreground` as a detached process; returns its pid."""
    paths.ensure()
    # a PyInstaller build *is* the career command; a Python install runs the module
    cmd = [sys.executable, "start", "--foreground"] if getattr(sys, "frozen", False) else [
        sys.executable, "-m", "career", "start", "--foreground"]
    kwargs: dict = {"stdin": subprocess.DEVNULL, "stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL, "close_fds": True}
    if sys.platform == "win32":
        kwargs["creationflags"] = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW
    else:
        kwargs["start_new_session"] = True
    env = os.environ.copy()
    env["CAREER_AGENT_HOME"] = str(paths.home)
    return subprocess.Popen(cmd, env=env, **kwargs).pid


def wait_for_start(paths: Paths, timeout: float = 5.0) -> AgentInfo | None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        info = read_agent_info(paths)
        if info:
            return info
        time.sleep(0.1)
    return None


def stop_agent(paths: Paths, timeout: float = 8.0) -> bool:
    """Ask the agent to stop; terminate it if it doesn't exit in time. True if it was running."""
    info = read_agent_info(paths)
    if info is None:
        return False
    paths.stop_file.touch()
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if not _is_agent_process(info.pid):
            break
        time.sleep(0.1)
    else:
        try:
            psutil.Process(info.pid).terminate()
        except psutil.Error:
            pass
    paths.pid_file.unlink(missing_ok=True)
    paths.stop_file.unlink(missing_ok=True)
    return True
