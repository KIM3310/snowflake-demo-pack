"""Catalog and user-event loader for the Media demo.

Loads:
  - CONTENT_CATALOG: 2,000 synthetic titles with templated descriptions.
  - USER_EVENTS: 50,000 events across 5,000 users and 2,000 titles.

Embedding generation is deferred to `03-fraud-model.py` so the SE can show
each step separately during a walkthrough.
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from common.connection import LOG, get_session, is_dry_run  # noqa: E402
from common.data_generators import (  # noqa: E402
    generate_media_catalog,
    generate_media_events,
)

N_EVENTS = int(os.getenv("MEDIA_DEMO_N_EVENTS", "50000"))
N_USERS = int(os.getenv("MEDIA_DEMO_N_USERS", "5000"))
N_CONTENT = int(os.getenv("MEDIA_DEMO_N_CONTENT", "2000"))
TARGET_DB = os.getenv("SNOWFLAKE_DATABASE", "SNOWFLAKE_DEMO_PACK")
TARGET_SCHEMA = "MEDIA"


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
    LOG.info(
        "Media loader: events=%s users=%s content=%s dry_run=%s",
        N_EVENTS,
        N_USERS,
        N_CONTENT,
        is_dry_run(),
    )

    catalog = generate_media_catalog(n_content=N_CONTENT)
    events = generate_media_events(n_rows=N_EVENTS, n_users=N_USERS, n_content=N_CONTENT)

    LOG.info("Sample catalog entry:\n%s", catalog.head(2).to_string(index=False))
    LOG.info("Sample event:\n%s", events.head(2).to_string(index=False))

    if is_dry_run():
        LOG.info(
            "Dry run complete. catalog=%s events=%s would be loaded into %s.%s.",
            len(catalog),
            len(events),
            TARGET_DB,
            TARGET_SCHEMA,
        )
        return 0

    session = get_session(schema_override=TARGET_SCHEMA)
    try:
        for tbl in ("CONTENT_CATALOG", "USER_EVENTS"):
            session.sql(f"TRUNCATE TABLE {TARGET_DB}.{TARGET_SCHEMA}.{tbl}").collect()
        session.create_dataframe(catalog).write.mode("append").save_as_table(
            f"{TARGET_DB}.{TARGET_SCHEMA}.CONTENT_CATALOG"
        )
        session.create_dataframe(events).write.mode("append").save_as_table(
            f"{TARGET_DB}.{TARGET_SCHEMA}.USER_EVENTS"
        )
        LOG.info("Loaded catalog=%s events=%s.", len(catalog), len(events))
    finally:
        session.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
