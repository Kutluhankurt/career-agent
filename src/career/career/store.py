"""Data access for Career Memory tables (kept apart from raw event storage)."""

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import delete, select

from career.database.database import Database
from career.database.models import (
    AchievementRow, AnalysisRow, CVBulletRow, ProfileRow, ProjectRow, ReviewRow, SkillRow, SkillScoreRow, StateRow,
)
from career.events.models import utc_now
from career.profile.models import Profile


def new_id() -> str:
    return str(uuid.uuid4())


class MemoryStore:
    def __init__(self, db: Database):
        self.db = db

    # profile ----------------------------------------------------------------
    def get_profile(self) -> Profile:
        with self.db.session() as s:
            row = s.get(ProfileRow, 1)
            if row is None:
                return Profile()
            setup_at = row.setup_at
            if setup_at is not None and setup_at.tzinfo is None:
                setup_at = setup_at.replace(tzinfo=timezone.utc)  # SQLite drops tzinfo; stored as UTC
            return Profile.model_validate({**(row.data or {}), "setup_at": setup_at})

    def save_profile(self, profile: Profile) -> Profile:
        if profile.setup_at is None:
            profile = profile.model_copy(update={"setup_at": utc_now()})
        elif profile.setup_at.tzinfo is None:
            profile = profile.model_copy(update={"setup_at": profile.setup_at.replace(tzinfo=timezone.utc)})
        else:
            profile = profile.model_copy(update={"setup_at": profile.setup_at.astimezone(timezone.utc)})
        with self.db.session() as s, s.begin():
            row = s.get(ProfileRow, 1) or ProfileRow(id=1)
            row.data = profile.model_dump(mode="json", exclude={"setup_at"})
            row.setup_at = profile.setup_at
            s.merge(row)
        return profile

    # kv state ---------------------------------------------------------------
    def get_state(self, key: str, default: Any = None) -> Any:
        with self.db.session() as s:
            row = s.get(StateRow, key)
            return row.value if row else default

    def set_state(self, key: str, value: Any) -> None:
        with self.db.session() as s, s.begin():
            s.merge(StateRow(key=key, value=value))

    # generic helpers ----------------------------------------------------------
    def all(self, model, *where, order_by=None) -> list:
        stmt = select(model).where(*where)
        if order_by is not None:
            stmt = stmt.order_by(order_by)
        with self.db.session() as s:
            return list(s.scalars(stmt))

    def get(self, model, key):
        with self.db.session() as s:
            return s.get(model, key)

    def save(self, *rows) -> None:
        with self.db.session() as s, s.begin():
            for row in rows:
                s.merge(row)

    def remove(self, model, *where) -> None:
        with self.db.session() as s, s.begin():
            s.execute(delete(model).where(*where))

    # typed shortcuts ------------------------------------------------------------
    def projects(self, include_merged: bool = False) -> list[ProjectRow]:
        rows = self.all(ProjectRow, order_by=ProjectRow.created_at)
        return rows if include_merged else [p for p in rows if not p.merged_into]

    def analyses(self, since_day: str | None = None, until_day: str | None = None) -> list[AnalysisRow]:
        where = []
        if since_day:
            where.append(AnalysisRow.day >= since_day)
        if until_day:
            where.append(AnalysisRow.day <= until_day)
        return self.all(AnalysisRow, *where, order_by=AnalysisRow.created_at)

    def skills(self) -> list[SkillRow]:
        return self.all(SkillRow, order_by=SkillRow.name)

    def skill_scores(self, skill_id: str) -> list[SkillScoreRow]:
        return self.all(SkillScoreRow, SkillScoreRow.skill_id == skill_id, order_by=SkillScoreRow.day)

    def achievements(self) -> list[AchievementRow]:
        return self.all(AchievementRow, order_by=AchievementRow.created_at)

    def reviews(self, status: str | None = "pending") -> list[ReviewRow]:
        where = [ReviewRow.status == status] if status else []
        return self.all(ReviewRow, *where, order_by=ReviewRow.created_at)

    def cv_bullets(self) -> list[CVBulletRow]:
        return self.all(CVBulletRow, order_by=CVBulletRow.position)

    @staticmethod
    def now() -> datetime:
        return utc_now()
