"""Streamlit recommendation app for the Media demo.

Three panels:
  - Natural-language catalog search (Cortex Search).
  - Per-user top-N recommendation list with similarity scores.
  - Feedback widget (click-through + rating) that writes back into
    RECOMMENDATION_FEEDBACK for future reranker training.
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

LOG = logging.getLogger("media-dashboard")


def _get_session():  # noqa: ANN202
    try:
        from snowflake.snowpark.context import get_active_session  # type: ignore[import-not-found]

        return get_active_session()
    except Exception:  # noqa: BLE001
        from common.connection import get_session

        return get_session(schema_override="MEDIA")


def _render() -> None:
    try:
        import pandas as pd
        import streamlit as st
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("Install `streamlit` via `make setup`.") from exc

    st.set_page_config(page_title="Catalog Recommendations", layout="wide")
    st.title("Catalog Recommendations")
    st.caption("Powered by Cortex Search + VECTOR_COSINE_SIMILARITY over content embeddings")

    session = _get_session()

    tab1, tab2 = st.tabs(["Semantic catalog search", "Per-user recommendations"])

    # ---- Semantic search tab ------------------------------------------
    with tab1:
        query = st.text_input(
            "Describe what you want to watch",
            value="tense political drama set in Seoul with a female lead",
        )
        limit = st.slider("Max results", 1, 20, 5)
        if st.button("Search"):
            try:
                results = session.sql(
                    f"""
                    SELECT
                        RESULT_VALUE:CONTENT_ID::STRING  AS CONTENT_ID,
                        RESULT_VALUE:TITLE::STRING        AS TITLE,
                        RESULT_VALUE:GENRE::STRING        AS GENRE,
                        RESULT_VALUE:RELEASE_YEAR::NUMBER AS RELEASE_YEAR,
                        RESULT_VALUE:DESCRIPTION::STRING  AS DESCRIPTION
                    FROM TABLE(
                        CORTEX_SEARCH(
                            'CONTENT_SEARCH',
                            OBJECT_CONSTRUCT('query', '{query}', 'limit', {limit})
                        )
                    ) AS T (RESULT_VALUE)
                    """
                ).to_pandas()
            except Exception as exc:  # noqa: BLE001
                LOG.warning("Using stub search results: %s", exc)
                results = pd.DataFrame(
                    {
                        "CONTENT_ID": [f"CNT_STUB_{i:04d}" for i in range(limit)],
                        "TITLE": [f"Mock Title {i}" for i in range(limit)],
                        "GENRE": ["DRAMA"] * limit,
                        "RELEASE_YEAR": [2024 - i for i in range(limit)],
                        "DESCRIPTION": [
                            "A political drama featuring a determined female lead."
                        ] * limit,
                    }
                )
            st.dataframe(results, use_container_width=True, hide_index=True)

    # ---- Per-user recommendation tab ----------------------------------
    with tab2:
        try:
            users = session.sql(
                "SELECT DISTINCT USER_ID FROM USER_PREFERENCE_VECTOR ORDER BY USER_ID LIMIT 500"
            ).to_pandas()
        except Exception as exc:  # noqa: BLE001
            LOG.warning("Using stub user list: %s", exc)
            users = pd.DataFrame({"USER_ID": [f"USR_STUB_{i:04d}" for i in range(40)]})

        user_id = st.selectbox("Pick a user", users["USER_ID"].tolist())
        try:
            recs = session.sql(
                f"""
                SELECT CONTENT_ID, TITLE, GENRE, SIMILARITY, DESCRIPTION
                FROM RECOMMENDATIONS_VIEW
                WHERE USER_ID = '{user_id}'
                ORDER BY SIMILARITY DESC
                LIMIT 10
                """
            ).to_pandas()
        except Exception as exc:  # noqa: BLE001
            LOG.warning("Using stub recommendations: %s", exc)
            recs = pd.DataFrame(
                {
                    "CONTENT_ID": [f"CNT_STUB_{i:04d}" for i in range(10)],
                    "TITLE": [f"Suggested Title {i}" for i in range(10)],
                    "GENRE": ["DRAMA", "COMEDY", "ACTION"] * 3 + ["SCI_FI"],
                    "SIMILARITY": [round(0.95 - i * 0.04, 3) for i in range(10)],
                    "DESCRIPTION": ["Thematically similar to recent plays."] * 10,
                }
            )
        st.dataframe(recs, use_container_width=True, hide_index=True)

        # Feedback widget (best-effort; skipped in stub mode)
        st.subheader("Feedback")
        pick = st.selectbox("Title you clicked on", recs["CONTENT_ID"].tolist())
        rating = st.slider("Rate this recommendation (1-5)", 1, 5, 3)
        if st.button("Submit feedback"):
            try:
                session.sql(
                    f"""
                    INSERT INTO RECOMMENDATION_FEEDBACK (USER_ID, CONTENT_ID, RATING, CLICK_THROUGH)
                    VALUES ('{user_id}', '{pick}', {rating}, TRUE)
                    """
                ).collect()
                st.success("Feedback saved.")
            except Exception as exc:  # noqa: BLE001
                st.warning(f"Feedback write skipped in this environment: {exc}")


if __name__ == "__main__":  # pragma: no cover
    logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
    if "streamlit" in os.environ.get("_", ""):
        _render()
    else:
        LOG.info("Run with `streamlit run`.")
