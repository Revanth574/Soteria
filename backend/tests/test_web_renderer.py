from datetime import UTC, datetime, timedelta
import html
import json
from pathlib import Path

from soteria.ephemeral import EphemeralConfig, EphemeralStore, SignupFreeFlow
from soteria.extraction import ExtractionResult
from soteria.web import (
    AnalysisWebController,
    render_anonymous_results,
    render_full_results,
    render_session_page,
    render_signup_gate,
    render_upload_page,
)


class FakeExtractor:
    def __init__(self, analysis: dict) -> None:
        self.analysis = analysis

    def analyze(self, document) -> ExtractionResult:
        return ExtractionResult(json=self.analysis, schema_version=self.analysis["schema_version"])


def _config(tmp_path: Path, *, ttl_seconds: int = 3600) -> EphemeralConfig:
    data_dir = tmp_path / "ephemeral"
    return EphemeralConfig(
        database_url=f"sqlite:///{(data_dir / 'soteria_dev.db').as_posix()}",
        ephemeral_data_dir=data_dir,
        ttl_seconds=ttl_seconds,
        max_upload_bytes=1024 * 1024,
        anonymous_uploads_per_ip_per_hour=10,
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


def _analysis_with_flags(flag_count: int = 5) -> dict:
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
        "waiting_periods": [
            {
                "applies_to": "PED",
                "duration_months": 36,
                "raw_clause": "PED raw clause",
                "confidence": 0.88,
            }
        ],
        "sub_limits": [
            {
                "applies_to": "Maternity",
                "limit_value": 30000,
                "raw_clause": "Maternity raw clause",
                "confidence": 0.83,
            }
        ],
        "exclusions": [
            {
                "description": "Cosmetic surgery",
                "raw_clause": "Cosmetic raw clause",
                "confidence": 0.95,
            }
        ],
        "red_flags": [
            {
                "title": f"Flag {index}",
                "plain_explanation": f"Plain explanation {index}",
                "scenario": f"If scenario {index}",
                "raw_clause": f"FULL RAW CLAUSE {index}\nLine two {index}",
                "confidence": 0.8,
            }
            for index in range(1, flag_count + 1)
        ],
    }


def _gold_super_star_render_fixture() -> dict:
    return {
        "schema_version": "1.2",
        "summary": "Your Super Star base policy is unusually clean, but several optional covers can change claim outcomes.",
        "red_flags": [
            {
                "title": "Limitless Care one-shot forfeiture mechanics",
                "plain_explanation": "Once a claim is paid under this optional cover, that cover permanently ceases.",
                "scenario": "If you use Limitless Care for one large claim, you may have no Limitless balance for the rest of the year.",
                "raw_clause": "Once the claim is paid under Limitless Care, this optional cover ceases permanently and cannot be re-opted.",
                "confidence": 0.92,
            },
            {
                "title": "Smart Network conditional co-pay",
                "plain_explanation": "The discount can turn into a co-pay when treatment is outside the Smart Network.",
                "scenario": "If your preferred hospital leaves the Smart Network before admission, a co-pay may apply.",
                "raw_clause": "15% co-pay shall apply for treatment outside the Smart Network except accidents.",
                "confidence": 0.9,
            },
            {
                "title": "Proportionate deduction dormant, not absent",
                "plain_explanation": "The base policy has any-room eligibility, but Room Rent Modification can activate deduction mechanics.",
                "scenario": "If you opt for a cheaper room eligibility and take a higher room, associated charges may be reduced.",
                "raw_clause": "Associated medical expenses shall be proportionately deducted where room eligibility is exceeded.",
                "confidence": 0.87,
            },
        ],
    }


def test_xss_in_raw_clause_is_escaped_visible_text_not_executable() -> None:
    analysis = _analysis_with_flags(1)
    analysis["red_flags"][0]["raw_clause"] = "<script>alert(1)</script>"

    rendered = render_anonymous_results(analysis, session_token="tok")

    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in rendered
    assert "<script>alert(1)</script>" not in rendered


def test_anonymous_results_contains_exact_top_three_raw_clauses_only() -> None:
    analysis = _analysis_with_flags(5)

    rendered = render_anonymous_results(analysis, session_token="tok")

    assert rendered.count('class="red-flag-card"') == 3
    for index in range(1, 4):
        assert f"Flag {index}" in rendered
        assert f"FULL RAW CLAUSE {index}\nLine two {index}" in html.unescape(rendered)
    assert "Flag 4" not in rendered
    assert "FULL RAW CLAUSE 4" not in rendered
    assert "Flag 5" not in rendered


def test_field_outside_anonymous_tier_is_absent_not_hidden() -> None:
    rendered = render_anonymous_results(_analysis_with_flags(5), session_token="tok")

    assert "Full tier only coverage value" not in rendered
    assert "Full tier coverage clause" not in rendered
    assert "secret_full_tier_field" not in rendered
    assert "PED raw clause" not in rendered
    assert "Maternity raw clause" not in rendered
    assert "Cosmetic raw clause" not in rendered


def test_full_signed_up_results_group_fields_with_source_clause_and_confidence() -> None:
    rendered = render_full_results(_analysis_with_flags(5))

    assert "Coverage" in rendered
    assert "Waiting Periods" in rendered
    assert "Sub-limits" in rendered
    assert "Exclusions" in rendered
    assert "All Red Flags" in rendered
    assert "Full tier only coverage value" in rendered
    assert "Full tier coverage clause" in rendered
    assert "Confidence: 0.91" in rendered
    assert "Maternity raw clause" in rendered
    assert "Confidence: 0.83" in rendered
    assert "Cosmetic raw clause" in rendered
    assert "Confidence: 0.95" in rendered
    assert "<details" in rendered


def test_expired_session_renders_not_found_page_not_stack_trace(tmp_path: Path) -> None:
    config = _config(tmp_path, ttl_seconds=1)
    flow = SignupFreeFlow(
        store=EphemeralStore(config),
        extractor=FakeExtractor(_analysis_with_flags(1)),
        config=config,
    )
    created_at = datetime(2026, 1, 1, tzinfo=UTC)
    response = flow.submit_anonymous_upload(
        pdf_bytes=_pdf_bytes("Policy text"),
        filename="policy.pdf",
        ip_address="203.0.113.50",
        now=created_at,
    )

    rendered = render_session_page(
        store=flow.store,
        session_token=response.session_token,
        now=created_at + timedelta(seconds=2),
    )

    assert "This analysis has expired" in rendered
    assert "Traceback" not in rendered
    assert "500" not in rendered


def test_upload_controller_uses_ephemeral_submit_anonymous_upload_only(tmp_path: Path) -> None:
    config = _config(tmp_path)
    flow = SignupFreeFlow(
        store=EphemeralStore(config),
        extractor=FakeExtractor(_analysis_with_flags(1)),
        config=config,
    )
    controller = AnalysisWebController(flow=flow, config=config)

    rendered = controller.submit_upload(
        pdf_bytes=_pdf_bytes("Policy text"),
        filename="policy.pdf",
        ip_address="203.0.113.51",
    )

    assert "Your policy has a complete anonymous summary." in rendered
    assert "Flag 1" in rendered


def test_upload_page_has_file_picker_size_cap_and_progress_state(tmp_path: Path) -> None:
    config = _config(tmp_path)

    rendered = render_upload_page(config)

    assert 'type="file"' in rendered
    assert 'accept="application/pdf,.pdf"' in rendered
    assert f'data-max-bytes="{config.max_upload_bytes}"' in rendered
    assert "Analyzing your policy" in rendered
    assert "drag" in rendered.lower()


def test_signup_gate_surfaces_dev_only_stub_token() -> None:
    rendered = render_signup_gate(
        email="user@example.com",
        signup_token="dev-token-123",
        session_token="session-token",
    )

    assert "DEV-ONLY" in rendered
    assert "dev-token-123" in rendered
    assert "keep this analysis" in rendered.lower()
    assert "blur" not in rendered.lower()


def test_signup_token_consumption_renders_signed_up_full_tier(tmp_path: Path) -> None:
    config = _config(tmp_path)
    flow = SignupFreeFlow(
        store=EphemeralStore(config),
        extractor=FakeExtractor(_analysis_with_flags(5)),
        config=config,
    )
    controller = AnalysisWebController(flow=flow, config=config)
    upload_response = flow.submit_anonymous_upload(
        pdf_bytes=_pdf_bytes("Policy text"),
        filename="policy.pdf",
        ip_address="203.0.113.52",
    )
    token = flow.issue_signup_token(
        email="user@example.com",
        session_token=upload_response.session_token,
    )

    rendered = controller.consume_signup(signup_token=token.token)

    assert "Full policy analysis" in rendered
    assert "Full tier coverage clause" in rendered
    assert "All Red Flags" in rendered


def test_gold_super_star_anonymous_render_dump_fixture() -> None:
    rendered = render_anonymous_results(_gold_super_star_render_fixture(), session_token="gold-001")

    assert "Limitless Care one-shot forfeiture mechanics" in rendered
    assert "Smart Network conditional co-pay" in rendered
    assert "Proportionate deduction dormant, not absent" in rendered
    assert "Once the claim is paid under Limitless Care" in rendered
