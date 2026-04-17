# Retail — 360° Customer View: 5-Minute SE Pitch

*Delivery script for a pre-sales conversation. Total runtime: 5 minutes.*

---

## 0:00 — 0:30 — Anchor the problem

> "You know your customers shop across your web, app, email, store, and marketplace channels. But your marketing team can't execute a coordinated campaign to a single customer across those channels because the data is in 5 systems, keyed differently, refreshed on different schedules. Your retention team operates on 3-day-old data while the customer just bought the thing."

**What to watch**: the marketing or retention leader in the room will react. Marketing tolerates "eventual consistency" less than any other department.

## 0:30 — 1:15 — Show the architecture

Open `demos/02-retail-customer-360/architecture.md` in a side panel.

> "Every channel writes via Snowpipe Streaming into a raw landing layer. Iceberg Tables let you keep cold history in your own S3 while Snowflake handles the metadata layer — you never duplicate the data. A Dynamic Table graph materializes the 360 view at a 2-minute target lag. Cortex LLM functions enrich free-text feedback into structured sentiment. Secure Data Sharing lets you expose the curated view to your partners without copying."

**What to emphasize**: Iceberg Tables is the new-to-many-customers primitive. "You keep control of the data at rest, Snowflake handles the query layer."

## 1:15 — 2:30 — Live query walk-through

Run these queries from `04-analytics.sql`:

1. **Cross-channel customer count** — unique customers active on 2+ channels.
2. **Retention cohort analysis** — 90-day retention by acquisition channel.
3. **Sentiment-aware recommendation candidates** — join LLM-enriched feedback with purchase history.

> "Notice query 3 joins unstructured feedback sentiment to structured purchase history in a single SQL statement. Your current platform probably needs a separate ML pipeline for this."

## 2:30 — 3:15 — The Cortex LLM angle

> "Cortex `COMPLETE` and `EXTRACT_ANSWER` let you ask questions of free-text feedback without leaving the governed boundary. The LLM runs in your region, against your data, with your access controls. For a retailer, that's the difference between 'we could try GenAI' and 'our legal team approves GenAI on customer data.'"

**What to emphasize**: if the customer has a Generative AI initiative, this is the wedge.

## 3:15 — 4:15 — The TCO framing

| Current state (typical) | This pattern |
|-------------------------|--------------|
| 5 channel systems → nightly ETL → CDP → marketing platform → BI | Landing → Dynamic Tables → Iceberg (cold) → consumption |
| 2-4 day channel-to-activation lag | 2-minute Dynamic Table lag |
| Separate ML infra for sentiment/topic modeling | Cortex in-platform |
| CDP licensing: $400K-$1.2M annually for mid-size retailer | Demo estimates 1.1 credits per run; CDP replacement TBD |

> "Most retailers adopt this incrementally — start with 1-2 channels, prove the lag reduction, expand."

## 4:15 — 4:45 — Proof-of-concept offer

> "3-week POC. You bring the customer-key mapping between two channels — web and app. I bring Snowpipe Streaming wire-up, Dynamic Table graph build-out, and a retention dashboard. At the end, your marketing team has an activated customer segment refreshed every 2 minutes instead of every 72 hours. Their reaction is the POC outcome."

## 4:45 — 5:00 — Close with the ask

> "Who on your marketing technology team owns the current CDP? Their pain is the clearest signal. Can you make a 30-minute intro?"

---

## Objection bank

| Objection | Response |
|-----------|----------|
| "We already have a CDP." | "Great. The 360 view in Snowflake becomes the single source of truth that feeds your CDP. Your CDP stops being the place where data arrives late and starts being the activation layer." |
| "Our channel data is in 5 different databases." | "Snowpipe Streaming ingests from each. Iceberg Tables let you leave archival data in place. You don't need to migrate." |
| "Identity resolution is hard." | "Snowflake doesn't solve identity resolution algorithmically — you plug in your existing identity graph (LiveRamp, Amperity, etc.) as a table, join to it. The lag reduction comes from everything being in one query surface." |
| "Our privacy team says we can't consolidate customer data." | "Row Access Policies + Dynamic Data Masking give per-role, per-jurisdiction column/row controls. You consolidate the storage; you don't consolidate access." |
| "What about real-time activation to marketing platforms?" | "Reverse ETL via Hightouch or Census runs off the governed 360 view. The marketing platform gets the same data, refreshed 2-minute lag instead of 3-day lag." |

## What to bring

- Pre-loaded demo account running `make demo-retail`.
- Streamlit dashboard with 2-minute-refreshed customer segments.
- `value-case.md` as leave-behind.
- Access to the marketing-technology or CDP owner.
