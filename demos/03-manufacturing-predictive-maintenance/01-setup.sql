-- ---------------------------------------------------------------------------
-- demos/03-manufacturing-predictive-maintenance/01-setup.sql
-- Creates the Manufacturing schema objects for the predictive-maintenance demo.
--
-- Feature set exercised here:
--   * Snowpipe Streaming landing for IoT telemetry
--   * Streams and Tasks for low-latency aggregation
--   * Dynamic Tables for rolling health metrics
--   * Alerts for pushing high-risk events to an email integration
--   * Application Package scaffolding for Native App distribution
-- ---------------------------------------------------------------------------

USE ROLE SYSADMIN;
USE WAREHOUSE DEMO_WH;
USE DATABASE SNOWFLAKE_DEMO_PACK;
USE SCHEMA MANUFACTURING;

-- 1. Raw telemetry landing table
CREATE OR REPLACE TABLE SENSOR_TELEMETRY (
    MACHINE_ID         STRING        NOT NULL,
    LINE_ID            STRING        NOT NULL,
    SITE               STRING        NOT NULL,
    SENSOR_TYPE        STRING        NOT NULL,
    SENSOR_UNIT        STRING,
    VALUE              NUMBER(18, 4) NOT NULL,
    RECORDED_AT        TIMESTAMP_NTZ NOT NULL,
    INGEST_TIMESTAMP   TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP()
)
CLUSTER BY (RECORDED_AT, MACHINE_ID)
COMMENT = 'High-frequency IoT telemetry; landed by Snowpipe Streaming';

-- 2. Machine dimension
CREATE OR REPLACE TABLE MACHINES (
    MACHINE_ID       STRING        NOT NULL,
    LINE_ID          STRING        NOT NULL,
    SITE             STRING        NOT NULL,
    MODEL_CODE       STRING,
    COMMISSIONED_AT  DATE,
    LAST_PM_AT       DATE,
    CONSTRAINT PK_MACHINES PRIMARY KEY (MACHINE_ID)
)
COMMENT = 'Machine dimension; populated by 02-load-data.py';

-- 3. Stream over raw telemetry for change-data feeds
CREATE OR REPLACE STREAM TELEMETRY_STREAM
    ON TABLE SENSOR_TELEMETRY
    APPEND_ONLY = TRUE
    SHOW_INITIAL_ROWS = FALSE
    COMMENT = 'CDC stream consumed by HEALTH_ROLLUP_TASK';

-- 4. Rolling 1-hour sensor health per machine (Dynamic Table)
CREATE OR REPLACE DYNAMIC TABLE SENSOR_HEALTH_1H
    TARGET_LAG = '2 minutes'
    WAREHOUSE = DEMO_WH
AS
SELECT
    MACHINE_ID,
    LINE_ID,
    SITE,
    SENSOR_TYPE,
    DATE_TRUNC('minute', RECORDED_AT)                      AS MINUTE_BUCKET,
    COUNT(*)                                               AS SAMPLE_COUNT,
    AVG(VALUE)                                             AS MEAN_VALUE,
    STDDEV_SAMP(VALUE)                                     AS STDDEV_VALUE,
    MAX(VALUE)                                             AS MAX_VALUE,
    MIN(VALUE)                                             AS MIN_VALUE,
    MAX(RECORDED_AT)                                       AS LATEST_RECORDED_AT
FROM SENSOR_TELEMETRY
WHERE RECORDED_AT >= DATEADD('hour', -1, CURRENT_TIMESTAMP())
GROUP BY MACHINE_ID, LINE_ID, SITE, SENSOR_TYPE, MINUTE_BUCKET
COMMENT = 'Rolling one-hour per-sensor aggregates used by the scoring UDF';

-- 5. Per-machine latest rollup (Dynamic Table, narrower)
CREATE OR REPLACE DYNAMIC TABLE MACHINE_FEATURES_NOW
    TARGET_LAG = '2 minutes'
    WAREHOUSE = DEMO_WH
AS
WITH PIVOTED AS (
    SELECT
        MACHINE_ID,
        LINE_ID,
        SITE,
        AVG(CASE WHEN SENSOR_TYPE = 'VIBRATION'  THEN MEAN_VALUE END) AS VIBRATION_MEAN,
        AVG(CASE WHEN SENSOR_TYPE = 'TEMPERATURE' THEN MEAN_VALUE END) AS TEMPERATURE_MEAN,
        AVG(CASE WHEN SENSOR_TYPE = 'PRESSURE'    THEN MEAN_VALUE END) AS PRESSURE_MEAN,
        AVG(CASE WHEN SENSOR_TYPE = 'CURRENT'     THEN MEAN_VALUE END) AS CURRENT_MEAN,
        AVG(CASE WHEN SENSOR_TYPE = 'RPM'         THEN MEAN_VALUE END) AS RPM_MEAN,
        MAX(CASE WHEN SENSOR_TYPE = 'VIBRATION'   THEN MAX_VALUE  END) AS VIBRATION_MAX,
        MAX(CASE WHEN SENSOR_TYPE = 'TEMPERATURE' THEN MAX_VALUE  END) AS TEMPERATURE_MAX,
        MAX(LATEST_RECORDED_AT)                                        AS LATEST_RECORDED_AT
    FROM SENSOR_HEALTH_1H
    GROUP BY MACHINE_ID, LINE_ID, SITE
)
SELECT * FROM PIVOTED
COMMENT = 'Flat feature vector per machine; scored by PREDICT_MACHINE_FAILURE_UDF';

-- 6. Scored table (Dynamic Table) invoking the Snowpark ML UDF
CREATE OR REPLACE DYNAMIC TABLE MACHINE_HEALTH_SCORE
    TARGET_LAG = '2 minutes'
    WAREHOUSE = DEMO_WH
AS
SELECT
    M.MACHINE_ID,
    M.LINE_ID,
    M.SITE,
    M.VIBRATION_MEAN,
    M.TEMPERATURE_MEAN,
    M.PRESSURE_MEAN,
    M.CURRENT_MEAN,
    M.RPM_MEAN,
    PREDICT_MACHINE_FAILURE_UDF(
        COALESCE(M.VIBRATION_MEAN, 0.0),
        COALESCE(M.TEMPERATURE_MEAN, 0.0),
        COALESCE(M.PRESSURE_MEAN, 0.0),
        COALESCE(M.CURRENT_MEAN, 0.0),
        COALESCE(M.RPM_MEAN, 0.0),
        COALESCE(M.VIBRATION_MAX, 0.0),
        COALESCE(M.TEMPERATURE_MAX, 0.0)
    )                                                             AS RISK_SCORE,
    M.LATEST_RECORDED_AT,
    CURRENT_TIMESTAMP()                                           AS LAST_SCORED_AT
FROM MACHINE_FEATURES_NOW AS M
COMMENT = 'Per-machine failure risk score refreshed every 2 minutes';

-- 7. Alert: fires when any machine exceeds the 0.8 threshold
--    Email integration is assumed to exist; see live-run instructions below.
-- CREATE OR REPLACE NOTIFICATION INTEGRATION PDM_EMAIL_INT
--     TYPE = EMAIL
--     ENABLED = TRUE
--     ALLOWED_RECIPIENTS = ('ops@example.com');

CREATE OR REPLACE ALERT HIGH_RISK_MACHINE_ALERT
    WAREHOUSE = DEMO_WH
    SCHEDULE = '5 minutes'
    COMMENT = 'Notifies the maintenance team when any machine risk exceeds 0.8'
    IF (EXISTS (
        SELECT 1
        FROM MACHINE_HEALTH_SCORE
        WHERE RISK_SCORE >= 0.8
          AND LAST_SCORED_AT >= DATEADD('minute', -10, CURRENT_TIMESTAMP())
    ))
    THEN
        SELECT
            SYSTEM$SEND_EMAIL(
                'PDM_EMAIL_INT',
                'ops@example.com',
                CONCAT('[PdM] High-risk machines detected at ', CURRENT_TIMESTAMP()::STRING),
                CONCAT(
                    'The following machines crossed the 0.8 risk threshold in the last 10 minutes:\n\n',
                    (
                        SELECT LISTAGG(
                            CONCAT(MACHINE_ID, ' (line ', LINE_ID, ' site ', SITE, ') risk=', ROUND(RISK_SCORE, 3)),
                            '\n'
                        )
                        FROM MACHINE_HEALTH_SCORE
                        WHERE RISK_SCORE >= 0.8
                          AND LAST_SCORED_AT >= DATEADD('minute', -10, CURRENT_TIMESTAMP())
                    )
                )
            );

-- Leave the alert suspended at setup to avoid accidental email sends.
ALTER ALERT HIGH_RISK_MACHINE_ALERT SUSPEND;

-- 8. Native App scaffolding: Application Package
--    The package is created but not versioned here so the demo remains cheap.
CREATE APPLICATION PACKAGE IF NOT EXISTS PDM_NATIVE_APP_PKG
    COMMENT = 'Predictive maintenance Native App distributed to OEM partners';

GRANT APPLICATION ROLE PDM_NATIVE_APP_PKG.APP_PUBLIC TO SHARE IN APPLICATION PACKAGE PDM_NATIVE_APP_PKG;

-- Application package manifest and logic are staged here. See repo root docs/ for the
-- manifest.yml and app/setup.sql generated on package publish.

-- 9. Historical failure labels (seeded by the loader for model training)
CREATE OR REPLACE TABLE FAILURE_HISTORY (
    MACHINE_ID         STRING        NOT NULL,
    FAILURE_AT         TIMESTAMP_NTZ NOT NULL,
    FAILURE_MODE       STRING,
    DOWNTIME_MINUTES   NUMBER(18, 2),
    REPAIR_COST_USD    NUMBER(18, 2),
    CONSTRAINT FK_FAILURE_MACHINE FOREIGN KEY (MACHINE_ID) REFERENCES MACHINES (MACHINE_ID)
)
COMMENT = 'Historical failure events used by Snowpark ML training script';

-- End of 01-setup.sql
