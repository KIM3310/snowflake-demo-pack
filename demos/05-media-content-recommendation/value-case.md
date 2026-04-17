# Value Case — Media Content Recommendation with Vector Search

*A composite narrative based on typical streaming-media operators. Numbers are illustrative.*

## Customer context

"Northwave Streaming" is a regional streaming-media operator with 10 million daily active users across Asia-Pacific. Their catalog is 45,000 titles (long-form episodic + movies + short-form). They run a classical collaborative-filtering recommendation stack on Spark + Redis. The team of 6 ML engineers has been blocked for 9 months on a cold-start problem: new titles take 14+ days to appear meaningfully in recommendations, and the marketing team wants day-of-release discoverability.

## Before state

- **Cold-start blind spot**: 14-day median time-to-recommendation for new titles. Marketing reports this as the #1 acquisition-lift blocker.
- **Two separate systems**: collaborative filtering in Spark (hourly rebuild) + metadata-based rule engine (manual tuning). The two produced contradictory recommendations 11% of the time in internal QA.
- **Cross-language discovery failure**: Korean-drama subscribers saw Japanese content in their recommendations only 3% of the time despite surveys showing 31% cross-language viewing behavior.
- **Compute budget**: $68K/month on Spark compute + Redis for the recommendation pipeline alone.
- **ML engineer time**: 60% of the team's quarterly roadmap consumed by pipeline reliability, not model improvement.
- **Watch-through rate plateau**: flat at 42% for 4 consecutive quarters despite catalog growth.

## After state (6 months post-deployment)

- **Day-zero discoverability**: new titles appear in semantic search within 60 seconds of catalog ingest (embed-on-write via Cortex `EMBED_TEXT_768`).
- **Single system**: vector search + user preference vector (computed via Dynamic Table) replaces both previous systems. Internal contradiction rate dropped to near zero.
- **Cross-language discovery**: 17% of recommendations now cross language boundaries, with a 23% watch-through rate on cross-language impressions. This alone justifies the program.
- **Compute budget**: $26K/month Snowflake consumption replaced $68K/month Spark + Redis.
- **ML engineer time**: team reclaimed 50% of capacity for model work (replaced reliability firefighting).
- **Watch-through rate**: 42% → 50% over the 6 months post-cutover.

## Financial summary

| Line item | Annual |
|-----------|--------|
| Compute cost reduction ($42K/mo × 12) | $504K |
| Engineering capacity reclaim (3 FTE-months/quarter × burdened rate) | $360K |
| Revenue uplift from 8-pt watch-through increase (model: 3% ARPU lift) | $1.9M |
| **Gross annual benefit** | **$2.76M** |
| Snowflake incremental consumption already netted in compute line | – |
| Engineering build-out (one-time, amortized 3 yr) | $120K |
| **Net annual benefit** | **$2.64M** |

## Intangible benefits

1. **Marketing alignment**: new-title launches now have a reliable recommendation substrate within launch-day. The marketing team's creative planning cycle de-risks.
2. **Catalog acquisition leverage**: content licensing negotiations reference the ability to surface new content immediately.
3. **Cross-language engagement**: a surprise outcome. Drove a content-licensing strategy shift toward dual-language slate acquisition.

## How this demo maps to the customer story

| Customer moment | Demo artifact |
|-----------------|---------------|
| "Show me semantic search on a cold-start title." | Insert a title via `02-load-data.py`, run the vector search query in 04-analytics.sql seconds later. |
| "How does user personalization layer in?" | Show the Dynamic Table maintaining rolling user-preference vectors. |
| "What about cross-language discovery?" | Query with a Korean description, see Japanese/English results in top-10. |
| "Is it Snowflake-only?" | The Streamlit in Snowflake dashboard (05-dashboard.py) runs inside the account boundary with no external system. |
| "What happens when we add 1M new events/day?" | Cortex Search scales horizontally on the account's warehouse budget. |

## SE talking points

1. "Day-zero discoverability" is the single strongest framing for media customers. Every media customer has a cold-start problem.
2. Snowflake's VECTOR data type + Cortex `EMBED_TEXT_768` + Cortex Search is the first time they can keep the recommendation layer inside the data platform. The consolidation story is strong.
3. The cross-language discovery angle often surfaces during demo and surprises customers. Pre-load the demo with titles in 3+ languages to trigger it.
4. Watch-through rate + ARPU lift are the revenue-side anchors. Engineering cost reduction is the CFO framing.

## What would a real deployment look like differently?

- **Multi-model embedding strategy**: the demo uses one embedding model. Production will blend a general-purpose model with a domain-fine-tuned model and A/B test.
- **A/B experimentation framework**: production recommendation systems always run experiments. Tie the candidate generation to an experimentation layer.
- **Diversity re-ranking**: raw similarity ranking over-converges. Production systems apply MMR or determinantal point-process re-ranking.
- **Cold-start user handling**: the demo handles cold-start titles. A separate pattern is needed for new users (onboarding flow with seed preferences).
- **Compliance**: GDPR / local data-residency requirements will shape which embeddings can cross region boundaries.

These are implementation items in a production rollout. The demo establishes the substrate on which they would be built.
