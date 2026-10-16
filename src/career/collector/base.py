"""Platform abstraction. Business logic only ever talks to ActivityCollector.

Each OS implements the two primitive probes (active window, idle time). Everything
built on top of them (event generation, sessions, AI) is shared across platforms.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

import psutil


@dataclass(frozen=True)
class ActiveWindow:
    application: str | None
    title: str | None
    pid: int | None = None
    process: str | None = None
    extra: dict[str, Any] = field(default_factory=dict, compare=False)


class CollectorUnavailable(RuntimeError):
    """The current desktop can't be observed (e.g. no display, missing permission)."""


class ActivityCollector(ABC):
    name: str = "base"
    source: str = "os"

    @abstractmethod
    def get_active_window(self) -> ActiveWindow | None:
        """The focused window, or None if it can't be determined right now."""

    @abstractmethod
    def get_idle_time(self) -> float | None:
        """Seconds since the last keyboard/mouse input, or None if unknown."""

    def get_running_apps(self) -> list[str]:
        """Names of running processes. Context only, never proof of work."""
        names: set[str] = set()
        for proc in psutil.process_iter(["name"]):
            name = proc.info.get("name")
            if name:
                names.add(name)
        return sorted(names)

    def start(self) -> None:
        """Acquire OS resources (display connection, etc.)."""

    def stop(self) -> None:
        """Release OS resources."""

    @staticmethod
    def process_name(pid: int | None) -> str | None:
        if not pid:
            return None
        try:
            return psutil.Process(pid).name()
        except (psutil.Error, ValueError):
            return None
