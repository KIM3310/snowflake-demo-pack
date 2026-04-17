# Value Case — Unified Customer 360 on Snowflake

*Target audience: CMO and CDO at a multi-channel retailer with $500M+ annual revenue.*

## Executive Summary

For a reference retailer with 500,000 active customers, $500M in annual revenue, and five channels:

| Value driver | Annual impact (USD) |
|---|---|
| Revenue uplift from cross-channel recognition (4 percent repeat rate lift) | 3,600,000 |
| Marketing efficiency (suppression of mis-targeted sends) | 600,000 |
| Customer Data Platform retirement | 1,200,000 |
| Attribution model consolidation | 450,000 |
| **Net annual benefit** | **5,850,000** |

| Cost line | Annual impact (USD) |
|---|---|
| Snowflake compute (RFM + journey Dynamic Tables) | 260,000 |
| Snowflake storage (event archive, 1 year) | 35,000 |
| Iceberg external volume (S3) | 18,000 |
| Implementation project (12 weeks, 3 FTE blended) | 360,000 |
| **Total first-year cost** | **673,000** |

**Year-one net: $5.18M. Payback: under 5 months.**

---

## Problem Framing

Retailers who operate five channels — web, mobile, POS, call center, marketplace — usually see each channel's data land in a separate system of record with its own customer identifier scheme. This creates three expensive problems:

1. **Duplicate marketing spend.** A customer who just completed a $400 purchase in a physical store is frequently re-targeted the next day with a web ad for the same product, because the two channels do not share state. Industry benchmarks place this waste at 8 to 15 percent of performance-marketing spend.
2. **Broken personalization.** The mobile app cannot give a gold-tier customer their benefits because tier status lives in the loyalty database, not in the app's customer profile. Conversion on the mobile app tier-specific offer page drops 20 to 30 percent for cross-channel customers.
3. **Stalled data-platform projects.** Most retailers have tried to build a "Customer Data Platform" with a vendor CDP or a home-grown warehouse. The projects typically stall because identity resolution, security, and data-sharing controls are not in a single platform.

The architecture in this demo replaces the separate CDP with Snowflake-native components, using Iceberg for open interoperability and Secure Data Sharing for zero-copy partner distribution.

## Solution Mechanics

The demo materializes a single `CUSTOMER_360_VIEW` built from:

- `CUSTOMERS` — master dimension as an Iceberg Table (readable by external compute).
- `CUSTOMER_EVENTS` — append-only cross-channel event stream ingested via Snowpipe Streaming.
- `CUSTOMER_RFM_DAILY` — Dynamic Table maintaining 90-day RFM aggregates.
- `CUSTOMER_JOURNEY` — Dynamic Table maintaining sessionized journeys.
- `CALL_CENTER_THEMES` — Cortex COMPLETE + SUMMARIZE output bucketing free-text notes.

Downstream, a Secure Data Share exposes a cleanly-governed subset to the marketing agency and loyalty partner accounts.

## Quantified Benefits

### 1. Revenue uplift from cross-channel recognition

A 4 percent lift on repeat-purchase rate is conservative relative to published CDP benchmarks (5 to 9 percent). On a baseline of $180 average customer LTV and 500,000 active customers, the math is:

- Current repeat buyers: 500,000 * 0.28 = 140,000.
- Uplift: 140,000 * 0.04 = 5,600 additional repeat buyers.
- Average incremental revenue per retained customer: $180 LTV * 0.35 = $63.
- Direct: 5,600 * $63 = **$352,800 annually on pure retention**.
- Expanded basket size: omnichannel customers spend 30 percent more per order than single-channel; applying that lift across the 30 percent of customers newly recognized as omnichannel (150,000 customers, $210 average annual spend each) gives: 150,000 * $210 * 0.30 = $9.45M; we conservatively credit **$3.25M annually** of this to the 360 initiative.

Combined: ~$3.6M.

### 2. Marketing efficiency

Suppression of mis-targeted sends (customer who just bought, customer who just complained, customer outside the offer's eligibility) typically cuts unsubscribe rate by 18 percent and reduces wasted send volume by 12 percent. For a retailer sending 50M emails per month at a blended CPM of $1:

- Volume reduction: 50M * 12 * 0.12 = 72M fewer sends = **$600K saved annually**.

### 3. Customer Data Platform retirement

A vendor CDP for a 500K-customer retailer typically costs $80K-$180K per month. Average is around $100K/month = $1.2M/year. The demo architecture covers every must-have function of the CDP (identity resolution, segmentation, activation) directly in Snowflake, so the license can be dropped after parallel-run validation.

### 4. Attribution model consolidation

Each channel commonly runs its own attribution model. Consolidating on a single journey surface enables one attribution model rather than five, saving roughly 1.5 FTE in analytics engineering ($300K) plus licenses for per-channel attribution tools ($150K) = **$450K annually**.

## Implementation Timeline

| Week | Deliverable |
|---|---|
| 1 | Snowflake account + Iceberg external volume provisioned |
| 2 | Snowpipe Streaming from first two channels (web + mobile) live |
| 3 | Remaining three channels (POS, call, marketplace) connected |
| 4 | `CUSTOMERS` Iceberg master dimension loaded from golden-record process |
| 5 | Dynamic Tables (RFM + journey) at target lag |
| 6 | Cortex enrichment on call-center notes |
| 7 | Streamlit timeline app live, stakeholder UAT |
| 8 | Parallel run with existing CDP begins |
| 9-10 | Reconciliation; identity-resolution rule tuning |
| 11 | Secure Data Share to marketing agency and loyalty partner |
| 12 | CDP decommissioning; steering committee sign-off |

## Risks and Mitigations

| Risk | Mitigation |
|---|---|
| Identity-resolution rule debate | Treat `CUSTOMER_360_VIEW` as the canonical rule set; reviewed monthly |
| External volume cost for Iceberg | Lifecycle policy on S3 keeps Iceberg snapshots within 1 year |
| Cortex model cost on call-note enrichment | Process only new notes via the `WHERE T.NOTE_ID IS NULL` guard |
| Data-sharing legal review delay | Secure Data Share provisioning is a 1-hour workstream; schedule legal review in week 10 |

## What We Need from the Customer

- Access to a 90-day event extract from each of the 5 channels.
- The current golden-record output from the CDP for master-dimension seeding.
- A named data-governance owner for the masking policy approval chain.
- Agreement on the three identity-resolution rules (email match, phone match, loyalty ID match) prior to implementation week 3.

## Call to Action

We recommend starting with a 12-week PoV scoped to the web and mobile channels only. Success metric: "The CUSTOMER_360_VIEW returns a complete profile for any customer in under one second, and the RFM refresh stays within a 5-minute lag while processing 90 days of event history." Clearing that bar opens the door to the call-center and POS integrations in weeks 13 through 20.
