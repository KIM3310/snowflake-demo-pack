"""Healthcare EHR data loader.

Loads:
  - PATIENT_ENCOUNTERS: 5,000 synthetic de-identified rows (50,000 at full scale).
  - BILLING_CLAIMS: one claim per encounter, with payer and capitation metadata.

The patient pseudonym is the only identifying field, and it is already a
SHA-style surrogate produced by the data generator. No actual PHI is
materialized.
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
from common.data_generators import generate_healthcare_records  # noqa: E402

N_ROWS = int(os.getenv("HEALTHCARE_DEMO_N_ROWS", "5000"))
TARGET_DB = os.getenv("SNOWFLAKE_DATABASE", "SNOWFLAKE_DEMO_PACK")
TARGET_SCHEMA = "HEALTHCARE"

PAYERS = [
    ("BCBS_IL", 0.28, 12_500),
    ("AETNA", 0.18, 10_800),
    ("UNITED", 0.20, 11_200),
    ("MEDICARE_FEE_FOR_SERVICE", 0.25, 0),
    ("MEDICAID_STATE_A", 0.07, 0),
    ("SELF_PAY", 0.02, 0),
]
CLAIM_STATUSES = ["PAID", "PAID", "PAID", "PENDING", "DENIED", "APPEAL"]


def _make_claims(encounters: pd.DataFrame) -> pd.DataFrame:
    rnd = random.Random(2026)
    rows: list[dict[str, object]] = []
    for _, enc in encounters.iterrows():
        payer_name, _, capitation = rnd.choices(
            PAYERS, weights=[p[1] for p in PAYERS]
        )[0]
        allowed = float(enc["BILLED_AMOUNT_USD"]) * rnd.uniform(0.45, 0.9)
        status = rnd.choice(CLAIM_STATUSES)
        rows.append(
            {
                "ENCOUNTER_ID": enc["ENCOUNTER_ID"],
                "PATIENT_PSEUDONYM": enc["PATIENT_PSEUDONYM"],
                "PAYER": payer_name,
                "BILLED_AMOUNT_USD": enc["BILLED_AMOUNT_USD"],
                "ALLOWED_AMOUNT_USD": round(allowed, 2),
                "CONTRACT_CAPITATION_USD": capitation,
                "CLAIM_STATUS": status,
            }
        )
    return pd.DataFrame(rows)


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
    LOG.info("Healthcare loader: n_rows=%s dry_run=%s", N_ROWS, is_dry_run())

    encounters = generate_healthcare_records(n_rows=N_ROWS)
    claims = _make_claims(encounters)

    LOG.info("Sample encounter:\n%s", encounters.head(2).to_string(index=False))
    LOG.info("Sample claim:\n%s", claims.head(2).to_string(index=False))

    if is_dry_run():
        LOG.info(
            "Dry run complete. encounters=%s claims=%s would be loaded into %s.%s.",
            len(encounters),
            len(claims),
            TARGET_DB,
            TARGET_SCHEMA,
        )
        return 0

    session = get_session(schema_override=TARGET_SCHEMA)
    try:
        for tbl in ("PATIENT_ENCOUNTERS", "BILLING_CLAIMS"):
            session.sql(f"TRUNCATE TABLE {TARGET_DB}.{TARGET_SCHEMA}.{tbl}").collect()
        session.create_dataframe(encounters).write.mode("append").save_as_table(
            f"{TARGET_DB}.{TARGET_SCHEMA}.PATIENT_ENCOUNTERS"
        )
        session.create_dataframe(claims).write.mode("append").save_as_table(
            f"{TARGET_DB}.{TARGET_SCHEMA}.BILLING_CLAIMS"
        )
        LOG.info("Loaded encounters=%s claims=%s.", len(encounters), len(claims))
    finally:
        session.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
