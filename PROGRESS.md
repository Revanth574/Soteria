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
