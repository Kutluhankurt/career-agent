from datetime import datetime

from pydantic import BaseModel, Field


class Profile(BaseModel):
    name: str = ""
    job_title: str = ""
    focus: str = ""
    projects: list[str] = Field(default_factory=list)
    tools: list[str] = Field(default_factory=list)
    screen_understanding: bool = False
    autostart: bool = False
    ai_provider: str = "none"   # claude | gemini | openai | local | none
    language: str = "en"
    setup_at: datetime | None = None

    @property
    def complete(self) -> bool:
        return self.setup_at is not None

    @property
    def first_name(self) -> str | None:
        return self.name.split()[0] if self.name.strip() else None
