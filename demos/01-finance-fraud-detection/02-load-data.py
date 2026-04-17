"""Synthetic transaction stream loader for the Finance demo.

Responsibilities:
  1. Generate 10,000 synthetic authorization events with a controlled fraud
     rate using `common.data_generators.generate_finance_transactions`.
  2. In dry-run mode, log the row count and a preview slice (no network I/O).
  3. In live mode, write the rows to `FINANCE.TRANSACTIONS_RAW` via Snowpark
     (or the snowflake-connector-python bulk path as fallback).
  4. Populate `FINANCE.TRANSACTIONS_LABELED` with 70 percent of the rows so
     the Cortex CLASSIFICATION training step has a starting corpus.

The loader is idempotent across runs: we always TRUNCATE the target tables
first. In a real customer setting you would replace this with Snowpipe
Streaming via the Java SDK.
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from common.connection import LOG, get_session, is_dry_run  # noqa: E402
from common.data_generators import generate_finance_transactions  # noqa: E402

N_ROWS = int(os.getenv("FINANCE_DEMO_N_ROWS", "10000"))
N_CUSTOMERS = int(os.getenv("FINANCE_DEMO_N_CUSTOMERS", "2000"))
FRAUD_RATE = float(os.getenv("FINANCE_DEMO_FRAUD_RATE", "0.008"))
TARGET_DB = os.getenv("SNOWFLAKE_DATABASE", "SNOWFLAKE_DEMO_PACK")
TARGET_SCHEMA = "FINANCE"


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
    LOG.info(
        "Finance loader: n_rows=%s n_customers=%s fraud_rate=%s dry_run=%s",
        N_ROWS,
        N_CUSTOMERS,
        FRAUD_RATE,
        is_dry_run(),
    )

    df = generate_finance_transactions(
        n_rows=N_ROWS,
        n_customers=N_CUSTOMERS,
        fraud_rate=FRAUD_RATE,
    )

    LOG.info("Sample preview:\n%s", df.head(3).to_string(index=False))

    if is_dry_run():
        LOG.info(
            "Dry run complete. %s rows would be inserted into %s.%s.TRANSACTIONS_RAW.",
            len(df),
            TARGET_DB,
            TARGET_SCHEMA,
        )
        return 0

    session = get_session(schema_override=TARGET_SCHEMA)
    try:
        # TRUNCATE for idempotency; use TRUNCATE not DELETE for a cheaper reset.
        session.sql(f"TRUNCATE TABLE {TARGET_DB}.{TARGET_SCHEMA}.TRANSACTIONS_RAW").collect()
        session.sql(f"TRUNCATE TABLE {TARGET_DB}.{TARGET_SCHEMA}.TRANSACTIONS_LABELED").collect()

        # Snowpark write path handles pandas → Snowflake bulk ingest via PUT+COPY.
        sdf = session.create_dataframe(df)
        sdf.write.mode("append").save_as_table(
            f"{TARGET_DB}.{TARGET_SCHEMA}.TRANSACTIONS_RAW"
        )

        # Training set: the 70 percent of rows with a non-null ground truth label.
        label_cutoff = int(len(df) * 0.7)
        label_df = df.head(label_cutoff)
        label_sdf = session.create_dataframe(label_df)
        label_sdf.write.mode("append").save_as_table(
            f"{TARGET_DB}.{TARGET_SCHEMA}.TRANSACTIONS_LABELED"
        )

        LOG.info(
            "Loaded %s rows into TRANSACTIONS_RAW, %s into TRANSACTIONS_LABELED.",
            len(df),
            label_cutoff,
        )
    finally:
        session.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
