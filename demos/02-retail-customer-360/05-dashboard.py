"""Streamlit customer-360 timeline app for the Retail demo.

Three panels:
  - Customer picker with summary card (segment, tier, LTV).
  - Channel-touch Sankey: web -> app -> POS transitions in the last 90 days.
  - Timeline view of the most recent 20 events across all channels.
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

LOG = logging.getLogger("retail-dashboard")


def _get_session():  # noqa: ANN202
    try:
        from snowflake.snowpark.context import get_active_session  # type: ignore[import-not-found]

        return get_active_session()
    except Exception:  # noqa: BLE001
        from common.connection import get_session

        return get_session(schema_override="RETAIL")


def _render() -> None:
    try:
        import pandas as pd
        import plotly.graph_objects as go
        import streamlit as st
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError(
            "Install `streamlit` and `plotly` via `make setup` to run this file."
        ) from exc

    st.set_page_config(page_title="Customer 360 Timeline", layout="wide")
    st.title("Customer 360 Timeline")
    st.caption("Backed by SNOWFLAKE_DEMO_PACK.RETAIL.CUSTOMER_360_VIEW")

    session = _get_session()

    # ---- Customer picker ----------------------------------------------
    try:
        ids = session.sql(
            "SELECT CUSTOMER_ID FROM RETAIL.CUSTOMERS ORDER BY CUSTOMER_ID LIMIT 500"
        ).to_pandas()
    except Exception as exc:  # noqa: BLE001
        LOG.warning("Falling back to stub customer list: %s", exc)
        ids = pd.DataFrame({"CUSTOMER_ID": [f"RCUST_STUB_{i:04d}" for i in range(20)]})

    customer_id = st.selectbox(
        "Customer",
        ids["CUSTOMER_ID"].tolist(),
        index=0,
        help="Shows the full 360 profile for the selected customer.",
    )

    # ---- Summary card --------------------------------------------------
    try:
        profile = session.sql(
            f"SELECT * FROM RETAIL.CUSTOMER_360_VIEW WHERE CUSTOMER_ID = '{customer_id}'"
        ).to_pandas()
    except Exception as exc:  # noqa: BLE001
        LOG.warning("Using stub profile: %s", exc)
        profile = pd.DataFrame(
            [
                {
                    "CUSTOMER_ID": customer_id,
                    "SEGMENT": "LOYAL",
                    "LOYALTY_TIER": "GOLD",
                    "LIFETIME_VALUE_USD": 1_842.55,
                    "DAYS_SINCE_LAST_EVENT": 4,
                    "EVENT_COUNT_90D": 62,
                    "GROSS_SPEND_90D": 540.22,
                    "CHANNELS_USED_90D": 3,
                }
            ]
        )

    if not profile.empty:
        row = profile.iloc[0]
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Segment", str(row.get("SEGMENT", "-")))
        c2.metric("Loyalty tier", str(row.get("LOYALTY_TIER", "-")))
        c3.metric("Lifetime value", f"${float(row.get('LIFETIME_VALUE_USD', 0)):,.0f}")
        c4.metric("Channels used, 90d", int(row.get("CHANNELS_USED_90D", 0)))

    # ---- Channel transition Sankey ------------------------------------
    st.subheader("Channel transitions, last 90 days")
    try:
        transitions = session.sql(
            f"""
            WITH ORDERED AS (
                SELECT
                    CUSTOMER_ID,
                    CHANNEL,
                    EVENT_TIMESTAMP,
                    LAG(CHANNEL) OVER (
                        PARTITION BY CUSTOMER_ID ORDER BY EVENT_TIMESTAMP
                    ) AS PREV_CHANNEL
                FROM RETAIL.CUSTOMER_EVENTS
                WHERE CUSTOMER_ID = '{customer_id}'
                  AND EVENT_TIMESTAMP >= DATEADD('day', -90, CURRENT_TIMESTAMP())
            )
            SELECT
                PREV_CHANNEL,
                CHANNEL,
                COUNT(*) AS N
            FROM ORDERED
            WHERE PREV_CHANNEL IS NOT NULL AND PREV_CHANNEL != CHANNEL
            GROUP BY PREV_CHANNEL, CHANNEL
            """
        ).to_pandas()
    except Exception as exc:  # noqa: BLE001
        LOG.warning("Using stub transitions: %s", exc)
        transitions = pd.DataFrame(
            {
                "PREV_CHANNEL": ["WEB", "WEB", "MOBILE_APP", "POS", "CALL_CENTER"],
                "CHANNEL": ["MOBILE_APP", "POS", "POS", "WEB", "WEB"],
                "N": [9, 4, 7, 3, 2],
            }
        )

    if not transitions.empty:
        labels = sorted(set(transitions["PREV_CHANNEL"]).union(transitions["CHANNEL"]))
        idx = {lbl: i for i, lbl in enumerate(labels)}
        fig = go.Figure(
            go.Sankey(
                node=dict(pad=15, thickness=16, label=labels),
                link=dict(
                    source=[idx[s] for s in transitions["PREV_CHANNEL"]],
                    target=[idx[t] for t in transitions["CHANNEL"]],
                    value=transitions["N"].tolist(),
                ),
            )
        )
        fig.update_layout(height=360, margin=dict(l=10, r=10, t=10, b=10))
        st.plotly_chart(fig, use_container_width=True)

    # ---- Recent events timeline ---------------------------------------
    st.subheader("Most recent 20 events")
    try:
        timeline = session.sql(
            f"""
            SELECT EVENT_TIMESTAMP, CHANNEL, EVENT_TYPE, PRODUCT_CATEGORY, AMOUNT_USD
            FROM RETAIL.CUSTOMER_EVENTS
            WHERE CUSTOMER_ID = '{customer_id}'
            ORDER BY EVENT_TIMESTAMP DESC
            LIMIT 20
            """
        ).to_pandas()
    except Exception as exc:  # noqa: BLE001
        LOG.warning("Using stub timeline: %s", exc)
        timeline = pd.DataFrame(
            {
                "EVENT_TIMESTAMP": pd.date_range(end="now", periods=20, freq="6H"),
                "CHANNEL": ["WEB", "MOBILE_APP"] * 10,
                "EVENT_TYPE": ["VIEW", "PURCHASE"] * 10,
                "PRODUCT_CATEGORY": ["APPAREL", "ELECTRONICS"] * 10,
                "AMOUNT_USD": [0, 78.50] * 10,
            }
        )

    st.dataframe(timeline, use_container_width=True, hide_index=True)

    st.caption(
        "Profile joined at query time from Iceberg-backed CUSTOMERS + Dynamic Table RFM + journey aggregates."
    )


if __name__ == "__main__":  # pragma: no cover
    logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
    if "streamlit" in os.environ.get("_", ""):
        _render()
    else:
        LOG.info("Run with `streamlit run` to view the dashboard.")
