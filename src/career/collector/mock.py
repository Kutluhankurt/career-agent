"""Scripted collector for tests and demos: replays a list of (window, idle) samples."""

from collections.abc import Iterable
from dataclasses import dataclass

from career.collector.base import ActiveWindow, ActivityCollector


@dataclass(frozen=True)
class Sample:
    application: str | None
    title: str | None = None
    idle: float = 0.0


class MockCollector(ActivityCollector):
    name = "mock"
    source = "mock"

    def __init__(self, samples: Iterable[Sample]):
        self._samples = list(samples)
        self._index = 0

    def advance(self) -> None:
        """Move to the next scripted sample (stays on the last one when exhausted)."""
        if self._index < len(self._samples) - 1:
            self._index += 1

    @property
    def current(self) -> Sample:
        return self._samples[self._index]

    def get_active_window(self) -> ActiveWindow | None:
        s = self.current
        return ActiveWindow(application=s.application, title=s.title) if s.application else None

    def get_idle_time(self) -> float | None:
        return self.current.idle

    def get_running_apps(self) -> list[str]:
        return sorted({s.application for s in self._samples if s.application})
