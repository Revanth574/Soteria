# GOLD ANNOTATION #001 — Star Health "Super Star"
Protocol: SOTERIA_REFERENCE_ANALYSIS_PROTOCOL.md — Steps 0–1 + Step 5 (partial)
Status: GOLD PASS COMPLETE (annotated BEFORE any extraction run; extraction
prompt deliberately not applied in this pass)
Annotator: Claude (architect lane) — severity calls pending Revanth adjudication

---

## STEP 0 — INTAKE RECORD

| Field | Value |
|---|---|
| Insurer | Star Health and Allied Insurance Company Limited (IRDAI Regn. 129) |
| Product | Super Star |
| UIN | SHAHLIP27049V022627 |
| Document 1 | Policy Wordings, POL / SS / V.5 / 2026, 66 pages, native text (clean) |
| Document 2 | Brochure, BRO / SS / V.3 / 2026, native text (clean) |
| Schedule | NOT PROVIDED — personal-variable checks out of scope this run |
| CIS | NOT PROVIDED — insurer-summary cross-check out of scope this run |
| policy_kind | retail (product sold as Individual / Floater / Multi-Individual) |
| OCR issues | None material. Minor source typos preserved verbatim where quoted ("peerson", "Bronchical Thermoplasty", "otherwards") — these are verbatim-rule test material |

**Important context for scoring:** this is a PREMIUM product with unusually
clean base terms (no room-rent cap, no disease-wise sub-limits in base cover,
90/180 pre/post-hosp, all-day-care). The traps here live almost entirely in
(a) optional covers, (b) benefit mechanics fine print, and (c) waiting-period
lists. A lazy extractor that pattern-matches for classic traps (room caps,
sub-limits) will produce FALSE-FLAGS; an extractor that only looks for classic
traps will produce MISSES on the mechanics traps. This policy is a superb
discriminator.

---

## STEP 1 — GOLD EXTRACTION VALUES (key fields, schema-aligned)

### metadata
- insurer_name: "Star Health and Allied Insurance Company Limited"
- product_name: "Super Star"
- product_uin: "SHAHLIP27049V022627"
- policy_type: sold as individual | family_floater | multi-individual → schema
  value "individual" is WRONG as sole answer; correct gold: both individual and
  floater offered (schema forces one enum — flag as SCHEMA LIMITATION #1)
- policy_term_years: 1–5 offered (schema expects single integer — SCHEMA
  LIMITATION #2; document states options 1|2|3|4|5)
- sum_insured_options (INR): [500000, 750000, 1000000, 1500000, 2000000,
  2500000, 5000000, 10000000, "Unlimited"] (schema expects integers —
  "Unlimited Sum Insured" breaks it — SCHEMA LIMITATION #3)

### coverage (gold values)
- inpatient_hospitalization: covered=true, minimum_hours=24 (per
  Hospitalization definition, with day-care exception)
- room rent: "Room Rent (Any Room), Boarding, Nursing Expenses as provided by
  the Hospital / Nursing Home" → NO CAP in base cover
- restoration_benefit: available=true, restore_to_original_si=true (100%),
  number_of_times=unlimited (schema integer — LIMITATION #4),
  same_illness_covered=true BUT only for a SUBSEQUENT hospitalization; single
  claim under restoration ≤ SI; 45-day relapse = same hospitalization ("Any
  one illness"); not applicable to Unlimited SI; unutilized restored SI does
  not carry forward
- no_claim_bonus (Cumulative Bonus): available=true, type=cumulative_increase,
  percentage_per_year=50, max_percentage=100; calculated on EXPIRING SI;
  reduced only to extent utilized; not applicable to Unlimited SI
- pre_hospitalization.days_covered: 90
- post_hospitalization.days_covered: 180
- day_care: covered=true, specific_list_only=FALSE ("All Day Care Treatments")
- domiciliary_hospitalization: covered=true (>3 days), no monetary sub-limit,
  BUT large excluded-disease list (asthma, bronchitis, diabetes, hypertension,
  epilepsy, psychiatric, arthritis/gout/rheumatism, etc.)
- ayush: covered=true up to SI; Yoga & Naturopathy claims require PRIOR
  APPROVAL from Company
- modern_treatments: covered=true, 12 procedures listed, up to SI (no
  sub-limit incl. pre/post) — robotic surgery, oral chemo, immunotherapy,
  stem cell (haematological BMT), etc.
- organ_donor: covered=true incl. screening + donor post-donation
  complications (redo surgery/ICU ≤180 days from discharge); limit "up to the
  Sum Insured and over and above the Sum Insured"
- ambulance: road covered (3 scenarios, no stated monetary cap); AIR ambulance
  ₹5,00,000/policy year
- network_hospitals: brochure claims 14,000+; preferred_network_exists=true
  ONLY IF Smart Network optional cover opted
- lifetime_renewability: guaranteed=true (renewable unless product withdrawn /
  fraud / non-disclosure); entry age 18 to any age; renewal_age_cap=none

### financial_terms (gold values)
- room_rent_cap.type: no_cap (base). CRITICAL NUANCE: the proportionate-
  deduction MACHINERY exists in Definitions ("Associated medical expenses")
  and ACTIVATES only if Optional Cover 12 (Room Rent Modification) is opted
  and insured occupies above modified eligibility. Also explicitly NOT applied
  where hospital doesn't follow differential billing. Gold:
  linked_to_proportionate_deduction=false for base policy;
  proportionate_deduction.clause_present=true (definition present, conditional
  applicability) — this field pairing is the single most likely extraction
  failure in this document.
- co_pay.applies: false (base; brochure: "Mandatory Co-Pay: Not applicable").
  Conditional co-pays: (1) Smart Network optional → 15% on every claim
  (except accident) if treated OUTSIDE Smart Network list; (2) Voluntary
  Co-payment optional 10/20/30/40/50%. applies_to=specific_conditions.
- deductible.applies: false (base). Voluntary Deductible optional:
  aggregate_annual, 10k/25k/50k/1L/2L/3L/4L/5L; mutually exclusive with
  voluntary co-pay; once opted cannot reduce/opt out.
- non_medical_expenses: excluded_per_irdai_list=true (Excl 37 + Lists I–IV);
  waiver_available=true (Optional Cover III-3, opt-in within first 3 policy
  years only)

### waiting_periods (gold set — every entry)
1. initial | all illness (non-accident) | 30 days | Excl 03
2. pre_existing_disease | PED + direct complications | 36 months | Excl 01 |
   industry_standard=36 | is_longer_than_standard=false
3. specific_disease | 14-category list (cataract/eye/ENT/thyroid/breast-benign;
   benign lumps/CTS/trigger finger etc.; tendon/ligament/bone/joint incl.
   arthroplasty; degenerative disc/vertebral; hepato-pancreato-biliary +
   kidney/GU calculi; ALL hernia; desmoid/umbilical; all cervix/uterus/
   fallopian/ovary/uterine bleeding/PID; prostate/stricture/obstructive
   uropathy; epididymis/spermatocele/varicocele/hydrocele; fistula/fissure/
   hemorrhoids/pilonidal/rectal prolapse/stress incontinence; varicose veins/
   ulcers; ALL transplants; congenital internal) | 24 months | Excl 02 |
   longer-of-two rule vs PED; accident carve-out
4. maternity Option A | delivery + newborn | 24 months | no wait for
   subsequent deliveries; max 4 lifetime
5. maternity Option B | delivery + newborn | 12 months | same notes
6. ART Option C | assisted reproduction | 24 months | both self+spouse
   covered 24m continuous required
7. Quick Shield (optional) REDUCES PED to 31 days for listed conditions
   (diabetes, hypertension, asthma, hyperlipidemia, CAD-with-PTCA>1yr)
8. Optional 17: specified disease 24→12 months (first purchase only, ≤45 yrs)
9. Optional 18: PED 36→24/12 months (first purchase only, ≤65 yrs)
10. Moratorium: 60 continuous months → non-contestability except fraud

### sub_limits (gold set — base + optional covers)
- Air ambulance: ₹5,00,000 / policy year
- High-end diagnostics (optional): ₹25,000 / policy year, OPD, 9 listed tests
- Annual health check (optional): 1% of SI max ₹25,000, cashless, digital
  booking only
- Newborn cover (maternity options): ₹2,00,000 (SI 5–25L) / ₹5,00,000
  (SI 50L+); waived for congenital internal treatment of newborn
- Delivery expenses: Option A ₹50,000 or ₹1,00,000/delivery; Option B
  ₹30,000/delivery
- ART: ₹1L / ₹2L / ₹4L by SI band; 1 cycle/policy year
- Durable medical equipment (optional): ₹5,00,000 LIFETIME, once, then cover
  ceases permanently
- Compassionate visit (optional): ₹10,000/occurrence
- Hospital cash (optional): ₹1,000–5,000/day, 30/60/90/180 days as opted
- Dental check-up (built-in): consultation + IOPA X-ray + scaling only, one
  insured/policy/year, cashless only, 2nd & 3rd policy years only
- is_low_for_procedure_type: maternity Option B ₹30,000 and Option A ₹50,000
  are BELOW realistic C-section costs (₹70k–2L) → feeds RF-G07

### claim_process (gold)
- cashless_available: true (network only)
- planned intimation: ≥48 hours prior
- emergency intimation: within 24 hours
- reimbursement submission: 15 days from discharge (15 days after post-hosp
  period completion for post-hosp claims)
- pre_authorization_required: true (cashless); denial ≠ denial of coverage
- TPA: none named in wording (in-house claims; helplines 044-69006900 /
  1800 425 2255)

---

## STEP 1 (continued) — GOLD RED FLAGS

Severity discipline: financial impact in realistic scenarios, on THIS policy
as sold. Base policy is clean; most flags are conditional or mechanical.

**RF-G01 | HIGH | Limitless Care one-shot forfeiture mechanics** (Optional 19)
Once ANY claim is paid under it: cover ceases permanently, can never be
re-opted, and Total SI drops to ZERO for that policy year. A user who takes a
₹12L claim via Limitless on a ₹10L policy is uninsured for the rest of that
year (restoration language doesn't rescue the Limitless path). Scenario +
what_to_do must cover "check remaining-year exposure before invoking."
Taxonomy fit: NONE clean (closest RF-013 spirit). → gap candidate.

**RF-G02 | HIGH | Smart Network conditional 15% co-pay + dynamic list**
(Optional 1) 15% premium discount, but 15% co-pay on EVERY claim (except
accident) at any hospital outside "Smart Network," AND the list is dynamic —
"Star Health reserves the right to change the list by adding or deleting the
hospitals at its discretion." The hospital you bought around can leave the
list before you claim. Not available Zone C. Fits RF-006 (conditional co-pay)
+ RF-012 (restricted network) but the discretionary-list-change element
exceeds both. → gap candidate (unilateral benefit modification).

**RF-G03 | MEDIUM-HIGH | Proportionate deduction is dormant, not absent**
(Definitions "Associated medical expenses" + Optional 12) Base = any room, no
deduction. But if the user opts Room Rent Modification to cut premium, full
proportionate-deduction machinery activates on associated medical expenses.
Agents sell the discount; the definition holds the trap. Scenario: opted
Shared Room eligibility, took Single AC in an emergency → all professional
fees/OT/procedure charges scaled down. Fits RF-001 ONLY in conditional form —
extraction must not flag base policy as RF-001 (that's a FALSE-FLAG) and must
not return clause_present=false (that's a MISS). This is the discriminator
field of the whole run.

**RF-G04 | HIGH | Freeze Your Age floater unlock + hard stop at 56**
One member's claim in a floater unlocks age-based premium for ALL insured
members; benefit ends at 56 regardless of claims; entry ≤50 only. Brochure
headline ("keep your premiums young until you make a claim") omits the
all-members unlock and the 56 ceiling. Real cost: family premium repricing
after one small claim — worth modeling before claiming small amounts.
Taxonomy fit: none (premium mechanics, not claim mechanics). → gap candidate.

**RF-G05 | MEDIUM | Restoration reality vs "unlimited" marketing**
Restored SI usable only for SUBSEQUENT hospitalization; single-claim payout
never exceeds base SI; 45-day relapse counts as the SAME hospitalization
(blocks the classic "re-admit to reload" assumption); no carry-forward; N/A
for Unlimited SI. Financially: a single ₹18L cardiac event on ₹10L SI pays
₹10L, restoration notwithstanding. Fits taxonomy loosely (restoration
misunderstanding is not an RF pattern). → gap candidate.

**RF-G06 | MEDIUM | 24-month specific-disease list breadth** (Excl 02)
Standard duration, but the LIST is the trap: all hernias, all gynae disease,
cataract, joint replacement, all calculi, varicose veins, prostate — i.e. the
most common planned surgeries for the 30–55 buyer. Plus longer-of-two rule
when condition is also PED. Fits RF-004 (flag list breadth, standard length).

**RF-G07 | MEDIUM | Maternity limits below realistic delivery costs**
(Optional 5) Option B: ₹30,000/delivery vs realistic C-section ₹70k–₹2L;
Option A: ₹50,000 tier similar gap (₹1L tier borderline). Pre/post-hosp
explicitly NOT covered under maternity. Max 4 deliveries lifetime. Fits
RF-002 + RF-008 (short wait traded for very low limit in Option B).

**RF-G08 | MEDIUM | Quick Shield premium clawback** (Optional 2)
Premium for this cover is collected for five years; claim within the five
years → BALANCE premium deducted from the claim amount. Undisclosed-at-sale
effective claim reduction. Also instalment condition v: on any claim, ALL
subsequent premium instalments immediately due and deductible from claim.
Taxonomy fit: none (claim-amount offsets). → gap candidate.

**RF-G09 | MEDIUM | Consumables excluded by default** (Excl 37 + Lists I–IV)
68-item List I payable only if Optional III-3 opted (and only optable in
first 3 policy years). Typical ₹5k–30k OOP per hospitalization otherwise.
Fits RF-011 exactly (waiver exists = optional cover).

**RF-G10 | LOW-MEDIUM | External-website exclusion surfaces**
Excluded providers (Excl 11) and excluded expenses (Excl 37) live at
starhealth.in links, mutable outside the contract document. Also "Medical
protocols and Position statements" published/refreshed on website may govern
part-pay/deny decisions. Taxonomy fit: none (mutable external references).
→ gap candidate.

**RF-G11 | LOW | AYUSH Yoga/Naturopathy prior-approval condition**
Payable "subject to prior approval from the Company" — discretionary gate
inside an up-to-SI benefit. Fits no pattern cleanly; note as conditional gate.

**RF-G12 | LOW | Benefit-forfeiture on opt-out — Super Star Bonus**
(Optional 20) Opt out at renewal → ALL accumulated bonus reduced to zero.
Lock-in by forfeiture. → same gap family as RF-G01.

**RF-G13 | LOW | Domiciliary/Home-care exclusion lists**
Domiciliary excludes the chronic conditions most likely to need it (asthma,
diabetes, hypertension, epilepsy, psychiatric, arthritis...). "Home Care
Treatment covered" headline vs 12-condition whitelist (home care) and long
blacklist (domiciliary).

**Base-policy explicit NON-flags (FALSE-FLAG tripwires for the extractor):**
- NO room rent cap (RF-001 base = false)
- NO disease-wise sub-limits in base inpatient cover (RF-002 base = false,
  except optional-cover limits above)
- PED = 36 months = standard (RF-003 false)
- Day care = ALL procedures (RF-005 false)
- Modern treatments up to SI (RF-007 false)
- Post-hosp 180 days (RF-009 false)
- Lifetime renewal guaranteed (RF-010 false)
- ICU: no cap (RF-014 false)

---

## STEP 5 (partial) — BROCHURE vs POLICY DELTAS

1. "Trusted Hospitals, Any Room... all with no extra cost" — true ONLY if
   Room Rent Modification not opted; brochure omits the conditional
   proportionate-deduction machinery. (feeds RF-G03)
2. "Freeze Your Age — keep your premiums young until you make a claim" —
   omits: floater all-member unlock, hard stop at 56, entry ≤50. (RF-G04)
3. "Automatic Restoration... unlimited number of times" — omits single-claim
   ≤SI cap and 45-day same-illness rule. (RF-G05)
4. "90% claims settled in < 2 hours" — marketing statistic, no policy basis;
   out of scope for extraction but noted for the public red-flag page.
5. Brochure omits Quick Shield 5-year premium clawback entirely. (RF-G08)
6. Brochure "up to 21 optional covers" framing presents Smart Network as a
   discount; co-pay condition disclosed but dynamic-list discretion omitted.
   (RF-G02)

## STEP 6 (pre-registered) — TAXONOMY GAP CANDIDATES (RF-015+)

Candidate new patterns surfaced by gold pass (confirm after extraction run):
- **RF-015 Benefit forfeiture / one-shot covers:** benefits that permanently
  cease or reset accumulated value on claim or opt-out (RF-G01, G12; DME
  cover lifetime-once also fits).
- **RF-016 Premium/claim offset mechanics:** unpaid future premiums or
  cover-specific premium balances deducted from claim payouts (RF-G08).
- **RF-017 Unilateral mutable terms:** benefit-relevant lists (networks,
  excluded providers/expenses, medical position statements) changeable at
  insurer discretion via website (RF-G02, G10).
- **RF-018 Premium-mechanics traps:** age-lock/unlock, zone loading, discount
  conditions with hidden triggers (RF-G04).
- **RF-019 Conditional activation of dormant clauses via optional covers:**
  base-clean policies whose traps activate on premium-saving options (RF-G03)
  — arguably the most important pattern for premium products generally.

## SCHEMA LIMITATIONS SURFACED (feed to addendum after run)
1. policy_type enum forces single value; products are sold multi-form
2. policy_term_years single integer vs offered range 1–5
3. sum_insured_options integer array vs "Unlimited"
4. restoration number_of_times integer vs "unlimited"
5. No representation for optional covers AT ALL — this product's entire trap
   surface lives in 21 optional covers; schema has no optional_covers[] block.
   This is the biggest schema finding of the run and was invisible until a
   real premium product was annotated.

## NEXT: STEP 2 REQUIREMENTS (fresh-context extraction run)
Run in a NEW conversation with zero context from this one. Input =
prompts/v1/extract_policy.md with full policy wording text in {{POLICY_TEXT}}.
Return the raw JSON verbatim to this lane for Steps 3–7 scoring against this
document. Predicted failure concentrations: proportionate-deduction field
pairing (RF-G03), optional-cover blindness (schema limitation 5), Unlimited
SI type errors, and FALSE-FLAGS from classic-trap pattern matching.
