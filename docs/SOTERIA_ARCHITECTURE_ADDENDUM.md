# Soteria — Architecture & Spec Addendum v1 (SOTERIA_ARCHITECTURE_ADDENDUM.md)

Status: Approved-pending-Revanth-review — amends SOTERIA_ARCHITECTURE.md
and SOTERIA_PRODUCT_SPEC.md. Original documents remain authoritative
except where explicitly amended here.

---

## 1. Ingestion abstraction (amendment to Architecture — pipeline entry)

**Motivation.** India is building consumer insurance data rails right
now: NHCX (FHIR-based claims exchange between hospitals, insurers,
TPAs, already covering most of the retail health market), mandatory
e-policy issuance into e-Insurance Accounts, and IRDAI's proposed
Public Insurance Registry / Bima Sugam covering the policy lifecycle
including claims and grievances. Within Soteria's Horizon 3 window it
is plausible that users can consent-share structured policy and claim
data instead of uploading PDFs. Soteria must be the consumer
intelligence layer on those rails, and must not have PDF-parsing
assumptions baked into its core.

**Amendment.** The pipeline entry point becomes an ingestion interface,
not a PDF handler:

    PolicyIngestionSource (interface)
      -> ingest() -> CanonicalPolicyDocument

    Implementations:
      v1 (Horizon 1):  PdfUploadSource        — user PDF upload + OCR
      v2 (Horizon 2):  CameraCaptureSource    — mobile photo capture
      future:          StructuredPolicySource — eIA / PIR / Bima Sugam
                                                consent-shared payloads
      future:          NhcxClaimSource        — claim/settlement data
                                                (feeds dispute engine)

    CanonicalPolicyDocument:
      - full_text            (normalized text, present for all sources)
      - pages[]              (page-mapped text; null for structured sources)
      - structured_fields    (null for v1; pre-populated for structured
                              sources, still passed through extraction
                              for verification + red-flag analysis)
      - source_type, source_metadata, ingested_at, checksum

**Rules.** Everything downstream (extraction, red flags, dashboard,
estimator, dispute engine) consumes CanonicalPolicyDocument only. No
module below ingestion may reference "PDF," page images, or OCR
artifacts except through the canonical interface. raw_clause fields
continue to quote from full_text verbatim regardless of source.

**Cost today:** one interface + one implementation — near zero. Cost of
not doing it: rewriting the pipeline spine in 18 months while
competitors integrate the new rails first.

## 2. Extraction verification mode (new, enabled by §1)

When structured_fields arrive pre-populated (future sources), the
extraction engine runs in VERIFY mode: compare extracted values against
provided structured values, flag mismatches for review instead of
trusting either side. This doubles as a free accuracy telemetry channel
once structured data exists. Design the extraction output schema now to
carry an optional `verification` block per field (extracted_value,
provided_value, match: bool). No implementation in Horizon 1; schema
slot only.

## 3. Signup-free first analysis (amendment to Product Spec — core user flow)

**Old flow:** land → magic-link signup → upload → analyze → results.
**New flow:**

1. Land → upload immediately (no account)
2. Analyze (same pipeline; document held in an ephemeral session store,
   never written to the persistent policy store)
3. Show: summary card + top 3 red flags IN FULL (real value, not a
   teaser blur — a blurred teaser reads as a dark pattern and this
   brand cannot afford one)
4. Gate behind magic link: full field-by-field analysis, source-clause
   expansion, correction loop, Q&A, persistence
5. On signup: session analysis attaches to the new account
6. No signup: document + analysis hard-deleted at session end (TTL
   ≤ 24h). State this in the UI before upload: "Don't sign up and
   this document is gone in 24 hours. We can't read what we don't
   keep." The deletion IS the trust pitch.

**Engineering deltas:** ephemeral store with TTL enforcement + deletion
audit log; rate limiting / abuse control on anonymous uploads (per-IP
caps, file-type and size validation runs regardless of auth state);
analysis session → account attachment on magic-link completion; the
"zero data incidents" success criterion now explicitly covers the
ephemeral store.

**Metric change:** Horizon 1 success criteria gain one instrumented
funnel metric: anonymous-analysis → signup conversion (target: learn,
not hit — no number until baseline exists).

## 4. Vernacular output pulled forward (amendment to Product Spec — scope)

Old: Hindi/regional "deferred" indefinitely. New: **vernacular OUTPUT**
(plain-language fields rendered in Hindi first, then 2–3 regional
languages) is scheduled Horizon 2, month 4–5. Source clauses remain
verbatim English (they quote the document; translating them would
violate the verbatim rule). Vernacular INPUT (non-English policy
documents) remains deferred to Horizon 3 — it's an extraction-accuracy
problem, not a rendering problem, and needs its own gold set.

Implementation note: plain-language fields are generated, so this is
a prompt-level change (output-language parameter) plus a per-language
QA pass with native-speaker review — not a translation-layer bolt-on.
Budget the native-speaker review; machine-only vernacular in a
financial product is how trust dies in one screenshot.

## 5. Group-policy analysis noted as schema concern (forward flag)

Employer group policies (VISION_V2 §3, gap 3) differ structurally:
master policy + certificate of insurance, corporate buffer, floater
mechanics, job-loss continuity. Horizon 1 schema change: policy record
gains a `policy_kind` field (retail_individual | retail_floater |
group_certificate) captured at upload. No analysis behavior change in
Horizon 1 — the field exists so the data is not unlabeled when the
group-policy analyzer arrives in Horizon 2/3.

## 6. Codex task list deltas

Amend Horizon 1 tasks:
- Task (upload endpoint): add anonymous-session path, ephemeral store,
  TTL deletion job + deletion audit log, per-IP rate limiting
- Task (analysis persistence): add session→account attachment
- Schema: add policy_kind field; add optional verification block to
  extraction output schema

New Horizon 2 tasks (append to existing 17–35):
36. Ingestion interface refactor (PolicyIngestionSource +
    CanonicalPolicyDocument) — do FIRST in Horizon 2, before camera
    capture (task 31), which becomes its second implementation
37. Vernacular output rendering (prompt parameter + language QA harness)
38. Public red-flag page generator (static render of analyses of
    public policy wordings; DISTRIBUTION.md §2)
39. Share-card generation (privacy-safe result summary image)

Dispute engine tasks D1–D8 live in SOTERIA_DISPUTE_ENGINE.md §5 and
are NOT scheduled yet; they enter the task list only when Horizon 2.5
is greenlit by Horizon 1 results.

## 7. What is explicitly NOT amended

- Horizon 1 timeline, success criteria (except the added funnel
  metric), scope boundaries, and non-goals all stand.
- The anti-hallucination, verbatim source-clause, and confidence
  scoring constraints in prompts/v1/system.md are untouched and
  inherited by all future prompt files.
- The regulatory posture (analysis not advice, no recommendations,
  no insurer rankings) stands until formal legal review, regardless
  of any ambition in VISION_V2.
