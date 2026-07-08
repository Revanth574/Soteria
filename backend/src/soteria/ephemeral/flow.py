from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Protocol
from uuid import uuid4

from soteria.ephemeral.config import EphemeralConfig
from soteria.ephemeral.errors import RateLimitExceededError, UploadValidationError
from soteria.ephemeral.models import (
    AccountAttachment,
    AnonymousAnalysisResponse,
    DeletionResult,
    SignupFreePreview,
    SignupToken,
)
from soteria.ephemeral.store import EphemeralStore
from soteria.extraction import ExtractionResult
from soteria.ingestion import CanonicalPolicyDocument, PdfUploadSource

_PDF_MAGIC = b"%PDF-"


class Extractor(Protocol):
    def analyze(self, document) -> ExtractionResult:
        """Analyze a canonical policy document."""


class SignupFreeFlow:
    def __init__(
        self,
        *,
        store: EphemeralStore,
        extractor: Extractor,
        config: EphemeralConfig,
    ) -> None:
        self.store = store
        self.extractor = extractor
        self.config = config
        self._rate_limiter = _InMemoryRateLimiter(
            limit=config.anonymous_uploads_per_ip_per_hour,
            window=timedelta(hours=1),
        )

    def submit_anonymous_upload(
        self,
        *,
        pdf_bytes: bytes,
        filename: str,
        ip_address: str,
        now: datetime | None = None,
        analyze_inline: bool = True,
    ) -> AnonymousAnalysisResponse:
        now = now or datetime.now(UTC)
        self._validate_upload(pdf_bytes)
        self._rate_limiter.check(ip_address=ip_address, now=now)

        document = PdfUploadSource(pdf_bytes, filename=filename).ingest()
        session_token = uuid4().hex
        expires_at = now + timedelta(seconds=self.config.ttl_seconds)

        self.store.create_anonymous_session(
            session_token=session_token,
            ip_address=ip_address,
            filename=filename,
            pdf_bytes=pdf_bytes,
            document_text=document.full_text,
            analysis=None,
            status="processing",
            created_at=now,
            expires_at=expires_at,
        )

        if analyze_inline:
            extraction_result = self.complete_analysis(session_token=session_token, now=now)
        else:
            extraction_result = None

        return AnonymousAnalysisResponse(
            session_token=session_token,
            expires_at=expires_at,
            preview=_preview_from_analysis(extraction_result),
        )

    def complete_analysis(
        self,
        *,
        session_token: str,
        now: datetime | None = None,
    ) -> ExtractionResult:
        record = self.store.get_session(session_token, now=now or datetime.now(UTC))
        if record is None:
            raise LookupError("Ephemeral session is not available for analysis.")
        try:
            document = CanonicalPolicyDocument(
                full_text=record.document_text,
                source_type="pdf_upload",
                checksum="stored-ephemeral-session",
                pages=None,
                source_metadata={"session_token": session_token},
            )
            extraction_result = self.extractor.analyze(document)
        except Exception as exc:
            self.store.mark_analysis_failed(
                session_token=session_token,
                failure_message="Analysis failed before a valid result was produced.",
            )
            raise exc
        self.store.mark_analysis_complete(
            session_token=session_token,
            analysis=extraction_result,
        )
        return extraction_result

    def issue_signup_token(
        self,
        *,
        email: str,
        session_token: str,
        now: datetime | None = None,
    ) -> SignupToken:
        now = now or datetime.now(UTC)
        token = SignupToken(
            token=uuid4().hex,
            email=email,
            session_token=session_token,
            expires_at=now + timedelta(minutes=30),
        )
        self.store.create_signup_token(token=token, created_at=now)
        return token

    def consume_signup_token(
        self,
        token: str,
        *,
        now: datetime | None = None,
    ) -> AccountAttachment:
        now = now or datetime.now(UTC)
        return self.store.consume_signup_token(token=token, now=now)

    def delete_expired(self, *, now: datetime | None = None) -> DeletionResult:
        return self.store.delete_expired(now=now or datetime.now(UTC))

    def _validate_upload(self, pdf_bytes: bytes) -> None:
        if len(pdf_bytes) > self.config.max_upload_bytes:
            raise UploadValidationError("Upload size exceeds the configured max file size.")
        if not pdf_bytes.startswith(_PDF_MAGIC):
            raise UploadValidationError("Anonymous upload must be a PDF.")


def _preview_from_analysis(extraction_result: ExtractionResult | None) -> SignupFreePreview:
    payload = extraction_result.json if extraction_result is not None else {}
    red_flags = payload.get("red_flags") or []
    if not isinstance(red_flags, list):
        red_flags = []
    return SignupFreePreview(
        summary=payload.get("summary"),
        red_flags=red_flags[:3],
    )


class _InMemoryRateLimiter:
    def __init__(self, *, limit: int, window: timedelta) -> None:
        self.limit = limit
        self.window = window
        self._hits: dict[str, list[datetime]] = {}

    def check(self, *, ip_address: str, now: datetime) -> None:
        window_start = now - self.window
        hits = [hit for hit in self._hits.get(ip_address, []) if hit > window_start]
        if len(hits) >= self.limit:
            self._hits[ip_address] = hits
            raise RateLimitExceededError("Anonymous upload rate limit exceeded.")
        hits.append(now)
        self._hits[ip_address] = hits
