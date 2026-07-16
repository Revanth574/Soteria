# Soteria Build Progress

## 2026-07-07 - H1-1 Ingestion Spine + Canonical Document

Status: complete - merged to `main`.

Branch: `feature/h1-1-ingestion-spine`

Merge commit: `f7a3c6cd89384ed8e48205ef2209380c4de9ca06`

Implemented:
- Backend package scaffold under `backend/src/soteria`.
- `PolicyIngestionSource` protocol.
- `CanonicalPolicyDocument` and `CanonicalPolicyPage` models.
- `PdfUploadSource` for PDF upload bytes to canonical document conversion.
- SHA-256 checksum on uploaded PDF bytes.
- Addendum-aligned canonical fields:
  - `full_text`
  - `pages` nullable for future structured sources
  - `structured_fields`
  - `source_type`
  - `source_metadata`
  - `ingested_at`
  - `checksum`
  - `policy_kind`
- Explicit ingestion errors for unsupported file type, corrupt/unparseable PDF,
  and empty text extraction.
- RED-proof tests for:
  - valid PDF upload produces a canonical document,
  - non-PDF bytes are rejected,
  - blank/scanned-style PDFs fail with a clear empty-extraction error,
  - corrupt PDF bytes fail with a clear extraction error,
  - empty canonical documents cannot be constructed,
  - page-less structured-source canonical documents are representable.

Repo assets placed from architect handoff, without content edits:
- `docs/SOTERIA_CODEX_HANDOFF_H1.md`
- `docs/SOTERIA_ARCHITECTURE_ADDENDUM.md`
- `docs/SOTERIA_VALIDATION_LOG.md`
- `prompts/extract_policy_v1.2.md`
- `prompts/taxonomy_RF015-019.md`
- `fixtures/gold/GOLD_001_STARHEALTH_SUPERSTAR.md`

Validation:
- RED phase observed: tests first failed because `soteria.ingestion` did not
  exist.
- GREEN phase after implementation: `python -m pytest backend/tests` passed.
- Addendum reconciliation phase: `python -m pytest backend/tests` passes with
  `6 passed`.
- `python -m compileall -q backend/src` passes.

Self-audit against handoff prohibitions:
- Prompt and taxonomy assets were copied into place only; content not edited.
- No H1-2 extraction adapter work started.
- No renderer, store, signup, public page, or gold regression work started.
- No red-flag rendering logic added.
- No anonymous document persistence or TTL behavior added.
- Search found no prompt, extraction, signup, store, or renderer code in the
  H1-1 backend implementation.

Known gaps:
- `super_star_fulltext.txt` is still not present. It is not needed for H1-1,
  but will matter when fixture-driven extraction tests are scoped later.
- Coverage gap: scanned/image-only PDFs (where pdfplumber returns no text) are
  expected to raise EmptyExtractionError or PdfExtractionError, but no fixture
  yet proves the image-PDF path specifically hits a clear ingestion error rather
  than another failure. Non-blocking; revisit when OCR/image support is scoped.

Next action:
- H1-2 Extraction adapter + result type. Not started.

## 2026-07-07 - H1-2 Extraction Adapter + Result Type

Status: complete - merged to `main`.

Branch: `feature/h1-2-extraction-adapter`

Merge commit: `20d1b97d92a7ec3af0f417da9b0e886ce1dccbaf`

Implemented:
- `ExtractionAdapter` that accepts a `CanonicalPolicyDocument` and returns an
  `ExtractionResult`.
- Prompt loader for `prompts/extract_policy_v1.2.md`; prompt content was not
  edited.
- `{{POLICY_TEXT}}` injection from `CanonicalPolicyDocument.full_text`.
- `ExtractionConfig` sourced from environment or local `.env` files.
- Thin `AnthropicMessagesClient` wrapper using the official Anthropic SDK.
- Model string and API key are config/environment inputs, not hardcoded.
- Strict `schema_version == "1.2"` boundary validation.
- Retry-once behavior for malformed model JSON.
- `backend/.env.example` documents required extraction variables without
  secrets.

RED-proofs:
- RED phase observed: `backend/tests/test_extraction_adapter.py` first failed
  because `soteria.extraction` did not exist.
- F18: string literal `"null"` in model JSON is normalized to JSON null before
  return and is not silently stored as a string.
- F18 targeted RED check: temporarily disabling normalization made
  `test_f18_string_null_is_normalized_not_silently_stored` fail with
  `AssertionError: assert 'null' is None`.
- F19: malformed JSON from unescaped quotes in `raw_clause` is retried once;
  if the retry is also malformed, `MalformedModelOutputError` is raised with a
  clear "after 2 attempts" message.
- F19 targeted RED check: temporarily disabling the retry made
  `test_f19_malformed_raw_clause_is_retried_once_then_valid_response_is_returned`
  fail before consuming the valid second response.

Validation:
- `python -m pytest backend/tests/test_extraction_adapter.py` passes with
  `6 passed`.
- `python -m pytest backend/tests` passes with `12 passed`.
- `python -m compileall -q backend/src` passes.

Focused-review flag:
- Credential/config layer is implemented but not self-certified for security.
  It reads `ANTHROPIC_API_KEY` and `ANTHROPIC_MODEL` from environment/local
  `.env`; this needs architect/security review before production use.

Known gaps:
- H1-2 follow-up (non-blocking): `_normalize_string_nulls` currently converts
  any whole-string `"null"` to None globally across the JSON tree. Low
  corruption risk (only fires on exact-match `"null"` strings, not `"null"`
  within prose), but should be scoped to schema-nullable fields in a future
  hardening pass.

Self-audit against handoff prohibitions:
- Prompt/taxonomy content not edited.
- No renderer code added.
- No storage, signup, session attachment, or TTL/deletion behavior added.
- No gold regression runner added.

Next action:
- H1-3 Ephemeral store + signup-free flow. Not started.

## 2026-07-08 - H1-3 Ephemeral Store + Signup-Free Flow

Status: complete - merged to `main`.

Branch: `feature/h1-3-ephemeral-store`

Implemented:
- SQLite-backed `EphemeralStore` for anonymous sessions, signup tokens,
  account attachment records, and deletion audit rows.
- `EphemeralConfig` reads `DATABASE_URL` and `EPHEMERAL_DATA_DIR` from
  environment/local `.env`; SQLite database files must live under
  `EPHEMERAL_DATA_DIR`.
- Anonymous upload flow that validates file size and PDF magic bytes without
  requiring auth.
- Per-IP in-memory anonymous upload rate limiting.
- Ephemeral persistence of uploaded PDF artifact, canonical document text, and
  `ExtractionResult` JSON keyed by opaque session token.
- TTL enforcement for anonymous fetches with TTL capped at <= 24 hours.
- Deletion job that removes expired anonymous records and their PDF artifacts,
  then writes a deletion audit log.
- Signup-free preview containing summary plus the top 3 red flags in full,
  including raw clauses when present in the analysis JSON.
- Magic-link signup stub token issuance and consume flow; real email delivery
  remains out of scope.
- Session-to-account attachment that makes the previously anonymous document
  retrievable under the account and no longer subject to anonymous TTL deletion.

RED-proofs:
- RED phase observed: `backend/tests/test_ephemeral_flow.py` first failed
  because `soteria.ephemeral` did not exist.
- Deletion actually deletes: temporarily skipping artifact unlink made
  `test_deletion_job_deletes_records_and_artifacts_not_just_flags` fail because
  the SQLite row was gone but the PDF artifact still existed.
- TTL enforcement: temporarily disabling the expiry check made
  `test_ttl_is_enforced_on_fetch` return an expired session instead of `None`.
- Guards without auth: temporarily disabling the anonymous PDF magic-byte guard
  made `test_anonymous_upload_guards_run_without_auth` reach ingestion and
  raise the wrong error instead of `UploadValidationError`.
- Session-to-account attachment: temporarily leaving the anonymous expiry in
  place made
  `test_session_to_account_attachment_makes_anonymous_document_retrievable_under_account`
  fail after TTL.
- Architect Q1 deletion skip proof: `delete_expired` already skipped
  account-attached sessions. Added
  `test_delete_expired_skips_account_attached_sessions_and_artifacts`, which
  proves the account-scoped record and PDF artifact survive cleanup after the
  original anonymous TTL and that no deletion audit row is written for that
  session.
- Architect Q2 artifact path proof/fix: hostile filenames could influence the
  artifact filename. Added a failing test for path traversal, absolute path,
  and null-byte filenames, then fixed artifact path construction so the
  on-disk path is derived from the opaque session token plus a fixed internal
  artifact name. User-supplied filename remains display metadata in SQLite.

Validation:
- `python -m pytest backend/tests/test_ephemeral_flow.py` passes with
  `8 passed`.
- `python -m pytest backend/tests` passes with `20 passed`.
- `python -m compileall -q backend/src` passes.

Focused-review flag:
- This is security-relevant and not self-certified. Architect/security review
  should focus on deletion completeness, SQLite path confinement under
  `EPHEMERAL_DATA_DIR`, anonymous rate limiting, and the decision to make
  attached sessions no longer subject to anonymous TTL deletion.

Known gaps:
- Rate limiting is in-memory only; it will reset on process restart. This is
  adequate for H1-3 tests but should move to a shared/persistent limiter before
  multi-process deployment.
- Rate-limit window rollover is unproven: no test currently proves a second
  request succeeds after the hour elapses.
- IP rate limiting trusts the passed-in `ip_address`; `X-Forwarded-For` trust
  must be decided at deployment (H1-4+).
- The store deletes the uploaded PDF artifact and database row. No additional
  derived artifacts are currently written by H1-3.
- The local `.env` example path from the handoff put the SQLite file outside
  `EPHEMERAL_DATA_DIR`; the implementation enforces the stricter privacy
  invariant that the database file itself must live under `EPHEMERAL_DATA_DIR`.

Self-audit against handoff prohibitions:
- Prompt/taxonomy content not edited.
- No renderer code added.
- No public red-flag page generator added.
- No real email infrastructure added.
- No H1-4 analysis rendering started.

Next action:
- Architect/security review/ratification of H1-3. H1-4 not started.

## 2026-07-08 - H1-4 Analysis Renderer Web UI

Status: built and locally tested. Not merged.

Branch: `feature/h1-4-analysis-renderer`

Implemented:
- Minimal server-rendered HTML layer under `soteria.web`.
- Single-page PDF upload view with drag/drop language, file picker, client-side
  max-size check mirroring `EphemeralConfig.max_upload_bytes`, and a visible
  30-90 second analysis progress state on submit.
- `AnalysisWebController.submit_upload` delegates to the existing H1-3
  `SignupFreeFlow.submit_anonymous_upload`; no second upload path was added.
- Anonymous results renderer with full summary and top-3 red flags, including
  full `plain_explanation`, `scenario`, and untrimmed `raw_clause` blocks.
- Signed-up full-results renderer grouping coverage, waiting periods,
  sub-limits, exclusions, and all red flags with expandable source clause and
  confidence display.
- DEV-ONLY magic-link stub UI that surfaces the token and frames signup as
  persistence ("keep this analysis"), not content ransom.
- Stub signup consumption path that renders the signed-up full tier from the
  attached account session.
- Expired/not-found analysis page for expired anonymous sessions.

Tech choice:
- Used server-rendered Python HTML functions with minimal JavaScript only for
  client-side file-size validation and progress state. No SPA framework was
  added because the product is document-reading first, and this keeps the UI
  fast, inspectable, and usable without client-side rendering for results.

RED-proofs:
- RED phase observed: `backend/tests/test_web_renderer.py` first failed because
  `soteria.web` did not exist.
- XSS: a `raw_clause` containing `<script>alert(1)</script>` renders as escaped
  visible text and does not appear as executable script markup.
- Anonymous completeness: a fixture with 5 red flags renders exactly 3
  anonymous red-flag cards, and the top-3 raw clauses appear in full.
- Tier boundary: coverage/waiting-period fields outside the anonymous tier are
  absent from anonymous HTML, not hidden by CSS.
- Expired-session UX: fetching an expired session renders the expired page with
  no stack trace or empty 500.

Validation:
- `python -m pytest backend/tests/test_web_renderer.py` passes with
  `10 passed`.
- `python -m pytest backend/tests` passes with `30 passed`.
- `python -m compileall -q backend/src` passes.

Known gaps:
- Only one gold fixture exists in the repo (`GOLD_001_STARHEALTH_SUPERSTAR.md`).
  H1-4 includes a Super Star-derived render fixture for the anonymous HTML dump,
  but the requested six-gold render regression set cannot be completed until
  the other five gold analysis files are present.
- This is a renderer/controller layer, not a deployed HTTP server process. It
  is ready to mount behind the backend route layer when that is scoped.
- HTTP routing/serving framework is not yet wired; this increment covers render
  logic only.
- Certified-record design system (fonts, palette) from the Plan C public page
  is not yet applied to this renderer and needs a follow-up pass for brand
  consistency.

Self-audit against handoff prohibitions:
- Prompt/taxonomy content not edited.
- Docs and fixtures content not edited.
- No public red-flag page generator added.
- No H1-5 work started.

Next action:
- Architect review/ratification of H1-4. H1-5 not started.

## 2026-07-08 - H1-5 Public Page Generator

Status: built and locally tested. Not merged.

Branch: `feature/h1-5-public-page-generator`

Merge commit: `50afd55`

Implemented:
- Build-time public page generator under `soteria.public_pages`.
- `generate_public_page_html` accepts ExtractionResult-shaped JSON plus an
  optional explicit `policy_type`.
- `generate_public_pages` reads JSON files and writes one standalone static
  HTML file per input JSON to a designated output directory.
- Public page template is distinct from the H1-4 in-app renderer and labelled
  as a Plan C public red-flag page.
- Extracted content rendering reuses H1-4 escaping primitives from
  `soteria.web.render`, including a shared raw-clause block renderer.
- Policy-type shape split:
  - indemnity-style policies render `financial_impact_estimate` as the red-flag
    exposure language;
  - fixed-benefit policies (`critical_illness`, `fixed_benefit`) render
    "at stake: the entire Sum Insured" and do not use percentage-of-bill
    framing.
- Data-driven verdict copy:
  - any critical severity produces cautionary framing;
  - medium-or-lower-only pages may use a more positive-but-caveated framing.
- Public fallbacks for missing/schedule-dependent data:
  - null `metadata.product_uin` renders "UIN not stated in published wording";
  - empty `metadata.sum_insured_options` renders "set per policy schedule";
  - extracted uncertainty notes and schedule-dependent values are surfaced in a
    dedicated uncertainty section.
- `pattern_id == "novel"` red flags render a distinct "outside numbered
  taxonomy" marker.
- Fixed-benefit "What this gets right" filtering prevents structurally
  inapplicable "no room rent cap" and "no co-pay" claims from being inflated
  into product strengths.

RED-proofs:
- RED phase observed: `backend/tests/test_public_page_generator.py` first
  failed because `soteria.public_pages` did not exist.
- Batch generation: six gold-shaped JSON fixtures produce six standalone HTML
  files, each with escaped hostile extracted content.
- Indemnity shape: red-flag cards use the extracted
  `financial_impact_estimate`.
- Fixed-benefit shape: red-flag cards use entire-Sum-Insured forfeiture
  framing and do not render percentage-of-bill text.
- Critical severity: verdict text is cautionary and does not contain
  unconditionally positive phrases such as "genuinely good policy" or
  "clean policy".
- HDFC Ergo CI-equivalent fixture: null UIN and empty sum-insured options render
  the required public fallback strings and do not render `None`.
- Novel pattern: `pattern_id == "novel"` renders the distinct outside-taxonomy
  marker exactly once.
- Fixed-benefit strengths: HDFC Ergo CI-equivalent fixture keeps a positive
  fixed-benefit mechanic while excluding "No room rent cap" and "No co-pay".

Validation:
- `python -m pytest backend/tests/test_public_page_generator.py` passes with
  `8 passed`.
- `python -m pytest backend/tests/test_web_renderer.py` passes with
  `10 passed`.
- `python -m pytest backend/tests` passes with `38 passed`.
- `python -m compileall -q backend/src` passes.

Gold fixture comparison:
- The repo currently contains only one gold fixture file:
  `fixtures/gold/GOLD_001_STARHEALTH_SUPERSTAR.md`.
- The requested six gold-set JSON analysis fixtures are not present locally, so
  H1-5 uses six synthetic gold-shaped JSON render fixtures:
  `gold_001_star_super_star`, `gold_002_senior`, `gold_003_super_top_up`,
  `gold_004_individual`, `gold_005_ci_hdfc_ergo`, and `gold_006_ci_alt`.
- Generated output was compared against the Plan C public-page requirements
  rather than against hand-built Plan C fixture pages, because those pages are
  not present in this repo and were not touched.

Known divergences from hand-built Plan C pages:
- Bespoke per-policy insight sections such as SI-band tables, deductible
  ledgers, and compounding-caps tables remain manual and are not synthesized.
- The generator currently emits the shared public-page frame, metadata,
  verdict, red-flag cards, strengths, and uncertainty sections only.

Self-audit against handoff prohibitions:
- Prompt/taxonomy content not edited.
- Docs and fixtures content not edited, except this required `PROGRESS.md`
  update.
- No page editor, CMS, admin UI, public app route, or per-request serving layer
  added.
- No H1-6 or post-H1-5 work started.

Next action:
- H1-6 HTTP layer, real extractor, and design system. In progress on
  `feature/h1-6-http-real-extractor-design-system`.

## 2026-07-08 - H1-6 HTTP Layer + Claude Extractor + Certified-Record Design System

Status: complete - merged to `main`.

Branch: `feature/h1-6-http-real-extractor-design-system`

Merge commit: `a3fa0c9`

Framework choice:
- FastAPI was used for the HTTP layer. The app is built through an injectable
  factory so tests can wire `FakeExtractor` and a manual background queue while
  production wiring can construct the real `ClaudeExtractor`.

Implemented:
- FastAPI routes:
  - `GET /` upload page,
  - `POST /upload` anonymous upload,
  - `GET /a/{session_token}` anonymous result/status page,
  - `POST /signup/request`,
  - `GET /signup/confirm/{token}`,
  - `GET /a/{session_token}/full` signed-up full tier.
- `POST /upload` calls `SignupFreeFlow.submit_anonymous_upload` with
  background mode and does not introduce a second upload path.
- Explicit session status support in the SQLite store:
  `processing`, `complete`, and `failed`.
- Background analysis completion through `SignupFreeFlow.complete_analysis`.
- Processing page uses meta-refresh polling, so it works without JavaScript.
- Failure, malformed-token, unknown-token, and expired-token routes render clean
  pages instead of stack traces or raw 500 bodies.
- Rate-limit violations render HTTP 429 with a plain-language page.
- Oversized uploads return HTTP 413 before multipart parsing when
  `Content-Length` is over the configured cap plus multipart overhead; the
  existing H1-3 upload guard remains the authoritative size check after read.
- Client-IP policy:
  - direct connection IP is used by default;
  - `TRUST_PROXY_HEADERS=false` is documented in `.env.example`;
  - when true, `X-Forwarded-For` is read and the last listed IP is used.
- Security headers on all responses:
  - `Content-Security-Policy`,
  - `X-Content-Type-Options: nosniff`,
  - `X-Frame-Options: DENY`.
- `ClaudeExtractor` implementation with mocked-client unit tests:
  - loads system and extraction prompt files at construction time;
  - injects `{{POLICY_TEXT}}`;
  - makes one Claude Messages request per analysis with a 120s timeout;
  - reads API key from config/environment only;
  - parses/validates schema version 1.2 and surfaces malformed JSON without
    leaking raw model output to users.
- Certified-record design system applied through a static stylesheet served by
  the app:
  - requested palette,
  - Newsreader / IBM Plex Mono / Inter font families,
  - verified clause markers,
  - scenario "If -" framing,
  - scrollable verbatim clause blocks.

Markup/styling changes:
- Removed the previous inline `<style>` block from H1-4 renderer pages and
  replaced it with `/static/soteria.css`.
- Removed the previous inline upload-page script to keep CSP simple and avoid
  inline script allowances.
- Added a wrapper around raw-clause `<pre>` blocks so the verified marker can be
  displayed consistently. Anonymous/full tier selection logic was not changed.

RED-proofs:
- HTTP XSS: upload plus completed analysis containing
  `<script>alert(1)</script>` in `raw_clause` renders escaped text and no raw
  script tag.
- Upload path integrity: oversized upload returns 413; the N+1th upload from
  one IP returns 429; both are plain-language pages.
- Status honesty: processing, complete, and failed sessions render distinct
  honest pages; failure response contains no traceback or extractor exception
  detail.
- Token safety: malformed, unknown, and expired tokens each return clean 404
  pages with no stack trace or 500 body.
- Tier boundary over HTTP: anonymous route omits signed-up-tier fields; full
  route includes them after signup attachment.
- Proxy-header policy: default ignores `X-Forwarded-For`; trusted mode uses the
  configured forwarded header behavior.
- ClaudeExtractor tests use a mocked client only; zero real API calls are made
  by the test suite.

Validation:
- `python -m pytest backend/tests/test_claude_extractor.py` passes with
  `5 passed`.
- `python -m pytest backend/tests/test_http_app.py` passes with `6 passed`.
- `python -m pytest backend/tests` passes with `51 passed`.
- `python -m compileall -q backend/src` passes.

Deployment notes for H1-7:
- Background analysis currently uses FastAPI `BackgroundTasks`, which is
  in-process. A process restart can interrupt in-flight analyses; deployment
  should decide whether to keep this for Horizon 1 or move to a durable queue.
- `TRUST_PROXY_HEADERS` must stay false unless the app is behind a known trusted
  proxy that controls `X-Forwarded-For`.
- `SOTERIA_SYSTEM_PROMPT_PATH` defaults to `prompts/system.md`, but that file is
  not present in the repo. Creating/providing that prompt remains a
  Revanth-owned prompt asset decision; the extractor fails clearly at startup if
  the configured file is missing.
- No automatic Claude retries are implemented. Retry policy is deferred to
  H1-7+ to avoid retry storms and paid-API cost incidents.
- H1-7 should harden the background worker so any unexpected worker error,
  including store/write failures outside the extraction path, deterministically
  lands the session in `failed` instead of risking an indefinite processing
  page.

Known gaps:
- No deployment config, real email delivery, or public-page hosting added.
- Upload client-side size validation is no longer implemented with inline
  JavaScript; server-side 413/validation behavior is covered. A future pass can
  add a CSP-compatible external script if client-side validation is required.

Self-audit against handoff prohibitions:
- Prompt content not edited.
- Docs and fixtures content not edited, except this required `PROGRESS.md`
  update.
- No deployment configs, email delivery, public-page hosting, page editor, CMS,
  admin UI, or H2 feature work added.

Next action:
- H1-7a Production VM deployment. Repo-side runbook/code built; live deployment
  verification blocked in this local environment because `gcloud` is not
  installed.

## 2026-07-09 - H1-7a Production VM Deployment

Status: complete - production deployment live.

Branch: `feature/h1-7a-production-vm-deploy`

Implemented:
- Added shallow `GET /health` to the FastAPI app. This is the one app-code
  change in H1-7a; it returns `{"status": "ok"}` without DB, storage, or
  extractor dependency.
- Added a focused health test proving the endpoint remains live even when the
  injected extractor would fail.
- Added `DEPLOY.md` at repo root with exact VM commands for:
  - Ubuntu/Python confirmation,
  - official Caddy apt repository installation,
  - dedicated non-root `soteria` system user,
  - `/opt/soteria` code checkout,
  - `/opt/soteria/backend/.venv` dependency install from `pyproject.toml`,
  - `/opt/soteria/backend/.env` production environment file,
  - `/var/lib/soteria` persistent SQLite/session-artifact storage,
  - systemd service install and restart,
  - Caddy reverse proxy install and reload,
  - TLS/health/static-page/upload verification commands,
  - redeploy and log-check commands.
- Added combined prompt loading for production config:
  `SOTERIA_COMBINED_PROMPT_PATH` points at the one committed prompt asset,
  `prompts/extract_policy_v1.2.md`, and the extractor splits it on
  `## EXTRACTION TASK` at startup.
- Added explicit ambiguous-config validation: combined prompt mode now rejects
  non-empty legacy two-file prompt env vars instead of silently choosing one.
- Added `infra/soteria.service` production systemd unit template:
  - runs as `soteria`,
  - `WorkingDirectory=/opt/soteria/backend`,
  - `EnvironmentFile=/opt/soteria/backend/.env`,
  - binds uvicorn to `127.0.0.1:8000`,
  - uses `Restart=on-failure`.
- Added `infra/Caddyfile.production`:
  - routes `soteria.co.in` and `www.soteria.co.in` to `127.0.0.1:8000`,
  - serves `/policies/*` from `/var/www/soteria-public-pages`,
  - keeps Python out of the static public-page path,
  - relies on Caddy's automatic HTTPS/HTTP-to-HTTPS behavior.

Production deployment:
- Live domains: `soteria.co.in` and `www.soteria.co.in`.
- HTTPS is served by Caddy with Let's Encrypt.
- Backend runs as a systemd-managed service under the non-root `soteria` user.
- Uvicorn is bound loopback-only on `127.0.0.1:8000`; Caddy is the only
  internet-facing process.
- GCP VM: e2-micro, `asia-south1`, static IP `34.14.190.8`.
- All six public red-flag pages are served statically from
  `/var/www/soteria-public-pages`.
- End-to-end smoke test passed live over HTTPS: real PDF upload -> background
  extraction -> real Claude API (`claude-sonnet-5`) -> schema-validated result
  -> rendered anonymous analysis page.
- Anthropic API cost for smoke-test extractions:
  [Revanth to fill from console.anthropic.com usage].

Live smoke-test bugs surfaced and fixed:
- `claude-sonnet-5` rejected `temperature` with HTTP 400
  `invalid_request_error`; fixed by making temperature optional and omitting it
  when unset.
- Prompt loading expected separate system/extraction prompt files while the real
  asset was authored as one combined file; fixed with
  `SOTERIA_COMBINED_PROMPT_PATH`, `split_combined_prompt`, and ambiguous-config
  validation.
- The prompt file's embedded output-schema example hardcoded
  `"schema_version": "1.1"` while the app validator required `"1.2"`, causing
  extraction validation failure; corrected to `"1.2"`.
- Background-task exception swallowing made the three issues above slow to
  isolate; fixed by logging swallowed background exceptions with traceback and
  `session_token`, and by marking unexpected worker failures as `failed`.

Local validation:
- `python -m pytest backend/tests/test_http_app.py -q` passes with `9 passed`.
- `python -m pytest backend/tests -q` passes.
- `python -m compileall -q backend/src` passes.

Known gaps:
- Closed by H1-7b: signup magic-link email delivery is no longer a dev-only
  stub when `RESEND_API_KEY` is configured.

Self-audit against handoff prohibitions:
- No prompt content edited in this close-out branch.
- `docs/` and `fixtures/` not touched.
- No email delivery or magic-link sending added.
- No public-page hosting implementation beyond Caddy static-file routing.
- No H2 feature work started.

Next action:
- H1-7b ratification/merge, then operator DNS/domain verification for Resend.

## 2026-07-10 - H1-7b Real Magic-Link Email Delivery

Status: complete - built and locally tested. Not merged.

Branch: `feature/h1-7b-real-magic-link-email`

Implemented:
- Added `EmailSender` protocol with one method:
  `send_magic_link(to_email, magic_link_url)`.
- Added `LoggingEmailSender` dev/stub implementation that logs the generated
  magic link instead of sending.
- Added `ResendEmailSender` production implementation using Resend's REST API
  via Python stdlib HTTP calls; no new SDK dependency was added.
- Added `EmailConfig` with:
  - `RESEND_API_KEY` optional,
  - `EMAIL_FROM_ADDRESS` required when `RESEND_API_KEY` is set,
  - `SOTERIA_PUBLIC_BASE_URL` for absolute magic-link URL construction.
- Sender selection:
  - no `RESEND_API_KEY` -> `LoggingEmailSender`,
  - `RESEND_API_KEY` set -> `ResendEmailSender`.
- Wired `/signup/request` to send the already-generated signup token by email.
  Token generation, token storage, expiry, consume, and account attachment
  logic were not rebuilt or changed.
- Magic-link URL uses the existing confirm route:
  `{SOTERIA_PUBLIC_BASE_URL}/signup/confirm/{token}`.
- Email content is plain/minimal:
  - subject: "Your Soteria analysis link",
  - plain-text body,
  - minimal HTML body,
  - 30-minute expiry note matching the existing signup token TTL,
  - no policy content or analysis content.

RED-proofs:
- RED phase observed: `backend/tests/test_email_delivery.py` first failed
  because `soteria.email` did not exist.
- `/signup/request` with a mocked `EmailSender` calls `send_magic_link` exactly
  once with the requested recipient and an absolute HTTPS URL pointing at the
  real confirm route.
- End-to-end mocked-delivery signup path still works:
  request signup -> capture emailed link -> hit confirm route -> session is
  attached and full tier is accessible.
- With `RESEND_API_KEY` unset, config selects `LoggingEmailSender`; no real send
  is attempted.
- Email body contains the magic link and does not include policy text or
  analysis content.

Validation:
- `python -m pytest backend/tests/test_email_delivery.py -q` passes with
  `5 passed`.
- `python -m pytest backend/tests/test_http_app.py -q` passes with `9 passed`.
- `python -m pytest backend/tests -q` passes.
- `python -m compileall -q backend/src` passes.

Operator actions still required:
- Provision `RESEND_API_KEY` on the VM; never commit it.
- Provision `EMAIL_FROM_ADDRESS` on the VM.
- Set `SOTERIA_PUBLIC_BASE_URL=https://soteria.co.in` on the VM.
- Complete Resend DNS/domain verification for the sending domain.

Self-audit against handoff prohibitions:
- Prompt content not edited.
- Extraction pipeline not touched.
- Ephemeral deletion/TTL logic not touched.
- Token generation, expiry, consumption, and account attachment logic not
  touched.
- No real email was sent by the test suite.

Next action:
- H1-7b architect review/ratification, then merge.

## Session end - 2026-07-13: Live production, and the large-document ceiling

### What is live and working
- Full production deployment at soteria.co.in / www.soteria.co.in: HTTPS via
  Caddy + Let's Encrypt, systemd-managed FastAPI (uvicorn) running as non-root
  `soteria` user, loopback-only (127.0.0.1:8000), Caddy sole internet-facing
  process.
- GCP e2-medium (upgraded from e2-micro this session - see below),
  asia-south1, static IP 34.14.190.8.
- All six public red-flag pages served statically from
  /var/www/soteria-public-pages.
- Real magic-link email delivery LIVE: Resend, sending domain soteria.co.in
  verified (DKIM/SPF/MX via GoDaddy Domain Connect auto-configure). Config in
  `.env`: `RESEND_API_KEY`, `EMAIL_FROM_ADDRESS=noreply@soteria.co.in`,
  `SOTERIA_PUBLIC_BASE_URL=https://soteria.co.in`.
- Extraction pipeline works end-to-end through the live site for
  small-to-medium real documents.

### Bugs found + fixed this session (all live-only, none caught by the test suite)
1. `temperature` rejected by `claude-sonnet-5` (400) -> made
   optional/omitted-when-None. [merged]
2. Combined-prompt loading mismatch (prompt authored as one file, config
   expected two) -> `SOTERIA_COMBINED_PROMPT_PATH` + `split_combined_prompt` +
   ambiguous-config validation. [merged]
3. Prompt's embedded schema example hardcoded schema_version "1.1" while
   validator required "1.2" -> corrected. [merged]
4. Background task swallowed exceptions silently -> structured logging with
   session_token + traceback; mark-failed on any exception. [merged]
5. Memory exhaustion on e2-micro (1GB) - real full-size PDF parsing + large LLM
   round-trip pushed box into swap, wedged SSH -> resized to e2-medium (4GB).
   Root architectural note: PDF parsing is synchronous in request path; moving
   it into the background task is a future hardening item.
6. `max_tokens=16000` too low for Sonnet 5 - adaptive thinking (on by default)
   consumed the whole budget before emitting output -> empty response ->
   `MalformedModelOutputError`. Raised to `ANTHROPIC_MAX_TOKENS=64000` (in
   `.env`; also update code default + `.env.example`).
7. Added configurable `ANTHROPIC_TIMEOUT_SECONDS` (default 120), set to 300 in
   production. [merged]
8. Resend email requests sent through stdlib `urllib` were blocked by
   Cloudflare error 1010 because its default `Python-urllib/x.y` User-Agent
   looked bot-like. Fixed locally by sending the explicit identifying
   `Soteria/1.0 (+https://soteria.co.in)` User-Agent and logging a truncated
   third-party error response body without session, recipient, or email
   content. This was live-only because mocked delivery tests did not inspect
   real HTTP request headers. General lesson: every future stdlib `urllib` or
   raw HTTP client call to a third-party API must set an explicit User-Agent by
   default. [pending deployment]

### THE OPEN ITEM - large-document ceiling (next session)
Confirmed real architectural limit, not a config bug. A 308K-char / ~90K-token
real policy (Aditya Birla Activ One, UIN ADIHLIP24097V012324):
- Succeeds via direct diagnostic script at `max_tokens=64000` (~2m40s, 47K
  chars valid JSON ending in `}`).
- FAILS through the live service: the larger max_tokens lets Sonnet 5's
  adaptive thinking run long enough that the request exceeds the 300s timeout;
  the Anthropic client's default retries (~2x) stack to ~11 min before
  `APITimeoutError`.
- Every single-shot knob (memory / max_tokens / timeout) just moves the failure
  - this is the signal to build chunking.

**Decision:** build the chunking / map-reduce extraction increment next session,
as the correct architecture for large documents (NOT an optimization). Deferred
rather than built tired - correctness here is brand-critical (a missed trap is
the worst failure mode).

**Chunking increment starting facts:**
- Failure mode is timeout-from-LENGTH, not context-limit - 1M context window is
  ample (input is only ~90K tokens). The problem is generation time, not fitting
  the input.
- Design questions to solve deliberately: split without severing a raw_clause
  across a boundary; merge red_flags without dup/loss; keep base-vs-optional +
  waiting-period + sub_limit_table coherence across chunks; reconcile
  confidence.
- **Also evaluate first, may defer chunking further:** explicitly tuning DOWN
  Sonnet 5's adaptive thinking for extraction (`thinking:{type:"disabled"}` or
  a capped effort level). The long request time is largely thinking; capping it
  may get single-shot working for larger docs and push the chunking threshold
  higher.

### Follow-up config housekeeping (small, next session)
- Formalize `ANTHROPIC_MAX_TOKENS` default in code + `.env.example` (currently
  only set in production `.env`).
- Record smoke-test API costs in PROGRESS from console.anthropic.com.
- Consider installing sqlite3 CLI on VM for DB inspection (app itself doesn't
  need it).

## Full-tier analysis design - 2026-07-15

Status: implementation complete on `feature/design-full-tier`; awaiting
architect review. This branch changes only the signed-up
`GET /a/{token}/full` presentation. The anonymous preview contract and its
renderer remain unchanged.

Implemented:
- Rebuilt the full analysis as a certified-record reading experience using the
  supplied desktop light, desktop dark, and 430px mobile artifacts. Light is
  the default; the secondary dark theme is selected explicitly and persisted
  in a cookie. No operating-system theme detection is used.
- Added policy identity, deterministic Policy Health Score, verdict summary,
  complete red-flag cards, waiting-period timeline, coverage prose, exact
  stored extraction JSON, honest-gap disclosure, and saved-analysis action in
  the required section order.
- Added the 15 supplied glossary display terms and definitions verbatim, with
  keyboard-focusable and tap-capable CSS-only definitions. Extracted content
  remains escaped, and source clauses are rendered without truncation or
  whitespace normalization.

Validation:
- `python -m pytest backend/tests/test_full_tier_design.py -q` passes with 14
  test cases, including zero and 15+ flags, nulls, long clauses/names, score
  arithmetic, exact glossary copy, palette discipline, section order, and
  cookie persistence.
- `python -m pytest backend/tests -q` passes.
- `python -m compileall -q backend/src` and `git diff --check` pass.
- Browser verification passed at 1280px in light and dark themes and at 430px
  in the default light theme: no console warnings/errors, no horizontal
  overflow, no dropped/reordered sections, and the dark selection survives a
  reload.

Required follow-up (not built on this render-only branch):
- Persist a `policy_start_date` field wherever upload/signup captures policy
  metadata, including the store/model migration and route plumbing. Until that
  exists, the renderer explicitly states that calendar waiting-period end dates
  cannot be calculated; it does not invent dates. Once persisted, pass that
  value to the existing renderer input to enable server-side calendar-aware
  end-date calculation.
