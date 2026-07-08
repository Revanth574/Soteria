from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass(frozen=True, slots=True)
class SignupFreePreview:
    summary: Any
    red_flags: list[dict[str, Any]]


@dataclass(frozen=True, slots=True)
class AnonymousAnalysisResponse:
    session_token: str
    expires_at: datetime
    preview: SignupFreePreview


@dataclass(frozen=True, slots=True)
class EphemeralSessionRecord:
    session_token: str
    artifact_path: Path
    analysis_json: str
    document_text: str
    expires_at: datetime | None
    account_id: str | None


@dataclass(frozen=True, slots=True)
class SignupToken:
    token: str
    email: str
    session_token: str
    expires_at: datetime


@dataclass(frozen=True, slots=True)
class AccountAttachment:
    account_id: str
    email: str
    session_token: str


@dataclass(frozen=True, slots=True)
class DeletionResult:
    deleted_sessions: int
    deleted_artifacts: list[str]


@dataclass(frozen=True, slots=True)
class DeletionAuditRow:
    session_token: str
    deleted_at: datetime
    deleted_records: list[str]
    deleted_artifacts: list[str]
    reason: str

