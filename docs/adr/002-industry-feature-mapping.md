# ADR 002: Industry-to-Feature Mapping

- **Status**: Accepted
- **Date**: 2026-04-17
- **Context lead**: Doeon Kim

## Context

A demo pack with five industry verticals and limited SE-call time must make a choice: does each demo showcase the same Snowflake features, or does each demo focus on a feature set?

Option A — **Uniform feature coverage**: each demo uses a similar set of core features (Snowpipe, Dynamic Tables, Streamlit). This makes the demos look similar and comparable.

Option B — **Feature specialization per industry**: each demo showcases features particularly well-suited to that industry's pain. This makes the pack as a whole cover more of Snowflake's surface area.

## Decision

We adopt **Option B**: feature specialization. Each demo is mapped to a distinct combination of headline Snowflake features chosen to match that industry's characteristic pain.

The mapping:

| Demo | Headline feature combination | Why this mapping |
|------|------------------------------|-------------------|
| 01 Finance — Fraud Detection | Dynamic Tables + Snowpark UDF + Cortex CLASSIFICATION + Streaming | Fraud is a streaming-first, feature-rich ML problem. Dynamic Tables solve feature freshness; Cortex provides a managed second opinion. |
| 02 Retail — Customer 360 | Snowpipe Streaming + Iceberg + Secure Data Sharing + Cortex LLM | Retail is multi-channel (streaming ingest), has archival behavior (Iceberg), and partner sharing (data sharing). LLM handles unstructured feedback. |
| 03 Manufacturing — Predictive Maintenance | Streams + Tasks + Snowpark ML + Alerts + Native Apps | Manufacturing is IoT-telemetry-heavy (streams+tasks for feature pipeline) and needs packaging-for-OEM-partners (Native Apps). |
| 04 Healthcare — Governed EHR | Row Access Policies + Dynamic Data Masking + Tag-Based Masking + Secure Views + Access History | Healthcare is governance-first. The demo's value is the governance substrate; ML is not the primary story. |
| 05 Media — Content Recommendation | VECTOR type + Cortex Search + Cortex EMBED_TEXT + Streamlit in Snowflake | Media rec problems are embeddings-first. Vector type + Cortex Search is the differentiator vs standalone vector DBs. |

Across the five demos, the pack covers:

- Streaming: Snowpipe Streaming, Streams
- Orchestration: Tasks, Dynamic Tables
- ML/AI: Snowpark UDFs, Snowpark ML, Cortex CLASSIFICATION, Cortex EMBED_TEXT, Cortex Search, Cortex COMPLETE
- Governance: Row Access Policies, Dynamic Data Masking, Tag-Based Masking, Secure Views, Access History
- Data formats: native tables, Iceberg Tables, VECTOR type
- Packaging: Native Apps, Secure Data Sharing
- UI: Streamlit in Snowflake

This breadth means the full pack exercises most of Snowflake's feature surface that SEs need to demo.

## Consequences

### Positive

- **Feature breadth across the pack**: an SE running all five demos exercises the vast majority of Snowflake's features.
- **Each demo feels industry-native**: customers see a demo that reflects their sector's priorities, not a generic walkthrough.
- **Cross-demo learning for SEs**: working through the five demos builds deep familiarity across the full Snowflake surface.
- **Competitive differentiation per industry**: the specific feature chosen for each demo is one a competitor would struggle to match (e.g., Native Apps for manufacturing IoT packaging).

### Negative

- **Customers can't easily compare**: if a retail customer also asks about healthcare governance, they can't see it in the retail demo. They'd have to see the healthcare demo too.
- **Feature coverage is not symmetric**: some features (like Tag-Based Masking) appear prominently in only one demo. An SE who only runs one demo has uneven Snowflake fluency.
- **Higher per-demo learning curve**: SEs must learn five distinct feature sets rather than one.

### Mitigations

- The **presentation pitch scripts** (`presentations/*-5min-pitch.md`) cross-reference other demos when relevant objections arise. A finance customer asking about governance is pointed to the healthcare patterns.
- **Onboarding sequence for new SEs**: recommend running all five demos in sequence as a learning exercise. Documented in `docs/how-to-use.md`.
- **Feature matrix in root README**: a table showing which feature appears in which demo lets customers and SEs see coverage at a glance.

## Alternatives considered

### Option A — Uniform feature coverage

Rejected. The resulting demos would have:
- Repetitive architecture diagrams (five mermaid graphs that look nearly identical).
- Weak industry-specific storytelling (every demo would showcase the same features, making it feel generic).
- Limited breadth (less opportunity to demonstrate the full Snowflake surface area across the pack).

### Option C — Feature-per-demo instead of industry-per-demo

(e.g., `demos/01-dynamic-tables`, `demos/02-row-access-policy`, etc.)

Rejected because:
- SEs operate industry-first (they're in a conversation with a retail CTO, not with a DBA).
- Removes the value-case narrative that makes demos customer-ready.
- Turns the pack into a documentation alternative rather than a customer-facing artifact.

## How this ADR constrains future work

- **New industry added to the pack**: must declare its distinct feature combination and justify why that combination matches the industry. No two demos should share the same headline feature set.
- **New feature to demonstrate**: identify which industry has the most natural fit; expand that demo rather than create a standalone demo.
- **Customer-specific POC**: start from the industry demo closest to their vertical; customize features as needed.

## Measurement

Success of this mapping is measured by:

- SE feedback: do customers react to the industry-native framing vs. a generic demo?
- Conversion: do demos-to-POC conversion rates differ across the five demos?
- Feature coverage: do the 5 demos collectively cover 80%+ of Snowflake's demo-relevant features?

## Related decisions

- ADR 001: Synthetic Data Approach — enables per-industry data realism.
- Each demo's `README.md` — restates the feature mapping in customer language.
- `presentations/*-5min-pitch.md` — operationalize the mapping in delivery.
