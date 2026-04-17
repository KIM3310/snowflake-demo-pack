"""Snowflake connection helpers shared by all demos.

Design principles:

1. Every demo imports `get_session()` or `get_connection()`. There is a single
   source of truth for credentials, defaulting to environment variables.
2. When `SNOWFLAKE_DEMO_DRY_RUN=1` (the default in CI) the helpers return a
   stub that prints what *would* run but never opens a network connection.
   This lets scaffolding, syntax checks, and walkthroughs run with no
   Snowflake account.
3. SQL file execution is delegated to `run_sql_file()`, which splits on
   semicolons while being tolerant of `$$` block bodies (UDFs, procedures).
"""

from __future__ import annotations

import logging
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

LOG = logging.getLogger("snowflake-demo-pack")
if not LOG.handlers:
    _handler = logging.StreamHandler(sys.stdout)
    _handler.setFormatter(logging.Formatter("[%(asctime)s] %(levelname)s %(name)s: %(message)s"))
    LOG.addHandler(_handler)
    LOG.setLevel(os.getenv("SNOWFLAKE_DEMO_LOG_LEVEL", "INFO"))


# ---------------------------------------------------------------------------
# Connection configuration
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SnowflakeConfig:
    """Connection configuration resolved from environment variables."""

    account: str
    user: str
    password: str | None
    private_key_path: str | None
    role: str
    warehouse: str
    database: str
    schema: str
    authenticator: str

    @classmethod
    def from_env(cls, *, schema_override: str | None = None) -> SnowflakeConfig:
        return cls(
            account=os.getenv("SNOWFLAKE_ACCOUNT", "xy12345.us-west-2.aws"),
            user=os.getenv("SNOWFLAKE_USER", "DEMO_USER"),
            password=os.getenv("SNOWFLAKE_PASSWORD"),
            private_key_path=os.getenv("SNOWFLAKE_PRIVATE_KEY_PATH"),
            role=os.getenv("SNOWFLAKE_ROLE", "SYSADMIN"),
            warehouse=os.getenv("SNOWFLAKE_WAREHOUSE", "DEMO_WH"),
            database=os.getenv("SNOWFLAKE_DATABASE", "SNOWFLAKE_DEMO_PACK"),
            schema=schema_override or os.getenv("SNOWFLAKE_SCHEMA", "PUBLIC"),
            authenticator=os.getenv("SNOWFLAKE_AUTHENTICATOR", "snowflake"),
        )

    def masked(self) -> dict[str, str]:
        """Return a dict safe for logging."""
        return {
            "account": self.account,
            "user": self.user,
            "role": self.role,
            "warehouse": self.warehouse,
            "database": self.database,
            "schema": self.schema,
            "authenticator": self.authenticator,
            "password": "***" if self.password else "<none>",
            "private_key_path": self.private_key_path or "<none>",
        }


# ---------------------------------------------------------------------------
# Dry-run stubs
# ---------------------------------------------------------------------------


def is_dry_run() -> bool:
    """True when SNOWFLAKE_DEMO_DRY_RUN is a truthy value."""
    return os.getenv("SNOWFLAKE_DEMO_DRY_RUN", "1").lower() in {"1", "true", "yes", "on"}


class _DryRunCursor:
    """Minimal cursor stub that logs SQL instead of executing it."""

    def __init__(self, name: str = "dry-run") -> None:
        self._name = name
        self._last_sql: str | None = None

    def execute(self, sql: str, params: Any = None) -> _DryRunCursor:
        sql_flat = " ".join(sql.split())
        if len(sql_flat) > 180:
            sql_flat = sql_flat[:177] + "..."
        LOG.info("[DRY-RUN %s] execute: %s", self._name, sql_flat)
        self._last_sql = sql
        return self

    def executemany(self, sql: str, seq_params: Iterable[Any]) -> _DryRunCursor:
        seq_list = list(seq_params)
        LOG.info("[DRY-RUN %s] executemany: %s rows", self._name, len(seq_list))
        self._last_sql = sql
        return self

    def fetchone(self) -> tuple[Any, ...]:
        return (0,)

    def fetchall(self) -> list[tuple[Any, ...]]:
        return []

    def fetch_pandas_all(self):  # noqa: ANN201 - returns pandas lazily
        import pandas as pd

        return pd.DataFrame()

    def close(self) -> None:
        return None

    def __enter__(self) -> _DryRunCursor:
        return self

    def __exit__(self, *_exc: Any) -> None:
        self.close()


class _DryRunConnection:
    """Minimal connection stub that logs DDL/DML instead of executing it."""

    def __init__(self, cfg: SnowflakeConfig) -> None:
        self._cfg = cfg
        LOG.info("Opening dry-run connection: %s", cfg.masked())

    def cursor(self) -> _DryRunCursor:
        return _DryRunCursor(name=self._cfg.database)

    def close(self) -> None:
        LOG.info("Closing dry-run connection.")

    def commit(self) -> None:
        return None

    def rollback(self) -> None:
        return None

    def __enter__(self) -> _DryRunConnection:
        return self

    def __exit__(self, *_exc: Any) -> None:
        self.close()


class _DryRunSession:
    """Minimal Snowpark `Session`-like stub."""

    def __init__(self, cfg: SnowflakeConfig) -> None:
        self._cfg = cfg
        LOG.info("Opening dry-run Snowpark session: %s", cfg.masked())

    def sql(self, query: str):  # noqa: ANN201 - returns a stub DataFrame
        LOG.info("[DRY-RUN Snowpark.sql] %s", query.strip().split("\n")[0][:160])
        return _DryRunDataFrame()

    def table(self, name: str):  # noqa: ANN201
        LOG.info("[DRY-RUN Snowpark.table] %s", name)
        return _DryRunDataFrame()

    def create_dataframe(self, data, schema=None):  # noqa: ANN001,ANN201
        LOG.info(
            "[DRY-RUN Snowpark.create_dataframe] rows=%s schema=%s",
            len(list(data)) if hasattr(data, "__iter__") else "?",
            schema,
        )
        return _DryRunDataFrame()

    def close(self) -> None:
        LOG.info("Closing dry-run Snowpark session.")


class _DryRunDataFrame:
    def collect(self) -> list[Any]:
        return []

    def count(self) -> int:
        return 0

    def to_pandas(self):  # noqa: ANN201
        import pandas as pd

        return pd.DataFrame()

    def show(self, n: int = 10) -> None:
        LOG.info("[DRY-RUN DataFrame.show] requested %s rows", n)


# ---------------------------------------------------------------------------
# Live connectors
# ---------------------------------------------------------------------------


def get_connection(schema_override: str | None = None):
    """Return a `snowflake.connector` Connection or a dry-run stub.

    Callers use the object in a `with` block:

        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT CURRENT_TIMESTAMP()")
                print(cur.fetchone())
    """
    cfg = SnowflakeConfig.from_env(schema_override=schema_override)
    if is_dry_run():
        return _DryRunConnection(cfg)

    try:
        import snowflake.connector  # type: ignore[import-not-found]
    except ImportError as exc:  # pragma: no cover - exercised only in live mode
        raise RuntimeError(
            "snowflake-connector-python not installed. Run `make setup` or set "
            "SNOWFLAKE_DEMO_DRY_RUN=1 for dry-run mode."
        ) from exc

    kwargs: dict[str, Any] = {
        "account": cfg.account,
        "user": cfg.user,
        "role": cfg.role,
        "warehouse": cfg.warehouse,
        "database": cfg.database,
        "schema": cfg.schema,
        "authenticator": cfg.authenticator,
    }
    if cfg.password:
        kwargs["password"] = cfg.password
    if cfg.private_key_path:
        kwargs["private_key_file"] = cfg.private_key_path

    LOG.info("Opening Snowflake connection: %s", cfg.masked())
    return snowflake.connector.connect(**kwargs)


def get_session(schema_override: str | None = None):
    """Return a Snowpark `Session` or a dry-run stub."""
    cfg = SnowflakeConfig.from_env(schema_override=schema_override)
    if is_dry_run():
        return _DryRunSession(cfg)

    try:
        from snowflake.snowpark import Session  # type: ignore[import-not-found]
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError(
            "snowflake-snowpark-python not installed. Run `make setup` or set "
            "SNOWFLAKE_DEMO_DRY_RUN=1 for dry-run mode."
        ) from exc

    connection_parameters: dict[str, Any] = {
        "account": cfg.account,
        "user": cfg.user,
        "role": cfg.role,
        "warehouse": cfg.warehouse,
        "database": cfg.database,
        "schema": cfg.schema,
        "authenticator": cfg.authenticator,
    }
    if cfg.password:
        connection_parameters["password"] = cfg.password
    if cfg.private_key_path:
        connection_parameters["private_key_file"] = cfg.private_key_path

    LOG.info("Opening Snowpark session: %s", cfg.masked())
    return Session.builder.configs(connection_parameters).create()


# ---------------------------------------------------------------------------
# SQL file runner
# ---------------------------------------------------------------------------


_DOLLAR_QUOTE_RE = re.compile(r"\$\$.*?\$\$", re.DOTALL)


def split_sql_statements(sql_text: str) -> list[str]:
    """Split a SQL script on semicolons, preserving `$$...$$` bodies.

    Snowflake UDFs, stored procedures, and tasks frequently contain semicolons
    inside dollar-quoted bodies. Naive splitting breaks them. This function
    masks `$$...$$` blocks before splitting, then restores them.
    """
    placeholders: dict[str, str] = {}

    def _mask(match: re.Match[str]) -> str:
        token = f"__DOLLARQUOTE_{len(placeholders)}__"
        placeholders[token] = match.group(0)
        return token

    masked = _DOLLAR_QUOTE_RE.sub(_mask, sql_text)
    raw_statements = [stmt.strip() for stmt in masked.split(";")]

    statements: list[str] = []
    for stmt in raw_statements:
        if not stmt or stmt.startswith("--"):
            continue
        # Strip pure-comment leading lines so we keep executable content.
        lines = [line for line in stmt.splitlines() if line.strip() and not line.strip().startswith("--")]
        if not lines:
            continue
        restored = stmt
        for token, original in placeholders.items():
            restored = restored.replace(token, original)
        statements.append(restored.strip())
    return statements


def run_sql_file(path: str | Path) -> None:
    """Execute a SQL file statement-by-statement.

    In dry-run mode, prints each statement. In live mode, runs each one
    through the Snowflake connector and surfaces the first error.
    """
    sql_path = Path(path)
    if not sql_path.exists():
        raise FileNotFoundError(f"SQL file not found: {sql_path}")

    sql_text = sql_path.read_text(encoding="utf-8")
    statements = split_sql_statements(sql_text)
    LOG.info("Executing %s (%s statements)", sql_path, len(statements))

    with get_connection() as conn:
        with conn.cursor() as cur:
            for idx, stmt in enumerate(statements, start=1):
                try:
                    cur.execute(stmt)
                except Exception:
                    LOG.error("Statement %s failed:\n%s", idx, stmt)
                    raise
        conn.commit()


__all__ = [
    "SnowflakeConfig",
    "is_dry_run",
    "get_connection",
    "get_session",
    "split_sql_statements",
    "run_sql_file",
    "LOG",
]
