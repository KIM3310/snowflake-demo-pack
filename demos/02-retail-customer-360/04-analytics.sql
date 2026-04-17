-- ---------------------------------------------------------------------------
-- demos/02-retail-customer-360/04-analytics.sql
-- Business queries that demonstrate the unified customer 360.
-- ---------------------------------------------------------------------------

USE ROLE SYSADMIN;
USE WAREHOUSE DEMO_WH;
USE DATABASE SNOWFLAKE_DEMO_PACK;
USE SCHEMA RETAIL;

-- ---------------------------------------------------------------------------
-- Q1. [CX Director] Single-customer 360 lookup.
-- ---------------------------------------------------------------------------
SELECT *
FROM CUSTOMER_360_VIEW
LIMIT 5;

-- ---------------------------------------------------------------------------
-- Q2. [CMO] Channel reach and cross-channel overlap.
-- ---------------------------------------------------------------------------
WITH CHANNEL_TOUCH AS (
    SELECT
        CUSTOMER_ID,
        ARRAY_AGG(DISTINCT CHANNEL) WITHIN GROUP (ORDER BY CHANNEL) AS CHANNELS
    FROM CUSTOMER_EVENTS
    WHERE EVENT_TIMESTAMP >= DATEADD('day', -90, CURRENT_TIMESTAMP())
    GROUP BY CUSTOMER_ID
)
SELECT
    ARRAY_SIZE(CHANNELS)                                       AS N_CHANNELS_USED,
    COUNT(*)                                                   AS N_CUSTOMERS,
    ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 2)         AS PCT_CUSTOMERS
FROM CHANNEL_TOUCH
GROUP BY N_CHANNELS_USED
ORDER BY N_CHANNELS_USED;

-- ---------------------------------------------------------------------------
-- Q3. [Loyalty Ops] RFM segmentation on the trailing 90 days.
-- ---------------------------------------------------------------------------
WITH SCORED AS (
    SELECT
        CUSTOMER_ID,
        DAYS_SINCE_LAST_EVENT,
        PURCHASE_COUNT_90D,
        GROSS_SPEND_90D,
        NTILE(5) OVER (ORDER BY DAYS_SINCE_LAST_EVENT ASC)      AS RECENCY_Q,
        NTILE(5) OVER (ORDER BY PURCHASE_COUNT_90D DESC)        AS FREQUENCY_Q,
        NTILE(5) OVER (ORDER BY GROSS_SPEND_90D DESC)           AS MONETARY_Q
    FROM CUSTOMER_RFM_DAILY
    WHERE PURCHASE_COUNT_90D > 0
)
SELECT
    RECENCY_Q,
    FREQUENCY_Q,
    MONETARY_Q,
    COUNT(*)                                                    AS N_CUSTOMERS,
    AVG(GROSS_SPEND_90D)                                        AS AVG_SPEND_USD
FROM SCORED
GROUP BY RECENCY_Q, FREQUENCY_Q, MONETARY_Q
ORDER BY RECENCY_Q, FREQUENCY_Q, MONETARY_Q;

-- ---------------------------------------------------------------------------
-- Q4. [Call Center Ops] Volume by Cortex-generated theme.
-- ---------------------------------------------------------------------------
SELECT
    THEME,
    COUNT(*)                                                    AS N_NOTES,
    COUNT(DISTINCT CUSTOMER_ID)                                 AS N_CUSTOMERS,
    ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 2)          AS PCT_OF_NOTES
FROM CALL_CENTER_THEMES
GROUP BY THEME
ORDER BY N_NOTES DESC;

-- ---------------------------------------------------------------------------
-- Q5. [Marketing] Customers with cancel intent AND high lifetime value.
-- ---------------------------------------------------------------------------
SELECT
    C.CUSTOMER_ID,
    C.LIFETIME_VALUE_USD,
    C.LOYALTY_TIER,
    C.PREFERRED_CHANNEL,
    T.SUMMARY
FROM CUSTOMERS AS C
JOIN CALL_CENTER_THEMES AS T
    ON C.CUSTOMER_ID = T.CUSTOMER_ID
WHERE T.THEME = 'CANCEL_INTENT'
  AND C.LIFETIME_VALUE_USD >= 500
ORDER BY C.LIFETIME_VALUE_USD DESC;

-- ---------------------------------------------------------------------------
-- Q6. [Merchandising] Product-category affinity by loyalty tier.
-- ---------------------------------------------------------------------------
SELECT
    C.LOYALTY_TIER,
    E.PRODUCT_CATEGORY,
    COUNT(*)                                                    AS EVENT_COUNT,
    SUM(CASE WHEN E.EVENT_TYPE = 'PURCHASE' THEN E.AMOUNT_USD ELSE 0 END) AS PURCHASE_SPEND
FROM CUSTOMER_EVENTS AS E
JOIN CUSTOMERS AS C USING (CUSTOMER_ID)
WHERE E.EVENT_TIMESTAMP >= DATEADD('day', -30, CURRENT_TIMESTAMP())
GROUP BY C.LOYALTY_TIER, E.PRODUCT_CATEGORY
ORDER BY C.LOYALTY_TIER, PURCHASE_SPEND DESC;

-- ---------------------------------------------------------------------------
-- Q7. [Executive] Share-ready KPI summary.
-- ---------------------------------------------------------------------------
SELECT
    COUNT(DISTINCT CUSTOMER_ID)                                 AS ACTIVE_CUSTOMERS_90D,
    SUM(GROSS_SPEND_90D)                                        AS TOTAL_SPEND_90D,
    AVG(CHANNELS_USED_90D)                                      AS AVG_CHANNELS_PER_CUSTOMER,
    COUNT(
        CASE WHEN CHANNELS_USED_90D >= 2 THEN CUSTOMER_ID END
    )                                                           AS OMNICHANNEL_CUSTOMERS
FROM CUSTOMER_RFM_DAILY;
