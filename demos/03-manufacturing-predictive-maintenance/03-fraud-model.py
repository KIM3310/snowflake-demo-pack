"""Snowpark ML anomaly-detection model for the Manufacturing demo.

(File name kept consistent with the 7-file contract. The model is
`IsolationForest` rather than a fraud classifier; the UDF name is
`PREDICT_MACHINE_FAILURE_UDF`.)

Two execution paths:

1. Dry-run: train an IsolationForest locally on synthetic telemetry and log
   the expected UDF signature.
2. Live run: using the Snowpark ML Model Registry, register the trained model
   and wrap it in a vectorized UDF. The Dynamic Table `MACHINE_HEALTH_SCORE`
   in `01-setup.sql` references this UDF by name.
"""

from __future__ import annotations

import logging
import os
import pickle
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from common.connection import LOG, get_session, is_dry_run  # noqa: E402
from common.data_generators import generate_manufacturing_telemetry  # noqa: E402

TARGET_DB = os.getenv("SNOWFLAKE_DATABASE", "SNOWFLAKE_DEMO_PACK")
TARGET_SCHEMA = "MANUFACTURING"
UDF_NAME = "PREDICT_MACHINE_FAILURE_UDF"
MODEL_STAGE = "@SNOWFLAKE_DEMO_PACK.MANUFACTURING.DEMO_STAGE"

FEATURE_COLUMNS = [
    "VIBRATION_MEAN",
    "TEMPERATURE_MEAN",
    "PRESSURE_MEAN",
    "CURRENT_MEAN",
    "RPM_MEAN",
    "VIBRATION_MAX",
    "TEMPERATURE_MAX",
]


def _build_training_features() -> pd.DataFrame:
    """Build a machine-level feature table from a synthetic telemetry sample."""
    telemetry = generate_manufacturing_telemetry(n_machines=50, hours=12, reads_per_minute=1)
    # Aggregate to a single row per machine with the same 7 features as the
    # live MACHINE_FEATURES_NOW Dynamic Table.
    features = (
        telemetry.groupby("MACHINE_ID")
        .apply(
            lambda g: pd.Series(
                {
                    "VIBRATION_MEAN": g.loc[g["SENSOR_TYPE"] == "VIBRATION", "VALUE"].mean(),
                    "TEMPERATURE_MEAN": g.loc[g["SENSOR_TYPE"] == "TEMPERATURE", "VALUE"].mean(),
                    "PRESSURE_MEAN": g.loc[g["SENSOR_TYPE"] == "PRESSURE", "VALUE"].mean(),
                    "CURRENT_MEAN": g.loc[g["SENSOR_TYPE"] == "CURRENT", "VALUE"].mean(),
                    "RPM_MEAN": g.loc[g["SENSOR_TYPE"] == "RPM", "VALUE"].mean(),
                    "VIBRATION_MAX": g.loc[g["SENSOR_TYPE"] == "VIBRATION", "VALUE"].max(),
                    "TEMPERATURE_MAX": g.loc[g["SENSOR_TYPE"] == "TEMPERATURE", "VALUE"].max(),
                }
            ),
            include_groups=False,
        )
        .reset_index()
    )
    return features


def _train_model() -> Any:
    try:
        from sklearn.ensemble import IsolationForest
    except ImportError as exc:
        raise RuntimeError("scikit-learn is required. Run `make setup`.") from exc

    features = _build_training_features()
    feature_matrix = features[FEATURE_COLUMNS].fillna(0.0).to_numpy(dtype=float)
    model = IsolationForest(
        n_estimators=80,
        contamination=0.07,
        random_state=2026,
    )
    model.fit(feature_matrix)
    LOG.info("Trained IsolationForest on %s machines.", len(features))
    return model


def _register_udf(session: Any, model_bytes: bytes) -> None:
    try:
        from snowflake.snowpark.functions import udf  # type: ignore[import-not-found]
        from snowflake.snowpark.types import FloatType  # type: ignore[import-not-found]
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("snowflake-snowpark-python is required for UDF registration.") from exc

    model_path = Path("/tmp/pdm_model.pkl")
    model_path.write_bytes(model_bytes)
    session.file.put(str(model_path), MODEL_STAGE, auto_compress=False, overwrite=True)

    @udf(  # type: ignore[misc]
        name=f"{TARGET_DB}.{TARGET_SCHEMA}.{UDF_NAME}",
        replace=True,
        is_permanent=True,
        session=session,
        stage_location=MODEL_STAGE,
        imports=[f"{MODEL_STAGE}/pdm_model.pkl"],
        packages=["scikit-learn", "numpy"],
        return_type=FloatType(),
        input_types=[FloatType()] * len(FEATURE_COLUMNS),
    )
    def predict_machine_failure_udf(  # noqa: PLR0913 - fixed feature arity
        vibration_mean: float,
        temperature_mean: float,
        pressure_mean: float,
        current_mean: float,
        rpm_mean: float,
        vibration_max: float,
        temperature_max: float,
    ) -> float:
        import pickle as _pickle
        import sys as _sys

        import numpy as _np

        stage_dir = _sys.path[0]
        with open(f"{stage_dir}/pdm_model.pkl", "rb") as handle:
            model = _pickle.load(handle)
        features = _np.array(
            [[
                vibration_mean,
                temperature_mean,
                pressure_mean,
                current_mean,
                rpm_mean,
                vibration_max,
                temperature_max,
            ]],
            dtype=float,
        )
        # IsolationForest: decision_function is high for normal, low for anomaly.
        # Map to a [0, 1] risk score where 1 indicates high anomaly.
        raw_score = model.decision_function(features)[0]
        bounded = 1.0 / (1.0 + _np.exp(5.0 * raw_score))
        return float(bounded)

    LOG.info("Registered %s.%s.%s", TARGET_DB, TARGET_SCHEMA, UDF_NAME)


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
    LOG.info("Manufacturing model trainer: dry_run=%s", is_dry_run())
    model = _train_model()
    model_bytes = pickle.dumps(model)
    LOG.info("Serialized model: %s bytes", len(model_bytes))

    if is_dry_run():
        LOG.info(
            "Dry run: would register %s.%s.%s with %s features.",
            TARGET_DB,
            TARGET_SCHEMA,
            UDF_NAME,
            len(FEATURE_COLUMNS),
        )
        # Sanity-check the scoring logic inline.
        sample = np.array([[0.35, 68.0, 4.2, 12.5, 1750.0, 0.40, 70.0]])
        raw = model.decision_function(sample)[0]
        risk = 1.0 / (1.0 + np.exp(5.0 * raw))
        LOG.info("Sample risk (healthy machine): %.4f", risk)
        sample_bad = np.array([[0.95, 85.0, 4.2, 12.5, 1750.0, 1.2, 92.0]])
        raw_bad = model.decision_function(sample_bad)[0]
        risk_bad = 1.0 / (1.0 + np.exp(5.0 * raw_bad))
        LOG.info("Sample risk (degraded machine): %.4f", risk_bad)
        return 0

    session = get_session(schema_override=TARGET_SCHEMA)
    try:
        _register_udf(session, model_bytes)
    finally:
        session.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
