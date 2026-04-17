# ADR 001: Synthetic Data Approach

- **Status**: Accepted
- **Date**: 2026-04-17
- **Context lead**: Doeon Kim

## Context

A customer-facing Snowflake demo pack faces a data problem: where does the data come from?

Options considered:

1. **Real customer data**. Not an option in a public demo pack; would require NDA and create legal exposure.
2. **Public datasets** (Yelp reviews, MovieLens, etc.). Problem: each public dataset is biased toward one industry and doesn't give us breadth across 5 verticals.
3. **Deterministic synthetic data generators**. We build small Python generators that produce realistic-looking data with controlled parameters.
4. **Snowflake sample data** (`SNOWFLAKE_SAMPLE_DATA.TPCH_SF1` etc.). Doesn't cover PHI, sensor telemetry, or multi-channel retail at the shape we need.

## Decision

All five demos use **deterministic synthetic data generators** written in Python, seeded for reproducibility.

Generators live in `common/data_generators.py` for shared primitives (patient rows, transaction rows, sensor streams) and are called from each demo's `02-load-data.py`.

## Consequences

### Positive

- **Controlled scale**: we can generate 10K or 10M records with a single parameter change.
- **Reproducibility**: seeded generators produce byte-identical output run-to-run. Demos are reliable.
- **No licensing concerns**: the data doesn't exist before we generate it.
- **Realistic distributions**: generators match domain statistics (e.g., 0.8% fraud rate, 6-7% claim denial rate).
- **Cross-demo consistency**: the same patient IDs appear in encounter data, medication data, and claims data in the healthcare demo.

### Negative

- **Doesn't replicate real-world edge cases**: synthetic data has the distribution we give it, and customers' real data has long-tail oddities our generators don't produce.
- **Requires ongoing maintenance**: as Snowflake adds features and industries evolve, the generators need updates to stay representative.
- **Risk of over-neat results**: synthetic data can make demos look too clean and give the customer a false impression of their own data's quality.

### Mitigations

- Each demo's README includes a "What would be different with real data" section explicitly calling out the gap.
- Generators include optional noise parameters (e.g., `MISSING_RATE=0.03`) to roughen data where that's useful for a more realistic demo.
- A "customer-data-loader" pattern in `docs/customization-guide.md` documents how to swap synthetic for real data in a POC.

## Alternatives considered

### A. Pre-generated data files in the repo

**Rejected** because:
- Repo bloat (50K patient records × 200 bytes = 10MB; across 5 demos, 50-100MB checked in).
- Loses parameterization. Customer asks "what about at 10x scale?" and we'd have to regenerate and re-ship.

### B. Snowflake Sample Data only

**Rejected** because:
- No PHI-shaped data for the healthcare demo.
- No sensor telemetry for the manufacturing demo.
- Doesn't demonstrate Snowpipe Streaming (sample data is static).

### C. Open-source synthetic-data libraries (Faker, Mimesis, SDV)

**Partially accepted**. The generators use `faker` for string generation but wrap it in domain-specific logic. We don't use SDV (Synthetic Data Vault) because the added dependency is heavy for what we need.

## Measurement

Quality of synthetic data is measured by:

- Distribution fidelity: 0.8% fraud rate in the finance demo matches industry benchmarks.
- Referential integrity: every `patient_id` in `ENCOUNTERS` exists in `PATIENTS`.
- Temporal realism: encounter timestamps reflect realistic facility hours-of-operation patterns.
- Cross-demo consistency: a generator-produced `customer_id` in the retail demo has the same format as a generator-produced customer in the media demo (when they share schema).

## Related decisions

- ADR 002: Industry-to-Feature mapping (forthcoming) — constrains which Snowflake features each demo showcases.
- `common/data_generators.py` — implementation of this decision.
- `scripts/run_all.sh` — orchestrates generator invocation.
