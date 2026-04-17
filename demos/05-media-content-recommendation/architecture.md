# Architecture — Media Content Recommendation

## Component Diagram

```mermaid
flowchart LR
    Catalog[CONTENT_CATALOG<br/>titles + descriptions] -->|EMBED_TEXT_768| Embed[CONTENT_EMBEDDINGS<br/>VECTOR(FLOAT, 768)]

    subgraph CortexSearch
        Index[CORTEX SEARCH SERVICE<br/>CONTENT_SEARCH]
    end
    Catalog --> Index

    Client[User device] -->|Events<br/>Snowpipe Streaming| Events[USER_EVENTS]
    Events -->|Dynamic Table<br/>10 min lag| Recent[USER_RECENT_PLAYS]
    Recent -->|Dynamic Table<br/>10 min lag| UserVec[USER_PREFERENCE_VECTOR]

    UserVec --> Recs[RECOMMENDATIONS_VIEW<br/>VECTOR_COSINE_SIMILARITY]
    Embed --> Recs
    Index --> App[Streamlit recommendation app]
    Recs --> App
```

## Key Architectural Decisions

### 1. VECTOR data type for catalog embeddings

`CONTENT_EMBEDDINGS.EMBEDDING` is declared as `VECTOR(FLOAT, 768)`. This gives us:

- Native storage without serialization to base64 or arrays.
- `VECTOR_COSINE_SIMILARITY`, `VECTOR_INNER_PRODUCT`, and `VECTOR_L2_DISTANCE` functions.
- Query planner awareness for filtering before comparison.

### 2. Cortex Search for indexed semantic retrieval

`CONTENT_SEARCH` is a Cortex Search service defined over `DESCRIPTION` with `(TITLE, GENRE, CONTENT_TYPE, RELEASE_YEAR, LOCALE)` as attributes. Cortex Search maintains an inverted index and a vector index behind the scenes, so a natural-language query returns results in sub-100ms without the customer having to stand up a separate vector database.

### 3. Embedding generation via stored procedure

`REFRESH_CONTENT_EMBEDDINGS()` is a SQL procedure that MERGEs new catalog rows into `CONTENT_EMBEDDINGS`, calling `SNOWFLAKE.CORTEX.EMBED_TEXT_768` only for rows that do not yet have an embedding. This makes re-runs cheap and keeps the cold-start promise (new titles indexed within minutes of publication).

### 4. Dynamic Tables for user state

`USER_RECENT_PLAYS` and `USER_PREFERENCE_VECTOR` are two Dynamic Tables on a 10-minute lag:

- `USER_RECENT_PLAYS` materializes the last 10 plays per user.
- `USER_PREFERENCE_VECTOR` aggregates their descriptions and re-embeds the concatenation as a single centroid vector.

The centroid approach is intentionally simple; it is the right baseline for a pre-sales demo. A production system would maintain per-user preference vectors with exponential decay and re-embed at session boundaries rather than every 10 minutes.

### 5. Recommendations as a view

`RECOMMENDATIONS_VIEW` cross-joins every catalog embedding to every user preference vector and returns the top-20 per user via `QUALIFY ROW_NUMBER()`. Because Snowflake materializes the Dynamic Tables incrementally, this view only runs against a small user subset per read.

## Latency and Cost Notes

| Stage | Cost profile |
|---|---|
| Embedding a new title | One-time cost per description (about $0.0006 per row at current `EMBED_TEXT_768` pricing) |
| Cortex Search query | Sub-second; billed as a managed service call |
| User preference Dynamic Table refresh | Runs per user per 10-minute window; warehouse scales horizontally |
| Recommendation read from view | Cross-join to 2,000 catalog rows per user: trivial at demo scale, warrants top-K filtering in production |

At the production target of 10M events/day across 10M titles, the embedding refresh is only triggered on the 2 to 5 percent of the catalog that changes weekly (~200K titles/week), keeping costs predictable.

## Cold-Start Story

Because embeddings come from the description text rather than watch history, a new title is ranked the moment it enters the catalog and the `REFRESH_CONTENT_EMBEDDINGS` procedure runs. The cold-start KPI (query Q3 in `04-analytics.sql`) shows the percentage of titles with embeddings but zero plays; in the demo scaffold this starts near 100 percent and converges as synthetic plays accumulate.

## Customer-Facing Extensions

Recommended customizations for a real engagement:

- Switch the embedding model to `multilingual-e5-large` or Solar-embeddings for Korean-language catalogs.
- Add a reranker using `SNOWFLAKE.CORTEX.COMPLETE` with a diversity-seeking prompt.
- Feed `RECOMMENDATION_FEEDBACK` into a supervised reranker trained with Snowpark ML.
- Split `USER_PREFERENCE_VECTOR` into short-term (last 5 plays) and long-term (trailing 90-day) to balance responsiveness vs stability.
