"""Cortex LLM enrichment for the Retail demo.

(Filename kept consistent with the per-demo 7-file contract; the logic here is
call-center theme extraction, not fraud scoring.)

This script demonstrates two Cortex LLM Function patterns that retailers ask
for most often:

  1. `SNOWFLAKE.CORTEX.COMPLETE` with a bucketing prompt to classify free-text
     notes into a small controlled vocabulary.
  2. `SNOWFLAKE.CORTEX.SUMMARIZE` to produce a one-sentence synopsis per note.

In dry-run mode we generate stubbed output so the downstream analytics file
has rows to query without a live Cortex invocation.
"""

from __future__ import annotations

import logging
import os
import random
import sys
from pathlib import Path
from typing import Any

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from common.connection import LOG, get_session, is_dry_run  # noqa: E402

TARGET_DB = os.getenv("SNOWFLAKE_DATABASE", "SNOWFLAKE_DEMO_PACK")
TARGET_SCHEMA = "RETAIL"
CORTEX_MODEL = os.getenv("RETAIL_DEMO_CORTEX_MODEL", "mixtral-8x7b")

THEME_BUCKETS = [
    "BILLING",
    "SHIPPING",
    "PRODUCT_QUALITY",
    "CANCEL_INTENT",
    "LOYALTY_INQUIRY",
    "OTHER",
]


def _dry_run_enrich(n_notes: int = 50) -> pd.DataFrame:
    """Produce deterministic stub enrichment output."""
    rnd = random.Random(2026)
    rows: list[dict[str, Any]] = []
    for i in range(n_notes):
        rows.append(
            {
                "NOTE_ID": f"NOTE_STUB_{i:05d}",
                "CUSTOMER_ID": f"RCUST_STUB_{i % 25:04d}",
                "THEME": rnd.choice(THEME_BUCKETS),
                "SUMMARY": "Customer issue classified by dry-run stub for scaffold validation.",
                "MODEL_NAME": CORTEX_MODEL,
            }
        )
    return pd.DataFrame(rows)


def _run_cortex_enrichment(session: Any) -> int:
    """Enrich every row in CALL_CENTER_NOTES via Cortex COMPLETE + SUMMARIZE."""
    classify_prompt = (
        "Classify the following customer call note into exactly one of "
        f"{', '.join(THEME_BUCKETS)}. Reply with ONLY the category. "
        "Note: "
    )
    sql = f"""
        INSERT INTO {TARGET_DB}.{TARGET_SCHEMA}.CALL_CENTER_THEMES
            (NOTE_ID, CUSTOMER_ID, THEME, SUMMARY, MODEL_NAME)
        SELECT
            N.NOTE_ID,
            N.CUSTOMER_ID,
            TRIM(SNOWFLAKE.CORTEX.COMPLETE(
                '{CORTEX_MODEL}',
                CONCAT('{classify_prompt}', N.NOTE)
            )) AS THEME,
            SNOWFLAKE.CORTEX.SUMMARIZE(N.NOTE) AS SUMMARY,
            '{CORTEX_MODEL}' AS MODEL_NAME
        FROM {TARGET_DB}.{TARGET_SCHEMA}.CALL_CENTER_NOTES AS N
        LEFT JOIN {TARGET_DB}.{TARGET_SCHEMA}.CALL_CENTER_THEMES AS T
            ON T.NOTE_ID = N.NOTE_ID
        WHERE T.NOTE_ID IS NULL
    """
    result = session.sql(sql).collect()
    LOG.info("Cortex enrichment complete: %s rows processed", len(result))
    return len(result)


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
    LOG.info("Retail Cortex enricher: model=%s dry_run=%s", CORTEX_MODEL, is_dry_run())

    if is_dry_run():
        stub = _dry_run_enrich()
        LOG.info("Sample enrichment:\n%s", stub.head(5).to_string(index=False))
        LOG.info("Dry run complete. Would INSERT %s rows into CALL_CENTER_THEMES.", len(stub))
        return 0

    session = get_session(schema_override=TARGET_SCHEMA)
    try:
        _run_cortex_enrichment(session)
    finally:
        session.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
