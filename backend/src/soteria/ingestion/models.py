from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Literal, Mapping

from soteria.ingestion.errors import EmptyExtractionError

SourceType = Literal["pdf_upload", "camera_capture", "structured_policy", "nhcx_claim"]
PolicyKind = Literal["retail_individual", "retail_floater", "group_certificate", "unknown"]


@dataclass(frozen=True, slots=True)
class CanonicalPolicyPage:
    page_number: int
    text: str

    @property
    def char_count(self) -> int:
        return len(self.text)


@dataclass(frozen=True, slots=True)
class CanonicalPolicyDocument:
    full_text: str
    source_type: SourceType
    checksum: str
    pages: list[CanonicalPolicyPage] | None = None
    structured_fields: Mapping[str, Any] | None = None
    source_metadata: Mapping[str, Any] = field(default_factory=dict)
    ingested_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    policy_kind: PolicyKind = "unknown"

    def __post_init__(self) -> None:
        if not self.full_text.strip():
            raise EmptyExtractionError("Refusing to create empty canonical document.")
        if self.pages == []:
            raise EmptyExtractionError("Refusing to create empty canonical document.")
