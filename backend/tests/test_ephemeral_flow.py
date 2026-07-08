import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from soteria.ephemeral import (
    EphemeralConfig,
    EphemeralStore,
    RateLimitExceededError,
    SignupFreeFlow,
    StorageConfigurationError,
    UploadValidationError,
)
from soteria.extraction import ExtractionResult


class FakeExtractor:
    def __init__(self) -> None:
        self.calls = 0

    def analyze(self, document) -> ExtractionResult:
        self.calls += 1
        return ExtractionResult(
            json={
                "schema_version": "1.2",
                "summary": "Your policy has a concise test summary.",
                "red_flags": [
                    {"title": "Flag 1", "raw_clause": "Clause 1"},
                    {"title": "Flag 2", "raw_clause": "Clause 2"},
                    {"title": "Flag 3", "raw_clause": "Clause 3"},
                    {"title": "Flag 4", "raw_clause": "Clause 4"},
                ],
            },
            schema_version="1.2",
        )


def _escape_pdf_text(value: str) -> str:
    return value.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _pdf_bytes(text: str) -> bytes:
    stream = (
        "BT\n/F1 12 Tf\n72 720 Td\n"
        f"({_escape_pdf_text(text)}) Tj\n"
        "ET"
    ).encode("latin-1")
    objects: list[tuple[int, bytes]] = [
        (1, b"<< /Type /Catalog /Pages 2 0 R >>"),
        (2, b"<< /Type /Pages /Kids [4 0 R] /Count 1 >>"),
        (3, b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"),
        (
            4,
            b"<< /Type /Page /Parent 2 0 R "
            b"/Resources << /Font << /F1 3 0 R >> >> "
            b"/MediaBox [0 0 612 792] /Contents 5 0 R >>",
        ),
        (
            5,
            b"<< /Length " + str(len(stream)).encode("ascii") + b" >>\n"
            b"stream\n" + stream + b"\nendstream",
        ),
    ]

    pdf = b"%PDF-1.4\n"
    offsets: dict[int, int] = {}
    for object_number, body in objects:
        offsets[object_number] = len(pdf)
        pdf += f"{object_number} 0 obj\n".encode("ascii") + body + b"\nendobj\n"

    startxref = len(pdf)
    pdf += b"xref\n0 6\n0000000000 65535 f \n"
    for object_number in range(1, 6):
        pdf += f"{offsets[object_number]:010d} 00000 n \n".encode("ascii")
    pdf += f"trailer << /Size 6 /Root 1 0 R >>\nstartxref\n{startxref}\n%%EOF\n".encode(
        "ascii"
    )
    return pdf


def _config(tmp_path: Path, *, ttl_seconds: int = 3600, rate_limit: int = 10) -> EphemeralConfig:
    data_dir = tmp_path / "ephemeral"
    return EphemeralConfig(
        database_url=f"sqlite:///{(data_dir / 'soteria_dev.db').as_posix()}",
        ephemeral_data_dir=data_dir,
        ttl_seconds=ttl_seconds,
        max_upload_bytes=1024 * 1024,
        anonymous_uploads_per_ip_per_hour=rate_limit,
    )


def _flow(tmp_path: Path, *, ttl_seconds: int = 3600, rate_limit: int = 10) -> SignupFreeFlow:
    config = _config(tmp_path, ttl_seconds=ttl_seconds, rate_limit=rate_limit)
    return SignupFreeFlow(store=EphemeralStore(config), extractor=FakeExtractor(), config=config)


def test_deletion_job_deletes_records_and_artifacts_not_just_flags(tmp_path: Path) -> None:
    flow = _flow(tmp_path, ttl_seconds=1)
    created_at = datetime(2026, 1, 1, tzinfo=UTC)

    response = flow.submit_anonymous_upload(
        pdf_bytes=_pdf_bytes("Policy text"),
        filename="policy.pdf",
        ip_address="203.0.113.10",
        now=created_at,
    )
    record = flow.store.get_session(response.session_token, now=created_at)

    assert record is not None
    assert record.artifact_path.exists()
    assert flow.store.raw_session_exists(response.session_token)

    deletion_result = flow.delete_expired(now=created_at + timedelta(seconds=2))

    assert deletion_result.deleted_sessions == 1
    assert not flow.store.raw_session_exists(response.session_token)
    assert not record.artifact_path.exists()
    audit_rows = flow.store.list_deletion_audit()
    assert len(audit_rows) == 1
    assert audit_rows[0].session_token == response.session_token
    assert str(record.artifact_path) in audit_rows[0].deleted_artifacts


def test_ttl_is_enforced_on_fetch(tmp_path: Path) -> None:
    flow = _flow(tmp_path, ttl_seconds=1)
    created_at = datetime(2026, 1, 1, tzinfo=UTC)
    response = flow.submit_anonymous_upload(
        pdf_bytes=_pdf_bytes("Policy text"),
        filename="policy.pdf",
        ip_address="203.0.113.11",
        now=created_at,
    )

    assert flow.store.get_session(response.session_token, now=created_at) is not None
    assert flow.store.get_session(
        response.session_token,
        now=created_at + timedelta(seconds=2),
    ) is None


def test_anonymous_upload_guards_run_without_auth(tmp_path: Path) -> None:
    flow = _flow(tmp_path, rate_limit=1)

    with pytest.raises(UploadValidationError, match="PDF"):
        flow.submit_anonymous_upload(
            pdf_bytes=b"not a pdf",
            filename="policy.txt",
            ip_address="203.0.113.12",
        )

    with pytest.raises(UploadValidationError, match="size"):
        flow.submit_anonymous_upload(
            pdf_bytes=b"%PDF-" + (b"x" * (flow.config.max_upload_bytes + 1)),
            filename="too-large.pdf",
            ip_address="203.0.113.13",
        )

    flow.submit_anonymous_upload(
        pdf_bytes=_pdf_bytes("Policy text"),
        filename="policy.pdf",
        ip_address="203.0.113.14",
    )
    with pytest.raises(RateLimitExceededError, match="rate limit"):
        flow.submit_anonymous_upload(
            pdf_bytes=_pdf_bytes("Policy text"),
            filename="policy.pdf",
            ip_address="203.0.113.14",
        )


def test_signup_free_preview_contains_summary_and_top_three_red_flags(tmp_path: Path) -> None:
    flow = _flow(tmp_path)

    response = flow.submit_anonymous_upload(
        pdf_bytes=_pdf_bytes("Policy text"),
        filename="policy.pdf",
        ip_address="203.0.113.15",
    )

    assert response.preview.summary == "Your policy has a concise test summary."
    assert [flag["title"] for flag in response.preview.red_flags] == ["Flag 1", "Flag 2", "Flag 3"]
    assert all("raw_clause" in flag for flag in response.preview.red_flags)


def test_session_to_account_attachment_makes_anonymous_document_retrievable_under_account(
    tmp_path: Path,
) -> None:
    flow = _flow(tmp_path, ttl_seconds=1)
    created_at = datetime(2026, 1, 1, tzinfo=UTC)
    response = flow.submit_anonymous_upload(
        pdf_bytes=_pdf_bytes("Policy text"),
        filename="policy.pdf",
        ip_address="203.0.113.16",
        now=created_at,
    )

    signup_token = flow.issue_signup_token(
        email="user@example.com",
        session_token=response.session_token,
        now=created_at,
    )
    account = flow.consume_signup_token(signup_token.token, now=created_at)
    record = flow.store.get_account_session(
        account.account_id,
        response.session_token,
        now=created_at + timedelta(days=2),
    )

    assert record is not None
    assert record.account_id == account.account_id
    assert json.loads(record.analysis_json)["summary"] == "Your policy has a concise test summary."


def test_delete_expired_skips_account_attached_sessions_and_artifacts(tmp_path: Path) -> None:
    flow = _flow(tmp_path, ttl_seconds=1)
    created_at = datetime(2026, 1, 1, tzinfo=UTC)
    response = flow.submit_anonymous_upload(
        pdf_bytes=_pdf_bytes("Policy text"),
        filename="policy.pdf",
        ip_address="203.0.113.17",
        now=created_at,
    )
    signup_token = flow.issue_signup_token(
        email="user@example.com",
        session_token=response.session_token,
        now=created_at,
    )
    account = flow.consume_signup_token(signup_token.token, now=created_at)
    attached_record = flow.store.get_account_session(
        account.account_id,
        response.session_token,
        now=created_at,
    )

    assert attached_record is not None
    assert attached_record.artifact_path.exists()

    deletion_result = flow.delete_expired(now=created_at + timedelta(days=2))
    still_attached_record = flow.store.get_account_session(
        account.account_id,
        response.session_token,
        now=created_at + timedelta(days=2),
    )

    assert deletion_result.deleted_sessions == 0
    assert still_attached_record is not None
    assert still_attached_record.artifact_path.exists()
    assert flow.store.raw_session_exists(response.session_token)
    assert not any(
        row.session_token == response.session_token
        for row in flow.store.list_deletion_audit()
    )


def test_hostile_upload_filenames_cannot_influence_artifact_path(tmp_path: Path) -> None:
    flow = _flow(tmp_path)
    hostile_filenames = [
        "../../../evil.pdf",
        "C:/Windows/evil.pdf",
        "bad\x00name.pdf",
    ]

    for index, filename in enumerate(hostile_filenames):
        response = flow.submit_anonymous_upload(
            pdf_bytes=_pdf_bytes("Policy text"),
            filename=filename,
            ip_address=f"203.0.113.{30 + index}",
        )
        record = flow.store.get_session(response.session_token, now=datetime.now(UTC))

        assert record is not None
        assert record.artifact_path.resolve().is_relative_to(
            flow.config.ephemeral_data_dir.resolve()
        )
        assert record.artifact_path.parent.name == response.session_token
        assert record.artifact_path.name == "uploaded_policy.pdf"


def test_database_file_must_live_under_ephemeral_data_dir(tmp_path: Path) -> None:
    data_dir = tmp_path / "ephemeral"
    outside_db = tmp_path / "outside" / "soteria_dev.db"

    with pytest.raises(StorageConfigurationError, match="EPHEMERAL_DATA_DIR"):
        EphemeralConfig(
            database_url=f"sqlite:///{outside_db.as_posix()}",
            ephemeral_data_dir=data_dir,
            ttl_seconds=3600,
            max_upload_bytes=1024,
            anonymous_uploads_per_ip_per_hour=10,
        )
