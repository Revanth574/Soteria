from __future__ import annotations

from datetime import UTC, date, datetime
from html import escape
import json
from typing import Any

from soteria.ephemeral import EphemeralConfig, EphemeralStore
from soteria.web.design_system import (
    _attr as _design_attr,
    _glossary_text,
    render_red_flag_card,
)


def render_upload_page(config: EphemeralConfig) -> str:
    return _page(
        title="Soteria Policy Analysis",
        body=f"""
        <main class="sheet upload-sheet">
          <h1>Read your policy before it reads you</h1>
          <p class="lede">Upload a health insurance PDF for a signup-free first analysis.</p>
          <form method="post" action="/upload" enctype="multipart/form-data" data-max-bytes="{config.max_upload_bytes}">
            <label class="dropzone">
              <span>Drag a PDF here or pick a file</span>
              <input type="file" name="policy_pdf" accept="application/pdf,.pdf" required>
            </label>
            <p class="file-note">Maximum size: {_format_bytes(config.max_upload_bytes)}.</p>
            <button type="submit">Analyze policy</button>
            <p class="progress" role="status" aria-live="polite">Analyzing your policy. This can take 30-90 seconds.</p>
          </form>
        </main>
        """,
    )


def render_anonymous_results(
    analysis: dict[str, Any],
    *,
    session_token: str,
    theme: str = "light",
    current_path: str | None = None,
) -> str:
    selected_theme = theme if theme in {"light", "dark"} else "light"
    next_theme = "dark" if selected_theme == "light" else "light"
    theme_icon = "&#9790;" if next_theme == "dark" else "&#9788;"
    path = current_path or f"/a/{session_token}"
    summary = analysis.get("summary") or "No summary was returned."
    red_flags = _list(analysis.get("red_flags"))[:3]
    flag_cards = "".join(render_red_flag_card(flag, show_title=True) for flag in red_flags)
    if not flag_cards:
        flag_cards = (
            '<p class="no-risks">No red flags were identified in this extraction. '
            "Review the wording before relying on any claim outcome.</p>"
        )
    return f"""<!doctype html>
<html lang="en" data-theme="{_design_attr(selected_theme)}">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <link rel="stylesheet" href="/static/full-analysis.css">
  <title>Soteria Analysis Preview</title>
</head>
<body class="full-analysis-body anonymous-preview-body">
  <main class="analysis-shell anonymous-shell">
    <header class="brand-bar">
      <div class="brand-lockup">
        <span class="brand-name">Soteria</span>
        <span class="brand-kicker">insurance auditor</span>
      </div>
      <div class="brand-actions">
        <span class="paid-by-you"><span aria-hidden="true"></span>paid by you</span>
        <form method="post" action="/theme" class="theme-form">
          <input type="hidden" name="theme" value="{_design_attr(next_theme)}">
          <input type="hidden" name="next" value="{_design_attr(path)}">
          <button class="theme-toggle" type="submit" aria-label="Switch to {next_theme} theme" title="Switch to {next_theme} theme">{theme_icon}</button>
        </form>
      </div>
    </header>

    <section class="preview-summary" aria-labelledby="preview-title">
      <p class="section-kicker">Signup-free analysis</p>
      <h1 id="preview-title">Policy summary</h1>
      <p>{_glossary_text(summary)}</p>
    </section>

    <section class="risk-section preview-risks" aria-labelledby="risk-title">
      <div class="section-heading-row">
        <h2 id="risk-title">Top red flags</h2>
        <span>{len(red_flags)} shown</span>
      </div>
      <div class="risk-grid">{flag_cards}</div>
    </section>

    <section class="keep-card signup-gate" aria-labelledby="keep-title">
      <div>
        <p class="section-kicker">Persistence is optional</p>
        <h2 id="keep-title">Keep this analysis</h2>
        <p>The preview above is complete. Sign up only if you want to keep the full analysis after the anonymous session expires.</p>
      </div>
      <form method="post" action="/signup/request" class="signup-form">
        <input type="hidden" name="session_token" value="{_design_attr(session_token)}">
        <label for="signup-email">Email</label>
        <div class="signup-controls">
          <input id="signup-email" type="email" name="email" autocomplete="email" required>
          <button class="primary-action" type="submit">Send magic link</button>
        </div>
      </form>
    </section>
  </main>
</body>
</html>"""


def render_full_results(
    analysis: dict[str, Any],
    *,
    theme: str = "light",
    current_path: str = "/",
    policy_start_date: date | None = None,
    raw_analysis_json: str | None = None,
) -> str:
    from soteria.web.full_analysis import render_full_analysis

    return render_full_analysis(
        analysis,
        theme=theme,
        current_path=current_path,
        policy_start_date=policy_start_date,
        raw_analysis_json=raw_analysis_json,
    )


def render_session_page(
    *,
    store: EphemeralStore,
    session_token: str,
    now: datetime | None = None,
) -> str:
    record = store.get_session(session_token, now=now or datetime.now(UTC))
    if record is None:
        return render_expired_page()
    return render_anonymous_results(json.loads(record.analysis_json), session_token=session_token)


def render_signup_gate(*, email: str, signup_token: str, session_token: str) -> str:
    return _page(
        title="Soteria Dev Magic Link",
        body=f"""
        <main class="sheet">
          <p class="eyebrow">DEV-ONLY magic link stub</p>
          <h1>Keep this analysis</h1>
          <p>The anonymous preview remains complete. This signup stub exists only to persist the analysis for {_text(email)}.</p>
          <dl class="dev-token">
            <dt>Session token</dt>
            <dd><code>{_text(session_token)}</code></dd>
            <dt>Magic token</dt>
            <dd><code>{_text(signup_token)}</code></dd>
          </dl>
        </main>
        """,
    )


def render_expired_page() -> str:
    return _page(
        title="Analysis expired",
        body="""
        <main class="sheet status-sheet">
          <h1>This analysis has expired</h1>
          <p>Anonymous analyses are deleted after their short retention window. Upload the policy again to run a fresh analysis.</p>
        </main>
        """,
    )


def render_processing_page(*, session_token: str) -> str:
    return _page(
        title="Analysis in progress",
        refresh_url=f"/a/{session_token}",
        body=f"""
        <main class="sheet status-sheet">
          <p class="eyebrow">Analysis in progress</p>
          <h1>We are reading the policy wording</h1>
          <p>This page refreshes automatically until the analysis is ready.</p>
          <p class="muted">Typical turnaround is 30-90 seconds.</p>
        </main>
        """,
    )


def render_failure_page(*, session_token: str) -> str:
    return _page(
        title="Analysis failed",
        body=f"""
        <main class="sheet status-sheet">
          <p class="eyebrow">Analysis failed</p>
          <h1>We could not complete this analysis</h1>
          <p>The policy was accepted, but the analyzer did not produce a valid result.</p>
          <form method="post" action="/upload">
            <p class="muted">Retry by uploading the policy again.</p>
          </form>
          <p><a href="/a/{_attr(session_token)}">Check status again</a></p>
        </main>
        """,
    )


def render_not_found_page() -> str:
    return _page(
        title="Analysis not found",
        body="""
        <main class="sheet status-sheet">
          <h1>This analysis is not available</h1>
          <p>The link may be expired, malformed, or already deleted.</p>
        </main>
        """,
    )


def render_rate_limited_page() -> str:
    return _page(
        title="Too many uploads",
        body="""
        <main class="sheet status-sheet">
          <h1>Too many uploads</h1>
          <p>Please wait before uploading another policy from this connection.</p>
        </main>
        """,
    )


def render_upload_too_large_page() -> str:
    return _page(
        title="Upload too large",
        body="""
        <main class="sheet status-sheet">
          <h1>This PDF is too large</h1>
          <p>Upload a smaller policy PDF within the configured size limit.</p>
        </main>
        """,
    )


def _render_group(title: str, value: Any) -> str:
    items = _field_items(value)
    item_html = "\n".join(_render_field_item(label, item) for label, item in items)
    return f"""
    <section class="field-group">
      <h2>{_text(title)}</h2>
      {item_html or '<p class="muted">No extracted fields.</p>'}
    </section>
    """


def _field_items(value: Any) -> list[tuple[str, Any]]:
    if isinstance(value, dict):
        return [(str(key), item) for key, item in value.items()]
    if isinstance(value, list):
        return [(f"Item {index}", item) for index, item in enumerate(value, 1)]
    if value is None:
        return []
    return [("Value", value)]


def _render_field_item(label: str, item: Any) -> str:
    raw_clause = _extract_raw_clause(item)
    confidence = _extract_confidence(item)
    body = _text(_display_value(item))
    source_html = (
        render_raw_clause_block(raw_clause)
        if raw_clause is not None
        else '<p class="muted">No source clause returned.</p>'
    )
    confidence_html = f'<p class="confidence">Confidence: {_text(confidence)}</p>' if confidence else ""
    return f"""
    <details class="field-row">
      <summary>{_text(label)}: {body}</summary>
      {confidence_html}
      {source_html}
    </details>
    """


def _extract_raw_clause(value: Any) -> str | None:
    if isinstance(value, dict):
        for key in ("raw_clause", "clause_text", "source_clause"):
            if value.get(key) is not None:
                return str(value[key])
    return None


def _extract_confidence(value: Any) -> str | None:
    if isinstance(value, dict) and value.get("confidence") is not None:
        return str(value["confidence"])
    return None


def _display_value(value: Any) -> str:
    if isinstance(value, dict):
        display = {
            key: item
            for key, item in value.items()
            if key not in {"raw_clause", "clause_text", "source_clause", "confidence"}
        }
        return json.dumps(display, ensure_ascii=False)
    if isinstance(value, list):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def _page(*, title: str, body: str, refresh_url: str | None = None) -> str:
    refresh = (
        f'  <meta http-equiv="refresh" content="2; url={_attr(refresh_url)}">\n'
        if refresh_url is not None
        else ""
    )
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
{refresh}  <link rel="stylesheet" href="/static/soteria.css">
  <title>{_text(title)}</title>
</head>
<body>
{body}
</body>
</html>"""


def _list(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def escape_text(value: Any) -> str:
    return escape(str(value), quote=False)


def escape_attr(value: Any) -> str:
    return escape(str(value), quote=True)


def render_raw_clause_block(raw_clause: Any) -> str:
    raw_clause_text = "" if raw_clause is None else str(raw_clause)
    return (
        '<div class="clause-box">'
        '<p class="verified-marker">verified against the wording</p>'
        f'<pre class="raw-clause">{escape_text(raw_clause_text)}</pre>'
        "</div>"
    )


def _text(value: Any) -> str:
    return escape_text(value)


def _attr(value: Any) -> str:
    return escape_attr(value)


def _format_bytes(value: int) -> str:
    return f"{value // (1024 * 1024)} MB"

