"""Shared infrastructure for the Snowflake demo pack.

This package provides:
- `connection`: thin Snowflake connector wrapper with a dry-run mode for CI/dev.
- `data_generators`: deterministic synthetic-data functions for all five demos.

Import entry points:
    >>> from common.connection import get_session, run_sql_file
    >>> from common.data_generators import (
    ...     generate_finance_transactions,
    ...     generate_retail_events,
    ...     generate_manufacturing_telemetry,
    ...     generate_healthcare_records,
    ...     generate_media_events,
    ... )
"""

from __future__ import annotations

__version__ = "1.0.0"
__author__ = "Doeon Kim"
__all__ = [
    "__version__",
    "__author__",
]
