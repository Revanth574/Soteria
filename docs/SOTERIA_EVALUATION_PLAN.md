# Soteria — Evaluation Plan (Horizon 1)

## Why this exists

The product is the prompt. The prompt's quality must be measurable,
not vibes-based. Without an evaluation set, every prompt change is a
guess and every regression is invisible until a user is hurt by it.

## The gold set

20 real Indian health insurance policies, manually annotated by
Revanth, covering:

- 5 individual indemnity policies
- 5 family floater policies
- 3 senior citizen policies
- 3 critical illness or top-up policies
- 4 "complex / known-difficult" policies (high-page-count, multiple
  variants, or known to contain unusual clauses)

Source mix:
- Star Health: 4
- HDFC Ergo: 3
- ICICI Lombard: 3
- Niva Bupa: 3
- Care: 3
- Aditya Birla: 2
- Manipal Cigna: 2

Annotations live in `corpus/gold/` as `{policy_slug}.json` files,
matching the annotation schema exactly. Source PDFs are NOT
committed (copyright, size); they live in a private R2 bucket
referenced by the gold annotation.

## Metrics

For each gold policy, run the extraction prompt and compare output
to the gold annotation.

**Factual fields (exact match required):**
- sum_insured
- room_rent_cap.value
- room_rent_cap.type
- co_pay.percentage
- pre_hospitalization_days, post_hospitalization_days
- waiting_periods (matched as a set; precision and recall computed)

**Structured fields (semantic match):**
- sub_limits (precision/recall on the set, with fuzzy match on
  applies_to)
- exclusions (precision/recall on the set)

**Red flags (precision/recall):**
- For each red flag in the gold annotation: did the system catch it?
- For each red flag the system raised: is it in the gold annotation
  or is it a justifiable additional flag?
- False positives are evaluated by Revanth case-by-case;
  some are acceptable (extra caution), some are noise.

**Plain-language quality (qualitative):**
- For each gold policy, Revanth reads the generated `summary` and
  red flag explanations and rates each on a 1–5 scale for
  accuracy and clarity. Average must be ≥4.0.

## Targets at end of Horizon 1

- Factual fields: ≥90% exact match
- Structured fields: ≥85% F1
- Red flag recall: ≥75% (must catch the gold flags)
- Red flag precision: ≥80% (low noise)
- Plain-language quality: ≥4.0/5.0 average

If a target is not met, do not ship that prompt version to
production.

## Regression policy

Every prompt change is evaluated against the full gold set before
deployment. If any metric regresses by more than 5%, the change is
not deployed without explicit decision to accept the regression
(and a note in the prompt version's changelog).

## Cadence

- Pre-deployment: full eval run (manual; takes ~30 minutes)
- Weekly during Horizon 1: review of recent corrections to identify
  prompt failure patterns
- End of Horizon 1: comprehensive review; gold set may grow to
  30 policies if patterns suggest blind spots.

## Tooling

A simple `scripts/evaluate.py` that:
1. Loads every gold annotation
2. For each, fetches the corresponding policy text
3. Runs the current prompt
4. Computes metrics
5. Prints a report and writes per-policy diffs

This script is the single source of truth for prompt quality.

