"""Streamlit plant-floor dashboard for the Manufacturing demo.

Three panels:
  - Line status grid (color-coded by risk band).
  - Trend chart for a selected machine.
  - Alert history for the last 24 hours.
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

LOG = logging.getLogger("mfg-dashboard")


def _get_session():  # noqa: ANN202
    try:
        from snowflake.snowpark.context import get_active_session  # type: ignore[import-not-found]

        return get_active_session()
    except Exception:  # noqa: BLE001
        from common.connection import get_session

        return get_session(schema_override="MANUFACTURING")


def _render() -> None:
    try:
        import pandas as pd
        import plotly.express as px
        import streamlit as st
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("Install `streamlit` and `plotly` via `make setup`.") from exc

    st.set_page_config(page_title="Plant Floor — Machine Health", layout="wide")
    st.title("Plant Floor — Machine Health")
    st.caption("Real-time scoring from SNOWFLAKE_DEMO_PACK.MANUFACTURING.MACHINE_HEALTH_SCORE")

    session = _get_session()

    # ---- Risk heatmap --------------------------------------------------
    try:
        heat = session.sql(
            """
            SELECT SITE, LINE_ID, MACHINE_ID,
                   ROUND(RISK_SCORE, 3) AS RISK_SCORE,
                   LAST_SCORED_AT
            FROM MACHINE_HEALTH_SCORE
            ORDER BY SITE, LINE_ID, MACHINE_ID
            """
        ).to_pandas()
    except Exception as exc:  # noqa: BLE001
        LOG.warning("Using stub risk table: %s", exc)
        heat = pd.DataFrame(
            {
                "SITE": ["ULSAN"] * 8 + ["BUSAN"] * 8,
                "LINE_ID": sum(([f"LINE-{i}"] * 4 for i in range(1, 3)), []) * 2,
                "MACHINE_ID": [f"MCH_STUB_{i:03d}" for i in range(16)],
                "RISK_SCORE": [0.12, 0.18, 0.44, 0.87, 0.33, 0.21, 0.93, 0.61] * 2,
            }
        )

    st.subheader("Risk heatmap")
    fig = px.scatter(
        heat,
        x="LINE_ID",
        y="SITE",
        size="RISK_SCORE",
        color="RISK_SCORE",
        color_continuous_scale="RdYlGn_r",
        hover_data=["MACHINE_ID", "RISK_SCORE"],
        size_max=40,
    )
    fig.update_layout(height=380, margin=dict(l=10, r=10, t=10, b=10))
    st.plotly_chart(fig, use_container_width=True)

    # ---- Per-machine trend --------------------------------------------
    machine = st.selectbox("Pick a machine to trend", heat["MACHINE_ID"].tolist())
    try:
        trend = session.sql(
            f"""
            SELECT DATE_TRUNC('minute', RECORDED_AT) AS MINUTE,
                   SENSOR_TYPE,
                   AVG(VALUE) AS VALUE
            FROM SENSOR_TELEMETRY
            WHERE MACHINE_ID = '{machine}'
              AND RECORDED_AT >= DATEADD('hour', -12, CURRENT_TIMESTAMP())
            GROUP BY MINUTE, SENSOR_TYPE
            ORDER BY MINUTE
            """
        ).to_pandas()
    except Exception as exc:  # noqa: BLE001
        LOG.warning("Using stub trend: %s", exc)
        trend = pd.DataFrame(
            {
                "MINUTE": pd.date_range(end="now", periods=60, freq="min"),
                "SENSOR_TYPE": ["VIBRATION"] * 30 + ["TEMPERATURE"] * 30,
                "VALUE": [0.35 + i * 0.01 for i in range(30)] + [68.0 + i * 0.1 for i in range(30)],
            }
        )

    st.subheader(f"12-hour sensor trend for {machine}")
    fig2 = px.line(trend, x="MINUTE", y="VALUE", color="SENSOR_TYPE")
    fig2.update_layout(height=360, margin=dict(l=10, r=10, t=10, b=10))
    st.plotly_chart(fig2, use_container_width=True)

    # ---- Alert history -------------------------------------------------
    st.subheader("Recent alert candidates (risk >= 0.8)")
    try:
        alerts = session.sql(
            """
            SELECT MACHINE_ID, LINE_ID, SITE,
                   ROUND(RISK_SCORE, 3) AS RISK_SCORE,
                   LAST_SCORED_AT
            FROM MACHINE_HEALTH_SCORE
            WHERE RISK_SCORE >= 0.8
              AND LAST_SCORED_AT >= DATEADD('hour', -24, CURRENT_TIMESTAMP())
            ORDER BY RISK_SCORE DESC
            """
        ).to_pandas()
    except Exception as exc:  # noqa: BLE001
        LOG.warning("Using stub alerts: %s", exc)
        alerts = pd.DataFrame(
            {
                "MACHINE_ID": [f"MCH_STUB_{i:03d}" for i in range(3)],
                "LINE_ID": ["LINE-1", "LINE-2", "LINE-3"],
                "SITE": ["ULSAN", "ULSAN", "BUSAN"],
                "RISK_SCORE": [0.91, 0.88, 0.85],
                "LAST_SCORED_AT": pd.Timestamp.utcnow(),
            }
        )

    st.dataframe(alerts, use_container_width=True, hide_index=True)


if __name__ == "__main__":  # pragma: no cover
    logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
    if "streamlit" in os.environ.get("_", ""):
        _render()
    else:
        LOG.info("Run with `streamlit run`.")
