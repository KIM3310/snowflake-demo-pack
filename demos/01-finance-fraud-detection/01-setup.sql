-- ---------------------------------------------------------------------------
-- demos/01-finance-fraud-detection/01-setup.sql
-- Creates the Finance schema objects for the fraud-detection demo.
--
-- Feature set exercised here:
--   * Raw landing table for Snowpipe Streaming ingest
--   * Dynamic Tables with 1 minute target lag (enriched and scored layers)
--   * Streams and Tasks for alert routing
--   * Row Access Policy placeholder for customer-level isolation
-- ---------------------------------------------------------------------------

USE ROLE SYSADMIN;
USE WAREHOUSE DEMO_WH;
USE DATABASE SNOWFLAKE_DEMO_PACK;
USE SCHEMA FINANCE;

-- 1. Raw landing table for streaming authorizations
CREATE OR REPLACE TABLE TRANSACTIONS_RAW (
    TRANSACTION_ID             STRING        NOT NULL,
    CUSTOMER_ID                STRING        NOT NULL,
    CARD_ID                    STRING        NOT NULL,
    MERCHANT_CATEGORY_CODE     STRING,
    MERCHANT_CATEGORY_LABEL    STRING,
    CHANNEL                    STRING,
    COUNTRY_CODE               STRING,
    AMOUNT_USD                 NUMBER(18, 4),
    EVENT_TIMESTAMP            TIMESTAMP_NTZ NOT NULL,
    DEVICE_FINGERPRINT         STRING,
    IS_FRAUD_GROUND_TRUTH      BOOLEAN,
    INGEST_TIMESTAMP           TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
    CONSTRAINT PK_TRANSACTIONS_RAW PRIMARY KEY (TRANSACTION_ID)
)
CLUSTER BY (EVENT_TIMESTAMP, CUSTOMER_ID)
COMMENT = 'Landing table for Snowpipe Streaming authorization events';

-- 2. Labeled historical table used to train the Cortex CLASSIFICATION model
CREATE OR REPLACE TABLE TRANSACTIONS_LABELED AS
SELECT *
FROM TRANSACTIONS_RAW
WHERE 1 = 0;

-- 3. Enriched layer: rolling windows per card and per customer
--    Target lag of 60 seconds matches the near-real-time requirement.
CREATE OR REPLACE DYNAMIC TABLE TRANSACTIONS_ENRICHED
    TARGET_LAG = '1 minute'
    WAREHOUSE = DEMO_WH
AS
SELECT
    T.TRANSACTION_ID,
    T.CUSTOMER_ID,
    T.CARD_ID,
    T.MERCHANT_CATEGORY_CODE,
    T.MERCHANT_CATEGORY_LABEL,
    T.CHANNEL,
    T.COUNTRY_CODE,
    T.AMOUNT_USD,
    T.EVENT_TIMESTAMP,
    T.DEVICE_FINGERPRINT,
    T.IS_FRAUD_GROUND_TRUTH,

    -- Count of transactions on this card in the last hour
    COUNT(*) OVER (
        PARTITION BY T.CARD_ID
        ORDER BY T.EVENT_TIMESTAMP
        RANGE BETWEEN INTERVAL '1 hour' PRECEDING AND CURRENT ROW
    )                                                        AS CARD_TXN_COUNT_1H,

    -- Sum of transaction amount on this card in the last hour
    SUM(T.AMOUNT_USD) OVER (
        PARTITION BY T.CARD_ID
        ORDER BY T.EVENT_TIMESTAMP
        RANGE BETWEEN INTERVAL '1 hour' PRECEDING AND CURRENT ROW
    )                                                        AS CARD_AMOUNT_SUM_1H,

    -- Number of distinct countries on this card in the last 24 hours
    COUNT(DISTINCT T.COUNTRY_CODE) OVER (
        PARTITION BY T.CARD_ID
        ORDER BY T.EVENT_TIMESTAMP
        RANGE BETWEEN INTERVAL '24 hour' PRECEDING AND CURRENT ROW
    )                                                        AS CARD_DISTINCT_COUNTRIES_24H,

    -- Average transaction amount for this customer over the last 30 days
    AVG(T.AMOUNT_USD) OVER (
        PARTITION BY T.CUSTOMER_ID
        ORDER BY T.EVENT_TIMESTAMP
        RANGE BETWEEN INTERVAL '30 day' PRECEDING AND CURRENT ROW
    )                                                        AS CUSTOMER_AMOUNT_AVG_30D,

    -- Standard deviation of customer amount for z-score computation
    STDDEV_SAMP(T.AMOUNT_USD) OVER (
        PARTITION BY T.CUSTOMER_ID
        ORDER BY T.EVENT_TIMESTAMP
        RANGE BETWEEN INTERVAL '30 day' PRECEDING AND CURRENT ROW
    )                                                        AS CUSTOMER_AMOUNT_STDDEV_30D,

    -- Flag if this transaction is in a "high-risk" geography
    IFF(T.COUNTRY_CODE IN ('RU', 'NG', 'VE', 'IR'), 1, 0)    AS HIGH_RISK_COUNTRY_FLAG,
    IFF(T.CHANNEL = 'ECOMMERCE', 1, 0)                       AS ECOMMERCE_FLAG
FROM TRANSACTIONS_RAW AS T
COMMENT = 'Rolling-window feature table; refreshes incrementally every 60 seconds';

-- 4. Stream over the enriched table; drives alert-routing tasks
CREATE OR REPLACE STREAM TRANSACTIONS_ENRICHED_STREAM
    ON DYNAMIC TABLE TRANSACTIONS_ENRICHED
    SHOW_INITIAL_ROWS = FALSE
    COMMENT = 'CDC stream over the enriched layer; consumed by ALERT_ROUTER_TASK';

-- 5. Placeholder Cortex CLASSIFICATION model definition
--    In a live run, uncomment after TRANSACTIONS_LABELED has rows:
--
--    CREATE OR REPLACE SNOWFLAKE.ML.CLASSIFICATION FRAUD_CORTEX_MODEL(
--        INPUT_DATA   => SYSTEM$REFERENCE('VIEW', 'TRANSACTIONS_LABELED_V', 'SESSION'),
--        TARGET_COLNAME => 'IS_FRAUD_GROUND_TRUTH'
--    );
--
-- For scaffolding, we create a helper view referenced by the Dynamic Table below.
CREATE OR REPLACE VIEW TRANSACTIONS_LABELED_V AS
SELECT
    AMOUNT_USD,
    HIGH_RISK_COUNTRY_FLAG,
    ECOMMERCE_FLAG,
    CARD_TXN_COUNT_1H,
    CARD_AMOUNT_SUM_1H,
    CARD_DISTINCT_COUNTRIES_24H,
    CUSTOMER_AMOUNT_AVG_30D,
    COALESCE(CUSTOMER_AMOUNT_STDDEV_30D, 0.0) AS CUSTOMER_AMOUNT_STDDEV_30D,
    IS_FRAUD_GROUND_TRUTH
FROM TRANSACTIONS_ENRICHED
WHERE IS_FRAUD_GROUND_TRUTH IS NOT NULL;

-- 6. Scored layer (Dynamic Table)
--    Combines the Snowpark UDF with the Cortex prediction for a blended score.
--    The FRAUD_PROBABILITY_UDF function is registered by 03-fraud-model.py.
CREATE OR REPLACE DYNAMIC TABLE TRANSACTIONS_SCORED
    TARGET_LAG = '1 minute'
    WAREHOUSE = DEMO_WH
AS
SELECT
    E.*,
    FRAUD_PROBABILITY_UDF(
        E.AMOUNT_USD,
        E.HIGH_RISK_COUNTRY_FLAG,
        E.ECOMMERCE_FLAG,
        E.CARD_TXN_COUNT_1H,
        E.CARD_AMOUNT_SUM_1H,
        E.CARD_DISTINCT_COUNTRIES_24H,
        E.CUSTOMER_AMOUNT_AVG_30D,
        COALESCE(E.CUSTOMER_AMOUNT_STDDEV_30D, 0.0)
    )                                                                 AS FRAUD_PROBABILITY,
    0.0::FLOAT                                                        AS CORTEX_FRAUD_SCORE,
    CASE
        WHEN FRAUD_PROBABILITY_UDF(
            E.AMOUNT_USD,
            E.HIGH_RISK_COUNTRY_FLAG,
            E.ECOMMERCE_FLAG,
            E.CARD_TXN_COUNT_1H,
            E.CARD_AMOUNT_SUM_1H,
            E.CARD_DISTINCT_COUNTRIES_24H,
            E.CUSTOMER_AMOUNT_AVG_30D,
            COALESCE(E.CUSTOMER_AMOUNT_STDDEV_30D, 0.0)
        ) >= 0.85 THEN 'BLOCK'
        WHEN FRAUD_PROBABILITY_UDF(
            E.AMOUNT_USD,
            E.HIGH_RISK_COUNTRY_FLAG,
            E.ECOMMERCE_FLAG,
            E.CARD_TXN_COUNT_1H,
            E.CARD_AMOUNT_SUM_1H,
            E.CARD_DISTINCT_COUNTRIES_24H,
            E.CUSTOMER_AMOUNT_AVG_30D,
            COALESCE(E.CUSTOMER_AMOUNT_STDDEV_30D, 0.0)
        ) >= 0.60 THEN 'REVIEW'
        ELSE 'APPROVE'
    END                                                               AS RISK_ACTION,
    CURRENT_TIMESTAMP()                                               AS SCORED_AT
FROM TRANSACTIONS_ENRICHED AS E
COMMENT = 'Transaction-level scored output; drives analyst queue and Streamlit app';

-- 7. Alert queue table (populated by a downstream task)
CREATE OR REPLACE TABLE ALERT_QUEUE (
    ALERT_ID               STRING        DEFAULT UUID_STRING(),
    TRANSACTION_ID         STRING        NOT NULL,
    CUSTOMER_ID            STRING        NOT NULL,
    CHANNEL                STRING,
    AMOUNT_USD             NUMBER(18, 4),
    FRAUD_PROBABILITY      FLOAT,
    RISK_ACTION            STRING,
    ALERT_STATUS           STRING        DEFAULT 'OPEN',
    CREATED_AT             TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
    CLOSED_AT              TIMESTAMP_NTZ,
    DISPOSITION            STRING,
    CONSTRAINT PK_ALERT_QUEUE PRIMARY KEY (ALERT_ID)
)
COMMENT = 'Open analyst alert queue fed by the REVIEW and BLOCK bands';

-- 8. Task that moves high-risk rows from the enriched stream into the alert queue
CREATE OR REPLACE TASK ALERT_ROUTER_TASK
    WAREHOUSE = DEMO_WH
    SCHEDULE = '1 minute'
    COMMENT = 'Drains TRANSACTIONS_ENRICHED_STREAM into ALERT_QUEUE for analyst triage'
AS
INSERT INTO ALERT_QUEUE (
    TRANSACTION_ID,
    CUSTOMER_ID,
    CHANNEL,
    AMOUNT_USD,
    FRAUD_PROBABILITY,
    RISK_ACTION
)
SELECT
    S.TRANSACTION_ID,
    S.CUSTOMER_ID,
    S.CHANNEL,
    S.AMOUNT_USD,
    FRAUD_PROBABILITY_UDF(
        S.AMOUNT_USD,
        S.HIGH_RISK_COUNTRY_FLAG,
        S.ECOMMERCE_FLAG,
        S.CARD_TXN_COUNT_1H,
        S.CARD_AMOUNT_SUM_1H,
        S.CARD_DISTINCT_COUNTRIES_24H,
        S.CUSTOMER_AMOUNT_AVG_30D,
        COALESCE(S.CUSTOMER_AMOUNT_STDDEV_30D, 0.0)
    ) AS FRAUD_PROBABILITY,
    CASE
        WHEN FRAUD_PROBABILITY_UDF(
            S.AMOUNT_USD,
            S.HIGH_RISK_COUNTRY_FLAG,
            S.ECOMMERCE_FLAG,
            S.CARD_TXN_COUNT_1H,
            S.CARD_AMOUNT_SUM_1H,
            S.CARD_DISTINCT_COUNTRIES_24H,
            S.CUSTOMER_AMOUNT_AVG_30D,
            COALESCE(S.CUSTOMER_AMOUNT_STDDEV_30D, 0.0)
        ) >= 0.85 THEN 'BLOCK'
        ELSE 'REVIEW'
    END AS RISK_ACTION
FROM TRANSACTIONS_ENRICHED_STREAM AS S
WHERE FRAUD_PROBABILITY_UDF(
        S.AMOUNT_USD,
        S.HIGH_RISK_COUNTRY_FLAG,
        S.ECOMMERCE_FLAG,
        S.CARD_TXN_COUNT_1H,
        S.CARD_AMOUNT_SUM_1H,
        S.CARD_DISTINCT_COUNTRIES_24H,
        S.CUSTOMER_AMOUNT_AVG_30D,
        COALESCE(S.CUSTOMER_AMOUNT_STDDEV_30D, 0.0)
    ) >= 0.60;

-- Leaving the task suspended keeps the demo cheap; resume it during the live walkthrough.
ALTER TASK ALERT_ROUTER_TASK SUSPEND;

-- 9. Row access policy scaffold (enabled for multi-tenant issuer sharing)
CREATE OR REPLACE ROW ACCESS POLICY FRAUD_CUSTOMER_ACCESS AS (CUSTOMER_ID STRING)
    RETURNS BOOLEAN ->
    CURRENT_ROLE() IN ('ACCOUNTADMIN', 'SYSADMIN', 'DEMO_PACK_ROLE')
    OR EXISTS (
        SELECT 1
        FROM TABLE(INFORMATION_SCHEMA.CURRENT_ROLES()) AS R
        WHERE R.ROLE_NAME = 'ANALYST_' || CUSTOMER_ID
    );

-- The policy is defined but not attached by default so the demo runs cleanly.
-- To activate it:
--   ALTER TABLE ALERT_QUEUE ADD ROW ACCESS POLICY FRAUD_CUSTOMER_ACCESS ON (CUSTOMER_ID);

-- 10. Tag the scored table for governance lineage (Healthcare demo uses the same tags)
USE SCHEMA HEALTHCARE;
ALTER TABLE SNOWFLAKE_DEMO_PACK.FINANCE.TRANSACTIONS_SCORED
    SET TAG PII_CLASS = 'MEDIUM',
            COMPLIANCE_REGIME = 'PCI_DSS';

USE SCHEMA FINANCE;

-- End of 01-setup.sql
