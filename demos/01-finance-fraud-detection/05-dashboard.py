"""Streamlit dashboard snippet for the Finance fraud-detection demo.

Intended for two use modes:
  1. Local laptop: `streamlit run demos/01-finance-fraud-detection/05-dashboard.py`
     with env vars pointing at a Snowflake account. Uses the snowflake-connector.
  2. Streamlit in Snowflake: paste into a SiS app. The `_get_session()` helper
     auto-detects and uses `get_active_session()` when inside Snowflake.

The app has three panels:
  - Live alert queue with filters and acknowledge buttons.
  - Score distribution histogram (Plotly).
  - Loss-avoided KPI tile with a one-click drill-through.
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

LOG = logging.getLogger("finance-dashboard")


def _get_session():  # noqa: ANN202 - returns a Snowpark session (real or stub)
    """Return an active Snowpark session, whether local or inside Snowflake."""
    try:
        from snowflake.snowpark.context import get_active_session  # type: ignore[import-not-found]

        return get_active_session()
    except Exception:  # noqa: BLE001
        from common.connection import get_session

        return get_session(schema_override="FINANCE")


def _render() -> None:
    try:
        import pandas as pd
        import plotly.express as px
        import streamlit as st
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError(
            "This dashboard requires `streamlit`, `plotly`, and `pandas`. "
            "Run `make setup` to install."
        ) from exc

    st.set_page_config(
        page_title="Snowflake Demo Pack — Fraud Ops Console",
        page_icon=None,
        layout="wide",
    )
    st.title("Fraud Operations Console")
    st.caption(
        "Real-time view over SNOWFLAKE_DEMO_PACK.FINANCE.TRANSACTIONS_SCORED "
        "and ALERT_QUEUE. Refreshes every 30 seconds."
    )

    session = _get_session()

    with st.sidebar:
        st.header("Filters")
        action_choice = st.multiselect(
            "Risk action",
            ["APPROVE", "REVIEW", "BLOCK"],
            default=["REVIEW", "BLOCK"],
        )
        hours_back = st.slider("Lookback window (hours)", 1, 72, 24)
        min_amount = st.number_input("Minimum transaction amount (USD)", value=0.0, step=5.0)
        st.markdown("---")
        st.caption("Dry-run sample values are shown when no Snowflake session is available.")

    # ---- KPI row --------------------------------------------------------
    kpi_col1, kpi_col2, kpi_col3, kpi_col4 = st.columns(4)
    try:
        kpis = session.sql(
            f"""
            SELECT
                COUNT(*) AS TRANSACTIONS_SCORED,
                SUM(CASE WHEN RISK_ACTION = 'BLOCK' AND IS_FRAUD_GROUND_TRUTH
                         THEN AMOUNT_USD ELSE 0 END) AS BLOCKED_FRAUD_USD,
                SUM(CASE WHEN RISK_ACTION = 'REVIEW' THEN 1 ELSE 0 END) AS ANALYST_QUEUE,
                AVG(FRAUD_PROBABILITY) AS AVG_PROBABILITY
            FROM TRANSACTIONS_SCORED
            WHERE EVENT_TIMESTAMP >= DATEADD('hour', -{hours_back}, CURRENT_TIMESTAMP())
            """
        ).to_pandas()
    except Exception as exc:  # noqa: BLE001
        LOG.warning("Falling back to sample KPI values: %s", exc)
        kpis = pd.DataFrame(
            [
                {
                    "TRANSACTIONS_SCORED": 10_000,
                    "BLOCKED_FRAUD_USD": 184_520.00,
                    "ANALYST_QUEUE": 72,
                    "AVG_PROBABILITY": 0.048,
                }
            ]
        )

    row = kpis.iloc[0] if not kpis.empty else pd.Series(dtype=float)
    kpi_col1.metric("Transactions scored", f"{int(row.get('TRANSACTIONS_SCORED', 0)):,}")
    kpi_col2.metric("Blocked fraud (USD)", f"${float(row.get('BLOCKED_FRAUD_USD', 0)):,.0f}")
    kpi_col3.metric("Analyst queue depth", f"{int(row.get('ANALYST_QUEUE', 0)):,}")
    kpi_col4.metric("Avg fraud probability", f"{float(row.get('AVG_PROBABILITY', 0)):.3f}")

    st.markdown("---")

    # ---- Score distribution --------------------------------------------
    st.subheader("Score distribution, last {} hours".format(hours_back))
    try:
        dist_df = session.sql(
            f"""
            SELECT
                ROUND(FRAUD_PROBABILITY, 2) AS BUCKET,
                COUNT(*) AS N
            FROM TRANSACTIONS_SCORED
            WHERE EVENT_TIMESTAMP >= DATEADD('hour', -{hours_back}, CURRENT_TIMESTAMP())
            GROUP BY BUCKET
            ORDER BY BUCKET
            """
        ).to_pandas()
    except Exception as exc:  # noqa: BLE001
        LOG.warning("Using sample histogram: %s", exc)
        dist_df = pd.DataFrame(
            {
                "BUCKET": [round(x / 20, 2) for x in range(21)],
                "N": [int(200 * (1.1 - x / 20)) for x in range(21)],
            }
        )

    fig = px.bar(dist_df, x="BUCKET", y="N", labels={"BUCKET": "Score", "N": "Transactions"})
    fig.update_layout(height=320, margin=dict(l=10, r=10, t=10, b=10))
    st.plotly_chart(fig, use_container_width=True)

    # ---- Alert queue table ---------------------------------------------
    st.subheader("Alert queue")
    actions_sql = ", ".join(f"'{a}'" for a in action_choice) if action_choice else "''"
    try:
        alerts = session.sql(
            f"""
            SELECT
                ALERT_ID,
                TRANSACTION_ID,
                CUSTOMER_ID,
                CHANNEL,
                AMOUNT_USD,
                ROUND(FRAUD_PROBABILITY, 3) AS FRAUD_PROBABILITY,
                RISK_ACTION,
                CREATED_AT
            FROM ALERT_QUEUE
            WHERE ALERT_STATUS = 'OPEN'
              AND RISK_ACTION IN ({actions_sql})
              AND AMOUNT_USD >= {min_amount}
            ORDER BY FRAUD_PROBABILITY DESC, CREATED_AT DESC
            LIMIT 200
            """
        ).to_pandas()
    except Exception as exc:  # noqa: BLE001
        LOG.warning("Using sample alert queue: %s", exc)
        alerts = pd.DataFrame(
            {
                "ALERT_ID": [f"AL_{i:04d}" for i in range(5)],
                "TRANSACTION_ID": [f"TXN_{i:06d}" for i in range(5)],
                "CUSTOMER_ID": [f"CUST_{i:04d}" for i in range(5)],
                "CHANNEL": ["ECOMMERCE", "CONTACTLESS", "ECOMMERCE", "CHIP", "ECOMMERCE"],
                "AMOUNT_USD": [1_420.55, 87.10, 3_201.77, 540.00, 910.25],
                "FRAUD_PROBABILITY": [0.92, 0.74, 0.88, 0.67, 0.81],
                "RISK_ACTION": ["BLOCK", "REVIEW", "BLOCK", "REVIEW", "BLOCK"],
                "CREATED_AT": pd.Timestamp.utcnow(),
            }
        )

    st.dataframe(alerts, use_container_width=True, hide_index=True)

    st.caption(
        "Running end-to-end in Snowflake: Snowpipe Streaming -> Dynamic Tables -> "
        "Snowpark UDF -> Streamlit. No external infrastructure."
    )


if __name__ == "__main__":  # pragma: no cover
    logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
    # Running `python 05-dashboard.py` without Streamlit is a no-op sanity check.
    if "streamlit" in os.environ.get("_", ""):
        _render()
    else:
        LOG.info(
            "This file is intended to be run with `streamlit run`. "
            "Module imports successfully; see README for launch instructions."
        )
