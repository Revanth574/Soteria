# Soteria Build Progress

## 2026-07-07 - H1-1 Ingestion Spine + Canonical Document

Status: built and locally tested.

Branch: `feature/h1-1-ingestion-spine`

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

Next unbuilt increment:
- H1-2 Extraction adapter + result type.
