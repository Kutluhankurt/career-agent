"""Filesystem locations. Everything lives under one home directory (default ~/.career-agent).

Set CAREER_AGENT_HOME to use another directory (tests, portable installs).
"""

import os
from dataclasses import dataclass
from pathlib import Path

HOME_ENV = "CAREER_AGENT_HOME"


@dataclass(frozen=True)
class Paths:
    home: Path

    @property
    def database(self) -> Path:
        return self.home / "career.db"

    @property
    def config(self) -> Path:
        return self.home / "config.toml"

    @property
    def logs(self) -> Path:
        return self.home / "logs"

    @property
    def log_file(self) -> Path:
        return self.logs / "agent.log"

    @property
    def pid_file(self) -> Path:
        return self.home / "agent.pid"

    @property
    def stop_file(self) -> Path:
        return self.home / "agent.stop"

    @property
    def pause_file(self) -> Path:
        return self.home / "agent.pause"

    @property
    def backups(self) -> Path:
        return self.home / "backups"

    def ensure(self) -> "Paths":
        self.home.mkdir(parents=True, exist_ok=True)
        self.logs.mkdir(parents=True, exist_ok=True)
        return self


def get_paths() -> Paths:
    custom = os.environ.get(HOME_ENV)
    home = Path(custom).expanduser() if custom else Path.home() / ".career-agent"
    return Paths(home=home)
