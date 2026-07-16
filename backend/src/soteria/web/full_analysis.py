from __future__ import annotations

import calendar
from datetime import date, timedelta
from html import escape
import json
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
    """Return the deterministic policy score shown to users.

    Start at 100; subtract 30 per critical flag, 20 per high flag, 10 per
    medium flag, and 5 per low flag. Unknown severities subtract nothing. The
    displayed score never falls below 10.
    """

    deductions = sum(
        _SCORE_DEDUCTIONS.get(str(flag.get("severity") or "").lower(), 0)
        for flag in red_flags
    )
    return max(_SCORE_FLOOR, 100 - deductions)


def render_full_analysis(
    analysis: dict[str, Any],
    *,
    theme: str = "light",
    current_path: str = "/",
    policy_start_date: date | None = None,
    raw_analysis_json: str | None = None,
) -> str:
    selected_theme = theme if theme in {"light", "dark"} else "light"
    next_theme = "dark" if selected_theme == "light" else "light"
    theme_icon = "&#9790;" if next_theme == "dark" else "&#9788;"
    metadata = _dict(analysis.get("metadata"))
    red_flags = _dict_list(analysis.get("red_flags"))
    waiting_periods = _dict_list(analysis.get("waiting_periods"))
    summary = str(analysis.get("summary") or "No plain-language summary was returned.")
    score = calculate_health_score(red_flags)
    raw_json = raw_analysis_json
    if raw_json is None:
        raw_json = json.dumps(analysis, ensure_ascii=False, indent=2)

    product_name = metadata.get("product_name") or "Policy analysis"
    insurer_name = metadata.get("insurer_name") or "Insurer not identified"
    uin = metadata.get("product_uin")
    uin_value = str(uin) if uin else "Not stated in the extracted wording"

    return f"""<!doctype html>
<html lang="en" data-theme="{_attr(selected_theme)}">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <link rel="stylesheet" href="/static/full-analysis.css">
  <title>Soteria Full Policy Analysis</title>
</head>
<body class="full-analysis-body">
  <main class="analysis-shell">
    <header class="brand-bar">
      <div class="brand-lockup">
        <span class="brand-name">Soteria</span>
        <span class="brand-kicker">insurance auditor</span>
      </div>
      <div class="brand-actions">
        <span class="paid-by-you"><span aria-hidden="true"></span>paid by you</span>
        <form method="post" action="/theme" class="theme-form">
          <input type="hidden" name="theme" value="{_attr(next_theme)}">
          <input type="hidden" name="next" value="{_attr(current_path)}">
          <button class="theme-toggle" type="submit" aria-label="Switch to {next_theme} theme" title="Switch to {next_theme} theme">{theme_icon}</button>
        </form>
      </div>
    </header>

    <section class="policy-hero" aria-labelledby="policy-title">
      <div class="policy-identity">
        <p class="section-kicker">Saved analysis</p>
        <h1 id="policy-title">{_text(product_name)}</h1>
        <p class="insurer-name">{_text(insurer_name)}</p>
        <p class="uin-line">{_glossary_term("uin")} <span>{_text(uin_value)}</span></p>
      </div>
      {_render_score(score)}
    </section>

    {_render_verdict(summary, red_flags)}
    {_render_red_flags(red_flags)}
    {_render_waiting_periods(waiting_periods, policy_start_date=policy_start_date)}
    {_render_coverage_and_gaps(analysis, metadata, policy_start_date, raw_json)}

    <section class="keep-card" aria-labelledby="keep-title">
      <div>
        <p class="section-kicker">Saved analysis</p>
        <h2 id="keep-title">Keep this analysis</h2>
        <p>This analysis is attached to your account and remains available after the anonymous retention window.</p>
      </div>
      <a class="primary-action" href="/">Analyze another policy</a>
    </section>
  </main>
</body>
</html>"""


def _render_score(score: int) -> str:
    if score >= 80:
        verdict = "Strong on the wording, with details to verify"
        score_tone = "score-good"
    elif score >= 60:
        verdict = "Read carefully before you rely on it"
        score_tone = ""
    elif score >= 40:
        verdict = "Several claim-time risks need attention"
        score_tone = ""
    else:
        verdict = "High claim-time risk in the wording"
        score_tone = ""
    return f"""
    <article class="score-card">
      <div class="score-ring score-{score} {score_tone}" role="img" aria-label="Policy Health Score: {score} out of 100">
        <span class="score-number">{score}</span>
        <span class="score-total">/ 100</span>
      </div>
      <div class="score-copy">
        <p class="section-kicker">Policy Health Score</p>
        <p class="score-verdict">{_text(verdict)}</p>
        <details class="score-method">
          <summary>How this is scored</summary>
          <p>Starts at 100. Each critical flag subtracts 30 points, each high flag 20, each medium flag 10, and each low flag 5. The minimum score is 10.</p>
        </details>
      </div>
    </article>
    """


def _render_verdict(summary: str, red_flags: list[dict[str, Any]]) -> str:
    takeaways: list[str] = []
    for flag in red_flags[:3]:
        takeaway = flag.get("plain_explanation") or flag.get("title")
        if takeaway:
            takeaways.append(str(takeaway))
    for sentence in _summary_sentences(summary):
        if len(takeaways) >= 3:
            break
        if sentence not in takeaways:
            takeaways.append(sentence)
    cards = "".join(
        f'<article class="takeaway-card"><span aria-hidden="true"></span><strong>{_glossary_text(item)}</strong></article>'
        for item in takeaways[:3]
    )
    return f"""
    <section class="verdict-section" aria-labelledby="verdict-title">
      <p class="section-kicker" id="verdict-title">The verdict, first</p>
      <div class="takeaway-grid">{cards}</div>
      <details class="full-summary">
        <summary>Read the full summary</summary>
        <p>{_glossary_text(summary)}</p>
      </details>
    </section>
    """


def _render_red_flags(red_flags: list[dict[str, Any]]) -> str:
    if not red_flags:
        cards = (
            '<p class="no-risks">No red flags were identified in this extraction. '
            "Review the wording and extracted data before relying on any claim outcome.</p>"
        )
    else:
        cards = "".join(_render_red_flag(flag) for flag in red_flags)
    return f"""
    <section class="risk-section" aria-labelledby="risk-title">
      <div class="section-heading-row">
        <h2 id="risk-title">Top red flags</h2>
        <span>{len(red_flags)} found</span>
      </div>
      <div class="risk-grid">{cards}</div>
    </section>
    """


def _render_red_flag(flag: dict[str, Any]) -> str:
    severity = str(flag.get("severity") or "unknown").lower()
    if severity not in _SCORE_DEDUCTIONS:
        severity = "unknown"
    takeaway = flag.get("plain_explanation") or flag.get("title") or "Risk details unavailable."
    cost = flag.get("financial_impact_estimate") or "The wording does not quantify the cost."
    scenario = flag.get("scenario") or "No concrete claim scenario was returned."
    action = flag.get("what_to_do") or "Verify this clause with the insurer before relying on it."
    raw_clause = "" if flag.get("raw_clause") is None else str(flag["raw_clause"])
    clause_reference = flag.get("clause_reference") or "Reference not stated"
    return f"""
      <article class="risk-card">
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


def _render_waiting_periods(
    waiting_periods: list[dict[str, Any]],
    *,
    policy_start_date: date | None,
) -> str:
    if policy_start_date is None:
        intro = "Policy start date is not stored yet. Durations are shown without invented calendar dates."
    else:
        intro = (
            f"Assuming cover started {policy_start_date.strftime('%d %b %Y')}. "
            "Claims before each date may not be payable."
        )
    maximum_days = max((_waiting_days(item) for item in waiting_periods), default=1)
    items = "".join(
        _render_waiting_period(
            item,
            policy_start_date=policy_start_date,
            maximum_days=maximum_days,
        )
        for item in waiting_periods
    )
    if not items:
        items = '<p class="empty-state">No waiting periods were extracted.</p>'
    return f"""
    <section class="waiting-section" aria-labelledby="waiting-title">
      <h2 id="waiting-title">{_glossary_term("waitingPeriod", text="Waiting periods")}</h2>
      <p class="section-intro">{_text(intro)}</p>
      <div class="waiting-list">{items}</div>
    </section>
    """


def _render_waiting_period(
    item: dict[str, Any],
    *,
    policy_start_date: date | None,
    maximum_days: int,
) -> str:
    duration_days = _optional_int(item.get("duration_days"))
    duration_months = _optional_int(item.get("duration_months"))
    label = item.get("applies_to") or _humanize(item.get("category") or "Waiting period")
    if duration_days:
        duration = f"{duration_days} days"
    elif duration_months is not None:
        duration = f"{duration_months} months"
    else:
        duration = "Duration not stated"
    equivalent_days = _waiting_days(item)
    percent = round((equivalent_days / maximum_days) * 20) * 5 if maximum_days else 0
    percent = min(100, max(5 if equivalent_days else 0, percent))
    date_copy = "Calendar date pending policy start date"
    if policy_start_date is not None:
        if duration_days:
            end_date = policy_start_date + timedelta(days=duration_days)
            prefix = "Covered from"
        else:
            end_date = _add_months(policy_start_date, duration_months or 0)
            prefix = "Cover begins"
        date_copy = f"{prefix} {end_date.strftime('%d %b %Y')}"
    note = item.get("waiver_mechanism") or item.get("category") or ""
    return f"""
      <article class="waiting-item">
        <div class="waiting-meta"><strong>{_glossary_text(label)}</strong><span>{_text(duration)}</span></div>
        <div class="waiting-track"><span class="timeline-{percent}"></span></div>
        <div class="waiting-foot"><strong>{_text(date_copy)}</strong><span>{_text(_humanize(note))}</span></div>
      </article>
    """


def _render_coverage_and_gaps(
    analysis: dict[str, Any],
    metadata: dict[str, Any],
    policy_start_date: date | None,
    raw_json: str,
) -> str:
    coverage_sentences = _coverage_sentences(analysis)
    coverage_html = "".join(f"<p>{_glossary_text(sentence)}</p>" for sentence in coverage_sentences)
    if not coverage_html:
        coverage_html = '<p class="empty-state">Coverage details were not returned.</p>'
    gaps = _honest_gaps(analysis, metadata, policy_start_date)
    gap_html = ""
    if gaps:
        gap_items = "".join(f"<li>{_glossary_text(gap)}</li>" for gap in gaps)
        gap_html = f"""
        <aside class="honest-gap" aria-labelledby="gap-title">
          <p class="section-kicker" id="gap-title">One honest gap</p>
          <ul>{gap_items}</ul>
        </aside>
        """
    return f"""
    <section class="coverage-gap-grid" aria-label="Coverage and missing information">
      <article class="coverage-card">
        <h2>What's covered</h2>
        <div class="coverage-prose">{coverage_html}</div>
        <details class="raw-data">
          <summary>View extracted data</summary>
          <pre>{_text(raw_json)}</pre>
        </details>
      </article>
      {gap_html}
    </section>
    """


def _coverage_sentences(analysis: dict[str, Any]) -> list[str]:
    coverage = _dict(analysis.get("coverage"))
    financial_terms = _dict(analysis.get("financial_terms"))
    claim_process = _dict(analysis.get("claim_process"))
    sentences: list[str] = []

    inpatient = _dict(coverage.get("inpatient_hospitalization"))
    if inpatient.get("covered") is True:
        minimum_hours = inpatient.get("minimum_hours")
        suffix = f" after admission for at least {minimum_hours} hours" if minimum_hours else ""
        sentences.append(f"In-patient hospitalisation is covered{suffix}.")

    room_rent = _dict(financial_terms.get("room_rent_cap"))
    room_type = room_rent.get("type")
    if room_type == "no_cap":
        sentences.append("Room rent has no base-policy cap in the extracted wording.")
    elif room_type:
        description = room_rent.get("category_description") or _humanize(room_type)
        sentences.append(f"Room rent is limited by {description}.")

    day_care = _dict(coverage.get("day_care_procedures"))
    if day_care.get("covered") is True:
        qualifier = "a specific list" if day_care.get("specific_list_only") else "all stated procedures"
        sentences.append(f"Day care is covered for {qualifier}.")

    domiciliary = _dict(coverage.get("domiciliary_hospitalization"))
    if domiciliary.get("covered") is True:
        sentences.append("Domiciliary hospitalisation is covered, subject to its stated conditions.")
    elif domiciliary.get("covered") is False:
        sentences.append("Domiciliary hospitalisation is not covered in the extracted wording.")

    restoration = _dict(coverage.get("restoration_benefit"))
    if restoration.get("available") is True:
        conditions = restoration.get("conditions")
        sentence = "Restoration is available"
        sentence += f": {conditions}" if conditions else "."
        sentences.append(sentence)

    if claim_process.get("cashless_available") is True:
        sentences.append("Cashless claims are available subject to network and authorization rules.")
    elif claim_process.get("cashless_available") is False:
        sentences.append("Cashless claims are not available under the extracted wording.")
    return sentences


def _honest_gaps(
    analysis: dict[str, Any],
    metadata: dict[str, Any],
    policy_start_date: date | None,
) -> list[str]:
    gaps: list[str] = []
    if not metadata.get("product_uin"):
        gaps.append("The UIN was not stated in the extracted wording.")
    if not metadata.get("sum_insured_options"):
        gaps.append(
            "The policy Schedule was not available, so the Sum Insured and schedule-dependent amounts are not shown."
        )
    if policy_start_date is None:
        gaps.append(
            "The policy start date is not stored yet, so waiting-period end dates cannot be calculated."
        )
    if not _dict(analysis.get("coverage")):
        gaps.append("Coverage details were not returned.")
    return gaps


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


def _summary_sentences(summary: str) -> list[str]:
    return [item.strip() for item in re.split(r"(?<=[.!?])\s+", summary) if item.strip()]


def _waiting_days(item: dict[str, Any]) -> int:
    days = _optional_int(item.get("duration_days"))
    if days:
        return days
    months = _optional_int(item.get("duration_months")) or 0
    return months * 30


def _add_months(value: date, months: int) -> date:
    month_index = value.month - 1 + months
    year = value.year + month_index // 12
    month = month_index % 12 + 1
    day = min(value.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def _optional_int(value: Any) -> int | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _dict_list(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _humanize(value: Any) -> str:
    return str(value).replace("_", " ").strip().capitalize()


def _text(value: Any) -> str:
    return escape(str(value), quote=False)


def _attr(value: Any) -> str:
    return escape(str(value), quote=True)
