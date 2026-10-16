"""Normalized event model. Every OS collector produces exactly this shape."""

import uuid
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class EventType(StrEnum):
    WINDOW_FOCUS = "window_focus"
    APPLICATION_STARTED = "application_started"
    APPLICATION_CLOSED = "application_closed"
    IDLE_STARTED = "idle_started"
    IDLE_ENDED = "idle_ended"
    FILE_CHANGED = "file_changed"
    GIT_ACTIVITY = "git_activity"
    BROWSER_ACTIVITY = "browser_activity"
    TERMINAL_ACTIVITY = "terminal_activity"
    AGENT_STARTED = "agent_started"
    AGENT_STOPPED = "agent_stopped"


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Event(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = Field(default_factory=utc_now)
    type: EventType
    application: str | None = None
    window_title: str | None = None
    source: str = "os"
    metadata: dict[str, Any] = Field(default_factory=dict)
