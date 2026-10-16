"""Request bodies for the local API (responses follow docs/API.md)."""

from typing import Literal

from pydantic import BaseModel, Field


class PauseBody(BaseModel):
    minutes: float = Field(default=60, gt=0, le=24 * 60)


class SessionReviewBody(BaseModel):
    action: Literal["confirm", "reject", "edit"]
    activity: str | None = None
    project_id: str | None = None
    skills: list[str] | None = None


class ReviewBody(BaseModel):
    action: Literal["confirm", "reject", "edit", "answer"]
    title: str | None = None
    answer: str | None = None


class ProjectPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    state: Literal["observed", "inferred", "confirmed", "rejected"] | None = None


class MergeBody(BaseModel):
    into_id: str


class SkillPatch(BaseModel):
    state: Literal["observed", "inferred", "confirmed", "rejected"]


class AchievementPatch(BaseModel):
    title: str | None = Field(default=None, min_length=3, max_length=300)
    state: Literal["observed", "inferred", "confirmed", "rejected"] | None = None
    impact: str | None = Field(default=None, max_length=300)
    on_cv: bool | None = None


class BulletPatch(BaseModel):
    text: str = Field(min_length=3, max_length=400)


class AnalyzeBody(BaseModel):
    date: str | None = None
