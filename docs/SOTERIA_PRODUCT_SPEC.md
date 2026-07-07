# Soteria — Product Specification (Horizon 1)

## One-line definition
Soteria reads an Indian health insurance policy document and tells the
user, in plain language, the specific ways this policy is likely to bite
them at claim time.

## Scope of Horizon 1 (this document)
- Web application only. No mobile app in this phase.
- Health insurance only. No life, motor, or term.
- Analysis only. No recommendations, no tracking, no comparisons
  between insurers by name.
- India only. No international policies.
- English-language policies only in v1; Hindi/regional support deferred.

## Explicit non-goals for Horizon 1
- Selling or recommending insurance products (regulatory exposure under IRDAI).
- Telling users their claim "will be" rejected (legal exposure; replace with
  "clauses of this type historically lead to X type of dispute").
- Naming insurers in critical comparisons. Factual extraction from a
  named insurer's policy is fine; "Insurer X is worse than Insurer Y"
  is not, in Horizon 1.
- Storing policies for users who haven't created accounts.
- Multi-policy household analysis.

## Primary user
A salaried Indian, age 25–50, who either (a) recently bought a health
policy through an agent and has unread paperwork, (b) is renewing and
reconsidering, or (c) had a relative's claim rejected and wants to
check their own policy. Lives in a Tier 1 or Tier 2 city. Reads
English comfortably. Has a smartphone but is on a desktop/laptop for
this kind of task.

## Core user flow
1. User lands on soteria.app (or chosen domain).
2. Signs up via magic-link email. No password.
3. Uploads health policy PDF (max 25MB, max 100 pages).
4. Receives "analysis in progress" — typical 30–90 seconds.
5. Sees structured analysis: Summary card, Coverage details,
   Waiting periods, Sub-limits, Exclusions, Red flags.
6. Can expand any field to see the source clause text from the policy.
7. Can mark any field as "this is wrong" (correction loop).
8. Can ask follow-up questions over the policy (Q&A; deferred to
   week 6 if time-constrained).
9. Analyses persist in their account; can be re-opened later.

## Success criteria for end of Horizon 1 (week 8)
Hard metrics:
- 50 distinct users have completed at least one analysis with their own
  real policy.
- Of those, ≥40% return for a second session within 14 days.
- Extraction accuracy on the 20-policy gold set: ≥90% on factual fields,
  ≥75% on red flag identification (red flag present in our gold
  annotation is also flagged by the system).
- Median analysis turnaround time: <90 seconds wall-clock.
- Zero data incidents (no leaked documents, no unauthorized access).

Qualitative signal:
- At least 10 users provide unprompted positive feedback (email, Twitter,
  Reddit, WhatsApp screenshots forwarded).
- At least 5 users share their analysis with someone else (tracked via
  share button or referral signups).
- At least 3 users report a red flag the system caught that they did
  not previously know about.

If hard metrics are not met by week 8: do not start Horizon 2.
Diagnose, iterate on Horizon 1 for another 4 weeks.

## Trust and privacy commitments (user-facing)
- Documents encrypted at rest (AES-256, R2 server-side encryption).
- Documents never used to train any model without explicit opt-in
  consent given separately from terms-of-service acceptance.
- User can delete their account and all associated documents/analyses
  permanently within 24 hours of request.
- No sharing with insurers, brokers, or any third party.
- Analyses are not legal or financial advice; this is stated clearly
  on every analysis page, not buried in T&Cs.

## Out-of-scope risks acknowledged but not solved in Horizon 1
- Adversarial documents (deliberately confusing wordings) may produce
  lower-quality analysis. Mitigation: per-field confidence scores,
  user-facing uncertainty language.
- OCR failure on poor-quality scans. Mitigation: detect and prompt
  for re-upload.
- Insurer pushback. Mitigation: factual extraction language only,
  cite ombudsman precedents for risk patterns rather than
  editorializing.

## Pricing in Horizon 1
Free, unlimited analyses per user, with rate limit of 5 per day
to prevent abuse. Monetization deferred to Horizon 2.

## What is explicitly deferred
- Mobile app (Horizon 2)
- Q&A over policy via RAG (week 6 of Horizon 1 if time, else Horizon 2)
- Recommendation engine (Horizon 3+)
- Tracking of registered policies (Horizon 3+)
- Own model training (Horizon 3, conditional on traction)
- Hindi / regional language support (Horizon 2+)
- Comparisons across insurers (Horizon 2+)

