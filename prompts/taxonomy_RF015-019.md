# Soteria Red Flag Taxonomy — Expansion Pack v1.1 (RF-015 to RF-019)

Status: Adds five patterns to the 14-pattern taxonomy in
prompts/v1/extract_policy.md. Derived from GOLD_001 gap candidates,
confirmed by SCORING_001 (the run missed RF-G01/G12/DME because no
forfeiture pattern existed; found RF-G08/G10 despite no pattern, proving
these patterns are real and detectable once named).

Design note: patterns 1–14 are almost all about UNDER-coverage stated in
the base policy (caps, sub-limits, waiting periods). Patterns 15–19 are a
different species — they are about MECHANICS: how benefits erode, reset,
offset, or activate, and how "premium-saving" options reintroduce risk.
Premium products (clean base, complex options) hide their traps here.
These five patterns are what let the engine analyze a "good" policy
truthfully instead of declaring it clean.

---

### RF-015: Benefit forfeiture / one-shot & resetting covers (HIGH)
**Recognition:** A benefit that (a) can be used only once in the lifetime
of the policy and then ceases permanently, (b) zeroes the Sum Insured or a
bonus on a triggering event, or (c) resets accumulated value to zero on
opt-out or on a single claim.
**Trigger phrase patterns:** "cease to exist and cannot be opted again,"
"reduced to zero," "once during the life time of the policy," "for any one
claim during the lifetime," "shall not be available... upon subsequent
renewals," "all the bonus accumulated... will be reduced to zero."
**Why high:** The user believes they hold a benefit; the mechanics mean
that invoking it, or dropping the option for one year, destroys it. The
worst case is a benefit that ALSO zeroes the base Sum Insured for the
remaining policy year, leaving the user uninsured mid-year.
**Scenario obligation:** State the exact triggering event and the
post-trigger coverage state ("after this claim is paid, your Sum Insured
is zero until the next renewal — a second hospitalization that year is not
covered").
**Example (this document):** Limitless Care — one claim in the policy's
lifetime, then cover ceases AND Total Sum Insured drops to zero for that
Policy Year. Super Star Bonus — opt out at any renewal and all accumulated
bonus is wiped. Durable Medical Equipment — payable once, lifetime, then
gone.

### RF-016: Premium / claim offset mechanics (MEDIUM-HIGH)
**Recognition:** Any clause allowing the insurer to deduct amounts OTHER
than the covered medical shortfall from the claim payout — chiefly unpaid
future premium instalments, or a multi-year premium balance for an optional
cover, recovered out of the settlement.
**Trigger phrase patterns:** "deduct... premium from the claim amount,"
"all subsequent premium instalments shall immediately become due,"
"balance premium... deducted from the claim."
**Why:** The user expects the claim to pay the hospital bill; instead the
net payout silently shrinks by premium the user did not expect to owe yet.
Undisclosed at point of sale in almost every case.
**Scenario obligation:** Compute the timing worst case ("hospitalized in
month 3 of a monthly-instalment policy → the remaining 9 months of premium
come out of your settlement").
**Example (this document):** Instalment condition — any claim makes all
remaining instalments immediately due and deductible from the claim.
Quick Shield — five years of the cover's premium is collected, and an
admissible claim within five years deducts the balance premium from the
claim amount.

### RF-017: Unilaterally mutable terms (MEDIUM)
**Recognition:** A benefit-relevant list or standard that the insurer can
change at its own discretion, AFTER purchase, without policyholder consent
— network lists that gate co-pay, excluded-provider lists, excluded-expense
lists, or internal "medical protocols / position statements" that govern
pay/part-pay/deny decisions, especially when hosted on the insurer's
website rather than fixed in the contract.
**Trigger phrase patterns:** "list is dynamic," "reserves the right to
change... at its discretion," "as detailed in the website," "we will
periodically publish and refresh," "may fully pay, part pay... or deny...
based on these guidelines."
**Why:** The thing the user relied on when buying (this hospital is in
network; this expense is covered; this treatment is standard) can move
after the money is paid and before the claim. The contract points outside
itself to a document the insurer controls.
**Scenario obligation:** Name the specific reliance that can be defeated
("the hospital you chose this policy around can be removed from the Smart
Network list before you are admitted, triggering the 15% co-pay").
**Example (this document):** Smart Network dynamic list. Excluded Providers
(Excl 11) and Excl 37 expenses on the website. Medical protocols / position
statements governing part-pay and denial, including off-label / non-CDSCO
exclusions.

### RF-018: Premium-mechanics traps (MEDIUM)
**Recognition:** Premium-side mechanics whose headline reads as a benefit
but whose trigger conditions materially raise cost — age-lock benefits that
unlock on a claim (and, in floaters, unlock for ALL members on ONE member's
claim), hard age ceilings on such benefits, zone-based loading, or discount
conditions with a hidden claw-forward.
**Trigger phrase patterns:** "age is locked... till a claim is incurred,"
"we will unlock the age for all the Insured members," "whichever is
earlier," "premium will be charged as per... age at such renewal."
**Why:** Marketing frames it as "frozen premiums"; the mechanic means a
single small claim by one family member reprices the whole family, or the
benefit silently expires at an age cap. Distorts the decision to make a
small claim.
**Scenario obligation:** Surface the multiplier and the trigger ("in a
floater, one member's ₹40,000 day-care claim unlocks age-based premium for
all five members at the next renewal").
**Example (this document):** Freeze Your Age — locks at entry, unlocks on
any in-patient/day-care/AYUSH claim; in a floater ONE member's claim
unlocks ALL members; ends hard at age 56; entry only if ≤50.

### RF-019: Conditional activation of dormant clauses via optional covers (HIGH)
**Recognition:** A risk clause that is PRESENT in the policy (usually in
definitions) but DORMANT in the base cover, and which ACTIVATES only when
the user selects a premium-reducing optional cover. The base policy reads
clean; the option the agent recommends for a cheaper premium switches the
trap on.
**Trigger phrase patterns:** a definition describing a deduction/limit
mechanic ("proportionate deduction will apply... if... above the
eligibility defined in policy") whose activating condition lives in an
optional cover ("option to modify the room rent eligibility"). Also
voluntary co-pay / voluntary deductible options.
**Why high:** This is the signature trap of premium products and the one
most likely to be mis-sold — "take the room-rent modification, it's
cheaper" silently arms proportionate deduction on every future claim's
associated expenses. The base-policy analysis looks clean, so nobody warns
the user.
**Representation rule (critical):** For a dormant clause, the base-policy
boolean stays FALSE (no cap / no co-pay / no deduction in base), the
clause_present flag stays TRUE, and the risk is carried entirely by a
red flag whose scenario is explicitly conditioned on opting the cover.
Never set the base boolean true because the mechanic COULD activate.
**Scenario obligation:** State base-state then activated-state ("today,
with any-room cover, no proportionate deduction applies. If you opt Room
Rent Modification to lower premium and then use a higher room, your
surgeon/OT/procedure charges are cut proportionately").
**Example (this document):** "Associated medical expenses" definition
(dormant proportionate deduction) + Room Rent Modification optional cover
(the activator). Voluntary Co-payment and Voluntary Deductible optional
covers (dormant cost-sharing).

---

## Interaction with existing patterns
- RF-001 (room rent + proportionate deduction) now explicitly means the
  MANDATORY base-policy version. When the mechanic is dormant-and-optional,
  use RF-019 instead, and do NOT fire RF-001 against the base policy.
- RF-006 (easy-to-miss co-pay) covers co-pay that applies in the base
  policy under specific conditions. Optional-cover co-pay (Smart Network,
  Voluntary Co-pay) is RF-017 (mutable/discretionary network) and/or RF-019
  (dormant activation), not RF-006 against the base.
- RF-012 (restricted cashless network) and RF-017 overlap when the network
  is BOTH restricted AND discretionarily mutable; fire RF-017 (the mutable
  element is the sharper harm) and reference the restriction within it.

## Severity calibration reminder
Severity is still financial-impact-in-realistic-scenarios. A one-shot cover
that zeroes SI mid-year (RF-015) is HIGH because the downstream exposure is
the entire remaining Sum Insured. A premium-mechanics repricing (RF-018) is
MEDIUM unless the repricing is large and near-certain. Judge the money, not
the alarming language.
