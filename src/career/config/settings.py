"""User configuration stored as TOML (~/.career-agent/config.toml).

API keys never live here; they go to the OS keychain (Sprint 6).
"""

import tomllib
from pathlib import Path

import tomli_w
from pydantic import BaseModel, Field


class GeneralSettings(BaseModel):
    language: str = "en"
    timezone: str = "Europe/Istanbul"


class CollectorSettings(BaseModel):
    interval: float = Field(default=5.0, gt=0, description="Seconds between activity samples")
    idle_threshold: float = Field(default=300.0, gt=0, description="Seconds without input before idle")
    repo_roots: list[str] = Field(default_factory=lambda: ["~"], description="Folders searched for Git repositories")
    repo_scan_depth: int = Field(default=4, ge=1, le=8)
    git_interval: float = Field(default=60.0, gt=0, description="Seconds between Git checks of active repos")
    excluded_apps: list[str] = Field(default_factory=list, description="Apps never recorded (title and name hidden)")


class SessionSettings(BaseModel):
    split_gap: float = Field(default=600.0, gt=0, description="A pause at least this long (s) starts a new session")
    switch_min: float = Field(default=300.0, gt=0, description="A different project must last this long (s) to split")
    min_session: float = Field(default=180.0, ge=0, description="Shorter sessions (s) are merged into a neighbour")
    max_span: float = Field(default=7200.0, gt=0, description="Upper bound (s) for one uninterrupted window focus")
    rebuild_interval: float = Field(default=120.0, gt=0, description="How often (s) the agent refreshes today's sessions")


class PrivacySettings(BaseModel):
    screen_understanding: bool = False
    browser_tracking: bool = True
    file_tracking: bool = True


class AISettings(BaseModel):
    provider: str = Field(default="none", description="claude | gemini | openai | local | none (rules only)")
    model: str = Field(default="", description="Empty = the provider's default model")
    analysis_interval: int = Field(default=30, ge=1, description="Minutes between automatic analyses")
    local_url: str = "http://127.0.0.1:11434"
    polish_cv: bool = True


class ServerSettings(BaseModel):
    host: str = "127.0.0.1"
    port: int = 7342


class Settings(BaseModel):
    general: GeneralSettings = GeneralSettings()
    collector: CollectorSettings = CollectorSettings()
    sessions: SessionSettings = SessionSettings()
    privacy: PrivacySettings = PrivacySettings()
    ai: AISettings = AISettings()
    server: ServerSettings = ServerSettings()


def load_settings(path: Path) -> Settings:
    """Load settings, falling back to defaults for a missing file or missing keys."""
    if not path.exists():
        return Settings()
    with path.open("rb") as fh:
        return Settings.model_validate(tomllib.load(fh))


def save_settings(settings: Settings, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as fh:
        tomli_w.dump(settings.model_dump(), fh)
