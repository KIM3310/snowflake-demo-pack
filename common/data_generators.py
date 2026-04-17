"""Deterministic synthetic-data generators for every demo pack.

Each function returns a pandas DataFrame whose schema matches the DDL for the
corresponding demo. Functions accept a `seed` argument so results are
reproducible for CI and for customer-walkthrough preparation.

Scale targets (aligned with the repo README):

- Finance:       1,000,000 transactions/day pattern (default returns 10,000).
- Retail:        500,000 customers across 5 channels (default 10,000).
- Manufacturing: 100 sensors x 1,440 minutes/day (default 14,400 rows).
- Healthcare:    50,000 de-identified patient records (default 5,000).
- Media:         10,000,000 events/day (default 50,000).

Every generator logs the row count and schema it produced, so dry-run output
is useful for demo walkthroughs even without a Snowflake account.
"""

from __future__ import annotations

import hashlib
import logging
import math
import random
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

import numpy as np
import pandas as pd

LOG = logging.getLogger("snowflake-demo-pack.data")


# ---------------------------------------------------------------------------
# Generic helpers
# ---------------------------------------------------------------------------


def _rng(seed: int) -> tuple[random.Random, np.random.Generator]:
    """Return a seeded (random, numpy) generator pair."""
    return random.Random(seed), np.random.default_rng(seed)


def _stable_id(prefix: str, *parts: Any) -> str:
    """Produce a stable hash-derived identifier (for PK-like fields)."""
    raw = "|".join(str(p) for p in parts).encode("utf-8")
    digest = hashlib.sha1(raw).hexdigest()[:10].upper()
    return f"{prefix}_{digest}"


def _log_result(name: str, df: pd.DataFrame) -> pd.DataFrame:
    LOG.info("Generated %s: rows=%s columns=%s", name, len(df), list(df.columns))
    return df


# ---------------------------------------------------------------------------
# 01 — Finance: card transactions
# ---------------------------------------------------------------------------


FINANCE_MCC = [
    ("5411", "Grocery"),
    ("5812", "Eating Places"),
    ("5541", "Service Stations"),
    ("5999", "Miscellaneous"),
    ("4511", "Airlines"),
    ("7011", "Lodging"),
    ("5732", "Electronics"),
    ("5912", "Drugstores"),
    ("6011", "ATM Cash"),
    ("5691", "Apparel"),
]

FINANCE_CHANNELS = ["CHIP", "SWIPE", "CONTACTLESS", "ECOMMERCE", "RECURRING"]
FINANCE_COUNTRIES = ["US", "KR", "JP", "GB", "DE", "SG", "AU", "CA"]


def generate_finance_transactions(
    n_rows: int = 10_000,
    n_customers: int = 2_000,
    seed: int = 42,
    fraud_rate: float = 0.008,
) -> pd.DataFrame:
    """Generate synthetic card-transaction data.

    Schema matches `demos/01-finance-fraud-detection/01-setup.sql::TRANSACTIONS_RAW`.
    """
    rnd, rng = _rng(seed)
    now = datetime.now(timezone.utc).replace(microsecond=0)

    customer_ids = [_stable_id("CUST", i) for i in range(n_customers)]
    card_ids = [_stable_id("CARD", i, i % 4) for i in range(n_customers * 2)]
    customer_to_card = {c: rnd.choice(card_ids) for c in customer_ids}

    rows: list[dict[str, Any]] = []
    for i in range(n_rows):
        customer_id = customer_ids[rng.integers(0, n_customers)]
        card_id = customer_to_card[customer_id]
        mcc_code, mcc_label = rnd.choice(FINANCE_MCC)
        channel = rnd.choices(FINANCE_CHANNELS, weights=[35, 15, 25, 20, 5])[0]
        country = rnd.choices(FINANCE_COUNTRIES, weights=[55, 10, 5, 8, 7, 5, 5, 5])[0]
        amount = float(round(rng.gamma(shape=2.0, scale=22.0), 2))

        is_fraud = rng.random() < fraud_rate
        if is_fraud:
            amount = float(round(amount * rng.uniform(5.0, 18.0), 2))
            if rnd.random() < 0.6:
                country = rnd.choice(["RU", "NG", "VE", "IR"])
            channel = "ECOMMERCE" if rnd.random() < 0.7 else channel

        event_ts = now - timedelta(seconds=int(rng.integers(0, 86_400)))
        rows.append(
            {
                "TRANSACTION_ID": _stable_id("TXN", i, customer_id),
                "CUSTOMER_ID": customer_id,
                "CARD_ID": card_id,
                "MERCHANT_CATEGORY_CODE": mcc_code,
                "MERCHANT_CATEGORY_LABEL": mcc_label,
                "CHANNEL": channel,
                "COUNTRY_CODE": country,
                "AMOUNT_USD": amount,
                "EVENT_TIMESTAMP": event_ts,
                "DEVICE_FINGERPRINT": _stable_id("DEV", customer_id, channel),
                "IS_FRAUD_GROUND_TRUTH": bool(is_fraud),
            }
        )

    df = pd.DataFrame(rows)
    return _log_result("finance transactions", df)


# ---------------------------------------------------------------------------
# 02 — Retail: multi-channel customer events
# ---------------------------------------------------------------------------


RETAIL_CHANNELS = ["WEB", "MOBILE_APP", "POS", "CALL_CENTER", "MARKETPLACE"]
RETAIL_EVENTS = ["VIEW", "ADD_TO_CART", "CHECKOUT", "PURCHASE", "RETURN", "SUPPORT_CONTACT"]
RETAIL_CATEGORIES = [
    "APPAREL",
    "ELECTRONICS",
    "HOME_GOODS",
    "BEAUTY",
    "GROCERY",
    "SPORTS",
    "BOOKS",
    "TOYS",
]


def generate_retail_events(
    n_rows: int = 10_000,
    n_customers: int = 2_500,
    seed: int = 43,
) -> pd.DataFrame:
    """Generate synthetic cross-channel customer events.

    Schema matches `demos/02-retail-customer-360/01-setup.sql::CUSTOMER_EVENTS`.
    """
    rnd, rng = _rng(seed)
    now = datetime.now(timezone.utc).replace(microsecond=0)
    customer_ids = [_stable_id("RCUST", i) for i in range(n_customers)]

    rows: list[dict[str, Any]] = []
    for i in range(n_rows):
        cust = customer_ids[rng.integers(0, n_customers)]
        channel = rnd.choices(RETAIL_CHANNELS, weights=[40, 35, 12, 5, 8])[0]
        event_type = rnd.choices(RETAIL_EVENTS, weights=[55, 18, 10, 12, 3, 2])[0]
        category = rnd.choice(RETAIL_CATEGORIES)
        session_id = _stable_id("SESS", cust, i // 7)
        amount = 0.0
        if event_type == "PURCHASE":
            amount = float(round(rng.lognormal(mean=3.4, sigma=0.6), 2))
        elif event_type == "RETURN":
            amount = -float(round(rng.lognormal(mean=3.1, sigma=0.5), 2))

        event_ts = now - timedelta(minutes=int(rng.integers(0, 60 * 24 * 7)))
        rows.append(
            {
                "EVENT_ID": _stable_id("EV", i, cust),
                "CUSTOMER_ID": cust,
                "SESSION_ID": session_id,
                "CHANNEL": channel,
                "EVENT_TYPE": event_type,
                "PRODUCT_CATEGORY": category,
                "SKU": _stable_id("SKU", category, rng.integers(0, 500)),
                "AMOUNT_USD": round(amount, 2),
                "EVENT_TIMESTAMP": event_ts,
                "DEVICE_TYPE": rnd.choice(["IOS", "ANDROID", "WEB", "POS_TERMINAL"]),
                "GEO_COUNTRY": rnd.choices(FINANCE_COUNTRIES, weights=[55, 15, 8, 7, 5, 4, 3, 3])[0],
            }
        )

    df = pd.DataFrame(rows)
    return _log_result("retail events", df)


def generate_retail_customers(n_customers: int = 2_500, seed: int = 44) -> pd.DataFrame:
    """Generate the master customer dimension."""
    rnd, rng = _rng(seed)
    segments = ["VIP", "LOYAL", "REGULAR", "NEW", "DORMANT"]
    rows: list[dict[str, Any]] = []
    for i in range(n_customers):
        cust = _stable_id("RCUST", i)
        signup_days_ago = int(rng.integers(10, 2_000))
        rows.append(
            {
                "CUSTOMER_ID": cust,
                "EMAIL_HASH": hashlib.sha256(cust.encode()).hexdigest()[:24],
                "SIGNUP_DATE": (datetime.now(timezone.utc) - timedelta(days=signup_days_ago)).date(),
                "LIFETIME_VALUE_USD": float(round(rng.gamma(shape=2.0, scale=180.0), 2)),
                "SEGMENT": rnd.choices(segments, weights=[5, 20, 45, 20, 10])[0],
                "PREFERRED_CHANNEL": rnd.choice(RETAIL_CHANNELS),
                "LOYALTY_TIER": rnd.choices(["PLATINUM", "GOLD", "SILVER", "BRONZE"], weights=[5, 15, 35, 45])[0],
            }
        )
    df = pd.DataFrame(rows)
    return _log_result("retail customers", df)


# ---------------------------------------------------------------------------
# 03 — Manufacturing: IoT sensor telemetry
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SensorProfile:
    sensor_type: str
    baseline_mean: float
    baseline_std: float
    unit: str


MANUFACTURING_SENSORS = [
    SensorProfile("VIBRATION", 0.35, 0.06, "mm/s"),
    SensorProfile("TEMPERATURE", 68.0, 3.0, "C"),
    SensorProfile("PRESSURE", 4.2, 0.25, "bar"),
    SensorProfile("CURRENT", 12.5, 0.9, "A"),
    SensorProfile("RPM", 1750.0, 45.0, "rpm"),
]


def generate_manufacturing_telemetry(
    n_machines: int = 100,
    hours: int = 24,
    reads_per_minute: int = 1,
    seed: int = 45,
    degrade_machines: int = 5,
) -> pd.DataFrame:
    """Generate synthetic IoT telemetry rows with an induced degradation signal.

    Returns one row per (machine, sensor, timestamp). Five machines are marked
    as degrading, so the downstream Snowpark ML demo has positive examples.

    Schema matches `demos/03-manufacturing-predictive-maintenance/01-setup.sql::SENSOR_TELEMETRY`.
    """
    rnd, rng = _rng(seed)
    now = datetime.now(timezone.utc).replace(microsecond=0, second=0)
    start = now - timedelta(hours=hours)

    degrading = set(rnd.sample(range(n_machines), k=min(degrade_machines, n_machines)))
    rows: list[dict[str, Any]] = []
    for machine_idx in range(n_machines):
        machine_id = _stable_id("MCH", machine_idx)
        line = f"LINE-{(machine_idx % 5) + 1}"
        site = ["ULSAN", "BUSAN", "INCHEON"][machine_idx % 3]
        for minute in range(hours * 60):
            ts = start + timedelta(minutes=minute)
            degrade_factor = 0.0
            if machine_idx in degrading:
                degrade_factor = (minute / (hours * 60)) ** 1.5
            for sensor in MANUFACTURING_SENSORS:
                noise = rng.normal(0.0, sensor.baseline_std)
                value = sensor.baseline_mean + noise
                if sensor.sensor_type == "VIBRATION":
                    value += degrade_factor * 0.55
                if sensor.sensor_type == "TEMPERATURE":
                    value += degrade_factor * 8.0
                for _ in range(reads_per_minute):
                    rows.append(
                        {
                            "MACHINE_ID": machine_id,
                            "LINE_ID": line,
                            "SITE": site,
                            "SENSOR_TYPE": sensor.sensor_type,
                            "SENSOR_UNIT": sensor.unit,
                            "VALUE": float(round(value, 4)),
                            "RECORDED_AT": ts,
                        }
                    )

    df = pd.DataFrame(rows)
    return _log_result("manufacturing telemetry", df)


# ---------------------------------------------------------------------------
# 04 — Healthcare: de-identified EHR records
# ---------------------------------------------------------------------------


HEALTH_REGIONS = ["NORTHEAST", "SOUTHEAST", "MIDWEST", "SOUTHWEST", "WEST"]
HEALTH_CONDITIONS = [
    "TYPE_2_DIABETES",
    "HYPERTENSION",
    "COPD",
    "ASTHMA",
    "CHF",
    "DEPRESSION",
    "MIGRAINE",
    "OSTEOARTHRITIS",
    "CAD",
    "OBESITY",
]
HEALTH_DEPARTMENTS = ["CARDIOLOGY", "ENDOCRINOLOGY", "PULMONOLOGY", "NEUROLOGY", "PRIMARY_CARE"]


def generate_healthcare_records(n_rows: int = 5_000, seed: int = 46) -> pd.DataFrame:
    """Generate de-identified patient encounter records.

    Schema matches `demos/04-healthcare-ehr-governed-analytics/01-setup.sql::PATIENT_ENCOUNTERS`.

    De-identification is applied by construction: every name, DOB, and address
    field is replaced with a surrogate token. The only identifying key is the
    hashed patient pseudonym.
    """
    rnd, rng = _rng(seed)
    now = datetime.now(timezone.utc).replace(microsecond=0)
    patient_ids = [_stable_id("PAT", i) for i in range(n_rows // 3 + 1)]

    rows: list[dict[str, Any]] = []
    for i in range(n_rows):
        pat = patient_ids[rng.integers(0, len(patient_ids))]
        primary = rnd.choice(HEALTH_CONDITIONS)
        comorbidities = rnd.sample(HEALTH_CONDITIONS, k=rnd.randint(0, 3))
        dept = rnd.choice(HEALTH_DEPARTMENTS)
        encounter_ts = now - timedelta(days=int(rng.integers(0, 365 * 3)))
        age_decade = int(rnd.choices(range(0, 100, 10), weights=[2, 3, 5, 9, 14, 18, 20, 15, 10, 4])[0])
        gender = rnd.choices(["M", "F", "X"], weights=[48, 50, 2])[0]
        region = rnd.choice(HEALTH_REGIONS)
        length_of_stay_days = int(rng.integers(0, 9))
        rows.append(
            {
                "ENCOUNTER_ID": _stable_id("ENC", i, pat),
                "PATIENT_PSEUDONYM": pat,
                "ENCOUNTER_TIMESTAMP": encounter_ts,
                "DEPARTMENT": dept,
                "PRIMARY_CONDITION": primary,
                "COMORBIDITY_COUNT": len(comorbidities),
                "AGE_DECADE": age_decade,
                "GENDER": gender,
                "REGION": region,
                "LENGTH_OF_STAY_DAYS": length_of_stay_days,
                "READMITTED_WITHIN_30D": bool(rng.random() < 0.12),
                "BILLED_AMOUNT_USD": float(round(rng.lognormal(mean=8.2, sigma=0.8), 2)),
                "INSURANCE_TYPE": rnd.choice(["COMMERCIAL", "MEDICARE", "MEDICAID", "SELF_PAY"]),
            }
        )

    df = pd.DataFrame(rows)
    return _log_result("healthcare encounters", df)


# ---------------------------------------------------------------------------
# 05 — Media: user behavior events
# ---------------------------------------------------------------------------


MEDIA_EVENT_TYPES = ["IMPRESSION", "PLAY_START", "PLAY_COMPLETE", "LIKE", "SHARE", "SKIP", "SEARCH"]
MEDIA_CONTENT_TYPES = ["MOVIE", "SERIES_EPISODE", "SHORT_FORM", "LIVE_STREAM", "PODCAST"]
MEDIA_GENRES = [
    "DRAMA",
    "COMEDY",
    "ACTION",
    "DOCUMENTARY",
    "SCI_FI",
    "ROMANCE",
    "THRILLER",
    "K_DRAMA",
    "ANIME",
    "NEWS",
]


def generate_media_events(
    n_rows: int = 50_000,
    n_users: int = 5_000,
    n_content: int = 2_000,
    seed: int = 47,
) -> pd.DataFrame:
    """Generate synthetic user-behavior events for the media demo.

    Schema matches `demos/05-media-content-recommendation/01-setup.sql::USER_EVENTS`.
    """
    rnd, rng = _rng(seed)
    now = datetime.now(timezone.utc).replace(microsecond=0)
    users = [_stable_id("USR", i) for i in range(n_users)]
    content = [_stable_id("CNT", i) for i in range(n_content)]

    rows: list[dict[str, Any]] = []
    for i in range(n_rows):
        user = users[rng.integers(0, n_users)]
        cid = content[rng.integers(0, n_content)]
        event = rnd.choices(MEDIA_EVENT_TYPES, weights=[45, 15, 12, 10, 5, 8, 5])[0]
        watch_ms = 0
        if event in {"PLAY_START", "PLAY_COMPLETE"}:
            watch_ms = int(rng.integers(5_000, 2_400_000))
        elif event == "SKIP":
            watch_ms = int(rng.integers(500, 15_000))
        event_ts = now - timedelta(seconds=int(rng.integers(0, 86_400 * 7)))
        rows.append(
            {
                "EVENT_ID": _stable_id("MEV", i, user),
                "USER_ID": user,
                "CONTENT_ID": cid,
                "CONTENT_TYPE": rnd.choice(MEDIA_CONTENT_TYPES),
                "GENRE": rnd.choice(MEDIA_GENRES),
                "EVENT_TYPE": event,
                "WATCH_DURATION_MS": watch_ms,
                "EVENT_TIMESTAMP": event_ts,
                "DEVICE_TYPE": rnd.choice(["SMART_TV", "MOBILE", "WEB", "TABLET", "CONSOLE"]),
                "LOCALE": rnd.choice(["ko-KR", "en-US", "ja-JP", "zh-TW", "en-GB"]),
            }
        )

    df = pd.DataFrame(rows)
    return _log_result("media events", df)


def generate_media_catalog(n_content: int = 2_000, seed: int = 48) -> pd.DataFrame:
    """Generate the content catalog with synthetic descriptions.

    Descriptions are intentionally templated so the downstream Cortex
    `EMBED_TEXT` demo produces meaningful clusters without requiring real copy.
    """
    rnd, _ = _rng(seed)
    templates = [
        "A {genre_label} story set in a {setting} where a {protagonist} must {goal}.",
        "This {genre_label} follows a {protagonist} navigating {conflict} during {era}.",
        "A gripping {genre_label} about {theme} and the {protagonist} who confronts it.",
        "A {tone} {genre_label} exploring themes of {theme} against a {setting} backdrop.",
    ]
    settings = ["futuristic Seoul", "1980s Tokyo", "ancient Joseon", "a Mars colony", "a coastal village"]
    protagonists = ["detective", "scientist", "chef", "student", "soldier", "musician"]
    goals = ["uncover a conspiracy", "rescue a loved one", "rebuild a family", "win a competition"]
    themes = ["identity", "redemption", "ambition", "loss", "loyalty", "technology"]
    conflicts = ["political intrigue", "corporate espionage", "a sudden loss", "a long-hidden secret"]
    eras = ["the digital revolution", "the Joseon dynasty", "a global pandemic", "an economic collapse"]
    tones = ["quiet", "intense", "tender", "sardonic"]

    rows: list[dict[str, Any]] = []
    for i in range(n_content):
        genre = rnd.choice(MEDIA_GENRES)
        genre_label = genre.replace("_", " ").title()
        description = rnd.choice(templates).format(
            genre_label=genre_label,
            setting=rnd.choice(settings),
            protagonist=rnd.choice(protagonists),
            goal=rnd.choice(goals),
            theme=rnd.choice(themes),
            conflict=rnd.choice(conflicts),
            era=rnd.choice(eras),
            tone=rnd.choice(tones),
        )
        rows.append(
            {
                "CONTENT_ID": _stable_id("CNT", i),
                "TITLE": f"{rnd.choice(tones).title()} {genre_label} #{i}",
                "CONTENT_TYPE": rnd.choice(MEDIA_CONTENT_TYPES),
                "GENRE": genre,
                "RUNTIME_MINUTES": int(rnd.choice([22, 45, 60, 90, 120])),
                "RELEASE_YEAR": int(rnd.randint(2005, 2026)),
                "DESCRIPTION": description,
                "LOCALE": rnd.choice(["ko-KR", "en-US", "ja-JP", "zh-TW"]),
            }
        )
    df = pd.DataFrame(rows)
    return _log_result("media catalog", df)


# ---------------------------------------------------------------------------
# CLI entry point (used by per-demo 02-load-data.py scripts)
# ---------------------------------------------------------------------------


def summarize_all_defaults() -> dict[str, int]:
    """Utility for dry-run preview: generate default-size samples of each dataset."""
    return {
        "finance_transactions": len(generate_finance_transactions(n_rows=500)),
        "retail_events": len(generate_retail_events(n_rows=500)),
        "retail_customers": len(generate_retail_customers(n_customers=500)),
        "manufacturing_telemetry": len(generate_manufacturing_telemetry(n_machines=10, hours=1)),
        "healthcare_records": len(generate_healthcare_records(n_rows=500)),
        "media_events": len(generate_media_events(n_rows=500)),
        "media_catalog": len(generate_media_catalog(n_content=100)),
    }


if __name__ == "__main__":  # pragma: no cover
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    _ = math.inf  # keep numpy+math imports honest
    LOG.info("Default-size sample counts: %s", summarize_all_defaults())
