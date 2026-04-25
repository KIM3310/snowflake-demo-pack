"""IoT telemetry loader for the Manufacturing demo.

Generates:
  - MACHINES dimension (100 rows, 3 sites, 5 lines).
  - SENSOR_TELEMETRY: 100 machines * 1440 minutes * 5 sensors = 720,000 rows at
    full scale. The default scaffolding size (24 hours, 1 read/min) keeps this
    at 144,000 rows for manageable credit usage; override via env vars.
  - FAILURE_HISTORY: labeled failure events aligned with the 5 "degrading"
    machines in the synthetic stream.
"""

from __future__ import annotations

import logging
import os
import random
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import pandas as pd  # noqa: E402

from common.connection import LOG, get_session, is_dry_run  # noqa: E402
from common.data_generators import generate_manufacturing_telemetry  # noqa: E402

N_MACHINES = int(os.getenv("MFG_DEMO_N_MACHINES", "100"))
HOURS = int(os.getenv("MFG_DEMO_HOURS", "24"))
READS_PER_MINUTE = int(os.getenv("MFG_DEMO_READS_PER_MIN", "1"))
DEGRADE_MACHINES = int(os.getenv("MFG_DEMO_DEGRADE_MACHINES", "5"))
TARGET_DB = os.getenv("SNOWFLAKE_DATABASE", "SNOWFLAKE_DEMO_PACK")
TARGET_SCHEMA = "MANUFACTURING"

FAILURE_MODES = [
    "BEARING_SEIZURE",
    "THERMAL_OVERLOAD",
    "PRESSURE_LEAK",
    "MOTOR_WINDING_SHORT",
    "SPINDLE_IMBALANCE",
]


def _build_machines(telemetry: pd.DataFrame) -> pd.DataFrame:
    rows = telemetry[["MACHINE_ID", "LINE_ID", "SITE"]].drop_duplicates().copy()
    rnd = random.Random(512)
    rows["MODEL_CODE"] = rows["LINE_ID"].apply(lambda line: f"MDL-{rnd.randint(100, 999)}")
    rows["COMMISSIONED_AT"] = rows["MACHINE_ID"].apply(
        lambda _: (datetime.now(UTC).date() - timedelta(days=rnd.randint(180, 3 * 365)))
    )
    rows["LAST_PM_AT"] = rows["MACHINE_ID"].apply(
        lambda _: (datetime.now(UTC).date() - timedelta(days=rnd.randint(7, 120)))
    )
    return rows


def _build_failure_history(machines: pd.DataFrame, degrade_machines: int) -> pd.DataFrame:
    rnd = random.Random(513)
    targets = machines.sample(n=min(degrade_machines, len(machines)), random_state=513)
    rows: list[dict[str, object]] = []
    for _, m in targets.iterrows():
        # Seed each degraded machine with 1-2 historical failures in the past 365 days.
        for _ in range(rnd.choice([1, 2])):
            rows.append(
                {
                    "MACHINE_ID": m["MACHINE_ID"],
                    "FAILURE_AT": datetime.now(UTC) - timedelta(days=rnd.randint(30, 365)),
                    "FAILURE_MODE": rnd.choice(FAILURE_MODES),
                    "DOWNTIME_MINUTES": round(rnd.uniform(30, 360), 1),
                    "REPAIR_COST_USD": round(rnd.uniform(800, 24_000), 2),
                }
            )
    return pd.DataFrame(rows)


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
    LOG.info(
        "Manufacturing loader: machines=%s hours=%s reads/min=%s degrade=%s dry_run=%s",
        N_MACHINES,
        HOURS,
        READS_PER_MINUTE,
        DEGRADE_MACHINES,
        is_dry_run(),
    )

    telemetry = generate_manufacturing_telemetry(
        n_machines=N_MACHINES,
        hours=HOURS,
        reads_per_minute=READS_PER_MINUTE,
        degrade_machines=DEGRADE_MACHINES,
    )
    machines = _build_machines(telemetry)
    failures = _build_failure_history(machines, DEGRADE_MACHINES)

    LOG.info("Sample telemetry row:\n%s", telemetry.head(2).to_string(index=False))
    LOG.info("Machines dimension size: %s", len(machines))
    LOG.info("Failure history size: %s", len(failures))

    if is_dry_run():
        LOG.info(
            "Dry run complete. Would load telemetry=%s machines=%s failures=%s into %s.%s.",
            len(telemetry),
            len(machines),
            len(failures),
            TARGET_DB,
            TARGET_SCHEMA,
        )
        return 0

    session = get_session(schema_override=TARGET_SCHEMA)
    try:
        for tbl in ("SENSOR_TELEMETRY", "MACHINES", "FAILURE_HISTORY"):
            session.sql(f"TRUNCATE TABLE {TARGET_DB}.{TARGET_SCHEMA}.{tbl}").collect()
        session.create_dataframe(machines).write.mode("append").save_as_table(
            f"{TARGET_DB}.{TARGET_SCHEMA}.MACHINES"
        )
        session.create_dataframe(telemetry).write.mode("append").save_as_table(
            f"{TARGET_DB}.{TARGET_SCHEMA}.SENSOR_TELEMETRY"
        )
        if not failures.empty:
            session.create_dataframe(failures).write.mode("append").save_as_table(
                f"{TARGET_DB}.{TARGET_SCHEMA}.FAILURE_HISTORY"
            )
        LOG.info(
            "Loaded telemetry=%s machines=%s failures=%s.",
            len(telemetry),
            len(machines),
            len(failures),
        )
    finally:
        session.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
