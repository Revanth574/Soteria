from __future__ import annotations

from datetime import date
import html
import json
from pathlib import Path
import re

import pytest
from fastapi.testclient import TestClient

from soteria.ephemeral import EphemeralConfig, EphemeralStore, SignupFreeFlow
from soteria.extraction import ExtractionResult
from soteria.http import create_app
from soteria.web import render_full_results


GLOSSARY_DEFINITIONS = {
    "UIN": "Unique Identification Number — the IRDAI code that identifies this exact policy wording.",
    "PED": "Pre-existing disease — any condition you already had before buying the policy.",
    "Deductible": "A fixed amount you pay on every claim before the insurer pays anything.",
    "Co-pay": "A share of each bill you must pay yourself, usually a percentage.",
    "Sub-limit": "A cap on how much the policy pays for one specific item, like room rent.",
    "Waiting period": "A period after buying the policy during which certain claims aren't payable yet.",
    "Domiciliary hospitalisation": "Treatment given at home for something that would normally need a hospital stay.",
    "Day care": "Procedures that need less than 24 hours in hospital, like cataract surgery.",
    "Cashless": "The insurer settles the hospital bill directly, so you don't pay upfront and claim later.",
    "Sum Insured": "The maximum amount the policy will pay across a policy year.",
    "In-patient": "Treatment where you're formally admitted to hospital for 24 hours or more.",
    "Room rent": "The daily hospital room charge the policy will cover.",
    "Restoration": "Automatic top-up of your cover after it's used up during a policy year.",
    "Floater": "One shared cover amount for the whole family, rather than a separate amount per person.",
    "Moratorium": "After a set number of years, the insurer can no longer reject a claim over non-disclosure.",
}


class FakeExtractor:
    def __init__(self, analysis: dict) -> None:
        self.analysis = analysis

    def analyze(self, _document) -> ExtractionResult:
        return ExtractionResult(json=self.analysis, schema_version="1.2")


def _analysis(*, flag_count: int = 4) -> dict:
    severities = ["critical", "high", "medium", "low"]
    return {
        "schema_version": "1.2",
        "metadata": {
            "insurer_name": "Soteria Test General Insurance Company Limited",
            "product_name": "A Very Long Health Insurance Product Name That Must Wrap Cleanly",
            "product_uin": "TSTHLIP00001V012026",
            "policy_type": "family_floater",
            "sum_insured_options": [500000, 1000000],
        },
        "summary": (
            "Your policy covers in-patient hospitalisation and day care. "
            "A deductible and co-pay can still affect a claim. "
            "Read every waiting period and sub-limit before relying on the cover."
        ),
        "coverage": {
            "inpatient_hospitalization": {
                "covered": True,
                "minimum_hours": 24,
                "raw_clause": "Hospitalisation means admission for at least 24 hours.",
            },
            "restoration_benefit": {
                "available": True,
                "conditions": "Restoration applies after the Sum Insured is exhausted.",
                "raw_clause": "The Sum Insured shall be restored once exhausted.",
            },
            "day_care_procedures": {
                "covered": True,
                "specific_list_only": False,
                "raw_clause": "All day care procedures are covered.",
            },
            "domiciliary_hospitalization": {
                "covered": False,
                "raw_clause": "Domiciliary hospitalisation is excluded.",
            },
        },
        "financial_terms": {
            "room_rent_cap": {"type": "no_cap", "raw_clause": "Any room."},
            "deductible": {
                "applies": True,
                "amount_inr": 25000,
                "type": "per_claim",
                "raw_clause": "A deductible of Rs 25,000 applies per claim.",
            },
            "co_pay": {
                "applies": True,
                "percentage": 10,
                "raw_clause": "A 10% co-pay applies.",
            },
        },
        "waiting_periods": [
            {
                "category": "initial",
                "applies_to": "Any illness",
                "duration_months": 0,
                "duration_days": 30,
                "raw_clause": "Thirty-day waiting period.",
            },
            {
                "category": "pre_existing_disease",
                "applies_to": "PED",
                "duration_months": 36,
                "duration_days": None,
                "raw_clause": "PED is covered after 36 months.",
            },
        ],
        "sub_limits": [],
        "exclusions": [],
        "claim_process": {"cashless_available": True},
        "red_flags": [
            {
                "id": f"flag_{index}",
                "severity": severities[(index - 1) % len(severities)],
                "title": f"Flag {index}",
                "plain_explanation": f"Takeaway {index} about the policy.",
                "financial_impact_estimate": f"Cost estimate {index}.",
                "scenario": f"When this bites {index}.",
                "what_to_do": f"Action {index}.",
                "raw_clause": f"Verbatim clause {index}.",
                "clause_reference": f"Clause {index}",
            }
            for index in range(1, flag_count + 1)
        ],
    }


@pytest.mark.parametrize(
    ("flags", "expected"),
    [
        ([], 100),
        ([{"severity": "high"}], 80),
        (
            [
                {"severity": "critical"},
                {"severity": "high"},
                {"severity": "medium"},
                {"severity": "low"},
            ],
            35,
        ),
        ([{"severity": "critical"}] * 10, 10),
    ],
)
def test_health_score_formula(flags: list[dict], expected: int) -> None:
    from soteria.web.full_analysis import calculate_health_score

    assert calculate_health_score(flags) == expected


def test_zero_red_flags_renders_complete_nonempty_state() -> None:
    rendered = render_full_results(_analysis(flag_count=0))

    assert "No red flags were identified" in rendered
    assert 'class="risk-card"' not in rendered
    assert "Policy Health Score" in rendered


def test_fifteen_red_flags_render_without_truncation() -> None:
    rendered = render_full_results(_analysis(flag_count=16))

    assert rendered.count('class="risk-card"') == 16
    assert "Flag 16" in rendered
    assert "Verbatim clause 16." in rendered


def test_missing_schedule_and_null_fields_render_one_honest_gap() -> None:
    analysis = _analysis()
    analysis["metadata"]["product_uin"] = None
    analysis["metadata"]["sum_insured_options"] = []
    analysis["coverage"] = {}

    rendered = render_full_results(analysis)

    assert "One honest gap" in rendered
    assert "UIN" in rendered
    assert "policy Schedule" in rendered
    assert "policy start date" in rendered
    assert "Coverage details were not returned" in rendered


def test_long_clause_and_policy_names_are_complete_and_escaped() -> None:
    analysis = _analysis(flag_count=1)
    long_clause = "A < B & C " + ("long wording " * 50)
    analysis["red_flags"][0]["raw_clause"] = long_clause

    rendered = render_full_results(analysis)

    assert analysis["metadata"]["insurer_name"] in html.unescape(rendered)
    assert analysis["metadata"]["product_name"] in html.unescape(rendered)
    assert long_clause in html.unescape(rendered)
    assert "A < B" not in rendered
    assert '<details class="verified-wording">' in rendered


def test_waiting_period_dates_are_server_computed_when_start_date_is_available() -> None:
    rendered = render_full_results(
        _analysis(),
        policy_start_date=date(2026, 7, 15),
    )

    assert "Covered from 14 Aug 2026" in rendered
    assert "Cover begins 15 Jul 2029" in rendered


def test_glossary_uses_all_exact_display_terms_and_definitions() -> None:
    analysis = _analysis()
    analysis["summary"] += (
        " UIN PED deductible co-pay sub-limit waiting period domiciliary "
        "day care cashless Sum Insured in-patient room rent restoration floater moratorium."
    )

    rendered = render_full_results(analysis)

    for display_term, definition in GLOSSARY_DEFINITIONS.items():
        assert f'>{display_term}<' in rendered
        assert html.escape(definition, quote=True) in rendered


def test_view_extracted_data_contains_exact_stored_json() -> None:
    analysis = _analysis()
    stored_json = json.dumps(analysis, ensure_ascii=False, separators=(",", ":"))

    rendered = render_full_results(analysis, raw_analysis_json=stored_json)

    assert "View extracted data" in rendered
    assert stored_json in html.unescape(rendered)


def test_full_tier_css_has_no_hex_outside_theme_token_blocks() -> None:
    css_path = (
        Path(__file__).resolve().parents[1]
        / "src"
        / "soteria"
        / "web"
        / "static"
        / "full-analysis.css"
    )
    css = css_path.read_text(encoding="utf-8")
    theme_blocks = re.findall(
        r':root\[data-theme="(?:light|dark)"\]\s*\{.*?\}',
        css,
        flags=re.DOTALL,
    )
    assert len(theme_blocks) == 2
    expected_palettes = {
        "light": {
            "bg": "#FCFAF3",
            "card": "#F1ECDF",
            "text": "#1C1E15",
            "text-muted": "#4A4E3C",
            "border": "#E7E0CF",
            "accent": "#4E6B10",
            "accent-hover": "#37500A",
            "warning": "#B26A12",
            "warning-bg": "#F5F0E3",
        },
        "dark": {
            "bg": "#0C0E09",
            "card": "#14170E",
            "text": "#ECEEE2",
            "text-muted": "#C4C8B6",
            "border": "#262A1D",
            "accent": "#B7D93C",
            "accent-hover": "#8FA82E",
            "warning": "#E0A24A",
            "warning-bg": "#22261A",
        },
    }
    for theme, expected in expected_palettes.items():
        block = next(item for item in theme_blocks if f'data-theme="{theme}"' in item)
        actual = dict(re.findall(r"--([\w-]+):\s*(#[0-9A-Fa-f]{6})", block))
        assert actual == expected

    css_without_theme_blocks = css
    for block in theme_blocks:
        css_without_theme_blocks = css_without_theme_blocks.replace(block, "")

    assert re.findall(r"#[0-9A-Fa-f]{3,8}\b", css_without_theme_blocks) == []


def test_section_order_matches_design() -> None:
    rendered = render_full_results(_analysis())
    labels = [
        "Soteria",
        "Policy Health Score",
        "The verdict, first",
        "Top red flags",
        "Waiting periods",
        "What's covered",
        "Keep this analysis",
    ]

    positions = [rendered.index(label) for label in labels]

    assert positions == sorted(positions)


def test_theme_toggle_cookie_survives_reload_on_full_route(tmp_path: Path) -> None:
    analysis = _analysis()
    config = _ephemeral_config(tmp_path)
    flow = SignupFreeFlow(
        store=EphemeralStore(config),
        extractor=FakeExtractor(analysis),
        config=config,
    )
    upload = flow.submit_anonymous_upload(
        pdf_bytes=_pdf_bytes("Policy text"),
        filename="policy.pdf",
        ip_address="203.0.113.80",
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
    full_path = f"/a/{upload.session_token}/full"

    initial = client.get(full_path)
    toggle = client.post("/theme", data={"theme": "dark", "next": full_path})
    reloaded = client.get(full_path)

    assert 'data-theme="light"' in initial.text
    assert toggle.status_code == 303
    assert "soteria_theme=dark" in toggle.headers["set-cookie"]
    assert 'data-theme="dark"' in reloaded.text


def _ephemeral_config(tmp_path: Path) -> EphemeralConfig:
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
