# Finance — Real-Time Fraud Detection: 5-Minute SE Pitch

*Delivery script for a pre-sales conversation. Total runtime: 5 minutes.*

---

## 0:00 — 0:30 — Anchor the problem

> "Card-not-present fraud cost issuers $4.2B last year globally, and the average investigation costs $48 even when it turns out to be a legitimate transaction. Your ops team is spending nights chasing false positives while real fraud rings exploit the 8-hour gap in your batch pipeline. The question isn't 'can we catch more?' — it's 'can we catch faster without drowning your analysts in alerts?'"

**What to watch**: lean in when the customer nods at "nights chasing false positives." That's your anchor. If they push back ("our FP rate is only 15%"), pivot to "so the analyst time question is where the lever is."

## 0:30 — 1:15 — Show the architecture

Open `demos/01-finance-fraud-detection/architecture.md` in a side panel.

> "Everything you see here runs in Snowflake. Card authorization events land via Snowpipe Streaming into `TRANSACTIONS_RAW`. A Dynamic Table graph materializes rolling features at a 60-second target lag. Your existing fraud model runs as a Snowpark UDF — same scikit-learn you already wrote, no re-platform. Cortex `CLASSIFICATION` gives you a second opinion from a managed model. Both scores feed your analyst queue."

**What to emphasize**: Dynamic Tables is the unfamiliar primitive for many customers. Pause on it. "This is a declarative materialized graph — you define the end state, Snowflake handles the orchestration and lag targets."

## 1:15 — 2:30 — Live query walk-through

Run these queries from `04-analytics.sql` in a Snowflake worksheet, reading the numbers aloud:

1. **Fraud rate by channel** — show the distribution.
2. **"Loss avoided by blocking top decile"** — the business-impact query.
3. **Alert queue freshness** — query the Dynamic Table latency metric.

> "Your current platform probably can't answer question 2 in under an hour because joining streaming writes against a historical window takes a separate system. Here, it's a single SQL statement."

## 2:30 — 3:15 — The governance answer

> "Every query you see is captured in `ACCESS_HISTORY` and `QUERY_HISTORY` with 365-day retention on Enterprise Edition. Your auditor can answer 'who scored this transaction with which model version' from a single SQL query. Your model deployment is versioned as a Snowpark UDF, so rollback is a `DROP FUNCTION` away."

**What to emphasize**: this is usually the CISO's question in the room. Pre-empt it before they ask.

## 3:15 — 4:15 — The TCO framing

| Current state (typical) | This pattern |
|-------------------------|--------------|
| Kafka + Flink + Feature Store + online serving + analyst BI | Snowflake only |
| 4-6 systems, 4-6 skill sets | 1 system, SQL + Python |
| Median $1.2M/yr platform + 3 FTE to maintain | Demo estimates 0.7 credits / 10K events; analyst FTE unchanged |
| 8-hour batch lag on enrichment | 60-second Dynamic Table lag |

> "You're not trading functionality for consolidation. You're getting faster enrichment on a simpler stack."

## 4:15 — 4:45 — Proof-of-concept offer

> "Here's what I can commit to. In a 2-week POC I'll load your last 30 days of transaction data, wire up your existing fraud model as a Snowpark UDF, and benchmark the alert-to-block latency against your current pipeline. That's the measurable you take to your CFO. I bring the pattern, you bring 3 engineering hours across the 2 weeks."

## 4:45 — 5:00 — Close with the ask

> "Who on your team owns the current fraud platform's reliability? I'd want to start there — they'll have the clearest view of where the pain is and the fastest path to a measurable win. Can you make a 30-minute intro?"

---

## Objection bank

| Objection | Response |
|-----------|----------|
| "We can't move our fraud model to the cloud for regulatory reasons." | "The model runs as a Snowpark UDF inside Snowflake — the model weights live in your account. Data never leaves. Region pinning is available." |
| "Our fraud team uses proprietary feature store." | "Dynamic Tables replace the feature store for streaming features. For batch features, your existing store integrates via a Snowflake external function. Incremental migration is the norm." |
| "We have regulatory latency SLAs on auth decisions." | "Auth-time decisioning stays in your real-time system. Snowflake handles the analyst queue, historical investigation, and model retraining — the slower loop." |
| "How do we handle model governance?" | "Every UDF version is tracked in `INFORMATION_SCHEMA.FUNCTIONS`. Cortex models have versioned model cards. Deployment is GitOps via Snowflake CLI or dbt." |
| "What's the egress cost for analyst tools?" | "Analysts query in-place via Streamlit in Snowflake or their existing BI. Egress happens only when you choose to move data out, typically not for this use case." |

## What to bring

- A Snowflake account pre-loaded with the demo data (run `make demo-finance`).
- Your laptop with the Streamlit dashboard running locally.
- The `value-case.md` printed as a 1-pager you leave behind.
- Access to the customer's fraud-team engineering lead by end of call.
