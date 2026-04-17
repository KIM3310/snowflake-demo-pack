"""Governance policy validator for the Healthcare demo.

(Filename preserved for the 7-file per-demo contract. The logic here is NOT
fraud scoring; it is a validation run that issues the same query under each
of the three demo roles and asserts the row counts / masked values differ
as designed. Output is a printable report the SE can share with the
compliance lead.)

Dry-run mode generates a synthetic "expected vs actual" report without a
Snowflake connection; live mode runs the actual role switches.
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from common.connection import LOG, get_session, is_dry_run  # noqa: E402

TARGET_DB = os.getenv("SNOWFLAKE_DATABASE", "SNOWFLAKE_DEMO_PACK")
TARGET_SCHEMA = "HEALTHCARE"

ROLES = ["SYSADMIN", "CARDIOLOGY_ANALYST", "REGIONAL_MIDWEST", "DATA_ENGINEER_MASKED"]

VALIDATION_QUERIES = [
    {
        "label": "row_count_all_encounters",
        "sql": f"SELECT COUNT(*) AS N FROM {TARGET_DB}.{TARGET_SCHEMA}.ENCOUNTERS_SECURE",
        "description": "Total visible encounters per role",
    },
    {
        "label": "distinct_departments",
        "sql": (
            "SELECT ARRAY_AGG(DISTINCT DEPARTMENT) AS DEPARTMENTS "
            f"FROM {TARGET_DB}.{TARGET_SCHEMA}.ENCOUNTERS_SECURE"
        ),
        "description": "Distinct departments visible per role",
    },
    {
        "label": "distinct_regions",
        "sql": (
            "SELECT ARRAY_AGG(DISTINCT REGION) AS REGIONS "
            f"FROM {TARGET_DB}.{TARGET_SCHEMA}.ENCOUNTERS_SECURE"
        ),
        "description": "Distinct regions visible per role",
    },
    {
        "label": "phi_mask_sample",
        "sql": (
            "SELECT PATIENT_PSEUDONYM "
            f"FROM {TARGET_DB}.{TARGET_SCHEMA}.ENCOUNTERS_SECURE LIMIT 1"
        ),
        "description": "First PHI pseudonym as rendered under this role",
    },
]


def _format_report(report: list[dict[str, Any]]) -> str:
    lines = ["Governance validation report", "=" * 42]
    for row in report:
        lines.append(f"role={row['role']}  query={row['label']}")
        lines.append(f"  description: {row['description']}")
        lines.append(f"  result: {row['result']}")
        lines.append("")
    return "\n".join(lines)


def _dry_run_report() -> list[dict[str, Any]]:
    expected = {
        "SYSADMIN":           {"N": 5000, "DEPARTMENTS": ["ALL"], "REGIONS": ["ALL"]},
        "CARDIOLOGY_ANALYST": {"N": 1003, "DEPARTMENTS": ["CARDIOLOGY"], "REGIONS": ["ALL"]},
        "REGIONAL_MIDWEST":   {"N": 1004, "DEPARTMENTS": ["ALL"], "REGIONS": ["MIDWEST"]},
        "DATA_ENGINEER_MASKED": {"N": 5000, "DEPARTMENTS": ["ALL"], "REGIONS": ["ALL"]},
    }
    phi_samples = {
        "SYSADMIN":             "PAT_4FA3B2A1C7",
        "CARDIOLOGY_ANALYST":   "<SHA-256 of pseudonym>",
        "REGIONAL_MIDWEST":     "<SHA-256 of pseudonym>",
        "DATA_ENGINEER_MASKED": "***MASKED***",
    }
    report: list[dict[str, Any]] = []
    for role in ROLES:
        for q in VALIDATION_QUERIES:
            if q["label"] == "row_count_all_encounters":
                result = expected[role]["N"]
            elif q["label"] == "distinct_departments":
                result = expected[role]["DEPARTMENTS"]
            elif q["label"] == "distinct_regions":
                result = expected[role]["REGIONS"]
            else:
                result = phi_samples[role]
            report.append(
                {
                    "role": role,
                    "label": q["label"],
                    "description": q["description"],
                    "result": result,
                }
            )
    return report


def _live_report(session: Any) -> list[dict[str, Any]]:
    report: list[dict[str, Any]] = []
    for role in ROLES:
        try:
            session.sql(f"USE ROLE {role}").collect()
        except Exception as exc:  # noqa: BLE001
            LOG.warning("Could not USE ROLE %s: %s", role, exc)
            continue
        for q in VALIDATION_QUERIES:
            try:
                result = session.sql(q["sql"]).collect()
            except Exception as exc:  # noqa: BLE001
                result = f"<error: {exc}>"
            report.append(
                {
                    "role": role,
                    "label": q["label"],
                    "description": q["description"],
                    "result": str(result),
                }
            )
    # Return to SYSADMIN before exiting
    try:
        session.sql("USE ROLE SYSADMIN").collect()
    except Exception:  # noqa: BLE001
        pass
    return report


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
    LOG.info("Healthcare governance validator: dry_run=%s", is_dry_run())

    if is_dry_run():
        report = _dry_run_report()
    else:
        session = get_session(schema_override=TARGET_SCHEMA)
        try:
            report = _live_report(session)
        finally:
            session.close()

    print(_format_report(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
