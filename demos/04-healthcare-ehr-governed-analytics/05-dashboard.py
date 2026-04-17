"""Cohort explorer for the Healthcare demo.

Unlike the other demos, this dashboard is explicitly designed to be run under
different roles to demonstrate policy inheritance. The top-right corner shows
the active role and the resulting row count; the charts update accordingly.
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

LOG = logging.getLogger("healthcare-dashboard")


def _get_session():  # noqa: ANN202
    try:
        from snowflake.snowpark.context import get_active_session  # type: ignore[import-not-found]

        return get_active_session()
    except Exception:  # noqa: BLE001
        from common.connection import get_session

        return get_session(schema_override="HEALTHCARE")


def _render() -> None:
    try:
        import pandas as pd
        import plotly.express as px
        import streamlit as st
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("Install `streamlit` and `plotly` via `make setup`.") from exc

    st.set_page_config(page_title="Cohort Explorer", layout="wide")
    st.title("Cohort Explorer")
    st.caption("Policy-bound view over SNOWFLAKE_DEMO_PACK.HEALTHCARE.ENCOUNTERS_SECURE")

    session = _get_session()

    # ---- Current role indicator ---------------------------------------
    try:
        role_row = session.sql("SELECT CURRENT_ROLE() AS R").to_pandas()
        current_role = str(role_row.iloc[0]["R"])
    except Exception as exc:  # noqa: BLE001
        LOG.warning("Cannot detect role: %s", exc)
        current_role = "DRY_RUN"

    st.info(f"Active role: {current_role}")

    # ---- Cohort summary -----------------------------------------------
    try:
        summary = session.sql(
            """
            SELECT
                COUNT(*) AS ENCOUNTERS,
                COUNT(DISTINCT PATIENT_PSEUDONYM) AS PATIENTS,
                ROUND(AVG(LENGTH_OF_STAY_DAYS), 2) AS AVG_LOS,
                ROUND(100.0 * AVG(CASE WHEN READMITTED_WITHIN_30D THEN 1 ELSE 0 END), 2) AS READMIT_RATE_PCT
            FROM ENCOUNTERS_SECURE
            """
        ).to_pandas()
    except Exception as exc:  # noqa: BLE001
        LOG.warning("Using stub summary: %s", exc)
        summary = pd.DataFrame([{"ENCOUNTERS": 5000, "PATIENTS": 1667, "AVG_LOS": 2.6, "READMIT_RATE_PCT": 11.9}])

    row = summary.iloc[0]
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Encounters", f"{int(row['ENCOUNTERS']):,}")
    c2.metric("Patients", f"{int(row['PATIENTS']):,}")
    c3.metric("Avg LOS (days)", f"{float(row['AVG_LOS']):.1f}")
    c4.metric("30d readmit rate", f"{float(row['READMIT_RATE_PCT']):.1f}%")

    # ---- Condition readmission chart ----------------------------------
    st.subheader("30-day readmission rate by primary condition")
    try:
        by_cond = session.sql(
            """
            SELECT
                PRIMARY_CONDITION,
                COUNT(*) AS ENCOUNTERS,
                ROUND(100.0 * AVG(CASE WHEN READMITTED_WITHIN_30D THEN 1 ELSE 0 END), 2) AS READMIT_RATE_PCT
            FROM ENCOUNTERS_SECURE
            GROUP BY PRIMARY_CONDITION
            ORDER BY READMIT_RATE_PCT DESC
            """
        ).to_pandas()
    except Exception as exc:  # noqa: BLE001
        LOG.warning("Using stub chart: %s", exc)
        by_cond = pd.DataFrame(
            {
                "PRIMARY_CONDITION": ["CHF", "COPD", "CAD", "TYPE_2_DIABETES", "HYPERTENSION"],
                "ENCOUNTERS": [420, 510, 395, 680, 920],
                "READMIT_RATE_PCT": [18.3, 15.1, 13.9, 11.2, 9.4],
            }
        )

    fig = px.bar(by_cond, x="PRIMARY_CONDITION", y="READMIT_RATE_PCT", hover_data=["ENCOUNTERS"])
    fig.update_layout(height=360, margin=dict(l=10, r=10, t=10, b=10))
    st.plotly_chart(fig, use_container_width=True)

    # ---- PHI sample ---------------------------------------------------
    st.subheader("Sample encounter rows as rendered under the active role")
    try:
        sample = session.sql(
            "SELECT ENCOUNTER_ID, PATIENT_PSEUDONYM, DEPARTMENT, REGION, BILLED_AMOUNT_USD "
            "FROM ENCOUNTERS_SECURE LIMIT 10"
        ).to_pandas()
    except Exception as exc:  # noqa: BLE001
        LOG.warning("Using stub sample: %s", exc)
        sample = pd.DataFrame(
            {
                "ENCOUNTER_ID": [f"ENC_STUB_{i:04d}" for i in range(5)],
                "PATIENT_PSEUDONYM": ["***MASKED***"] * 5,
                "DEPARTMENT": ["CARDIOLOGY"] * 5,
                "REGION": ["MIDWEST"] * 5,
                "BILLED_AMOUNT_USD": [7000, 12000, 9000, 15000, 8000],
            }
        )

    st.dataframe(sample, use_container_width=True, hide_index=True)

    st.caption(
        "Switch roles in Snowsight (USE ROLE CARDIOLOGY_ANALYST | REGIONAL_MIDWEST | DATA_ENGINEER_MASKED) "
        "and reload this page to see row filtering and column masking update automatically."
    )


if __name__ == "__main__":  # pragma: no cover
    logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
    if "streamlit" in os.environ.get("_", ""):
        _render()
    else:
        LOG.info("Run with `streamlit run`.")
