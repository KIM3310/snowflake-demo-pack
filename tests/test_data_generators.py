from __future__ import annotations

from common.data_generators import (
    generate_finance_transactions,
    generate_healthcare_records,
    generate_manufacturing_telemetry,
    generate_media_catalog,
    generate_media_events,
    generate_retail_customers,
    generate_retail_events,
)


def test_finance_generator_produces_contract_columns() -> None:
    df = generate_finance_transactions(n_rows=25, n_customers=5, seed=101)

    assert len(df) == 25
    assert {
        "TRANSACTION_ID",
        "CUSTOMER_ID",
        "CARD_ID",
        "AMOUNT_USD",
        "EVENT_TIMESTAMP",
        "IS_FRAUD_GROUND_TRUTH",
    }.issubset(df.columns)
    assert df["TRANSACTION_ID"].is_unique


def test_retail_generators_produce_joinable_customer_ids() -> None:
    customers = generate_retail_customers(n_customers=8, seed=102)
    events = generate_retail_events(n_rows=30, n_customers=8, seed=103)

    assert len(customers) == 8
    assert len(events) == 30
    assert set(events["CUSTOMER_ID"]).issubset(set(customers["CUSTOMER_ID"]))


def test_manufacturing_generator_marks_degraded_machines() -> None:
    df = generate_manufacturing_telemetry(
        n_machines=4,
        hours=1,
        reads_per_minute=1,
        seed=104,
        degrade_machines=2,
    )

    assert not df.empty
    assert {"MACHINE_ID", "LINE_ID", "SENSOR_TYPE", "SENSOR_UNIT", "VALUE"}.issubset(df.columns)
    assert df["MACHINE_ID"].nunique() == 4
    assert (df["VALUE"] >= 0).all()


def test_healthcare_generator_returns_deidentified_records() -> None:
    df = generate_healthcare_records(n_rows=12, seed=105)

    assert len(df) == 12
    assert {"ENCOUNTER_ID", "PATIENT_PSEUDONYM", "DEPARTMENT", "REGION"}.issubset(df.columns)
    assert df["ENCOUNTER_ID"].is_unique
    assert df["PATIENT_PSEUDONYM"].str.startswith("PAT_").all()


def test_media_generators_produce_content_and_events() -> None:
    catalog = generate_media_catalog(n_content=6, seed=106)
    events = generate_media_events(n_rows=24, n_users=4, n_content=6, seed=107)

    assert len(catalog) == 6
    assert len(events) == 24
    assert {"CONTENT_ID", "TITLE", "GENRE"}.issubset(catalog.columns)
    assert {"EVENT_ID", "USER_ID", "CONTENT_ID", "EVENT_TYPE"}.issubset(events.columns)
