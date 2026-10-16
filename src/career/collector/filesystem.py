"""File activity tracking: metadata only (name, extension, folder, action).

File contents are never read. Watches the Git repositories found under the
configured roots, ignoring build output, dependencies and VCS internals.
"""

import logging
import queue
import time
from pathlib import Path

from career.events.models import Event, EventType

log = logging.getLogger(__name__)

IGNORED_PARTS = {".git", "node_modules", ".venv", "venv", "__pycache__", ".pytest_cache", ".mypy_cache", "dist", "build",
                 ".idea", ".vscode", ".tox", ".next", "target", ".gradle"}
IGNORED_SUFFIXES = {".pyc", ".pyo", ".swp", ".swx", ".tmp", ".lock", ".log~", ".crdownload", ".part", ".db-journal",
                    ".db-wal", ".db-shm"}


def is_relevant(path: Path) -> bool:
    if any(part in IGNORED_PARTS for part in path.parts):
        return False
    name = path.name
    if name.startswith((".#", "~$", ".~")) or name.endswith("~"):
        return False
    return path.suffix.lower() not in IGNORED_SUFFIXES


class FileActivity:
    """Collects file events from watchdog threads; the agent drains them each tick."""

    def __init__(self, roots: list[Path], debounce: float = 10.0):
        self.roots = roots
        self.debounce = debounce
        self._queue: "queue.Queue[Event]" = queue.Queue()
        self._last: dict[str, float] = {}
        self._observer = None

    def start(self) -> None:
        try:
            from watchdog.events import FileSystemEventHandler
            from watchdog.observers import Observer
        except ImportError:  # pragma: no cover
            log.warning("watchdog not installed; file tracking disabled")
            return
        outer = self

        class Handler(FileSystemEventHandler):
            def on_any_event(self, event):  # noqa: ANN001
                if event.is_directory or event.event_type not in ("created", "modified", "deleted", "moved"):
                    return
                path = getattr(event, "dest_path", None) or event.src_path
                outer.record(Path(path), event.event_type)

        self._observer = Observer()
        for root in self.roots:
            try:
                self._observer.schedule(Handler(), str(root), recursive=True)
            except OSError as exc:
                log.warning("Cannot watch %s: %s", root, exc)
        self._observer.daemon = True
        self._observer.start()
        log.info("Watching %s folders for file activity", len(self.roots))

    def stop(self) -> None:
        if self._observer:
            self._observer.stop()
            self._observer.join(timeout=3)
            self._observer = None

    def record(self, path: Path, action: str, now: float | None = None) -> bool:
        if not is_relevant(path):
            return False
        now = time.monotonic() if now is None else now
        key = f"{path}"
        if now - self._last.get(key, -1e9) < self.debounce:
            return False
        self._last[key] = now
        root = next((r for r in self.roots if r == path or r in path.parents), None)
        self._queue.put(Event(
            type=EventType.FILE_CHANGED,
            window_title=path.name,
            metadata={
                "action": action,
                "name": path.name,
                "extension": path.suffix.lower().lstrip("."),
                "folder": str(path.parent),
                "repository": root.name if root else None,
            },
        ))
        return True

    def drain(self) -> list[Event]:
        events = []
        while True:
            try:
                events.append(self._queue.get_nowait())
            except queue.Empty:
                return events
