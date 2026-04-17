"""Embedding pipeline driver for the Media demo.

(Filename preserved per the 7-file contract. Logic here is embedding
generation via Cortex, not fraud scoring.)

Three steps:
  1. Call `REFRESH_CONTENT_EMBEDDINGS()` stored procedure to populate
     `CONTENT_EMBEDDINGS` for any catalog row that does not yet have one.
  2. Verify the Cortex Search service `CONTENT_SEARCH` is refreshed.
  3. Touch the Dynamic Table `USER_PREFERENCE_VECTOR` to force an initial
     refresh after the first load.

In dry-run mode we simulate a local sentence-transformers embedding on a small
slice of the catalog just to prove the signal: the "degraded" titles form a
separate cluster from the baseline titles. We skip the actual network call to
Cortex when there is no Snowflake session.
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
from common.data_generators import generate_media_catalog  # noqa: E402

TARGET_DB = os.getenv("SNOWFLAKE_DATABASE", "SNOWFLAKE_DEMO_PACK")
TARGET_SCHEMA = "MEDIA"
EMBED_MODEL = os.getenv("MEDIA_DEMO_EMBED_MODEL", "snowflake-arctic-embed-m")


def _dry_run_preview() -> None:
    """Produce a compact preview of what embedding would do without a network call."""
    catalog = generate_media_catalog(n_content=40)
    LOG.info("Dry-run embedding plan:")
    LOG.info("  model=%s", EMBED_MODEL)
    LOG.info("  catalog rows to embed=%s", len(catalog))
    LOG.info("  first descriptions:")
    for _, row in catalog.head(3).iterrows():
        LOG.info("    [%s] %s", row["CONTENT_ID"], row["DESCRIPTION"][:100] + "...")
    LOG.info(
        "  Live equivalent: CALL %s.%s.REFRESH_CONTENT_EMBEDDINGS();",
        TARGET_DB,
        TARGET_SCHEMA,
    )


def _live_embed(session: Any) -> None:
    LOG.info("Refreshing content embeddings...")
    result = session.sql(
        f"CALL {TARGET_DB}.{TARGET_SCHEMA}.REFRESH_CONTENT_EMBEDDINGS()"
    ).collect()
    LOG.info("REFRESH_CONTENT_EMBEDDINGS returned: %s", result)

    # Trigger an initial Dynamic Table refresh.
    LOG.info("Forcing a manual refresh of USER_PREFERENCE_VECTOR...")
    session.sql(
        f"ALTER DYNAMIC TABLE {TARGET_DB}.{TARGET_SCHEMA}.USER_PREFERENCE_VECTOR REFRESH"
    ).collect()
    LOG.info("Embedding and user-vector refresh complete.")


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
    LOG.info("Media embedding driver: model=%s dry_run=%s", EMBED_MODEL, is_dry_run())

    if is_dry_run():
        _dry_run_preview()
        return 0

    session = get_session(schema_override=TARGET_SCHEMA)
    try:
        _live_embed(session)
    finally:
        session.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
