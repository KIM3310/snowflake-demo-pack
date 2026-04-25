"""Train a lightweight fraud model and register it as a Snowpark Python UDF.

Design notes:

- The model is intentionally simple (gradient-boosted trees on 8 tabular
  features). In a live customer engagement the SE swaps it with the
  customer's preferred model without changing the UDF signature.
- The Snowpark UDF is registered with `replace=True` and `is_permanent=True`
  so that the Dynamic Table defined in `01-setup.sql` can reference it by
  name. The UDF returns a float in [0, 1].
- Training data comes from `FINANCE.TRANSACTIONS_LABELED` (populated by
  `02-load-data.py`). In dry-run mode we train on the synthetic data
  in-process and do not register the UDF — we only print what would be done.
- Optionally, if `FINANCE_DEMO_TRAIN_CORTEX=1`, we also create a
  `SNOWFLAKE.ML.CLASSIFICATION` model alongside the Snowpark UDF. The
  Dynamic Table will pick both up on its next refresh.
"""

from __future__ import annotations

import logging
import os
import pickle
import sys
from pathlib import Path
from typing import Any

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from common.connection import LOG, get_session, is_dry_run  # noqa: E402
from common.data_generators import generate_finance_transactions  # noqa: E402

TARGET_DB = os.getenv("SNOWFLAKE_DATABASE", "SNOWFLAKE_DEMO_PACK")
TARGET_SCHEMA = "FINANCE"
UDF_NAME = "FRAUD_PROBABILITY_UDF"
MODEL_STAGE = "@SNOWFLAKE_DEMO_PACK.FINANCE.DEMO_STAGE"
TRAIN_CORTEX = os.getenv("FINANCE_DEMO_TRAIN_CORTEX", "0").lower() in {"1", "true", "yes"}

FEATURE_COLUMNS = [
    "AMOUNT_USD",
    "HIGH_RISK_COUNTRY_FLAG",
    "ECOMMERCE_FLAG",
    "CARD_TXN_COUNT_1H",
    "CARD_AMOUNT_SUM_1H",
    "CARD_DISTINCT_COUNTRIES_24H",
    "CUSTOMER_AMOUNT_AVG_30D",
    "CUSTOMER_AMOUNT_STDDEV_30D",
]


def _build_training_frame():  # noqa: ANN202 - returns pandas lazily
    """Produce a (features, labels) pair from synthetic data for dry-run training."""
    df = generate_finance_transactions(n_rows=5_000, n_customers=1_000, fraud_rate=0.015)
    df = df.rename(columns={"IS_FRAUD_GROUND_TRUTH": "LABEL"})
    df["HIGH_RISK_COUNTRY_FLAG"] = df["COUNTRY_CODE"].isin(["RU", "NG", "VE", "IR"]).astype(int)
    df["ECOMMERCE_FLAG"] = (df["CHANNEL"] == "ECOMMERCE").astype(int)
    # Window features approximated for the dry-run training set.
    df["CARD_TXN_COUNT_1H"] = np.random.default_rng(0).integers(1, 10, size=len(df))
    df["CARD_AMOUNT_SUM_1H"] = df["AMOUNT_USD"] * df["CARD_TXN_COUNT_1H"] * 0.6
    df["CARD_DISTINCT_COUNTRIES_24H"] = np.random.default_rng(1).integers(1, 4, size=len(df))
    df["CUSTOMER_AMOUNT_AVG_30D"] = df["AMOUNT_USD"].mean()
    df["CUSTOMER_AMOUNT_STDDEV_30D"] = df["AMOUNT_USD"].std()
    features_matrix = df[FEATURE_COLUMNS].to_numpy(dtype=float)
    y = df["LABEL"].astype(int).to_numpy()
    return features_matrix, y


def _train_model() -> Any:
    """Train a small gradient-boosted tree on synthetic features."""
    try:
        from sklearn.ensemble import GradientBoostingClassifier
    except ImportError as exc:
        raise RuntimeError(
            "scikit-learn is required for model training. Install via `make setup`."
        ) from exc

    features_matrix, y = _build_training_frame()
    if y.sum() == 0:
        LOG.warning("No positive training examples generated; boosting one synthetic positive.")
        y[0] = 1
    model = GradientBoostingClassifier(
        n_estimators=60,
        max_depth=3,
        learning_rate=0.1,
        random_state=2026,
    )
    model.fit(features_matrix, y)
    LOG.info(
        "Trained GradientBoostingClassifier: train_score=%.4f",
        model.score(features_matrix, y),
    )
    return model


def _serialize_model(model: Any) -> bytes:
    return pickle.dumps(model)


def _register_udf(session: Any, model_bytes: bytes) -> None:
    """Register the Snowpark Python UDF that the Dynamic Table references."""
    try:
        from snowflake.snowpark.functions import udf  # type: ignore[import-not-found]
        from snowflake.snowpark.types import (  # type: ignore[import-not-found]
            FloatType,
            IntegerType,
        )
    except ImportError as exc:  # pragma: no cover - exercised only in live mode
        raise RuntimeError(
            "snowflake-snowpark-python is required for UDF registration."
        ) from exc

    # Upload the pickled model to an internal stage. The UDF reads it at cold start.
    model_path = Path("/tmp/fraud_model.pkl")
    model_path.write_bytes(model_bytes)
    session.file.put(
        str(model_path),
        MODEL_STAGE,
        auto_compress=False,
        overwrite=True,
    )

    @udf(  # type: ignore[misc]
        name=f"{TARGET_DB}.{TARGET_SCHEMA}.{UDF_NAME}",
        replace=True,
        is_permanent=True,
        session=session,
        stage_location=MODEL_STAGE,
        imports=[f"{MODEL_STAGE}/fraud_model.pkl"],
        packages=["scikit-learn", "numpy"],
        return_type=FloatType(),
        input_types=[
            FloatType(),
            IntegerType(),
            IntegerType(),
            IntegerType(),
            FloatType(),
            IntegerType(),
            FloatType(),
            FloatType(),
        ],
    )
    def fraud_probability_udf(  # noqa: PLR0913 - fixed feature arity
        amount_usd: float,
        high_risk_country_flag: int,
        ecommerce_flag: int,
        card_txn_count_1h: int,
        card_amount_sum_1h: float,
        card_distinct_countries_24h: int,
        customer_amount_avg_30d: float,
        customer_amount_stddev_30d: float,
    ) -> float:
        import pickle as _pickle
        import sys as _sys

        import numpy as _np

        stage_dir = _sys.path[0]
        with open(f"{stage_dir}/fraud_model.pkl", "rb") as handle:
            model = _pickle.load(handle)
        features = _np.array(
            [[
                amount_usd,
                high_risk_country_flag,
                ecommerce_flag,
                card_txn_count_1h,
                card_amount_sum_1h,
                card_distinct_countries_24h,
                customer_amount_avg_30d,
                customer_amount_stddev_30d,
            ]],
            dtype=float,
        )
        proba = model.predict_proba(features)[:, 1]
        return float(proba[0])

    LOG.info("Registered %s.%s.%s", TARGET_DB, TARGET_SCHEMA, UDF_NAME)


def _train_cortex_classifier(session: Any) -> None:
    """Optionally train a Cortex CLASSIFICATION model on the labeled table."""
    LOG.info("Training Cortex CLASSIFICATION model FRAUD_CORTEX_MODEL...")
    create_sql = f"""
        CREATE OR REPLACE SNOWFLAKE.ML.CLASSIFICATION FRAUD_CORTEX_MODEL(
            INPUT_DATA   => SYSTEM$REFERENCE('VIEW', '{TARGET_DB}.{TARGET_SCHEMA}.TRANSACTIONS_LABELED_V', 'SESSION'),
            TARGET_COLNAME => 'IS_FRAUD_GROUND_TRUTH'
        )
    """
    session.sql(create_sql).collect()
    LOG.info("Cortex CLASSIFICATION model trained.")


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
    LOG.info("Finance model trainer: dry_run=%s train_cortex=%s", is_dry_run(), TRAIN_CORTEX)

    model = _train_model()
    model_bytes = _serialize_model(model)
    LOG.info("Serialized model: %s bytes", len(model_bytes))

    if is_dry_run():
        LOG.info(
            "Dry run: would register %s.%s.%s referencing %s/fraud_model.pkl.",
            TARGET_DB,
            TARGET_SCHEMA,
            UDF_NAME,
            MODEL_STAGE,
        )
        if TRAIN_CORTEX:
            LOG.info(
                "Dry run: would train SNOWFLAKE.ML.CLASSIFICATION FRAUD_CORTEX_MODEL."
            )
        return 0

    session = get_session(schema_override=TARGET_SCHEMA)
    try:
        _register_udf(session, model_bytes)
        if TRAIN_CORTEX:
            _train_cortex_classifier(session)
    finally:
        session.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
