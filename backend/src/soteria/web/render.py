from __future__ import annotations

from datetime import UTC, datetime
from html import escape
import json
from typing import Any

from soteria.ephemeral import EphemeralConfig, EphemeralStore


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


def render_anonymous_results(analysis: dict[str, Any], *, session_token: str) -> str:
    summary = _text(analysis.get("summary") or "No summary was returned.")
    red_flags = _list(analysis.get("red_flags"))[:3]
    flag_cards = "\n".join(_render_red_flag(flag, index) for index, flag in enumerate(red_flags, 1))
    return _page(
        title="Soteria Analysis Preview",
        body=f"""
        <main class="sheet">
          <section class="summary-card">
            <p class="eyebrow">Signup-free analysis</p>
            <h1>Policy summary</h1>
            <p>{summary}</p>
          </section>
          <section>
            <h2>Top red flags</h2>
            <div class="red-flags">{flag_cards}</div>
          </section>
          <section class="signup-gate">
            <h2>Keep this analysis</h2>
            <p>The preview above is complete. Sign up only if you want to keep the full analysis after the anonymous session expires.</p>
            <form method="post" action="/signup/request">
              <input type="hidden" name="session_token" value="{_attr(session_token)}">
              <label>Email <input type="email" name="email" required></label>
              <button type="submit">Send magic link</button>
            </form>
          </section>
        </main>
        """,
    )


def render_full_results(analysis: dict[str, Any]) -> str:
    sections = [
        ("Coverage", analysis.get("coverage")),
        ("Waiting Periods", analysis.get("waiting_periods")),
        ("Sub-limits", analysis.get("sub_limits")),
        ("Exclusions", analysis.get("exclusions")),
        ("All Red Flags", analysis.get("red_flags")),
    ]
    section_html = "\n".join(_render_group(title, value) for title, value in sections)
    return _page(
        title="Soteria Full Analysis",
        body=f"""
        <main class="sheet">
          <section class="summary-card">
            <p class="eyebrow">Saved analysis</p>
            <h1>Full policy analysis</h1>
            <p>{_text(analysis.get("summary") or "No summary was returned.")}</p>
          </section>
          {section_html}
        </main>
        """,
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


def _render_red_flag(flag: dict[str, Any], index: int) -> str:
    return f"""
    <article class="red-flag-card">
      <p class="eyebrow">Flag {index}</p>
      <h3>{_text(flag.get("title") or "Untitled red flag")}</h3>
      <p>{_text(flag.get("plain_explanation") or "")}</p>
      <p class="scenario">{_text(flag.get("scenario") or "")}</p>
      {render_raw_clause_block(flag.get("raw_clause"))}
    </article>
    """


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

