from __future__ import annotations

from html import escape
import re
from typing import Any


_SCORE_DEDUCTIONS = {"critical": 30, "high": 20, "medium": 10, "low": 5}
_SCORE_FLOOR = 10

_GLOSSARY = {
    "uin": (
        "UIN",
        "Unique Identification Number — the IRDAI code that identifies this exact policy wording.",
        ("UIN",),
    ),
    "ped": (
        "PED",
        "Pre-existing disease — any condition you already had before buying the policy.",
        ("PED", "pre-existing disease", "pre-existing diseases", "pre-existing conditions"),
    ),
    "deductible": (
        "Deductible",
        "A fixed amount you pay on every claim before the insurer pays anything.",
        ("deductible", "deductibles"),
    ),
    "copay": (
        "Co-pay",
        "A share of each bill you must pay yourself, usually a percentage.",
        ("co-pay", "copay", "co pay"),
    ),
    "subLimit": (
        "Sub-limit",
        "A cap on how much the policy pays for one specific item, like room rent.",
        ("sub-limit", "sub limit", "sublimit"),
    ),
    "waitingPeriod": (
        "Waiting period",
        "A period after buying the policy during which certain claims aren't payable yet.",
        ("waiting period", "waiting periods"),
    ),
    "domiciliary": (
        "Domiciliary hospitalisation",
        "Treatment given at home for something that would normally need a hospital stay.",
        (
            "domiciliary hospitalisation",
            "domiciliary hospitalization",
            "domiciliary",
        ),
    ),
    "dayCare": (
        "Day care",
        "Procedures that need less than 24 hours in hospital, like cataract surgery.",
        ("day care", "day-care"),
    ),
    "cashless": (
        "Cashless",
        "The insurer settles the hospital bill directly, so you don't pay upfront and claim later.",
        ("cashless",),
    ),
    "sumInsured": (
        "Sum Insured",
        "The maximum amount the policy will pay across a policy year.",
        ("sum insured",),
    ),
    "inPatient": (
        "In-patient",
        "Treatment where you're formally admitted to hospital for 24 hours or more.",
        ("in-patient", "inpatient"),
    ),
    "roomRent": (
        "Room rent",
        "The daily hospital room charge the policy will cover.",
        ("room rent",),
    ),
    "restoration": (
        "Restoration",
        "Automatic top-up of your cover after it's used up during a policy year.",
        ("restoration", "restored"),
    ),
    "floater": (
        "Floater",
        "One shared cover amount for the whole family, rather than a separate amount per person.",
        ("floater",),
    ),
    "moratorium": (
        "Moratorium",
        "After a set number of years, the insurer can no longer reject a claim over non-disclosure.",
        ("moratorium",),
    ),
}

_GLOSSARY_PATTERN_TO_KEY = {
    alias.casefold(): key
    for key, (_display, _definition, aliases) in _GLOSSARY.items()
    for alias in aliases
}
_GLOSSARY_PATTERN = re.compile(
    r"(?<![\w-])(" + "|".join(
        re.escape(alias)
        for alias in sorted(_GLOSSARY_PATTERN_TO_KEY, key=len, reverse=True)
    ) + r")(?![\w-])",
    flags=re.IGNORECASE,
)


def calculate_health_score(red_flags: list[dict[str, Any]]) -> int:
    """Return the deterministic policy score shown to users."""

    deductions = sum(
        _SCORE_DEDUCTIONS.get(str(flag.get("severity") or "").lower(), 0)
        for flag in red_flags
    )
    return max(_SCORE_FLOOR, 100 - deductions)


def render_red_flag_card(flag: dict[str, Any], *, show_title: bool = False) -> str:
    severity = str(flag.get("severity") or "unknown").lower()
    if severity not in _SCORE_DEDUCTIONS:
        severity = "unknown"
    takeaway = flag.get("plain_explanation") or flag.get("title") or "Risk details unavailable."
    cost = flag.get("financial_impact_estimate") or "The wording does not quantify the cost."
    scenario = flag.get("scenario") or "No concrete claim scenario was returned."
    action = flag.get("what_to_do") or "Verify this clause with the insurer before relying on it."
    raw_clause = "" if flag.get("raw_clause") is None else str(flag["raw_clause"])
    clause_reference = flag.get("clause_reference") or "Reference not stated"
    title = flag.get("title") or "Untitled red flag"
    title_html = f'\n        <h3 class="risk-title">{_text(title)}</h3>' if show_title else ""
    return f"""
      <article class="risk-card">{title_html}
        <span class="severity-tag severity-{_attr(severity)}">{_text(severity.title())}</span>
        <strong class="risk-takeaway">{_glossary_text(takeaway)}</strong>
        <p class="field-label warning-label">What it costs you</p>
        <div class="cost-impact">{_glossary_text(cost)}</div>
        <p class="field-label">When this bites you</p>
        <p class="risk-copy">{_glossary_text(scenario)}</p>
        <p class="field-label action-label">What you can do</p>
        <p class="risk-copy action-copy">{_glossary_text(action)}</p>
        <details class="verified-wording">
          <summary><span aria-hidden="true"></span>Verified against the wording</summary>
          <pre>{_text(raw_clause)}</pre>
          <p>Quoted verbatim · {_text(clause_reference)}</p>
        </details>
      </article>
    """


def _glossary_text(value: Any) -> str:
    text = str(value)
    output: list[str] = []
    position = 0
    for match in _GLOSSARY_PATTERN.finditer(text):
        output.append(_text(text[position:match.start()]))
        key = _GLOSSARY_PATTERN_TO_KEY[match.group(0).casefold()]
        output.append(_glossary_term(key))
        position = match.end()
    output.append(_text(text[position:]))
    return "".join(output)


def _glossary_term(key: str, *, text: str | None = None) -> str:
    display, definition, _aliases = _GLOSSARY[key]
    display_text = text or display
    return (
        f'<dfn class="glossary-term" tabindex="0" data-definition="{_attr(definition)}">'
        f"{_text(display_text)}</dfn>"
    )


def _text(value: Any) -> str:
    return escape(str(value), quote=False)


def _attr(value: Any) -> str:
    return escape(str(value), quote=True)
