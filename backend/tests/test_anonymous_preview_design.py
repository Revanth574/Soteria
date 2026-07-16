from __future__ import annotations

import html
from pathlib import Path
import re

from fastapi.testclient import TestClient

from soteria.ephemeral import EphemeralConfig, EphemeralStore, SignupFreeFlow
from soteria.extraction import ExtractionResult
from soteria.http import create_app
from soteria.web import render_anonymous_results


class FakeExtractor:
    def __init__(self, analysis: dict) -> None:
        self.analysis = analysis

    def analyze(self, _document) -> ExtractionResult:
        return ExtractionResult(json=self.analysis, schema_version="1.2")


def _analysis(*, flag_count: int = 5) -> dict:
    return {
        "schema_version": "1.2",
        "metadata": {
            "insurer_name": "Boundary Test Insurance",
            "product_name": "Boundary Test Policy",
            "product_uin": "TSTHLIP00001V012026",
        },
        "summary": (
            "Your deductible and co-pay need attention. "
            "The Sum Insured remains subject to the policy wording."
        ),
        "coverage": {
            "private_field": {
                "covered": True,
                "raw_clause": "FULL-TIER COVERAGE CLAUSE",
            }
        },
        "waiting_periods": [
            {
                "category": "pre_existing_disease",
                "duration_months": 36,
                "raw_clause": "FULL-TIER WAITING CLAUSE",
            }
        ],
        "sub_limits": [
            {"applies_to": "Maternity", "raw_clause": "FULL-TIER SUB-LIMIT CLAUSE"}
        ],
        "exclusions": [
            {"description": "Cosmetic treatment", "raw_clause": "FULL-TIER EXCLUSION CLAUSE"}
        ],
        "red_flags": [
            {
                "id": f"flag_{index}",
                "severity": "high" if index == 1 else "medium",
                "title": f"Flag {index}",
                "plain_explanation": f"Takeaway {index} about a waiting period.",
                "financial_impact_estimate": f"Cost estimate {index}.",
                "scenario": f"Scenario {index} affecting your Sum Insured.",
                "what_to_do": f"Action {index}.",
                "raw_clause": f"Verbatim clause {index}.",
                "clause_reference": f"Clause {index}",
            }
            for index in range(1, flag_count + 1)
        ],
    }


def test_anonymous_raw_clause_uses_shared_card_and_escapes_hostile_content() -> None:
    analysis = _analysis(flag_count=1)
    hostile_clause = '<script>alert("claim")</script> A < B & C'
    analysis["red_flags"][0]["raw_clause"] = hostile_clause

    rendered = render_anonymous_results(analysis, session_token="session-token")

    assert rendered.count('class="risk-card"') == 1
    assert '<details class="verified-wording">' in rendered
    assert hostile_clause in html.unescape(rendered)
    assert "<script>" not in rendered
    assert "&lt;script&gt;" in rendered
    assert "A &lt; B &amp; C" in rendered


def test_anonymous_refresh_preserves_pre_refresh_tier_boundary_and_signup_form() -> None:
    rendered = render_anonymous_results(_analysis(), session_token="opaque-session-token")

    visible_text = html.unescape(re.sub(r"<[^>]+>", "", rendered))
    assert "Your Deductible and Co-pay need attention." in visible_text
    assert rendered.count('class="risk-card"') == 3
    assert "Flag 1" in rendered
    assert "Flag 3" in rendered
    assert "Flag 4" not in rendered
    assert "Verbatim clause 1." in rendered
    assert "Verbatim clause 3." in rendered
    assert "Verbatim clause 4." not in rendered
    assert "FULL-TIER COVERAGE CLAUSE" not in rendered
    assert "FULL-TIER WAITING CLAUSE" not in rendered
    assert "FULL-TIER SUB-LIMIT CLAUSE" not in rendered
    assert "FULL-TIER EXCLUSION CLAUSE" not in rendered
    assert "View extracted data" not in rendered
    assert 'class="waiting-section"' not in rendered
    assert 'class="coverage-gap-grid"' not in rendered
    assert 'method="post" action="/signup/request"' in rendered
    assert 'name="session_token" value="opaque-session-token"' in rendered
    assert 'name="email"' in rendered
    assert "Keep this analysis" in rendered


def test_anonymous_summary_and_cards_use_shared_glossary_matcher() -> None:
    rendered = render_anonymous_results(_analysis(flag_count=1), session_token="session-token")

    assert '>Deductible<' in rendered
    assert (
        'data-definition="A fixed amount you pay on every claim before the insurer pays anything."'
        in rendered
    )
    assert '>Co-pay<' in rendered
    assert (
        'data-definition="A share of each bill you must pay yourself, usually a percentage."'
        in rendered
    )
    assert '>Sum Insured<' in rendered
    assert '>Waiting period<' in rendered


def test_anonymous_uses_shared_stylesheet_and_no_inline_palette() -> None:
    rendered = render_anonymous_results(_analysis(flag_count=1), session_token="session-token")

    assert '<link rel="stylesheet" href="/static/full-analysis.css">' in rendered
    assert "<style" not in rendered
    assert "#FCFAF3" not in rendered
    assert "#0C0E09" not in rendered


def test_theme_cookie_set_on_anonymous_page_is_honored_on_full_page(tmp_path: Path) -> None:
    analysis = _analysis()
    config = _config(tmp_path)
    flow = SignupFreeFlow(
        store=EphemeralStore(config),
        extractor=FakeExtractor(analysis),
        config=config,
    )
    upload = flow.submit_anonymous_upload(
        pdf_bytes=_pdf_bytes("Policy text"),
        filename="policy.pdf",
        ip_address="203.0.113.90",
    )
    signup_token = flow.issue_signup_token(
        email="user@example.com",
        session_token=upload.session_token,
    )
    flow.consume_signup_token(signup_token.token)
    app = create_app(
        flow=flow,
        config=config,
        public_base_url="https://soteria.test",
    )
    client = TestClient(app, base_url="https://soteria.test", follow_redirects=False)
    anonymous_path = f"/a/{upload.session_token}"
    full_path = f"{anonymous_path}/full"

    initial = client.get(anonymous_path)
    toggle = client.post("/theme", data={"theme": "dark", "next": anonymous_path})
    anonymous_dark = client.get(anonymous_path)
    full_dark = client.get(full_path)

    assert 'data-theme="light"' in initial.text
    assert toggle.status_code == 303
    assert "soteria_theme=dark" in toggle.headers["set-cookie"]
    assert 'data-theme="dark"' in anonymous_dark.text
    assert 'data-theme="dark"' in full_dark.text


def _config(tmp_path: Path) -> EphemeralConfig:
    data_dir = tmp_path / "ephemeral"
    return EphemeralConfig(
        database_url=f"sqlite:///{(data_dir / 'soteria_dev.db').as_posix()}",
        ephemeral_data_dir=data_dir,
        ttl_seconds=3600,
        max_upload_bytes=1024 * 1024,
        anonymous_uploads_per_ip_per_hour=10,
    )


def _pdf_bytes(text: str) -> bytes:
    escaped = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    stream = ("BT\n/F1 12 Tf\n72 720 Td\n" f"({escaped}) Tj\n" "ET").encode("latin-1")
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
            b"<< /Length "
            + str(len(stream)).encode("ascii")
            + b" >>\nstream\n"
            + stream
            + b"\nendstream",
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
    pdf += (
        f"trailer << /Size 6 /Root 1 0 R >>\nstartxref\n{startxref}\n%%EOF\n".encode(
            "ascii"
        )
    )
    return pdf
