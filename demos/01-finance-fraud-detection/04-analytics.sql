-- ---------------------------------------------------------------------------
-- demos/01-finance-fraud-detection/04-analytics.sql
-- Business queries that tell the fraud-detection story end-to-end.
-- Each block has a header comment naming who cares about the answer.
-- ---------------------------------------------------------------------------

USE ROLE SYSADMIN;
USE WAREHOUSE DEMO_WH;
USE DATABASE SNOWFLAKE_DEMO_PACK;
USE SCHEMA FINANCE;

-- ---------------------------------------------------------------------------
-- Q1. [Fraud Operations Director] Fraud rate by channel, last 24 hours.
-- ---------------------------------------------------------------------------
SELECT
    CHANNEL,
    COUNT(*)                                                              AS N_TRANSACTIONS,
    SUM(CASE WHEN IS_FRAUD_GROUND_TRUTH THEN 1 ELSE 0 END)                AS N_FRAUD,
    SUM(CASE WHEN IS_FRAUD_GROUND_TRUTH THEN 1 ELSE 0 END)::FLOAT
        / NULLIF(COUNT(*), 0)                                             AS FRAUD_RATE,
    SUM(AMOUNT_USD)                                                       AS GROSS_VOLUME_USD,
    SUM(CASE WHEN IS_FRAUD_GROUND_TRUTH THEN AMOUNT_USD ELSE 0 END)       AS FRAUD_VOLUME_USD
FROM TRANSACTIONS_SCORED
WHERE EVENT_TIMESTAMP >= DATEADD('hour', -24, CURRENT_TIMESTAMP())
GROUP BY CHANNEL
ORDER BY FRAUD_RATE DESC;

-- ---------------------------------------------------------------------------
-- Q2. [CFO] Loss avoided by blocking the top risk decile.
-- ---------------------------------------------------------------------------
WITH SCORED AS (
    SELECT
        TRANSACTION_ID,
        AMOUNT_USD,
        FRAUD_PROBABILITY,
        IS_FRAUD_GROUND_TRUTH,
        NTILE(10) OVER (ORDER BY FRAUD_PROBABILITY DESC) AS RISK_DECILE
    FROM TRANSACTIONS_SCORED
)
SELECT
    RISK_DECILE,
    COUNT(*)                                                                   AS N,
    SUM(CASE WHEN IS_FRAUD_GROUND_TRUTH THEN 1 ELSE 0 END)                     AS N_TRUE_POSITIVES,
    SUM(CASE WHEN NOT IS_FRAUD_GROUND_TRUTH THEN 1 ELSE 0 END)                 AS N_FALSE_POSITIVES,
    SUM(CASE WHEN IS_FRAUD_GROUND_TRUTH THEN AMOUNT_USD ELSE 0 END)            AS LOSS_AVOIDED_USD,
    SUM(CASE WHEN NOT IS_FRAUD_GROUND_TRUTH THEN AMOUNT_USD ELSE 0 END)        AS FRICTION_USD
FROM SCORED
WHERE RISK_DECILE <= 3
GROUP BY RISK_DECILE
ORDER BY RISK_DECILE;

-- ---------------------------------------------------------------------------
-- Q3. [Model Risk Committee] Score distribution and calibration check.
-- ---------------------------------------------------------------------------
SELECT
    CASE
        WHEN FRAUD_PROBABILITY < 0.1 THEN 'P00_10'
        WHEN FRAUD_PROBABILITY < 0.2 THEN 'P10_20'
        WHEN FRAUD_PROBABILITY < 0.3 THEN 'P20_30'
        WHEN FRAUD_PROBABILITY < 0.4 THEN 'P30_40'
        WHEN FRAUD_PROBABILITY < 0.5 THEN 'P40_50'
        WHEN FRAUD_PROBABILITY < 0.6 THEN 'P50_60'
        WHEN FRAUD_PROBABILITY < 0.7 THEN 'P60_70'
        WHEN FRAUD_PROBABILITY < 0.8 THEN 'P70_80'
        WHEN FRAUD_PROBABILITY < 0.9 THEN 'P80_90'
        ELSE 'P90_100'
    END                                                                       AS PROBABILITY_BAND,
    COUNT(*)                                                                  AS N,
    AVG(CASE WHEN IS_FRAUD_GROUND_TRUTH THEN 1.0 ELSE 0.0 END)                AS ACTUAL_FRAUD_RATE,
    AVG(FRAUD_PROBABILITY)                                                    AS MEAN_PREDICTED
FROM TRANSACTIONS_SCORED
GROUP BY PROBABILITY_BAND
ORDER BY PROBABILITY_BAND;

-- ---------------------------------------------------------------------------
-- Q4. [Analyst Team Lead] Open alert queue summary.
-- ---------------------------------------------------------------------------
SELECT
    RISK_ACTION,
    COUNT(*)                                                                  AS OPEN_ALERTS,
    AVG(FRAUD_PROBABILITY)                                                    AS AVG_PROBABILITY,
    SUM(AMOUNT_USD)                                                           AS TOTAL_EXPOSURE_USD,
    MIN(CREATED_AT)                                                           AS OLDEST_OPEN_ALERT,
    MAX(CREATED_AT)                                                           AS NEWEST_ALERT
FROM ALERT_QUEUE
WHERE ALERT_STATUS = 'OPEN'
GROUP BY RISK_ACTION
ORDER BY AVG_PROBABILITY DESC;

-- ---------------------------------------------------------------------------
-- Q5. [Customer Experience] False-positive burden by customer segment.
-- ---------------------------------------------------------------------------
SELECT
    CASE
        WHEN CUSTOMER_AMOUNT_AVG_30D < 50    THEN 'LOW_SPEND'
        WHEN CUSTOMER_AMOUNT_AVG_30D < 200   THEN 'MID_SPEND'
        ELSE                                      'HIGH_SPEND'
    END                                                                       AS CUSTOMER_SEGMENT,
    COUNT(*)                                                                  AS TOTAL_TXN,
    SUM(CASE WHEN RISK_ACTION IN ('REVIEW', 'BLOCK') THEN 1 ELSE 0 END)       AS FLAGGED,
    SUM(
        CASE
            WHEN RISK_ACTION IN ('REVIEW', 'BLOCK') AND NOT IS_FRAUD_GROUND_TRUTH
            THEN 1
            ELSE 0
        END
    )                                                                         AS FALSE_POSITIVES,
    SUM(
        CASE
            WHEN RISK_ACTION IN ('REVIEW', 'BLOCK') AND NOT IS_FRAUD_GROUND_TRUTH
            THEN 1
            ELSE 0
        END
    )::FLOAT / NULLIF(COUNT(*), 0)                                            AS FP_RATE
FROM TRANSACTIONS_SCORED
GROUP BY CUSTOMER_SEGMENT
ORDER BY CUSTOMER_SEGMENT;

-- ---------------------------------------------------------------------------
-- Q6. [Fraud Strategy] Cross-tab: UDF vs Cortex agreement.
-- ---------------------------------------------------------------------------
SELECT
    CASE WHEN FRAUD_PROBABILITY    >= 0.7 THEN 'UDF_HIGH'    ELSE 'UDF_LOW'    END AS UDF_BAND,
    CASE WHEN CORTEX_FRAUD_SCORE   >= 0.7 THEN 'CORTEX_HIGH' ELSE 'CORTEX_LOW' END AS CORTEX_BAND,
    COUNT(*)                                                                        AS N,
    AVG(CASE WHEN IS_FRAUD_GROUND_TRUTH THEN 1.0 ELSE 0.0 END)                      AS OBSERVED_FRAUD_RATE
FROM TRANSACTIONS_SCORED
GROUP BY UDF_BAND, CORTEX_BAND
ORDER BY UDF_BAND, CORTEX_BAND;

-- ---------------------------------------------------------------------------
-- Q7. [Executive slide] Single-number headline KPI for the 5-minute demo.
-- ---------------------------------------------------------------------------
SELECT
    COUNT(*)                                                                        AS TRANSACTIONS_SCORED,
    ROUND(100.0 * AVG(CASE WHEN IS_FRAUD_GROUND_TRUTH THEN 1.0 ELSE 0.0 END), 3)    AS OVERALL_FRAUD_RATE_PCT,
    SUM(CASE WHEN RISK_ACTION = 'BLOCK'  AND IS_FRAUD_GROUND_TRUTH THEN AMOUNT_USD ELSE 0 END) AS BLOCKED_FRAUD_USD,
    SUM(CASE WHEN RISK_ACTION = 'BLOCK'  AND NOT IS_FRAUD_GROUND_TRUTH THEN 1 ELSE 0 END)      AS FALSE_BLOCKS,
    SUM(CASE WHEN RISK_ACTION = 'REVIEW' THEN 1 ELSE 0 END)                                    AS ANALYST_QUEUE_DEPTH,
    DATEDIFF(
        'millisecond',
        MIN(EVENT_TIMESTAMP),
        MAX(SCORED_AT)
    )::FLOAT / NULLIF(COUNT(*), 0)                                                             AS AVG_LATENCY_MS
FROM TRANSACTIONS_SCORED
WHERE EVENT_TIMESTAMP >= DATEADD('hour', -24, CURRENT_TIMESTAMP());
