from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Boolean, DateTime, Float, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class EventRow(Base):
    """Raw normalized event. OS-specific details go into `meta` so the schema stays stable."""

    __tablename__ = "events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    type: Mapped[str] = mapped_column(String(32), index=True)
    application: Mapped[str | None] = mapped_column(String(255))
    title: Mapped[str | None] = mapped_column(Text)
    meta: Mapped[dict[str, Any]] = mapped_column("metadata", JSON, default=dict)
    source: Mapped[str] = mapped_column(String(32))


class SessionRow(Base):
    """A work session built by the Session Engine. Rebuilt deterministically from events."""

    __tablename__ = "sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    start: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    end: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    active_seconds: Mapped[float] = mapped_column(Float)
    idle_seconds: Mapped[float] = mapped_column(Float)
    event_count: Mapped[int] = mapped_column(Integer)
    label: Mapped[str] = mapped_column(String(255))
    score: Mapped[float] = mapped_column(Float)
    is_open: Mapped[bool] = mapped_column(Boolean, default=False)
    data: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


# --- Career Memory (migration v3) ------------------------------------------------
# Truth states (roadmap §22): observed | inferred | confirmed | rejected


class ProfileRow(Base):
    __tablename__ = "user_profile"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    data: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    setup_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ProjectRow(Base):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    state: Mapped[str] = mapped_column(String(16), default="inferred")
    color: Mapped[int] = mapped_column(Integer, default=0)
    aliases: Mapped[list[str]] = mapped_column(JSON, default=list)  # "workspace:supervisor", "ticket:AI", "repo:x"
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    merged_into: Mapped[str | None] = mapped_column(String(36), nullable=True)


class AnalysisRow(Base):
    """What a session was about. Survives session rebuilds (keyed by the stable session id)."""

    __tablename__ = "ai_analysis"

    session_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    day: Mapped[str] = mapped_column(String(10), index=True)
    activity: Mapped[str] = mapped_column(String(255))
    category: Mapped[str] = mapped_column(String(64))
    project_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    confidence: Mapped[float] = mapped_column(Float)
    skills: Mapped[list[str]] = mapped_column(JSON, default=list)
    evidence: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    state: Mapped[str] = mapped_column(String(16), default="inferred")
    provider: Mapped[str] = mapped_column(String(32))
    model: Mapped[str | None] = mapped_column(String(64), nullable=True)
    session_events: Mapped[int] = mapped_column(Integer, default=0)
    active_seconds: Mapped[float] = mapped_column(Float, default=0)
    edited: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class SkillRow(Base):
    __tablename__ = "skills"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(128), unique=True)
    category: Mapped[str] = mapped_column(String(32))
    state: Mapped[str] = mapped_column(String(16), default="inferred")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class SkillScoreRow(Base):
    __tablename__ = "skill_scores"

    skill_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    day: Mapped[str] = mapped_column(String(10), primary_key=True)
    score: Mapped[float] = mapped_column(Float)
    factors: Mapped[dict[str, float]] = mapped_column(JSON, default=dict)


class AchievementRow(Base):
    __tablename__ = "achievements"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    key: Mapped[str] = mapped_column(String(255), unique=True)
    title: Mapped[str] = mapped_column(String(500))
    project_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    ticket: Mapped[str | None] = mapped_column(String(64), nullable=True)
    state: Mapped[str] = mapped_column(String(16), default="inferred")
    confidence: Mapped[float] = mapped_column(Float)
    steps: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    impact: Mapped[str | None] = mapped_column(Text, nullable=True)
    on_cv: Mapped[bool] = mapped_column(Boolean, default=False)
    session_ids: Mapped[list[str]] = mapped_column(JSON, default=list)
    edited: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ReviewRow(Base):
    __tablename__ = "review_items"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    kind: Mapped[str] = mapped_column(String(16))
    ref_id: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(16), default="pending", index=True)
    data: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class CVBulletRow(Base):
    __tablename__ = "cv_bullets"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    key: Mapped[str] = mapped_column(String(255), unique=True)
    project_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    project_name: Mapped[str] = mapped_column(String(255))
    text: Mapped[str] = mapped_column(Text)
    evidence: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    confidence: Mapped[float] = mapped_column(Float)
    state: Mapped[str] = mapped_column(String(16))
    edited: Mapped[bool] = mapped_column(Boolean, default=False)
    position: Mapped[int] = mapped_column(Integer, default=0)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class StateRow(Base):
    """Small key/value store for engine state (co-occurrence counts, last runs...)."""

    __tablename__ = "kv_state"

    key: Mapped[str] = mapped_column(String(128), primary_key=True)
    value: Mapped[Any] = mapped_column(JSON)
