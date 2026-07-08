from __future__ import annotations

import html
import json
import re
from pathlib import Path

from soteria.public_pages import generate_public_page_html, generate_public_pages


def _base_analysis(*, policy_type: str, severity: str = "medium") -> dict:
    return {
        "schema_version": "1.2",
        "metadata": {
            "insurer_name": "Example Health",
            "product_name": f"Example {policy_type.replace('_', ' ').title()}",
            "product_uin": "UIN-EXAMPLE-001",
            "policy_type": policy_type,
            "sum_insured_options": [500000, 1000000],
        },
        "summary": "This wording has specific claim-time mechanics to verify.",
        "coverage": {
            "schedule_bound_cover": {
                "available": True,
                "amount": None,
                "uncertainty": "Amount is schedule-dependent and must be checked in the policy schedule.",
                "raw_clause": "Benefit amount is as specified in the Policy Schedule.",
            }
        },
        "red_flags": [
            {
                "pattern_id": "RF-001",
                "severity": severity,
                "title": "Room rent and linked deduction",
                "plain_explanation": "A room category mismatch can reduce payable charges.",
                "scenario": "If the admitted room is above eligibility, related charges may be reduced.",
                "raw_clause": "Room rent is capped. <script>alert(1)</script>",
                "financial_impact_estimate": "20% of the admissible bill may be at risk.",
            },
            {
                "pattern_id": "RF-002",
                "severity": "medium",
                "title": "Procedure sub-limit",
                "plain_explanation": "A named procedure has a capped payout.",
                "scenario": "If hospital cost exceeds the cap, the excess is paid by you.",
                "raw_clause": "Cataract expenses are limited per eye.",
                "financial_impact_estimate": "Costs above the sub-limit remain with the policyholder.",
            },
        ],
        "what_this_gets_right": ["No room rent cap for listed any-room variants."],
    }


def _fixed_benefit_analysis() -> dict:
    analysis = _base_analysis(policy_type="critical_illness", severity="high")
    analysis["metadata"]["insurer_name"] = "HDFC Ergo"
    analysis["metadata"]["product_name"] = "Critical Illness Silver"
    analysis["metadata"]["product_uin"] = None
    analysis["metadata"]["sum_insured_options"] = []
    analysis["red_flags"][0]["title"] = "Survival-period forfeiture"
    analysis["red_flags"][0]["plain_explanation"] = (
        "The claim can fail entirely if the survival condition is not met."
    )
    analysis["red_flags"][0]["scenario"] = (
        "If the insured person dies within the survival period, the fixed benefit may not pay."
    )
    analysis["red_flags"][0]["raw_clause"] = (
        "The insured must survive 30 days after diagnosis. <script>alert(1)</script>"
    )
    analysis["red_flags"][0]["financial_impact_estimate"] = (
        "100% of the hospital bill framing would be wrong here."
    )
    analysis["what_this_gets_right"] = [
        "Full Sum Insured undiminished once you qualify.",
        "No room rent cap.",
        "No co-pay.",
    ]
    return analysis


def _six_gold_shaped_analyses() -> list[tuple[str, dict]]:
    return [
        ("gold_001_star_super_star", _base_analysis(policy_type="family_floater")),
        ("gold_002_senior", _base_analysis(policy_type="senior_citizen")),
        ("gold_003_super_top_up", _base_analysis(policy_type="super_top_up")),
        ("gold_004_individual", _base_analysis(policy_type="individual")),
        ("gold_005_ci_hdfc_ergo", _fixed_benefit_analysis()),
        ("gold_006_ci_alt", _base_analysis(policy_type="critical_illness")),
    ]


def test_batch_generator_writes_one_escaped_html_file_per_gold_shaped_json(tmp_path: Path) -> None:
    inputs = []
    for slug, analysis in _six_gold_shaped_analyses():
        source = tmp_path / f"{slug}.json"
        source.write_text(json.dumps(analysis), encoding="utf-8")
        inputs.append(source)

    output_paths = generate_public_pages(inputs, output_dir=tmp_path / "public")

    assert len(output_paths) == 6
    for path in output_paths:
        rendered = path.read_text(encoding="utf-8")
        assert rendered.startswith("<!doctype html>")
        assert rendered.rstrip().endswith("</html>")
        assert "&lt;script&gt;alert(1)&lt;/script&gt;" in rendered
        assert "<script>alert(1)</script>" not in rendered
        assert "Plan C public red-flag page" in rendered


def test_indemnity_shape_uses_financial_impact_estimate_as_percentage_exposure() -> None:
    rendered = generate_public_page_html(_base_analysis(policy_type="family_floater"))

    assert "20% of the admissible bill may be at risk." in rendered
    assert "at stake: the entire Sum Insured" not in rendered


def test_fixed_benefit_shape_uses_entire_sum_insured_not_percentage_bill_framing() -> None:
    rendered = generate_public_page_html(_fixed_benefit_analysis())

    assert "at stake: the entire Sum Insured" in rendered
    assert "100% of the hospital bill framing would be wrong here" not in rendered
    assert "percentage of bill" not in rendered.lower()


def test_critical_severity_verdict_is_not_unconditionally_positive() -> None:
    rendered = generate_public_page_html(
        _base_analysis(policy_type="family_floater", severity="critical")
    )
    verdict = html.unescape(rendered)

    assert "critical claim-time risk" in verdict.lower()
    assert "genuinely good policy" not in verdict.lower()
    assert "clean policy" not in verdict.lower()


def test_medium_or_lower_severity_verdict_uses_positive_branch() -> None:
    rendered = generate_public_page_html(
        _base_analysis(policy_type="family_floater", severity="medium")
    )
    verdict = html.unescape(rendered)

    assert "Broadly workable wording, with listed caveats to verify" in verdict
    assert "critical claim-time risk present" not in verdict.lower()
    assert "material claim-time risks need review" not in verdict.lower()


def test_missing_uin_and_empty_sum_insured_options_use_public_fallbacks() -> None:
    rendered = generate_public_page_html(_fixed_benefit_analysis())

    assert "UIN not stated in published wording" in rendered
    assert "set per policy schedule" in rendered
    assert ">None<" not in rendered
    assert "Sum insured range: -" not in rendered


def test_schedule_dependent_uncertainty_is_rendered_as_uncertainty() -> None:
    rendered = generate_public_page_html(_base_analysis(policy_type="family_floater"))

    assert "Amount is schedule-dependent and must be checked in the policy schedule." in rendered
    assert "schedule-dependent" in rendered


def test_novel_pattern_gets_marker_that_numbered_patterns_do_not_get() -> None:
    analysis = _base_analysis(policy_type="family_floater")
    analysis["red_flags"][1]["pattern_id"] = "novel"

    rendered = generate_public_page_html(analysis)
    flag_cards = re.findall(
        r'(<article class="red-flag-card.*?</article>)',
        rendered,
        flags=re.DOTALL,
    )
    numbered_segment = flag_cards[0]
    novel_segment = flag_cards[1]

    assert "outside numbered taxonomy" in rendered
    assert rendered.count("outside numbered taxonomy") == 1
    assert "outside numbered taxonomy" not in numbered_segment
    assert "outside numbered taxonomy" in novel_segment


def test_fixed_benefit_gets_right_does_not_inflate_structurally_inapplicable_terms() -> None:
    rendered = generate_public_page_html(_fixed_benefit_analysis())
    rendered_text = html.unescape(rendered)

    assert "Full Sum Insured undiminished once you qualify." in rendered_text
    assert "No room rent cap" not in rendered_text
    assert "No co-pay" not in rendered_text


def test_indemnity_gets_right_preserves_legitimate_cap_strengths() -> None:
    analysis = _base_analysis(policy_type="family_floater")
    analysis["what_this_gets_right"] = ["No ICU cap for this Sum Insured band."]

    rendered = generate_public_page_html(analysis)
    rendered_text = html.unescape(rendered)

    assert "No ICU cap for this Sum Insured band." in rendered_text
