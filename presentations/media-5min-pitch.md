# Media — Content Recommendation with Vector Search: 5-Minute SE Pitch

*Delivery script for a pre-sales conversation. Total runtime: 5 minutes.*

---

## 0:00 — 0:30 — Anchor the problem

> "Your marketing team spends weeks promoting a new title launch. Your recommendation engine takes 14 days to catch up. For those 14 days, your biggest acquisition lever is running blind. And when your ML team finally gets the title into the recommender, the system pushes it to users with the wrong genre tastes because classical collaborative filtering can't read the description field."

**What to watch**: the content lead or marketing lead will react to the 14-day lag figure.

## 0:30 — 1:15 — Show the architecture

Open `demos/05-media-content-recommendation/architecture.md`.

> "Catalog writes go through Cortex `EMBED_TEXT_768` — the VECTOR column is populated at ingest. Cortex Search provides the semantic index. User watch events land via Snowpipe Streaming. A Dynamic Table graph maintains rolling user-preference vectors. Recommendation queries are vector cosine similarity over catalog, filtered by availability, ranked by a blend of content similarity and user preference."

**What to emphasize**: "Your embeddings live in Snowflake as a first-class data type. Not in a separate vector database."

## 1:15 — 2:30 — Live query walk-through — *the "aha" moment*

Run these from `04-analytics.sql`:

1. **Cold-start test**: insert a new title with description → query vector similarity 30 seconds later → show top-10 similar titles.
2. **Cross-language discovery**: query with a Korean description, see Japanese and English results in the top-10.
3. **User personalization**: for a known user, recommend-next using their rolling preference vector joined to content similarity.

> "Query 2 is the surprise result for most customers. Classical collaborative filtering can't cross language lines because watch behavior is within-language. Vector search reads the description itself."

## 2:30 — 3:15 — The consolidation framing

> "You likely run a classical recommender on Spark, a separate vector DB for embeddings-based search, and a third system for personalization. All three are in Snowflake here. One platform, one query language, one governance surface."

**What to emphasize**: if the customer has a vector-DB vendor contract coming up for renewal, this is the wedge.

## 3:15 — 4:15 — The TCO framing

| Current state (typical) | This pattern |
|-------------------------|--------------|
| Spark for CF + Pinecone/Weaviate for embeddings + Redis for serving | Snowflake with VECTOR type + Cortex Search |
| 3 platforms, 3 skill sets | 1 platform, SQL |
| Typical mid-size media: $68K/mo recommendation compute | Demo estimates $26K/mo at 10M events/day scale |
| 14-day cold-start | 60-second cold-start |
| Cross-language discovery: 3% | 17% in reference customers |

> "The compute savings pays for the build-out in under 3 months. The cross-language discovery lift is the revenue story."

## 4:15 — 4:45 — Proof-of-concept offer

> "5-week POC. You bring catalog descriptions in native languages and 30 days of anonymized watch events. I bring the embedding pipeline, Cortex Search index, user-preference Dynamic Table, and a recommendation UI. Success criterion: 10-point watch-through improvement on new-title impressions vs your current system, or 5x cold-start reduction — your pick."

## 4:45 — 5:00 — Close with the ask

> "Who owns your recommendation engine's reliability? I'd want to start with them — they know the cold-start pain best. Can you make a 30-minute intro to your head of ML platform?"

---

## Objection bank

| Objection | Response |
|-----------|----------|
| "We already have a vector database." | "Snowflake's VECTOR type is a data-platform feature, not a vendor swap. Most customers start by using it for new use cases where the vector DB adds too much operational overhead, then migrate over time. It's not either/or." |
| "Classical collaborative filtering works fine for our main recommendations." | "Keep it. Cortex Search covers what CF can't — cold-start, cross-language, semantic search. They're complementary." |
| "Embedding quality varies by domain." | "You can swap models — Cortex exposes multiple embedding functions, or bring your own via a Snowpark UDF. The pattern doesn't lock you in." |
| "How does this scale to 100M events/day?" | "Snowflake's warehouse auto-scaling handles spikes. Cost scales with usage, not with always-on infrastructure." |
| "Our data is in S3, not Snowflake." | "Iceberg Tables — you keep data in S3, Snowflake queries it. You don't migrate. Latency is within 2x native Snowflake tables for most workloads." |

## What to bring

- Pre-loaded demo running `make demo-media`.
- A multilingual catalog pre-loaded (3+ languages) so cross-language discovery triggers naturally in the demo.
- `value-case.md` as leave-behind.
- Access to the ML platform or recommendation engineering lead.
