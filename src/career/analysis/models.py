from datetime import datetime

from pydantic import BaseModel, Field


class WorkSession(BaseModel):
    """A continuous, coherent stretch of work built from raw events (no AI involved)."""

    id: str
    start: datetime
    end: datetime
    active_seconds: float
    idle_seconds: float
    event_count: int
    label: str
    score: float = Field(ge=0, le=1, description="How coherent the session is (rules, not AI)")
    is_open: bool = False
    applications: dict[str, float] = Field(default_factory=dict, description="app → active seconds, largest first")
    workspaces: dict[str, float] = Field(default_factory=dict)
    tickets: dict[str, float] = Field(default_factory=dict)
    files: dict[str, float] = Field(default_factory=dict)
    titles: list[str] = Field(default_factory=list, description="Most-used window titles")
    event_ids: list[str] = Field(default_factory=list)

    @property
    def duration_seconds(self) -> float:
        return (self.end - self.start).total_seconds()
