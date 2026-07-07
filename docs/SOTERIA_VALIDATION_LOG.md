# Soteria — Extraction Engine Validation Log & Gold-Set Registry
Status: CANONICAL. Consolidates SCORING_001–004 into one tracker. Update this
after every new policy instead of leaving findings scattered across reports.
Current engine: prompts/v1.2/extract_policy_v1.2.md. Current kit:
SOTERIA_PORTABLE_ANALYSIS_KIT_v1.2.md.

═══════════════════════════════════════════════════════════════
## GOLD-SET REGISTRY (6 of 20 target)
═══════════════════════════════════════════════════════════════

| # | Insurer | Product | UIN | Profile | Gold type | Engine ver | Result |
|---|---|---|---|---|---|---|---|
| 1 | Star | Super Star | SHAHLIP27049V022627 | clean-premium | HUMAN-adjudicated | v1.0→v1.1 | converged run 2 |
| 2 | Star | Family Health Optima | SHAHLIP26046V092526 | classic-trap retail | machine | v1.1 | pass, trap-detection ✓ |
| 3 | Star | Senior Red Carpet | SHAHLIP26041V082526 | senior high-copay | machine | v1.1 | pass, novel-cap caught ✓ |
| 4 | Care | Supreme Enhance | CHIHLIP25036V012425 | super-top-up | machine | v1.1 | pass, RF-013 ✓, F16 wobble |
| 5 | Niva Bupa | ReAssure 2.0 | NBHHLIP27054V032627 | feature-heavy indemnity | machine | v1.2 | pass, P8 confirmed fixed ✓ |
| 6 | HDFC Ergo | Critical Illness | (not in doc) | critical-illness fixed-benefit | machine | v1.2 | pass, graceful degradation ✓✓ |

**Diversity coverage:** clean / classic / senior / super-top-up / feature-heavy
indemnity / critical-illness ✓. Insurers: Star ×3, Care, Niva Bupa, HDFC Ergo
(4 insurers). Product classes: indemnity + fixed-benefit. **Gaps remaining:**
human-adjudicated golds (1 of target 3+ — the last real Plan-A gap).

═══════════════════════════════════════════════════════════════
## CORE DISCRIMINATOR SCORECARD (the headline evidence)
═══════════════════════════════════════════════════════════════
Every core pattern proven BIDIRECTIONAL — fires when present, silent when absent.

| Pattern | proven ABSENT on | proven FIRED on |
|---|---|---|
| RF-001 room cap + prop. deduction | Super Star (dormant/optional) | Optima, Red Carpet, Care, Niva Bupa |
| RF-006 co-pay | Super Star, Care, Niva Bupa, HDFC-CI | Optima (age 61+), Red Carpet (all, 30%) |
| RF-010 renewal age cap | Star×3, Care, Niva Bupa | HDFC-CI (age 66/67) ✓ |
| RF-013 aggregate deductible | Star ×3, HDFC-CI | Care, Niva Bupa |
| RF-014 ICU cap | Super Star, Care, Niva Bupa, HDFC-CI | Red Carpet |
| RF-015 forfeiture / one-shot | (indemnity bases) | Super Star (Limitless), HDFC-CI (terminate-on-claim) |
| RF-018 premium-mechanics | (others) | Super Star (Freeze Age), Niva Bupa (Lock-the-Clock, mistagged novel — F17) |
| RF-019 dormant-optional activation | base-active policies | Super Star, Care |
| RF-020 billing-category caps | (others) | Red Carpet (caught as novel → now named) |

**False-flag rate: 0 across all 6 policies / 4 insurers / 2 product classes.**
**Hallucination: 0 (Care F16 wobble fixed in v1.2 P8, confirmed on Niva Bupa).**
**Graceful degradation on non-indemnity product: proven (HDFC-CI).**

═══════════════════════════════════════════════════════════════
## FAILURE LEDGER (what each run taught, and where it was fixed)
═══════════════════════════════════════════════════════════════

Resolved in v1.1 (from run 1): F1 base/optional inconsistency→P1; F2 forfeiture
taxonomy→RF-015; F3 verbatim→P3; F4 references→P4; F5/F6 inference/moratorium→P5.

Resolved in v1.2 (from runs 3–4): F8/F9 matrix-table under-extraction→P6
(sub_limit_tables[]); F14 ICU-detected-not-flagged→P7; F16 SI-options
hallucination→P8; novel billing caps→RF-020; F10 NCB enum→P10; F12 confidence
scale→P9; F13/R2 null-handling→P10; R1 markdown-link→P3a; RF-015 consistency.

Open (deferred, need 2nd occurrence before fixing):
- Plan A/B parallel-deductible structure (Care only so far) — watch for repeat
  before adding deductible_plans[].
- Amount-capped post-hospitalization (Red Carpet) — partial slot added in kit
  v1.2 (post_hospitalization.amount_capped); confirm it's used correctly next
  senior/older plan.

New from runs 5–6 (batch into eventual v1.3; none blocking):
- F17 (LOW): "Lock the Clock"-style age-unlock tagged novel, should be RF-018.
  Strengthen RF-018 recognition of "age locked at entry, unlocks on claim".
- F18 (LOW): string literal "null" emitted instead of JSON null in several
  type/applies_to fields (both run-5 policies). Add "use JSON null, never the
  string 'null'".
- F19 (LOW): curly/smart quotes and unescaped `"` leaking into raw_clause →
  can break strict JSON.parse(). Normalize/escape quotes in raw_clause.
- F20 (MEDIUM, CI product-class): no survival_period field — the defining CI
  mechanic. Only fixable if CI becomes in-scope (schema v1.3).
- F21 (MEDIUM, CI product-class): no benefit_structure block (payout_type,
  trigger, covered_conditions[], terminates_on_claim). CI describes traps but
  not what the product DOES. In-scope decision required.
- F22 (LOW, CI): "not_applicable" needed as a distinct value from false/no_cap
  for non-indemnity products.

═══════════════════════════════════════════════════════════════
## PROCESS LEARNINGS (amend the reference protocol with these)
═══════════════════════════════════════════════════════════════

1. **Two gold types now exist.** HUMAN-adjudicated (Super Star) and MACHINE
   (via portable kit). Machine gold is adequate for trap-detection validation
   and rapid iteration, but shares blind spots with the extractor — an error
   both make is invisible. RULE: the statistical ≥90%/≥75% claim requires at
   least 3 HUMAN-adjudicated golds; machine golds count toward coverage
   diversity but not toward the accuracy claim.

2. **The portable-kit workflow** (offload PDF to a fresh chat, return gold +
   JSON as text) is now the standard intake path — bypasses the upload limit
   and enforces the annotation-before-extraction firewall by construction.

3. **Gold values must be source-tagged** (wording / schedule / brochure / CIS).
   Run 1 error: gold used brochure-sourced delivery limits against a
   wording-only extraction. Machine gold from the kit is wording-only by
   default; do not penalize the extractor for schedule/brochure facts absent
   from its input.

4. **Convergence is fast.** Super Star converged in 2 runs. Subsequent policies
   passed on v1.1 first-try (no re-run needed) because the fixes generalized.
   Expect most policies to pass first-try now; re-runs only when a NEW failure
   class appears.

5. **Pick policies for structural difference, not volume.** Each of the 4 was
   chosen to test a specific profile the prior ones lacked. Continue this:
   next-most-informative = critical-illness (new product logic) + 3rd insurer
   (structural overfit check).

═══════════════════════════════════════════════════════════════
## NEXT POLICIES TO RUN (priority order)
═══════════════════════════════════════════════════════════════
1. Critical-illness / fixed-benefit plan (e.g. any CI plan) — completely
   different logic: defined payout on diagnosis, not indemnity. Tests whether
   the schema (built for indemnity) even fits, and likely surfaces schema gaps.
2. A 3rd insurer's flagship indemnity plan (Niva Bupa ReAssure / HDFC Ergo
   Optima Secure / Aditya Birla) — cross-insurer structural check.
3. A human-adjudicated re-gold of ONE machine-gold policy (Optima or Care) —
   converts a coverage entry into an accuracy-claim entry.

Each run: portable kit v1.2 → paste gold+JSON back → score → append a row to
the registry above and a line to the failure ledger. Only revise the prompt
(v1.3) when a new failure class recurs; batch low fixes.
