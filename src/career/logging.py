"""Logging setup. The agent logs to ~/.career-agent/logs/agent.log with rotation."""

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

FORMAT = "%(asctime)s %(levelname)-7s %(name)s: %(message)s"


def setup_logging(log_file: Path | None = None, level: int = logging.INFO, console: bool = False) -> None:
    root = logging.getLogger("career")
    root.setLevel(level)
    root.handlers.clear()
    if log_file is not None:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        handler = RotatingFileHandler(log_file, maxBytes=2_000_000, backupCount=3, encoding="utf-8")
        handler.setFormatter(logging.Formatter(FORMAT))
        root.addHandler(handler)
    if console:
        stream = logging.StreamHandler()
        stream.setFormatter(logging.Formatter(FORMAT))
        root.addHandler(stream)
