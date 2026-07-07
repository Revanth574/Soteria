# SOTERIA — Horizon 1 Codex Build Handoff (SOTERIA_CODEX_HANDOFF_H1.md)

Status: MASTER handoff. This is the document that moves Soteria from a
validated prompt to a running application. Codex is the autonomous BUILDER;
Claude (chat) is the ARCHITECT who scopes increments and ratifies verdicts.
This is the INVERSE of the Delphi role split — do not carry Delphi's
"Codex reviews Claude Code's work" model here. On Soteria, Codex writes the
application code; Claude reviews the increment and scopes the next one.

Working-style commitments carried over from Delphi (these transfer; the role
split does not): Iron Laws discipline, RED-proof invariants (write the failing
test first, prove it bites, then fix), honest severity labeling, PROGRESS.md
as the living record with no aspirational claims, and HARD STOP POINTS that
end a session whether clean or interrupted.

═══════════════════════════════════════════════════════════════
## 0. WHAT IS BEING BUILT (and what is NOT)
═══════════════════════════════════════════════════════════════

Horizon 1 = the analyzer, end to end, for 50 real users. A person uploads a
health-insurance policy PDF and receives a plain-language analysis with red
flags, each backed by the verbatim clause. Nothing more.

IN SCOPE (H1):
- PDF ingestion → text extraction → extraction-engine call → structured JSON
- Rendering that JSON as (a) an in-app analysis and (b) the public red-flag
  page (template already designed — see §4)
- Signup-free first analysis with ephemeral storage + 24h deletion
- The 20-policy gold set as an automated regression suite

EXPLICITLY OUT OF SCOPE (do not build, do not scaffold for):
- The dispute engine (Horizon 2.5+ — SOTERIA_DISPUTE_ENGINE.md)
- The claim estimator, benefits dashboard, tracker (Horizon 2)
- Pre-purchase comparison, vernacular, employer B2B2C
- Any CI/critical-illness product support (the engine degrades gracefully on
  these but H1 is scoped to INDEMNITY health policies — see validation log)
- Optional-cover deep modeling beyond what the current schema captures

If an increment tempts you to build toward an out-of-scope feature "while
we're here," STOP and surface it — that is scope creep (Iron Law: build the
scoped increment, not the imagined future).

═══════════════════════════════════════════════════════════════
## 1. THE ARTIFACTS CODEX RECEIVES (and their status)
═══════════════════════════════════════════════════════════════

**DEPLOYMENT ASSETS — ship as-is, do NOT author or edit prompt content:**
- `extract_policy_v1.2.md` — the extraction engine. This is a VERSIONED
  DEPLOYMENT ASSET, not editable code. Codex builds the loader, the
  version-pinning, and the call harness around it. Codex must NEVER modify the
  prompt's instructions, schema, or taxonomy — those are architect-owned. If a
  policy exposes a prompt bug, Codex FILES it (PROGRESS.md + surfaces to
  architect), it does not patch the prompt.
- `taxonomy_RF015-019.md` — referenced by the prompt; same rule.

**REGRESSION FIXTURES — wire into the test suite, treat as ground truth:**
- `GOLD_001_STARHEALTH_SUPERSTAR.md` — gold-set entry #1, the ONLY
  human-adjudicated gold. This becomes automated fixture #1: the pipeline run
  on Super Star's wording must reproduce this analysis within tolerance, or CI
  fails. (See §5 for the fixture protocol.)
- The five machine-gold analyses (Optima, Red Carpet, Care, Niva Bupa,
  HDFC-CI) from the scoring reports — wire as fixtures #2–6 at LOWER assertion
  strictness (machine gold shares blind spots; assert structure + red-flag
  pattern_ids, not every field).

**BUILD SPECS — implement these:**
- `SOTERIA_ARCHITECTURE_ADDENDUM.md` — MANDATORY. Amends H1 tasks:
  ingestion abstraction (§1), signup-free flow + ephemeral store (§3),
  policy_kind field (§5), Codex task deltas (§6). Build to the addendum, not
  to any older architecture doc, wherever they conflict.
- This handoff (§3 increments, §4 rendering, §5 fixtures).

**CONTEXT — read once, do not build from directly:**
- `SOTERIA_VALIDATION_LOG.md` — the engine's proven behavior + known open
  bugs (F17–F22). Read so you know what the engine does and does not do.
- `SOTERIA_VISION_V2.md`, `SOTERIA_DISTRIBUTION.md` — strategy; H1 consequences
  only (signup-free flow, red-flag pages). Do not build ahead of them.

Everything else in the repo is architect-lane and NOT part of the H1 build.

═══════════════════════════════════════════════════════════════
## 2. ARCHITECTURE SPINE (build order enforced)
═══════════════════════════════════════════════════════════════

Per the addendum's ingestion abstraction, the pipeline is:

    PolicyIngestionSource → CanonicalPolicyDocument → ExtractionEngine
      → ExtractionResult(JSON, schema_version) → { InAppRenderer, PageRenderer }
      → EphemeralStore | (on signup) PersistentStore

Hard rules:
- Everything downstream of ingestion consumes CanonicalPolicyDocument ONLY.
  No module below ingestion references "PDF", OCR, or page images except
  through the canonical interface. (Addendum §1 — this is what lets NHCX/eIA
  sources slot in later without a spine rewrite.)
- The ExtractionEngine call is a thin, swappable adapter: {prompt asset +
  policy text} → model → JSON. The prompt is injected, never inlined. Model
  string is config, not hardcoded.
- ExtractionResult carries schema_version. Renderers assert the version they
  support and fail loudly on mismatch (no silent partial renders).

═══════════════════════════════════════════════════════════════
## 3. THE INCREMENTS (one Codex session each; hard stop between)
═══════════════════════════════════════════════════════════════

Each increment: build → self-audit → Codex-internal tests green → STOP →
paste output back to architect → architect reviews + scopes next. Do NOT
chain increments in one session. Each ends with a PROGRESS.md update carrying
honest status (mark unbuilt things unbuilt).

**H1-1 — Ingestion spine + canonical document.**
PolicyIngestionSource interface + PdfUploadSource impl (upload + text
extract; the extraction approach that produced super_star_fulltext.txt is the
reference — faithful text, tolerate two-column reflow). Output
CanonicalPolicyDocument (full_text, pages[], source_type, checksum,
policy_kind slot). RED-proof: a scanned/garbled fixture must either extract or
fail with a clear ingestion error — never silently produce empty text that
looks like a valid document.

**H1-2 — Extraction adapter + result type.**
Load extract_policy_v1.2.md, inject {{POLICY_TEXT}}, call the model, parse
JSON, validate against schema_version 1.2. RED-proofs (these encode real
observed failures — F18/F19): (a) a response containing the string literal
"null" where JSON null is expected must be caught, not silently stored;
(b) a raw_clause containing an unescaped quote / smart-quote that breaks
JSON.parse must be handled (repair or reject with a clear error), never crash
the pipeline. Retry-once-then-surface on malformed model output.

**H1-3 — Ephemeral store + signup-free flow.** (Addendum §3)
Anonymous upload path; ephemeral store with TTL ≤24h + a deletion job + a
deletion AUDIT LOG; per-IP rate limiting + file-type/size validation that runs
REGARDLESS of auth state. First analysis shows summary + top-3 red flags in
full (NOT a blurred teaser — that reads as a dark pattern this brand can't
afford). Full analysis + persistence gated behind magic-link signup;
session→account attachment on signup. RED-proof: a document with no signup
must be UNRECOVERABLE after TTL — prove deletion actually deletes (assert the
row and any derived blobs are gone, not just flagged).

**H1-4 — In-app renderer.**
Render ExtractionResult as the in-app analysis. Field-by-field + red flags
with verbatim clauses. Handle the graceful-degradation case (a CI/non-indemnity
result where most fields are null) without rendering a broken/empty shell.

**H1-5 — Public red-flag page generator.** (Distribution §2, addendum task 38)
Turn an ExtractionResult into the page whose template is already built:
`redflag_page_star_super_star.html`. The generator maps JSON → that template.
Requirements baked into the template and non-negotiable: verbatim clause per
flag, the "what this gets right" balance section, the exact disclaimers
(analysis of public wording / not affiliated / not advice), signup-free CTA.
RED-proof: a page must never render a red flag WITHOUT its verbatim clause
(the clause-as-evidence is the brand's integrity guarantee).

**H1-6 — Gold regression suite + CI.** (See §5.)
Wire all 6 gold analyses as fixtures; CI runs the pipeline on each wording and
asserts against gold at the tiered strictness in §5. CI fails on regression.

Increment ORDER is fixed: H1-1 → H1-2 are the spine and must precede
everything; H1-3/4/5 can be reordered by the architect after the spine lands;
H1-6 comes last so it has all renderers to test.

═══════════════════════════════════════════════════════════════
## 4. RENDERING — the page template is a spec, not a suggestion
═══════════════════════════════════════════════════════════════

`redflag_page_star_super_star.html` is the canonical public-page design.
H1-5 generates instances of it from JSON. The generator must preserve:
- One flag card per red_flag: severity chip, plain title, plain_explanation,
  the "IF →" scenario, and the VERBATIM raw_clause with its clause_reference.
- conditional_on_optional_cover surfaced ("only if you opt for X") when set.
- The balance section from the true base-policy strengths.
- Disclaimers + signup-free CTA verbatim.
Do not redesign the page in H1; if the design needs changes, that is an
architect task, filed not freelanced.

═══════════════════════════════════════════════════════════════
## 5. GOLD FIXTURE PROTOCOL (the accuracy guarantee)
═══════════════════════════════════════════════════════════════

The gold set is the regression backbone. Tiered strictness reflects gold type:

- **Tier A — human-adjudicated (Super Star only, today):** assert factual
  fields match gold within tolerance AND all gold red-flag pattern_ids are
  reproduced AND zero false flags introduced. A Tier-A regression FAILS CI.
- **Tier B — machine gold (other 5):** assert product classification,
  structural shape (base-vs-optional booleans), and red-flag pattern_ids.
  Do NOT assert every field (machine gold can be wrong). A Tier-B mismatch
  WARNS and surfaces to architect; it fails CI only on a structural break
  (e.g. a false flag appears, or a core discriminator flips).

Non-determinism: model output varies run-to-run. The suite asserts on
STRUCTURE and PATTERN presence, not exact prose. Pin model + temperature in
config; record them with each fixture run.

The statistical ≥90% factual / ≥75% recall CLAIM is NOT met by this suite
alone — it needs ≥3 human-adjudicated golds (currently 1). Codex does not
manufacture that claim; the architect converts machine golds to human golds
out-of-band. CI proves NO REGRESSION; it does not prove the accuracy bar.

═══════════════════════════════════════════════════════════════
## 6. THE PROHIBITIONS (Iron Laws, Soteria-specialized)
═══════════════════════════════════════════════════════════════

1. Never edit prompt/taxonomy content. Prompt bugs are FILED, not patched.
2. Never build out-of-scope (§0). Surface the temptation, don't act on it.
3. Never let a red flag render without its verbatim clause.
4. Never store or persist an anonymous document past its TTL; prove deletion.
5. Never silently accept malformed model output (string-"null", broken JSON) —
   catch, repair-or-reject, surface. These are known failure modes (F18/F19).
6. Never self-certify a security-relevant increment (ephemeral store deletion,
   rate limiting, PII handling in policy docs) — those get a focused architect
   review round, flagged loudly in the session output.
7. PROGRESS.md is honest: unbuilt = marked unbuilt, no aspirational green.
8. Hard stop at each increment boundary. One increment per session.
9. RED-proof discipline: for every invariant, write the failing test first,
   prove it bites, then fix. A test that passes against the bug it claims to
   catch is a defect (the Delphi R2-03 lesson).

═══════════════════════════════════════════════════════════════
## 7. FIRST SESSION FOR CODEX
═══════════════════════════════════════════════════════════════

Scope: H1-1 only (ingestion spine + CanonicalPolicyDocument). Do not proceed
to H1-2. Session-start protocol:
1. Read: this handoff, the architecture addendum, the validation log.
2. Confirm the repo state + branch; create the H1 branch structure.
3. Build H1-1 to the §3 spec with its RED-proof.
4. Self-audit against §6 prohibitions.
5. Run the increment's tests green.
6. Update PROGRESS.md (H1-1 status, honest).
7. STOP. Paste full session output back to architect for review + H1-2 scope.

The architect (Claude chat) will review the H1-1 output, ratify or send
revisions, and scope H1-2. Nothing merges to main until the architect
confirms the increment and — for security-relevant increments — a focused
review round passes.

═══════════════════════════════════════════════════════════════
## APPENDIX — open engine bugs Codex should know (not fix)
═══════════════════════════════════════════════════════════════
From the validation log, deferred to a future v1.3 prompt revision (architect-
owned). Codex handles their DOWNSTREAM effects in the pipeline, does not fix
the prompt:
- F17: "age unlock on claim" sometimes tagged novel vs RF-018 — renderer must
  handle pattern_id="novel" gracefully.
- F18: string "null" vs JSON null — H1-2 RED-proof covers this.
- F19: smart-quote / unescaped quote in raw_clause — H1-2 RED-proof covers.
- F20/F21/F22: CI-product schema gaps — out of H1 scope (indemnity only).