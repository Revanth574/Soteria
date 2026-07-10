from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import pytest
from fastapi.testclient import TestClient

from soteria.ephemeral import EphemeralConfig, EphemeralStore, SignupFreeFlow
from soteria.email import EmailConfig, LoggingEmailSender, build_magic_link_email, create_email_sender
from soteria.extraction import ExtractionResult
from soteria.http.app import _build_magic_link_url


class FakeExtractor:
    def analyze(self, document) -> ExtractionResult:
        analysis = {
            "schema_version": "1.2",
            "summary": "Your policy has a complete anonymous summary.",
            "coverage": {
                "secret_full_tier_field": {
                    "value": "Full tier only coverage value",
                    "raw_clause": "Full tier coverage clause",
                    "confidence": 0.91,
                }
            },
            "red_flags": [],
        }
        return ExtractionResult(json=analysis, schema_version="1.2")


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


class RecordingEmailSender:
    def __init__(self) -> None:
        self.calls: list[dict[str, str]] = []

    def send_magic_link(self, *, to_email: str, magic_link_url: str) -> None:
        self.calls.append({"to_email": to_email, "magic_link_url": magic_link_url})


@pytest.fixture
def http_signup_client(tmp_path: Path):
    from soteria.http import create_app

    data_dir = tmp_path / "ephemeral"
    config = EphemeralConfig(
        database_url=f"sqlite:///{(data_dir / 'soteria_dev.db').as_posix()}",
        ephemeral_data_dir=data_dir,
        ttl_seconds=3600,
        max_upload_bytes=1024 * 1024,
        anonymous_uploads_per_ip_per_hour=10,
    )
    flow = SignupFreeFlow(
        store=EphemeralStore(config),
        extractor=FakeExtractor(),
        config=config,
    )
    queue = ManualBackgroundQueue()
    sender = RecordingEmailSender()
    app = create_app(
        flow=flow,
        config=config,
        background_queue_factory=queue.factory,
        email_sender=sender,
        public_base_url="https://soteria.test",
    )
    return TestClient(app, follow_redirects=False), flow, queue, sender


def test_stub_sender_is_selected_when_resend_api_key_is_unset() -> None:
    config = EmailConfig.from_env(
        env={
            "SOTERIA_PUBLIC_BASE_URL": "https://soteria.co.in",
            "EMAIL_FROM_ADDRESS": "noreply@soteria.co.in",
        }
    )

    sender = create_email_sender(config)

    assert isinstance(sender, LoggingEmailSender)


def test_magic_link_email_body_contains_link_and_no_policy_or_analysis_content() -> None:
    magic_link_url = "https://soteria.co.in/signup/confirm/token123"

    email = build_magic_link_email(magic_link_url=magic_link_url, expires_minutes=30)

    assert email.subject == "Your Soteria analysis link"
    assert magic_link_url in email.text
    assert magic_link_url in email.html
    assert "Policy full text" not in email.text
    assert "Policy full text" not in email.html
    assert "Your policy has a complete anonymous summary" not in email.text
    assert "Your policy has a complete anonymous summary" not in email.html


def test_magic_link_url_is_absolute_https_and_points_to_confirm_route() -> None:
    url = _build_magic_link_url(
        public_base_url="https://soteria.co.in/",
        token="abc123",
    )

    parsed = urlparse(url)
    assert parsed.scheme == "https"
    assert parsed.netloc == "soteria.co.in"
    assert parsed.path == "/signup/confirm/abc123"


def test_signup_request_sends_magic_link_once_to_correct_recipient(http_signup_client) -> None:
    client, _flow, queue, sender = http_signup_client
    upload_response = client.post(
        "/upload",
        files={"policy_pdf": ("policy.pdf", _pdf_bytes("Policy text"), "application/pdf")},
    )
    session_token = upload_response.headers["location"].removeprefix("/a/")
    queue.run_all()

    response = client.post(
        "/signup/request",
        data={"email": "user@example.com", "session_token": session_token},
    )

    assert response.status_code == 200
    assert len(sender.calls) == 1
    call = sender.calls[0]
    assert call["to_email"] == "user@example.com"
    parsed = urlparse(call["magic_link_url"])
    assert parsed.scheme == "https"
    assert parsed.netloc == "soteria.test"
    assert parsed.path.startswith("/signup/confirm/")
    emailed_token = parsed.path.removeprefix("/signup/confirm/")
    assert emailed_token in response.text
    assert "DEV-ONLY" in response.text


def test_signup_confirm_still_attaches_session_from_emailed_link(http_signup_client) -> None:
    client, flow, queue, sender = http_signup_client
    upload_response = client.post(
        "/upload",
        files={"policy_pdf": ("policy.pdf", _pdf_bytes("Policy text"), "application/pdf")},
    )
    session_token = upload_response.headers["location"].removeprefix("/a/")
    queue.run_all()

    client.post(
        "/signup/request",
        data={"email": "user@example.com", "session_token": session_token},
    )
    magic_link_url = sender.calls[0]["magic_link_url"]
    confirm_path = urlparse(magic_link_url).path
    confirm_response = client.get(confirm_path)

    assert confirm_response.status_code == 303
    assert confirm_response.headers["location"] == f"/a/{session_token}/full"
    full_response = client.get(f"/a/{session_token}/full")
    assert full_response.status_code == 200
    assert "Full tier only coverage value" in full_response.text


def _pdf_bytes(text: str) -> bytes:
    escaped = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    stream = (
        "BT\n/F1 12 Tf\n72 720 Td\n"
        f"({escaped}) Tj\n"
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
