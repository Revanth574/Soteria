from __future__ import annotations

import json
import re
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

from soteria.web.render import escape_attr, escape_text, render_raw_clause_block


FIXED_BENEFIT_POLICY_TYPES = frozenset({"critical_illness", "fixed_benefit"})
_INAPPLICABLE_FIXED_BENEFIT_STRENGTHS = ("no room rent cap", "no co-pay", "no copay")


def generate_public_pages(input_paths: Iterable[Path], *, output_dir: Path) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    output_paths: list[Path] = []
    for input_path in input_paths:
        analysis = json.loads(Path(input_path).read_text(encoding="utf-8"))
        output_path = output_dir / f"{_safe_slug(Path(input_path).stem)}.html"
        output_path.write_text(generate_public_page_html(analysis), encoding="utf-8")
        output_paths.append(output_path)
    return output_paths


def generate_public_page_html(
    analysis: Mapping[str, Any], *, policy_type: str | None = None
) -> str:
    metadata = _dict(analysis.get("metadata"))
    resolved_policy_type = (
        policy_type
        or _string(metadata.get("policy_type"))
        or _string(analysis.get("policy_type"))
        or "unknown"
    )
    red_flags = _red_flags(analysis.get("red_flags"))
    fixed_benefit = _is_fixed_benefit(resolved_policy_type)
    title = _page_title(metadata)
    verdict = _verdict(red_flags)

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escape_text(title)} | Soteria Plan C</title>
  <style>
    :root {{
      --paper: #fbf7ef;
      --ink: #16130f;
      --muted: #635b50;
      --rule: #d9cbb4;
      --accent: #146b5b;
      --critical: #9f2f24;
      --tag: #efe2c9;
    }}
    body {{
      margin: 0;
      background: #f1eadc;
      color: var(--ink);
      font-family: Georgia, 'Times New Roman', serif;
      line-height: 1.55;
    }}
    .public-page {{
      width: min(1040px, calc(100% - 32px));
      margin: 0 auto;
      padding: 40px 0 56px;
    }}
    .masthead, .section {{
      border-bottom: 1px solid var(--rule);
      padding: 28px 0;
    }}
    .eyebrow {{
      color: var(--accent);
      font-size: 0.78rem;
      font-weight: 700;
      letter-spacing: 0;
      margin: 0 0 8px;
      text-transform: uppercase;
    }}
    h1, h2, h3 {{ margin: 0 0 12px; }}
    h1 {{ font-size: clamp(2rem, 4vw, 4.4rem); line-height: 1.02; }}
    .lede {{ color: var(--muted); font-size: 1.1rem; max-width: 760px; }}
    .meta-grid {{
      display: grid;
      gap: 12px;
      grid-template-columns: repeat(auto-fit, minmax(190px, 1fr));
      margin-top: 24px;
    }}
    .meta-item {{
      border-top: 1px solid var(--rule);
      padding-top: 10px;
    }}
    .meta-item dt {{ color: var(--muted); font-size: 0.86rem; }}
    .meta-item dd {{ margin: 4px 0 0; }}
    .flag-grid {{
      display: grid;
      gap: 18px;
      grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
    }}
    .red-flag-card {{
      background: var(--paper);
      border: 1px solid var(--rule);
      padding: 18px;
    }}
    .severity-critical {{ border-color: var(--critical); }}
    .scenario {{ color: var(--critical); }}
    .impact {{ font-weight: 700; }}
    .tag {{
      background: var(--tag);
      display: inline-block;
      font-size: 0.8rem;
      margin: 4px 0 10px;
      padding: 2px 7px;
    }}
    .raw-clause {{
      background: #fffdf8;
      border: 1px solid var(--rule);
      max-height: 240px;
      overflow: auto;
      padding: 12px;
      white-space: pre-wrap;
    }}
    .strengths li, .uncertainty li {{ margin-bottom: 8px; }}
    .muted {{ color: var(--muted); }}
  </style>
</head>
<body>
  <main class="public-page">
    <section class="masthead">
      <p class="eyebrow">Plan C public red-flag page</p>
      <h1>{escape_text(title)}</h1>
      <p class="lede">{escape_text(_summary(analysis))}</p>
      {_render_metadata(metadata, resolved_policy_type)}
    </section>
    <section class="section verdict">
      <p class="eyebrow">Verdict</p>
      <h2>{escape_text(verdict)}</h2>
    </section>
    <section class="section">
      <p class="eyebrow">Claim-time red flags</p>
      <div class="flag-grid">
        {"".join(_render_red_flag_card(flag, fixed_benefit=fixed_benefit) for flag in red_flags)}
      </div>
    </section>
    <section class="section">
      <p class="eyebrow">What this gets right</p>
      {_render_strengths(analysis, fixed_benefit=fixed_benefit)}
    </section>
    <section class="section">
      <p class="eyebrow">Schedule-dependent or uncertain data</p>
      {_render_uncertainties(analysis)}
    </section>
  </main>
</body>
</html>"""


def _render_metadata(metadata: Mapping[str, Any], policy_type: str) -> str:
    uin = _string(metadata.get("product_uin")) or "UIN not stated in published wording"
    return f"""
      <dl class="meta-grid">
        <div class="meta-item">
          <dt>Insurer</dt>
          <dd>{escape_text(_string(metadata.get("insurer_name")) or "Not stated")}</dd>
        </div>
        <div class="meta-item">
          <dt>Product type</dt>
          <dd>{escape_text(policy_type.replace("_", " "))}</dd>
        </div>
        <div class="meta-item">
          <dt>Product UIN</dt>
          <dd>{escape_text(uin)}</dd>
        </div>
        <div class="meta-item">
          <dt>Sum insured range</dt>
          <dd>{escape_text(_sum_insured_options(metadata.get("sum_insured_options")))}</dd>
        </div>
      </dl>
    """


def _render_red_flag_card(flag: Mapping[str, Any], *, fixed_benefit: bool) -> str:
    severity = _string(flag.get("severity")) or "medium"
    classes = f"red-flag-card severity-{_safe_slug(severity)}"
    novel_marker = (
        '<span class="tag">outside numbered taxonomy</span>'
        if _string(flag.get("pattern_id")).lower() == "novel"
        else ""
    )
    impact = (
        "at stake: the entire Sum Insured"
        if fixed_benefit
        else _string(flag.get("financial_impact_estimate"))
        or "Financial exposure depends on the claim amount and policy schedule."
    )
    return f"""
        <article class="{escape_attr(classes)}">
          <p class="eyebrow">{escape_text(severity)} red flag</p>
          {novel_marker}
          <h3>{escape_text(_string(flag.get("title")) or "Untitled red flag")}</h3>
          <p>{escape_text(_string(flag.get("plain_explanation")))}</p>
          <p class="scenario">{escape_text(_string(flag.get("scenario")))}</p>
          <p class="impact">{escape_text(impact)}</p>
          {render_raw_clause_block(flag.get("raw_clause"))}
        </article>
    """


def _render_strengths(analysis: Mapping[str, Any], *, fixed_benefit: bool) -> str:
    strengths = _strengths(analysis)
    if fixed_benefit:
        strengths = [
            item
            for item in strengths
            if not any(blocked in item.lower() for blocked in _INAPPLICABLE_FIXED_BENEFIT_STRENGTHS)
        ]
    if not strengths:
        return '<p class="muted">No wording-stated strengths were extracted for this page.</p>'
    return "<ul class=\"strengths\">" + "".join(
        f"<li>{escape_text(strength)}</li>" for strength in strengths
    ) + "</ul>"


def _render_uncertainties(analysis: Mapping[str, Any]) -> str:
    uncertainties = _find_uncertainties(analysis)
    if not uncertainties:
        return '<p class="muted">No schedule-dependent values were extracted.</p>'
    return "<ul class=\"uncertainty\">" + "".join(
        f"<li>{escape_text(item)}</li>" for item in uncertainties
    ) + "</ul>"


def _find_uncertainties(value: Any) -> list[str]:
    found: list[str] = []
    if isinstance(value, Mapping):
        uncertainty = value.get("uncertainty") or value.get("uncertainty_note")
        if uncertainty is not None:
            found.append(str(uncertainty))
        if value.get("schedule_dependent") is True:
            found.append("This value is schedule-dependent and must be checked in the policy schedule.")
        for key, item in value.items():
            if key in {"raw_clause", "clause_text", "source_clause"}:
                continue
            found.extend(_find_uncertainties(item))
    elif isinstance(value, list):
        for item in value:
            found.extend(_find_uncertainties(item))
    elif isinstance(value, str) and "schedule-dependent" in value.lower():
        found.append(value)
    return _dedupe(found)


def _strengths(analysis: Mapping[str, Any]) -> list[str]:
    for key in ("what_this_gets_right", "strengths", "gets_right"):
        value = analysis.get(key)
        if isinstance(value, list):
            return [str(item) for item in value if item is not None and str(item).strip()]
    return []


def _red_flags(value: Any) -> list[Mapping[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, Mapping)]


def _verdict(red_flags: list[Mapping[str, Any]]) -> str:
    severities = {_string(flag.get("severity")).lower() for flag in red_flags}
    if "critical" in severities:
        return "Proceed carefully: critical claim-time risk present"
    if severities <= {"", "low", "medium"}:
        return "Broadly workable wording, with listed caveats to verify"
    return "Material claim-time risks need review before relying on this wording"


def _summary(analysis: Mapping[str, Any]) -> str:
    summary = analysis.get("summary")
    if isinstance(summary, str) and summary.strip():
        return summary
    if isinstance(summary, Mapping):
        return json.dumps(summary, ensure_ascii=False)
    return "Soteria extracted claim-time mechanics from this policy wording."


def _page_title(metadata: Mapping[str, Any]) -> str:
    product_name = _string(metadata.get("product_name")) or "Policy wording"
    insurer_name = _string(metadata.get("insurer_name"))
    return f"{insurer_name} {product_name}".strip() if insurer_name else product_name


def _sum_insured_options(value: Any) -> str:
    if not isinstance(value, list) or not value:
        return "set per policy schedule"
    cleaned = [item for item in value if item is not None and str(item).strip()]
    if not cleaned:
        return "set per policy schedule"
    if len(cleaned) == 1:
        return _format_money(cleaned[0])
    return f"{_format_money(cleaned[0])} - {_format_money(cleaned[-1])}"


def _format_money(value: Any) -> str:
    try:
        return f"INR {int(value):,}"
    except (TypeError, ValueError):
        return str(value)


def _is_fixed_benefit(policy_type: str) -> bool:
    return policy_type.strip().lower().replace("-", "_").replace(" ", "_") in FIXED_BENEFIT_POLICY_TYPES


def _dict(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _string(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    unique: list[str] = []
    for value in values:
        key = value.strip()
        if not key or key in seen:
            continue
        seen.add(key)
        unique.append(key)
    return unique


def _safe_slug(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9_-]+", "-", value.strip().lower()).strip("-")
    return slug or "policy"
