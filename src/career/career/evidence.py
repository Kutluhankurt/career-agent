"""Evidence items (roadmap §21). Every career claim points at some of these."""

import hashlib
from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel


class TruthState(StrEnum):
    """Roadmap §22. Only OBSERVED and CONFIRMED facts may reach the CV without a warning."""

    OBSERVED = "observed"
    INFERRED = "inferred"
    CONFIRMED = "confirmed"
    REJECTED = "rejected"


class EvidenceType(StrEnum):
    APPLICATION = "application"
    WINDOW = "window"
    FILE = "file"
    GIT = "git"
    BROWSER = "browser"
    TICKET = "ticket"
    COMMAND = "command"
    USER_CONFIRMATION = "user_confirmation"


LABELS = {
    EvidenceType.APPLICATION: "App", EvidenceType.WINDOW: "Window", EvidenceType.FILE: "File",
    EvidenceType.GIT: "Commit", EvidenceType.BROWSER: "Site", EvidenceType.TICKET: "Ticket",
    EvidenceType.COMMAND: "Command", EvidenceType.USER_CONFIRMATION: "You confirmed",
}


class Evidence(BaseModel):
    id: str
    type: EvidenceType
    value: str
    label: str
    observed_at: datetime | None = None
    session_id: str | None = None


def make_evidence(type: EvidenceType, value: str, session_id: str | None = None, observed_at: datetime | None = None) -> Evidence:
    digest = hashlib.sha1(f"{session_id}|{type}|{value}".encode()).hexdigest()[:12]
    return Evidence(id=digest, type=type, value=value, label=LABELS[type], observed_at=observed_at, session_id=session_id)
