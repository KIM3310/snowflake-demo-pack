# Value Case — Real-Time Fraud Detection on Snowflake

*Target audience: VP of Fraud Operations, CFO office, and technical champion at a mid-sized issuer.*

## Executive Summary

A reference issuer running 1,000,000 card transactions per day ($280M monthly volume) can deploy the architecture in this demo and expect:

| Value driver | Annual impact (USD) |
|---|---|
| Direct fraud loss reduction (1 percentage-point precision lift) | 10,200,000 |
| Analyst productivity (40 percent false-positive reduction) | 2,400,000 |
| Legacy fraud-system retirement (license + infra) | 1,800,000 |
| Data-engineering headcount avoidance (batch -> streaming migration) | 900,000 |
| **Net annual benefit** | **15,300,000** |

| Cost line | Annual impact (USD) |
|---|---|
| Snowflake compute (scored warehouse + Dynamic Tables) | 420,000 |
| Snowflake storage and cloud services | 95,000 |
| Snowpark development and operating (1 FTE) | 180,000 |
| **Total annual cost** | **695,000** |

**Net annual benefit after cost: $14.6M. ROI payback: under 3 months assuming a 6-week implementation.**

---

## Problem Framing

Card-not-present fraud is growing at roughly 12 percent year over year. The control set a typical issuer currently deploys is some combination of:

- A vendor fraud score delivered through the authorization message (fixed thresholds, limited customization).
- A rules engine maintained by the fraud-ops team (high maintenance burden, slow to adapt).
- A nightly batch that updates customer-level features (hours of stale data during attack windows).

The architecture in this demo addresses all three limitations. It puts the customer's full transaction history, customer-level feature computation, and inline scoring in a single governed platform, with a refresh cadence that matches the attacker's iteration speed.

## Solution Mechanics

The demo materializes three layers in Snowflake:

1. **Ingest**: Snowpipe Streaming commits authorization events with sub-10-second freshness.
2. **Feature computation**: Dynamic Tables at one-minute target lag maintain rolling card and customer aggregates incrementally.
3. **Scoring**: A Snowpark Python UDF invokes a gradient-boosted model; a Cortex CLASSIFICATION model provides a managed second opinion.

Downstream, a Stream + Task pipe eligible rows into an alert queue that analysts consume via a Streamlit dashboard.

All five Snowflake products used are GA in commercial regions as of April 2026. Customer data never leaves the Snowflake trust boundary; no external ML platform, no Kafka cluster, no ETL scheduler.

## Baseline — What Life Looks Like Today

Typical mid-sized issuer baseline (1M transactions/day):

- Fraud loss rate: 0.20 percent of gross volume = $204M * 0.002 = $408,000 per day = **$149M annually**.
- Investigation cost: $48 per case * 1,200 manual reviews per day = **$21M annually**.
- Batch data warehouse license: **$1.6M annually**.
- Legacy streaming platform (Kafka + KSQL + custom feature store): **$1.2M annually** + 3 FTEs (~$540K).

## Quantified Benefits

### 1. Direct fraud loss reduction

Assumption: deploying the demo architecture lifts top-decile precision by 1 percentage point (from 89 percent to 90 percent), which at $280 average fraud amount and 1M transactions/day translates to 36 additional fraud transactions blocked per day:

- 36 * $280 * 365 = **$3.7M annually** from incremental precision.
- Recall lift of 0.5 percentage points on the same volume (catching attacks that batch misses): 56 * $280 * 365 = **$5.7M annually**.
- Combined: roughly **$9.4M to $10.5M per year**. We budget **$10.2M** as the planning assumption.

### 2. Analyst productivity

False-positive reviews consume analyst time. Baseline assumption:

- Current review volume: 1,200 per day.
- Average handling time: 5 minutes.
- Team size: 30 FTE at a fully-loaded cost of $85/hour.
- A 40 percent false-positive reduction removes 480 reviews/day = 2,400 hours/month = **28,800 hours/year**.
- At $85/hour = **$2.45M annually**.

### 3. Legacy system retirement

The demo architecture replaces three paid components:

- Batch warehouse license for fraud analytics: $800K/year.
- Separate streaming infra (Kafka + KSQL cluster + feature store SaaS): $750K/year.
- Rules engine annual support and upgrades: $250K/year.

Total: **$1.8M annually**.

### 4. Avoided headcount

The typical fraud platform team has a ratio of roughly 2 data engineers per 1 data scientist. Moving the feature layer into Dynamic Tables removes the custom pipeline maintenance workload, which in practice freezes one data-engineering role rather than growing it as volume scales. Savings at $180K fully loaded = **$900K annually**.

## Implementation Timeline

| Week | Workstream | Outcome |
|---|---|---|
| 1 | Data-platform discovery, Snowflake account setup | `SNOWFLAKE_DEMO_PACK` provisioned, auth event schema agreed |
| 2 | Snowpipe Streaming ingest, raw landing table | Live event stream arriving, 10-second freshness verified |
| 3 | Dynamic Tables for enrichment, feature validation | Parity with batch feature set demonstrated on 30 days of history |
| 4 | Snowpark UDF model packaged, scored table live | Top-decile precision tracked against legacy score |
| 5 | Cortex CLASSIFICATION trained, second-opinion column online | Model-disagreement dashboard published |
| 6 | Task + alert queue + Streamlit app | Analyst team UAT begins |

Six weeks from kickoff to production-like operation is typical. By week 8 the legacy batch can be decommissioned.

## Risks and Mitigations

| Risk | Mitigation |
|---|---|
| Model drift during deployment | Shadow mode for two weeks; compare UDF vs Cortex vs legacy scores side by side before cutover |
| Analyst workflow change management | Streamlit dashboard mirrors the existing case-management fields; no hard cutover |
| Data-sharing legal review | Row Access Policy `FRAUD_CUSTOMER_ACCESS` allows multi-tenant isolation without separate databases |
| Cost overruns | X-Small warehouse with 60-second auto-suspend; resource monitor caps the fraud pipeline at a credit ceiling |

## What We Need from the Customer

- A 30-day auth event extract for feature validation.
- A labeled fraud history (one year or more) for Cortex model training.
- Two-hour working session with the fraud-ops lead to codify risk-action policy thresholds.
- Two-hour working session with the model-risk team to approve the shadow-mode validation plan.

## Call to Action

We recommend a 6-week PoV on the customer's own data, scoped to the "Ingest -> Enriched -> Scored" path with a clear success metric: "Top-decile precision is within 1 percentage point of the legacy score, at a data freshness of under 3 minutes end-to-end." Reaching that milestone unlocks the full production rollout in weeks 7 through 10.
