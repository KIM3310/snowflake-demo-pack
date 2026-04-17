-- ---------------------------------------------------------------------------
-- demos/02-retail-customer-360/01-setup.sql
-- Creates the Retail schema objects for the 360 degree customer view.
--
-- Feature set exercised here:
--   * Snowpipe Streaming landing for cross-channel events
--   * Iceberg Tables as the master customer dimension
--   * Dynamic Tables maintaining RFM and journey state
--   * Secure Data Share for external consumer distribution
--   * Cortex LLM Functions on call-center notes
-- ---------------------------------------------------------------------------

USE ROLE SYSADMIN;
USE WAREHOUSE DEMO_WH;
USE DATABASE SNOWFLAKE_DEMO_PACK;
USE SCHEMA RETAIL;

-- 1. Master customer dimension (Iceberg-backed for open table format)
--    External volume and Iceberg catalog are out of scope for the scaffold; we
--    create a standard table by default and leave the Iceberg DDL commented.
--
-- Live-run alternative (external volume already provisioned):
--
--   CREATE OR REPLACE ICEBERG TABLE CUSTOMERS (
--       CUSTOMER_ID            STRING,
--       EMAIL_HASH             STRING,
--       SIGNUP_DATE            DATE,
--       LIFETIME_VALUE_USD     NUMBER(18, 2),
--       SEGMENT                STRING,
--       PREFERRED_CHANNEL      STRING,
--       LOYALTY_TIER           STRING
--   )
--   CATALOG = 'SNOWFLAKE'
--   EXTERNAL_VOLUME = 'RETAIL_ICEBERG_VOLUME'
--   BASE_LOCATION = 'retail/customers/'
--   COMMENT = 'Master customer dimension as Iceberg for open consumption';
CREATE OR REPLACE TABLE CUSTOMERS (
    CUSTOMER_ID            STRING        NOT NULL,
    EMAIL_HASH             STRING        NOT NULL,
    SIGNUP_DATE            DATE,
    LIFETIME_VALUE_USD     NUMBER(18, 2),
    SEGMENT                STRING,
    PREFERRED_CHANNEL      STRING,
    LOYALTY_TIER           STRING,
    LAST_UPDATED_AT        TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
    CONSTRAINT PK_CUSTOMERS PRIMARY KEY (CUSTOMER_ID)
)
COMMENT = 'Master customer dimension (Iceberg-compatible schema)';

-- 2. Cross-channel customer events
CREATE OR REPLACE TABLE CUSTOMER_EVENTS (
    EVENT_ID               STRING        NOT NULL,
    CUSTOMER_ID            STRING        NOT NULL,
    SESSION_ID             STRING,
    CHANNEL                STRING        NOT NULL,
    EVENT_TYPE             STRING        NOT NULL,
    PRODUCT_CATEGORY       STRING,
    SKU                    STRING,
    AMOUNT_USD             NUMBER(18, 4),
    EVENT_TIMESTAMP        TIMESTAMP_NTZ NOT NULL,
    DEVICE_TYPE            STRING,
    GEO_COUNTRY            STRING,
    INGEST_TIMESTAMP       TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
    CONSTRAINT PK_CUSTOMER_EVENTS PRIMARY KEY (EVENT_ID)
)
CLUSTER BY (EVENT_TIMESTAMP, CUSTOMER_ID)
COMMENT = 'Append-only cross-channel event stream (web, app, POS, call, marketplace)';

-- 3. Call-center notes (used by the Cortex COMPLETE demo)
CREATE OR REPLACE TABLE CALL_CENTER_NOTES (
    NOTE_ID                STRING        DEFAULT UUID_STRING(),
    CUSTOMER_ID            STRING        NOT NULL,
    AGENT_ID               STRING,
    CREATED_AT             TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
    NOTE                   STRING,
    CONSTRAINT PK_CALL_CENTER_NOTES PRIMARY KEY (NOTE_ID)
)
COMMENT = 'Free-text notes summarized by Cortex COMPLETE downstream';

-- 4. Dynamic Table: customer RFM buckets (recency, frequency, monetary)
CREATE OR REPLACE DYNAMIC TABLE CUSTOMER_RFM_DAILY
    TARGET_LAG = '5 minutes'
    WAREHOUSE = DEMO_WH
AS
SELECT
    CUSTOMER_ID,
    DATEDIFF(
        'day',
        MAX(EVENT_TIMESTAMP),
        CURRENT_TIMESTAMP()
    )                                                         AS DAYS_SINCE_LAST_EVENT,
    COUNT(*)                                                  AS EVENT_COUNT_90D,
    SUM(CASE WHEN EVENT_TYPE = 'PURCHASE' THEN 1 ELSE 0 END)  AS PURCHASE_COUNT_90D,
    SUM(CASE WHEN EVENT_TYPE = 'PURCHASE' THEN AMOUNT_USD ELSE 0 END) AS GROSS_SPEND_90D,
    COUNT(DISTINCT CHANNEL)                                   AS CHANNELS_USED_90D,
    MIN(EVENT_TIMESTAMP)                                      AS FIRST_EVENT_90D,
    MAX(EVENT_TIMESTAMP)                                      AS LAST_EVENT_90D
FROM CUSTOMER_EVENTS
WHERE EVENT_TIMESTAMP >= DATEADD('day', -90, CURRENT_TIMESTAMP())
GROUP BY CUSTOMER_ID
COMMENT = 'Incremental RFM per customer over a trailing 90 day window';

-- 5. Dynamic Table: customer journey (sessionized)
CREATE OR REPLACE DYNAMIC TABLE CUSTOMER_JOURNEY
    TARGET_LAG = '10 minutes'
    WAREHOUSE = DEMO_WH
AS
SELECT
    CUSTOMER_ID,
    SESSION_ID,
    MIN(EVENT_TIMESTAMP)                                        AS SESSION_START,
    MAX(EVENT_TIMESTAMP)                                        AS SESSION_END,
    DATEDIFF('second', MIN(EVENT_TIMESTAMP), MAX(EVENT_TIMESTAMP)) AS SESSION_DURATION_S,
    COUNT(*)                                                    AS EVENT_COUNT,
    ARRAY_AGG(DISTINCT CHANNEL) WITHIN GROUP (ORDER BY CHANNEL) AS CHANNELS,
    ARRAY_AGG(DISTINCT EVENT_TYPE) WITHIN GROUP (ORDER BY EVENT_TYPE) AS EVENT_TYPES,
    SUM(CASE WHEN EVENT_TYPE = 'PURCHASE' THEN AMOUNT_USD ELSE 0 END) AS SESSION_SPEND_USD
FROM CUSTOMER_EVENTS
GROUP BY CUSTOMER_ID, SESSION_ID
COMMENT = 'Sessionized journey per customer for timeline visualization';

-- 6. The 360 view: joins every serving table into one row per customer
CREATE OR REPLACE VIEW CUSTOMER_360_VIEW AS
SELECT
    C.CUSTOMER_ID,
    C.EMAIL_HASH,
    C.SIGNUP_DATE,
    C.LIFETIME_VALUE_USD,
    C.SEGMENT,
    C.PREFERRED_CHANNEL,
    C.LOYALTY_TIER,

    RFM.DAYS_SINCE_LAST_EVENT,
    RFM.EVENT_COUNT_90D,
    RFM.PURCHASE_COUNT_90D,
    RFM.GROSS_SPEND_90D,
    RFM.CHANNELS_USED_90D,
    RFM.LAST_EVENT_90D,

    -- Journey summary (latest 3 sessions)
    (
        SELECT ARRAY_AGG(
            OBJECT_CONSTRUCT(
                'SESSION_ID', J.SESSION_ID,
                'SESSION_START', J.SESSION_START,
                'DURATION_S', J.SESSION_DURATION_S,
                'CHANNELS', J.CHANNELS,
                'SESSION_SPEND_USD', J.SESSION_SPEND_USD
            )
        )
        FROM (
            SELECT * FROM CUSTOMER_JOURNEY
            WHERE CUSTOMER_ID = C.CUSTOMER_ID
            ORDER BY SESSION_START DESC
            LIMIT 3
        ) AS J
    )                                                            AS RECENT_SESSIONS,

    CURRENT_TIMESTAMP()                                          AS AS_OF
FROM CUSTOMERS AS C
LEFT JOIN CUSTOMER_RFM_DAILY AS RFM
    USING (CUSTOMER_ID);

-- 7. Masking policy for email hashes (defensive: hashes are already safe,
--    but this demonstrates the policy pattern in a cross-share context)
CREATE OR REPLACE MASKING POLICY EMAIL_HASH_MASK AS (VAL STRING)
    RETURNS STRING ->
    CASE
        WHEN CURRENT_ROLE() IN ('ACCOUNTADMIN', 'SYSADMIN', 'DEMO_PACK_ROLE')
            THEN VAL
        ELSE CONCAT('****', RIGHT(VAL, 4))
    END;

ALTER TABLE CUSTOMERS
    MODIFY COLUMN EMAIL_HASH SET MASKING POLICY EMAIL_HASH_MASK;

-- 8. Secure share definition (consumer-side provisioning is done by the consumer)
CREATE OR REPLACE SECURE VIEW CUSTOMER_360_SHARE AS
SELECT
    CUSTOMER_ID,
    LOYALTY_TIER,
    SEGMENT,
    LIFETIME_VALUE_USD,
    EVENT_COUNT_90D,
    GROSS_SPEND_90D,
    PREFERRED_CHANNEL,
    AS_OF
FROM CUSTOMER_360_VIEW;

-- Uncomment in a live run to publish the share:
--   CREATE OR REPLACE SHARE CUSTOMER_360_SHARE_OUTBOUND;
--   GRANT USAGE ON DATABASE SNOWFLAKE_DEMO_PACK TO SHARE CUSTOMER_360_SHARE_OUTBOUND;
--   GRANT USAGE ON SCHEMA RETAIL TO SHARE CUSTOMER_360_SHARE_OUTBOUND;
--   GRANT SELECT ON VIEW CUSTOMER_360_SHARE TO SHARE CUSTOMER_360_SHARE_OUTBOUND;
--   ALTER SHARE CUSTOMER_360_SHARE_OUTBOUND ADD ACCOUNTS = ('<consumer_account>');

-- 9. Cortex-enriched themes table (populated by 03-enrichment.py)
CREATE OR REPLACE TABLE CALL_CENTER_THEMES (
    NOTE_ID                STRING,
    CUSTOMER_ID            STRING,
    THEME                  STRING,
    SUMMARY                STRING,
    MODEL_NAME             STRING,
    GENERATED_AT           TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
    CONSTRAINT PK_CALL_CENTER_THEMES PRIMARY KEY (NOTE_ID)
)
COMMENT = 'Cortex COMPLETE output bucketing call notes into themes';

-- End of 01-setup.sql
