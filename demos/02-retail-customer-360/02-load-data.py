"""Cross-channel customer-event loader for the Retail demo.

Loads three tables:
  - CUSTOMERS: master dimension (2,500 rows by default, 500,000 in production).
  - CUSTOMER_EVENTS: 10,000 events across 5 channels by default.
  - CALL_CENTER_NOTES: a small synthetic set for the Cortex enrichment step.
"""

from __future__ import annotations

import logging
import os
import random
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import pandas as pd  # noqa: E402

from common.connection import LOG, get_session, is_dry_run  # noqa: E402
from common.data_generators import (  # noqa: E402
    generate_retail_customers,
    generate_retail_events,
)

N_EVENTS = int(os.getenv("RETAIL_DEMO_N_EVENTS", "10000"))
N_CUSTOMERS = int(os.getenv("RETAIL_DEMO_N_CUSTOMERS", "2500"))
N_CALL_NOTES = int(os.getenv("RETAIL_DEMO_N_CALL_NOTES", "100"))
TARGET_DB = os.getenv("SNOWFLAKE_DATABASE", "SNOWFLAKE_DEMO_PACK")
TARGET_SCHEMA = "RETAIL"

CALL_NOTE_TEMPLATES = [
    "Customer called about a delayed shipment on order {sku}. Requests a delivery date update.",
    "Customer is unhappy with the packaging of product {sku}, arrived damaged. Wants a replacement.",
    "Customer reports duplicate charge on last month statement for {sku}; needs refund.",
    "Customer wants to cancel their subscription renewal. Cites price increase on {sku}.",
    "Customer asking if item {sku} is available in another size. Considering a switch.",
    "Customer dissatisfied with product quality of {sku}. Reports it broke within a week.",
    "Customer calling to confirm loyalty tier upgrade after latest purchase of {sku}.",
    "Customer wants to return {sku} but is outside the 30 day window; requests exception.",
]


def _make_call_notes(customers: pd.DataFrame, n: int) -> pd.DataFrame:
    rnd = random.Random(101)
    rows: list[dict[str, object]] = []
    for _ in range(n):
        row = customers.sample(n=1, random_state=rnd.randint(0, 10_000)).iloc[0]
        sku = f"SKU_{rnd.randint(1000, 9999)}"
        rows.append(
            {
                "CUSTOMER_ID": row["CUSTOMER_ID"],
                "AGENT_ID": f"AG_{rnd.randint(100, 250):03d}",
                "NOTE": rnd.choice(CALL_NOTE_TEMPLATES).format(sku=sku),
            }
        )
    return pd.DataFrame(rows)


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
    LOG.info(
        "Retail loader: events=%s customers=%s call_notes=%s dry_run=%s",
        N_EVENTS,
        N_CUSTOMERS,
        N_CALL_NOTES,
        is_dry_run(),
    )

    customers = generate_retail_customers(n_customers=N_CUSTOMERS)
    events = generate_retail_events(n_rows=N_EVENTS, n_customers=N_CUSTOMERS)
    call_notes = _make_call_notes(customers, N_CALL_NOTES)

    LOG.info("Sample customer:\n%s", customers.head(2).to_string(index=False))
    LOG.info("Sample event:\n%s", events.head(2).to_string(index=False))
    LOG.info("Sample call note:\n%s", call_notes.head(2).to_string(index=False))

    if is_dry_run():
        LOG.info(
            "Dry run complete. customers=%s events=%s call_notes=%s would be loaded into %s.%s.",
            len(customers),
            len(events),
            len(call_notes),
            TARGET_DB,
            TARGET_SCHEMA,
        )
        return 0

    session = get_session(schema_override=TARGET_SCHEMA)
    try:
        for tbl in ("CUSTOMERS", "CUSTOMER_EVENTS", "CALL_CENTER_NOTES", "CALL_CENTER_THEMES"):
            session.sql(f"TRUNCATE TABLE {TARGET_DB}.{TARGET_SCHEMA}.{tbl}").collect()

        session.create_dataframe(customers).write.mode("append").save_as_table(
            f"{TARGET_DB}.{TARGET_SCHEMA}.CUSTOMERS"
        )
        session.create_dataframe(events).write.mode("append").save_as_table(
            f"{TARGET_DB}.{TARGET_SCHEMA}.CUSTOMER_EVENTS"
        )
        session.create_dataframe(call_notes).write.mode("append").save_as_table(
            f"{TARGET_DB}.{TARGET_SCHEMA}.CALL_CENTER_NOTES"
        )
        LOG.info(
            "Loaded %s customers, %s events, %s call notes.",
            len(customers),
            len(events),
            len(call_notes),
        )
    finally:
        session.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
