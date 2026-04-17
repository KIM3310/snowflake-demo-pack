# Value Case — Governed EHR Analytics on Snowflake

*Target audience: Chief Data Officer and Chief Compliance Officer at a regional IDN operating 4 hospitals and 28 clinics.*

## Executive Summary

Reference IDN: 4 hospitals, 28 clinics, 1.2 million annual encounters, $1.8B net patient revenue.

| Value driver | Annual impact (USD) |
|---|---|
| Faster data-use-agreement cycle (8 weeks faster) | 1,800,000 |
| Compliance audit cost reduction (tag-based masking) | 320,000 |
| Data engineering efficiency (one pipeline, three personas) | 500,000 |
| Denial recovery lift (earlier visibility into payer mix) | 600,000 |
| **Total annual benefit** | **3,220,000** |

| Cost line | Annual impact (USD) |
|---|---|
| Snowflake compute (8 hours/day on X-Small) | 35,000 |
| Snowflake storage (90-day retention) | 12,000 |
| Implementation project (8 weeks, 2 FTE) | 192,000 |
| Ongoing governance ownership (0.5 FTE) | 85,000 |
| **Total first-year cost** | **324,000** |

**Year-one net: $2.9M. Payback: under 4 months.**

---

## Problem Framing

The IDN has three analytics programs that need the same data with different access rules:

- Clinical quality program: 30-day readmission, HEDIS, Leapfrog measures.
- Revenue-cycle program: denial management, contract performance.
- Population health program: care management, risk stratification.

Historically each program built a separate data mart with its own ETL pipeline and its own access-control scheme. The problem with three marts is threefold:

1. **Data drift**: the three programs report different numbers for the same question.
2. **Governance overhead**: each mart has its own per-column access review, done quarterly, consuming 400 reviewer-hours per year.
3. **Project speed**: every new data-use agreement (DUA) with a payer partner requires legal review of the target mart's access controls. The customer reports a typical DUA cycle of 14 weeks.

The solution: one governed data layer, three consumption roles. Row access policies and masking policies in Snowflake replace the separate marts.

## Quantified Benefits

### 1. Faster data-use-agreement cycle

Baseline DUA cycle: 14 weeks. With platform-native governance evidence (tag reports, `ACCESS_HISTORY` exports, masking policy DDL), the cycle drops to 6 weeks. For an IDN that signs 8 DUAs per year with a typical $300K-$500K data product value per DUA:

- 8 DUAs * 8 weeks earlier * average $45K weekly value = **$2.88M earlier revenue**.
- Conservatively credit **$1.8M** to the platform change rather than the negotiation.

### 2. Compliance audit cost reduction

The existing quarterly access review covers 400+ columns across the three marts. Each review consumes 100 reviewer-hours. Tag-based masking replaces per-column review with per-tag review (7 tags), cutting the exercise to 12 hours per review:

- Saved 88 reviewer-hours per quarter = 352 hours/year.
- At $85/hour fully loaded = $29,920/year.
- Plus an external audit consulting engagement annually: $280K of which $250K is column-by-column sampling; platform evidence cuts this to $30K.
- Total: ~**$320K annually**.

### 3. Data engineering efficiency

Baseline: three separate ETL pipelines, each requiring ~0.8 FTE to maintain. Consolidation to one pipeline with three role-based views drops total ownership to 1.3 FTE (saving 1.1 FTE):

- 1.1 FTE * $180K fully loaded = $198K in labor.
- Infrastructure saving from retiring two data marts: $250K.
- Tool license retirement (the legacy data catalog): $50K.
- Total: **~$500K annually**.

### 4. Denial recovery lift

Earlier visibility into payer denial patterns (via the `CONTRACT_CAPITATION_USD` shortfall query) allows the revenue cycle team to re-submit denied claims within the 90-day window more consistently. Conservative recovery lift of 2 percent on $30M denied revenue = **$600K annually**.

## Implementation Timeline

| Week | Deliverable |
|---|---|
| 1 | Snowflake account provisioned; tag vocabulary defined; 3 demo roles |
| 2 | De-identified EHR extract landing via secure data sharing |
| 3 | Billing claims joined; ENCOUNTERS_SECURE view live |
| 4 | Masking policies attached; test queries run under all 3 roles |
| 5 | Row access policies for Department and Region; validated against expected row counts |
| 6 | Tag-based masking policy (any column tagged HIGH auto-masked) |
| 7 | Audit report exported into the GRC tool; compliance team UAT |
| 8 | Parallel run with existing marts; discrepancy report; go-live decision |

## Risks and Mitigations

| Risk | Mitigation |
|---|---|
| De-identification fidelity | Expert Determination methodology review in week 1; pseudonyms are SHA-derived with a salt rotated annually |
| Role proliferation | Keep to 7 production roles maximum; review quarterly |
| Policy debugging difficulty | `INFORMATION_SCHEMA.POLICY_REFERENCES` and `SYSTEM$GET_TAG` provide policy lineage out of the box |
| Staff training on new tooling | 2 hands-on workshops in weeks 7 and 8; Streamlit cohort explorer reduces the learning curve |

## What We Need from the Customer

- De-identified EHR and billing extracts (Expert Determination preferred over Safe Harbor).
- Written role-to-department-and-region matrix signed by the compliance officer.
- 2-hour working session to define the PII_CLASS tag vocabulary.
- Named governance owner responsible for the quarterly tag-review cycle after go-live.

## Call to Action

We recommend an 8-week PoV scoped to cardiology encounters only. Success metrics:

1. A cardiology analyst can answer the top-5 quality questions within 2 seconds using the governed view.
2. A non-cardiology role running the same SQL sees zero cardiology rows.
3. The compliance officer's 24-hour audit report surfaces every query we ran during the PoV.

Meeting all three metrics validates the platform for full IDN rollout in the following quarter.
