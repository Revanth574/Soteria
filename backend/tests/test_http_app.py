from __future__ import annotations

import re
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from soteria.ephemeral import EphemeralConfig, EphemeralStore, SignupFreeFlow
from soteria.extraction import ExtractionResult
from soteria.extraction.errors import MalformedModelOutputError
from soteria.http import create_app


class FakeExtractor:
    def __init__(
        self,
        analysis: dict | None = None,
        *,
        fail: bool = False,
        error: Exception | None = None,
    ) -> None:
        self.analysis = analysis or _analysis_with_private_fields()
        self.fail = fail
        self.error = error

    def analyze(self, document) -> ExtractionResult:
        if self.error is not None:
            raise self.error
        if self.fail:
            raise RuntimeError("synthetic extraction failure")
        return ExtractionResult(json=self.analysis, schema_version=self.analysis["schema_version"])


class ManualBackgroundQueue:
    def __init__(self) -> None:
        self.tasks: list[tuple[Callable[..., Any], tuple[Any, ...], dict[str, Any]]] = []

    def factory(self, _background_tasks) -> "ManualBackgroundQueue":
        return self

    def add_task(self, func: Callable[..., Any], *args: Any, **kwargs: Any) -> None:
        self.tasks.append((func, args, kwargs))

    def run_all(self) -> None:
        tasks = list(self.tasks)
        self.tasks.clear()
        for func, args, kwargs in tasks:
            func(*args, **kwargs)


def _config(tmp_path: Path, *, ttl_seconds: int = 3600, rate_limit: int = 10) -> EphemeralConfig:
    data_dir = tmp_path / "ephemeral"
    return EphemeralConfig(
        database_url=f"sqlite:///{(data_dir / 'soteria_dev.db').as_posix()}",
        ephemeral_data_dir=data_dir,
        ttl_seconds=ttl_seconds,
        max_upload_bytes=1024 * 1024,
        anonymous_uploads_per_ip_per_hour=rate_limit,
    )


def _client(
    tmp_path: Path,
    *,
    analysis: dict | None = None,
    fail: bool = False,
    error: Exception | None = None,
    rate_limit: int = 10,
    trust_proxy_headers: bool = False,
) -> tuple[TestClient, SignupFreeFlow, ManualBackgroundQueue]:
    config = _config(tmp_path, rate_limit=rate_limit)
    flow = SignupFreeFlow(
        store=EphemeralStore(config),
        extractor=FakeExtractor(analysis, fail=fail, error=error),
        config=config,
    )
    queue = ManualBackgroundQueue()
    app = create_app(
        flow=flow,
        config=config,
        trust_proxy_headers=trust_proxy_headers,
        background_queue_factory=queue.factory,
    )
    return TestClient(app, follow_redirects=False), flow, queue


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


def _upload(client: TestClient, pdf_bytes: bytes | None = None):
    return client.post(
        "/upload",
        files={"policy_pdf": ("policy.pdf", pdf_bytes or _pdf_bytes("Policy text"), "application/pdf")},
    )


def _session_from_redirect(response) -> str:
    match = re.fullmatch(r"/a/([a-f0-9]{32})", response.headers["location"])
    assert match is not None
    return match.group(1)


def _analysis_with_private_fields() -> dict:
    return {
        "schema_version": "1.2",
        "summary": "Your policy has a complete anonymous summary.",
        "coverage": {
            "secret_full_tier_field": {
                "value": "Full tier only coverage value",
                "raw_clause": "Full tier coverage clause",
                "confidence": 0.91,
            }
        },
        "waiting_periods": [{"raw_clause": "PED raw clause", "confidence": 0.8}],
        "sub_limits": [{"raw_clause": "Maternity raw clause", "confidence": 0.8}],
        "exclusions": [{"raw_clause": "Cosmetic raw clause", "confidence": 0.8}],
        "red_flags": [
            {
                "title": "XSS red flag",
                "plain_explanation": "A clause contains untrusted markup.",
                "scenario": "If the renderer mishandles it, script markup appears.",
                "raw_clause": "<script>alert(1)</script>",
            }
        ],
    }


def test_xss_survives_http_layer_as_escaped_text(tmp_path: Path) -> None:
    client, _flow, queue = _client(tmp_path)
    upload_response = _upload(client)
    session_token = _session_from_redirect(upload_response)

    queue.run_all()
    response = client.get(f"/a/{session_token}")

    assert response.status_code == 200
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in response.text
    assert "<script>alert(1)</script>" not in response.text


def test_upload_route_returns_413_and_429_plain_language_pages(tmp_path: Path) -> None:
    client, _flow, queue = _client(tmp_path, rate_limit=1)

    oversized = b"%PDF-" + (b"x" * (1024 * 1024 + 20_000))
    oversized_response = _upload(client, oversized)

    assert oversized_response.status_code == 413
    assert "This PDF is too large" in oversized_response.text
    assert "Traceback" not in oversized_response.text

    first = _upload(client)
    assert first.status_code == 303
    queue.run_all()
    second = _upload(client)

    assert second.status_code == 429
    assert "Too many uploads" in second.text
    assert "Traceback" not in second.text


def test_status_processing_complete_and_failed_are_honest_pages(tmp_path: Path) -> None:
    client, _flow, queue = _client(tmp_path)
    upload_response = _upload(client)
    session_token = _session_from_redirect(upload_response)

    processing = client.get(f"/a/{session_token}")
    assert processing.status_code == 200
    assert "Analysis in progress" in processing.text

    queue.run_all()
    complete = client.get(f"/a/{session_token}")
    assert "Your policy has a complete anonymous summary." in complete.text

    failing_client, _failing_flow, failing_queue = _client(tmp_path / "failed", fail=True)
    failed_upload = _upload(failing_client)
    failed_session = _session_from_redirect(failed_upload)
    failing_queue.run_all()
    failed = failing_client.get(f"/a/{failed_session}")

    assert "We could not complete this analysis" in failed.text
    assert "Traceback" not in failed.text
    assert "synthetic extraction failure" not in failed.text


def test_malformed_extractor_output_uses_failure_page_without_raw_response_leak(
    tmp_path: Path,
) -> None:
    raw_response_fragment = "RAW_LLM_RESPONSE_FRAGMENT"
    client, _flow, queue = _client(
        tmp_path,
        error=MalformedModelOutputError(
            f"Model returned malformed JSON: {raw_response_fragment}"
        ),
    )
    upload_response = _upload(client)
    session_token = _session_from_redirect(upload_response)

    queue.run_all()
    failed = client.get(f"/a/{session_token}")

    assert failed.status_code == 200
    assert "We could not complete this analysis" in failed.text
    assert raw_response_fragment not in failed.text
    assert "malformed JSON" not in failed.text
    assert "Traceback" not in failed.text


def test_token_safety_clean_404_pages(tmp_path: Path) -> None:
    client, flow, _queue = _client(tmp_path)

    malformed = client.get("/a/not-a-token")
    unknown = client.get("/a/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa")
    flow.store.create_anonymous_session(
        session_token="bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
        ip_address="203.0.113.1",
        filename="expired.pdf",
        pdf_bytes=_pdf_bytes("Policy text"),
        document_text="Policy text",
        analysis=ExtractionResult(
            json={"schema_version": "1.2", "summary": "Expired"},
            schema_version="1.2",
        ),
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
        expires_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    expired = client.get("/a/bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb")

    assert malformed.status_code == 404
    assert "This analysis is not available" in malformed.text
    assert "Traceback" not in malformed.text
    assert "500" not in malformed.text

    assert unknown.status_code == 404
    assert "This analysis is not available" in unknown.text
    assert "Traceback" not in unknown.text
    assert "500" not in unknown.text

    assert expired.status_code == 404
    assert "This analysis is not available" in expired.text
    assert "Traceback" not in expired.text
    assert "500" not in expired.text


def test_tier_boundary_over_http(tmp_path: Path) -> None:
    client, flow, queue = _client(tmp_path)
    upload_response = _upload(client)
    session_token = _session_from_redirect(upload_response)
    queue.run_all()

    anonymous = client.get(f"/a/{session_token}")

    assert "Full tier only coverage value" not in anonymous.text
    assert "Full tier coverage clause" not in anonymous.text
    assert "Maternity raw clause" not in anonymous.text

    token = flow.issue_signup_token(email="user@example.com", session_token=session_token)
    account = flow.consume_signup_token(token.token)
    assert account.session_token == session_token
    full = client.get(f"/a/{session_token}/full")

    assert "Full tier only coverage value" in full.text
    assert "Full tier coverage clause" in full.text
    assert "Maternity raw clause" in full.text


def test_proxy_headers_are_ignored_by_default_and_trusted_only_when_enabled(tmp_path: Path) -> None:
    default_client, _flow, _queue = _client(tmp_path / "default", rate_limit=1)

    first = default_client.post(
        "/upload",
        files={"policy_pdf": ("policy.pdf", _pdf_bytes("Policy text"), "application/pdf")},
        headers={"X-Forwarded-For": "198.51.100.10"},
    )
    second = default_client.post(
        "/upload",
        files={"policy_pdf": ("policy.pdf", _pdf_bytes("Policy text"), "application/pdf")},
        headers={"X-Forwarded-For": "198.51.100.11"},
    )

    assert first.status_code == 303
    assert second.status_code == 429

    trusted_client, _trusted_flow, _trusted_queue = _client(
        tmp_path / "trusted",
        rate_limit=1,
        trust_proxy_headers=True,
    )
    trusted_first = trusted_client.post(
        "/upload",
        files={"policy_pdf": ("policy.pdf", _pdf_bytes("Policy text"), "application/pdf")},
        headers={"X-Forwarded-For": "198.51.100.10"},
    )
    trusted_second = trusted_client.post(
        "/upload",
        files={"policy_pdf": ("policy.pdf", _pdf_bytes("Policy text"), "application/pdf")},
        headers={"X-Forwarded-For": "198.51.100.11"},
    )

    assert trusted_first.status_code == 303
    assert trusted_second.status_code == 303
