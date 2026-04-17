-- ---------------------------------------------------------------------------
-- demos/03-manufacturing-predictive-maintenance/04-analytics.sql
-- Operations queries for the predictive maintenance demo.
-- ---------------------------------------------------------------------------

USE ROLE SYSADMIN;
USE WAREHOUSE DEMO_WH;
USE DATABASE SNOWFLAKE_DEMO_PACK;
USE SCHEMA MANUFACTURING;

-- ---------------------------------------------------------------------------
-- Q1. [Plant Manager] Top 10 machines by risk, right now.
-- ---------------------------------------------------------------------------
SELECT
    MACHINE_ID,
    LINE_ID,
    SITE,
    ROUND(RISK_SCORE, 3)   AS RISK_SCORE,
    VIBRATION_MEAN,
    TEMPERATURE_MEAN,
    LAST_SCORED_AT
FROM MACHINE_HEALTH_SCORE
ORDER BY RISK_SCORE DESC
LIMIT 10;

-- ---------------------------------------------------------------------------
-- Q2. [Reliability Engineer] Vibration trend on the highest-risk machine.
-- ---------------------------------------------------------------------------
WITH TOP_MACHINE AS (
    SELECT MACHINE_ID
    FROM MACHINE_HEALTH_SCORE
    ORDER BY RISK_SCORE DESC
    LIMIT 1
)
SELECT
    DATE_TRUNC('minute', T.RECORDED_AT) AS MINUTE,
    AVG(T.VALUE)                        AS AVG_VIBRATION_MM_S,
    MAX(T.VALUE)                        AS MAX_VIBRATION_MM_S
FROM SENSOR_TELEMETRY AS T
JOIN TOP_MACHINE AS TM USING (MACHINE_ID)
WHERE T.SENSOR_TYPE = 'VIBRATION'
GROUP BY MINUTE
ORDER BY MINUTE;

-- ---------------------------------------------------------------------------
-- Q3. [COO] Elevated-risk count by site and line.
-- ---------------------------------------------------------------------------
SELECT
    SITE,
    LINE_ID,
    COUNT(*)                                                         AS TOTAL_MACHINES,
    SUM(CASE WHEN RISK_SCORE >= 0.60 THEN 1 ELSE 0 END)              AS ELEVATED,
    SUM(CASE WHEN RISK_SCORE >= 0.80 THEN 1 ELSE 0 END)              AS HIGH_RISK,
    ROUND(AVG(RISK_SCORE), 3)                                        AS AVG_RISK
FROM MACHINE_HEALTH_SCORE
GROUP BY SITE, LINE_ID
ORDER BY HIGH_RISK DESC, ELEVATED DESC;

-- ---------------------------------------------------------------------------
-- Q4. [Maintenance Planner] Predicted failures by 72-hour window.
-- ---------------------------------------------------------------------------
SELECT
    MACHINE_ID,
    LINE_ID,
    SITE,
    ROUND(RISK_SCORE, 3)  AS RISK_SCORE,
    DATEADD('hour', 72 - ROUND(RISK_SCORE * 72), CURRENT_TIMESTAMP()) AS PREDICTED_FAILURE_BY,
    VIBRATION_MEAN,
    TEMPERATURE_MEAN,
    CURRENT_MEAN
FROM MACHINE_HEALTH_SCORE
WHERE RISK_SCORE >= 0.65
ORDER BY PREDICTED_FAILURE_BY;

-- ---------------------------------------------------------------------------
-- Q5. [Finance] Avoided-downtime savings estimate.
-- ---------------------------------------------------------------------------
WITH HISTORY AS (
    SELECT
        MACHINE_ID,
        AVG(DOWNTIME_MINUTES) AS AVG_DOWNTIME_MIN,
        AVG(REPAIR_COST_USD)  AS AVG_REPAIR_COST_USD
    FROM FAILURE_HISTORY
    GROUP BY MACHINE_ID
)
SELECT
    S.SITE,
    COUNT(*)                                           AS AT_RISK_MACHINES,
    SUM(COALESCE(H.AVG_DOWNTIME_MIN, 120))             AS EXPECTED_DOWNTIME_MIN_IF_NO_ACTION,
    SUM(COALESCE(H.AVG_REPAIR_COST_USD, 3500))         AS EXPECTED_REPAIR_USD_IF_NO_ACTION,
    -- Assume throughput lost at $2,500/hour, 45 percent avoided by scheduled intervention
    ROUND(
        0.45 * SUM(COALESCE(H.AVG_DOWNTIME_MIN, 120)) / 60.0 * 2500.0,
        2
    ) AS ESTIMATED_SAVINGS_USD
FROM MACHINE_HEALTH_SCORE AS S
LEFT JOIN HISTORY AS H USING (MACHINE_ID)
WHERE S.RISK_SCORE >= 0.70
GROUP BY S.SITE
ORDER BY ESTIMATED_SAVINGS_USD DESC;

-- ---------------------------------------------------------------------------
-- Q6. [PM Schedule Optimizer] Machines with overdue preventive maintenance AND elevated risk.
-- ---------------------------------------------------------------------------
SELECT
    M.MACHINE_ID,
    M.LINE_ID,
    M.SITE,
    M.LAST_PM_AT,
    DATEDIFF('day', M.LAST_PM_AT, CURRENT_DATE()) AS DAYS_SINCE_PM,
    ROUND(S.RISK_SCORE, 3) AS RISK_SCORE
FROM MACHINES AS M
JOIN MACHINE_HEALTH_SCORE AS S USING (MACHINE_ID)
WHERE DATEDIFF('day', M.LAST_PM_AT, CURRENT_DATE()) > 90
  AND S.RISK_SCORE >= 0.5
ORDER BY S.RISK_SCORE DESC;

-- ---------------------------------------------------------------------------
-- Q7. [Executive] Plant-wide KPI headline.
-- ---------------------------------------------------------------------------
SELECT
    COUNT(*)                                                                         AS MACHINES_MONITORED,
    ROUND(AVG(RISK_SCORE), 3)                                                        AS AVG_RISK,
    SUM(CASE WHEN RISK_SCORE >= 0.8 THEN 1 ELSE 0 END)                                AS HIGH_RISK_COUNT,
    SUM(CASE WHEN RISK_SCORE BETWEEN 0.6 AND 0.8 THEN 1 ELSE 0 END)                   AS ELEVATED_COUNT,
    MAX(LAST_SCORED_AT)                                                              AS LATEST_SCORED_AT
FROM MACHINE_HEALTH_SCORE;
