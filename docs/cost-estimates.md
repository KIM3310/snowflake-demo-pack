# Cost Estimates

Approximate Snowflake credit consumption per demo run.

## Methodology

Measurements taken on `X-Small` warehouse, US-East-1 commercial region, April 2026 Cortex pricing. Your actual consumption will vary with:

- Region (APAC typically 1.0-1.4x; EU typically 1.0-1.2x).
- Warehouse size (a larger warehouse finishes faster but costs more per second).
- Account edition (Standard lacks several features used here; Enterprise minimum).
- Cache warmth (repeat runs consume 30-60% less).
- Cloud service layer charges (Snowpipe, Cortex API calls have separate pricing).

## Per-demo consumption

| Demo | Warehouse credits | Cortex credits | Snowpipe credits | Total (approx) |
|------|-------------------|----------------|------------------|----------------|
| 01 Finance — Fraud Detection | 0.45 | 0.15 | 0.10 | **0.7 credits** |
| 02 Retail — Customer 360 | 0.75 | 0.25 | 0.10 | **1.1 credits** |
| 03 Manufacturing — Predictive Maintenance | 0.85 | 0.30 | 0.15 | **1.3 credits** |
| 04 Healthcare — Governed EHR | 0.35 | 0.00 | 0.15 | **0.5 credits** |
| 05 Media — Content Recommendation | 0.90 | 0.45 | 0.10 | **1.45 credits** |
| **All five sequentially (`make demo-all`)** | 3.30 | 1.15 | 0.60 | **≈5.05 credits** |

At $2/credit (list Enterprise US-East): approximately $10 total for a full end-to-end run of all 5 demos.

## Steady-state consumption (if left running)

Several demos include Dynamic Tables with target lag settings. Left running on an X-Small warehouse auto-resume, 24/7 consumption:

| Demo | Approximate daily credits (steady-state) |
|------|------------------------------------------|
| 01 Finance (60-sec DT lag) | 8-12 |
| 02 Retail (2-min DT lag) | 4-6 |
| 03 Manufacturing (1-min DT lag, 100 sensors) | 10-14 |
| 04 Healthcare (no DT, query-driven only) | < 0.5 |
| 05 Media (10-min DT lag) | 3-5 |

**Recommendation**: always run `make teardown` after a POC. Dynamic Tables left running accumulate material consumption.

## How these numbers were produced

Each demo's `04-analytics.sql` and `03-fraud-model.py` were run end-to-end 5 times; credits were pulled from:

```sql
SELECT
    QUERY_ID,
    WAREHOUSE_NAME,
    CREDITS_USED_CLOUD_SERVICES + CREDITS_USED AS TOTAL_CREDITS,
    QUERY_TEXT
FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
WHERE START_TIME >= DATEADD(hour, -24, CURRENT_TIMESTAMP())
  AND QUERY_TAG LIKE 'snowflake-demo-pack:%'
ORDER BY TOTAL_CREDITS DESC;
```

Each demo tags its queries via `ALTER SESSION SET QUERY_TAG = 'snowflake-demo-pack:<demo-name>'` so consumption can be attributed.

## What happens at customer scale

These estimates assume synthetic-data volumes. At customer scale:

- **Finance at 50M transactions/day** (10x synthetic): warehouse-hours scale approximately linearly for Dynamic Table refresh; Cortex `CLASSIFICATION` calls scale linearly with event count. Expect 7-10 credits/day steady-state.
- **Retail at 5M customers, 100M events/day**: bigger Dynamic Tables and more aggressive Cortex LLM enrichment of feedback text push steady-state toward 40-60 credits/day.
- **Manufacturing at 1,000 sensors/plant × 20 plants**: scale the Dynamic Table refresh budget roughly 20x; expect 200+ credits/day steady-state.
- **Healthcare at 500K patients, 2M encounters/year**: similar to demo — governance layer is query-driven, not refresh-driven. Steady-state negligible.
- **Media at 100M events/day**: vector embedding cost on catalog growth becomes the dominant line item. Expect 50-80 credits/day.

Customer-scale planning should be done with the Snowflake account team; these numbers are directional only.

## Optimization levers (in order of highest impact)

1. **Dynamic Table target lag**. Doubling the lag typically halves the refresh compute. 60-sec → 2-min on the finance demo cuts steady-state consumption by ~45%.
2. **Warehouse size and auto-suspend**. X-Small with 60-second auto-suspend is the default; tune up only if your lag targets demand it.
3. **Query-tag and isolate Cortex calls**. Cortex is separately priced; batching calls where possible reduces overhead.
4. **Iceberg vs native tables**. For cold data (rarely queried), Iceberg Tables shift storage cost to your cloud bucket at negligible query penalty.
5. **Caching**. Results cache and warehouse cache reduce repeat-run cost 30-60% — always warm the cache before a customer demo.

## What this pack does not do to control cost

- **Cross-region replication** is off. Enabling it roughly doubles storage cost; make a conscious decision.
- **Multi-cluster warehouse** is disabled. For steady-state high-concurrency workloads, enable it explicitly.
- **Query acceleration service** is off by default. It reduces query time for scan-heavy queries at a premium.

## References

- [Snowflake pricing](https://www.snowflake.com/pricing/)
- [Cortex function pricing](https://docs.snowflake.com/en/user-guide/snowflake-cortex/llm-functions#pricing)
- [Dynamic Table costs](https://docs.snowflake.com/en/user-guide/dynamic-tables-performance-guide)
- `QUERY_HISTORY` and `WAREHOUSE_METERING_HISTORY` for measurement
