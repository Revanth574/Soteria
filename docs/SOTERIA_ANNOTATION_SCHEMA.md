# Soteria — Policy Annotation Schema v0.1

This schema defines the structured output of the policy analyzer.
Both the LLM extraction prompt and the frontend rendering are built
against this schema. Schema versions are tracked; every analysis
in the database records which schema version produced it.

## Top-level structure

```json
{
  "schema_version": "0.1",
  "metadata": { ... },
  "summary": { ... },
  "coverage": { ... },
  "financial_terms": { ... },
  "waiting_periods": [ ... ],
  "sub_limits": [ ... ],
  "exclusions": [ ... ],
  "claim_process": { ... },
  "red_flags": [ ... ],
  "extraction_confidence": { ... }
}
```

## metadata

| Field | Type | Notes |
|---|---|---|
| insurer_name | string | As printed on the document |
| product_name | string | E.g. "Star Comprehensive" |
| product_uin | string|null | IRDAI product UIN if present |
| policy_type | enum | `individual`, `family_floater`, `group`, `senior_citizen`, `critical_illness`, `top_up`, `super_top_up`, `unknown` |
| policy_term_years | int|null | Length of policy term |
| document_date | string|null | If discoverable from document |

## summary

A 3–5 sentence plain-language overview, written in the second
person ("Your policy covers..."). Must NOT include red flags here;
red flags get their own dedicated treatment below. Tone: a careful
friend explaining, not a lawyer.

## coverage

| Field | Type | Notes |
|---|---|---|
| sum_insured | int | INR |
| sum_insured_type | enum | `individual`, `floater` |
| restoration_benefit | object|null | { available: bool, conditions: string } |
| no_claim_bonus | object|null | { type: "cumulative"|"discount", percentage_per_year: number, max_percentage: number } |
| network_hospitals_count | int|null | If stated; many policies state a count |
| ayush_coverage | object | { covered: bool, sub_limit: int|null } |
| domiciliary_coverage | object | { covered: bool, sub_limit: int|null } |
| day_care_procedures | object | { covered: bool, count: int|null, list_present: bool } |
| modern_treatment | object | { covered: bool, sub_limit: int|null, notes: string } |
| organ_donor | object | { covered: bool, sub_limit: int|null } |
| pre_hospitalization_days | int|null | Standard is 30; flag if shorter |
| post_hospitalization_days | int|null | Standard is 60; flag if shorter |

## financial_terms

| Field | Type | Notes |
|---|---|---|
| room_rent_cap | object | See below; this is one of the most important fields |
| icu_rent_cap | object | Same structure as room_rent_cap |
| co_pay | object | { applies: bool, percentage: number, conditions: string } |
| deductible | object | { amount: int, type: "per_claim"|"aggregate" } | null |
| proportionate_deduction_clause | object | { present: bool, clause_text: string, scenario_explanation: string } |

### room_rent_cap structure
```json
{
  "type": "absolute" | "percentage_of_si" | "category" | "none",
  "value_inr_per_day": number | null,
  "value_percentage": number | null,
  "category_description": string | null,
  "linked_to_proportionate_deduction": bool,
  "raw_clause": string
}
```

The `linked_to_proportionate_deduction` field is critical. A capped
room rent is only mildly bad on its own; combined with a
proportionate deduction clause, it becomes one of the most common
claim-reduction patterns in Indian health insurance. When both are
present, an automatic red flag MUST be generated.

## waiting_periods

Array of objects:
```json
{
  "category": "initial" | "pre_existing_disease" | "specific_disease" | "maternity",
  "applies_to": string,
  "duration_months": int,
  "raw_clause": string,
  "is_unusual": bool,
  "comparison_note": string
}
```

`is_unusual = true` if the waiting period is materially longer than
industry standard:
- Initial: standard 30 days; unusual >30
- PED: standard 24–48 months; unusual >48
- Specific diseases (cataract, hernia, etc.): standard 24 months;
  unusual >24
- Maternity: standard 24–36 months; unusual >36

## sub_limits

Array of objects:
```json
{
  "applies_to": string,
  "limit_type": "absolute" | "percentage_of_si",
  "limit_value": number,
  "raw_clause": string,
  "is_aggressive": bool
}
```

`is_aggressive = true` if the sub-limit is unusually low for the type
of treatment. Calibration table maintained separately.

## exclusions

Array of objects:
```json
{
  "category": "permanent" | "temporary" | "conditional",
  "description": string,
  "raw_clause": string,
  "is_unusual": bool
}
```

Standard exclusions (cosmetic surgery, war, nuclear, self-inflicted
injury, etc.) get is_unusual = false. Anything outside the standard
set gets is_unusual = true and surfaces in the UI.

## claim_process

| Field | Type | Notes |
|---|---|---|
| cashless_available | bool | |
| cashless_intimation_hours | int|null | Time before planned hospitalization |
| emergency_intimation_hours | int|null | Time after emergency admission |
| reimbursement_submission_days | int|null | After discharge |
| document_list_present | bool | |
| pre_authorization_required | bool | |

## red_flags

Array of objects, ordered by severity descending:
```json
{
  "id": string,
  "severity": "critical" | "high" | "medium" | "low",
  "title": string,
  "clause_reference": string,
  "raw_clause": string,
  "plain_explanation": string,
  "scenario": string,
  "what_to_do": string,
  "precedent_count": int | null
}
```

Red flag CATEGORIES (not exhaustive; expand as you annotate):

1. **Room-rent + proportionate deduction combo** — capped room rent
   AND proportionate deduction clause. Most common claim-reduction
   pattern in India. Always critical.

2. **Disease-wise sub-limits significantly below realistic costs** —
   e.g. cataract sub-limit of ₹25,000 when real cost is ₹40-60K.

3. **Long PED waiting period** — >48 months for pre-existing diseases.

4. **Restrictive day-care list** — policies that claim "day care
   covered" but list <50 procedures while industry standard is 150+.

5. **Co-pay applied to specific conditions or ages** — sometimes
   applies only to senior citizens or specific diseases; easy to miss.

6. **Modern treatment exclusions** — robotic surgery, immunotherapy,
   stem cell capped at low percentages of SI.

7. **Network hospital restrictions** — some policies limit cashless
   to a smaller "preferred" network within the broader network.

8. **Non-medical expense burden** — high prevalence of items
   classified non-payable per IRDAI Annexure I-II that this policy
   does not waive.

9. **Disease-specific exclusions in early years** — some specific
   diseases excluded for the first 2-4 years entirely, not just waiting.

10. **AYUSH treatment limited or excluded** despite being
    advertised as covered.

11. **Maternity waiting beyond 36 months** with low sub-limits.

12. **Renewal age cap** that's lower than expected (some policies
    cap at 65–70; lifetime renewal is the better standard).

(Maintain this list in a separate `RED_FLAG_CATALOG.md` and expand
it as new patterns are discovered through annotation.)

## extraction_confidence

For every top-level field, the LLM returns a confidence score
0.0–1.0. Frontend renders fields with confidence <0.7 with a
"verify against original" affordance.

## Source-text requirement

Every extracted field that has a `raw_clause` slot MUST include the
verbatim text from the policy. The UI displays this on expand.
This is non-negotiable: it's how users verify the analysis and
how we maintain trust.

