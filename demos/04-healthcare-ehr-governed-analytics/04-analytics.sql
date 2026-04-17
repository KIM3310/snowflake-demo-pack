-- ---------------------------------------------------------------------------
-- demos/04-healthcare-ehr-governed-analytics/04-analytics.sql
-- Clinical and financial analytics — each query is safe to run under any of
-- the three demo roles (SYSADMIN, CARDIOLOGY_ANALYST, REGIONAL_MIDWEST,
-- DATA_ENGINEER_MASKED) and will return policy-consistent results.
-- ---------------------------------------------------------------------------

USE ROLE SYSADMIN;
USE WAREHOUSE DEMO_WH;
USE DATABASE SNOWFLAKE_DEMO_PACK;
USE SCHEMA HEALTHCARE;

-- ---------------------------------------------------------------------------
-- Q1. [Quality Committee] 30-day readmission rate by primary condition.
-- ---------------------------------------------------------------------------
SELECT
    PRIMARY_CONDITION,
    COUNT(*)                                                        AS ENCOUNTERS,
    SUM(CASE WHEN READMITTED_WITHIN_30D THEN 1 ELSE 0 END)          AS READMITS_30D,
    ROUND(
        SUM(CASE WHEN READMITTED_WITHIN_30D THEN 1 ELSE 0 END)::FLOAT
            / NULLIF(COUNT(*), 0),
        4
    )                                                               AS READMIT_RATE,
    ROUND(AVG(LENGTH_OF_STAY_DAYS), 2)                              AS AVG_LOS_DAYS
FROM ENCOUNTERS_SECURE
GROUP BY PRIMARY_CONDITION
ORDER BY READMIT_RATE DESC;

-- ---------------------------------------------------------------------------
-- Q2. [Population Health] Cohort size by age decade and region.
-- ---------------------------------------------------------------------------
SELECT
    REGION,
    AGE_DECADE,
    COUNT(DISTINCT PATIENT_PSEUDONYM) AS PATIENTS,
    COUNT(*)                          AS ENCOUNTERS,
    ROUND(AVG(COMORBIDITY_COUNT), 2)  AS AVG_COMORBIDITIES
FROM ENCOUNTERS_SECURE
GROUP BY REGION, AGE_DECADE
ORDER BY REGION, AGE_DECADE;

-- ---------------------------------------------------------------------------
-- Q3. [Department Heads] Utilization by department.
-- ---------------------------------------------------------------------------
SELECT
    DEPARTMENT,
    COUNT(*)                          AS ENCOUNTERS,
    ROUND(AVG(LENGTH_OF_STAY_DAYS), 2) AS AVG_LOS_DAYS,
    ROUND(AVG(BILLED_AMOUNT_USD), 2)   AS AVG_BILLED_USD,
    SUM(BILLED_AMOUNT_USD)             AS TOTAL_BILLED_USD
FROM ENCOUNTERS_SECURE
GROUP BY DEPARTMENT
ORDER BY TOTAL_BILLED_USD DESC;

-- ---------------------------------------------------------------------------
-- Q4. [Contract Manager] Payer mix with capitation shortfall.
-- ---------------------------------------------------------------------------
SELECT
    PAYER,
    COUNT(*)                                                        AS CLAIMS,
    ROUND(AVG(BILLED_AMOUNT_USD), 2)                                AS AVG_BILLED_USD,
    ROUND(AVG(CONTRACT_CAPITATION_USD), 2)                          AS AVG_CAPITATION_USD,
    ROUND(
        AVG(BILLED_AMOUNT_USD - CONTRACT_CAPITATION_USD),
        2
    )                                                               AS AVG_SHORTFALL_USD,
    SUM(CASE WHEN CLAIM_STATUS = 'DENIED' THEN 1 ELSE 0 END)        AS DENIALS,
    SUM(CASE WHEN CLAIM_STATUS = 'PENDING' THEN 1 ELSE 0 END)       AS PENDING
FROM ENCOUNTERS_SECURE
WHERE PAYER IS NOT NULL
GROUP BY PAYER
ORDER BY AVG_SHORTFALL_USD DESC;

-- ---------------------------------------------------------------------------
-- Q5. [Compliance] 24-hour PHI access report.
-- ---------------------------------------------------------------------------
SELECT
    USER_NAME,
    ROLE_NAME,
    COUNT(*)                                      AS QUERY_COUNT,
    MIN(QUERY_START_TIME)                         AS FIRST_QUERY,
    MAX(QUERY_START_TIME)                         AS LAST_QUERY
FROM PHI_AUDIT_24H
GROUP BY USER_NAME, ROLE_NAME
ORDER BY QUERY_COUNT DESC;

-- ---------------------------------------------------------------------------
-- Q6. [CFO] Finance headline: revenue capture efficiency.
-- ---------------------------------------------------------------------------
WITH ROLLUP AS (
    SELECT
        SUM(BILLED_AMOUNT_USD)      AS TOTAL_BILLED,
        SUM(ALLOWED_AMOUNT_USD)     AS TOTAL_ALLOWED,
        SUM(CASE WHEN CLAIM_STATUS = 'DENIED' THEN ALLOWED_AMOUNT_USD ELSE 0 END) AS DENIED_ALLOWED
    FROM BILLING_CLAIMS
)
SELECT
    TOTAL_BILLED,
    TOTAL_ALLOWED,
    ROUND(100.0 * TOTAL_ALLOWED / NULLIF(TOTAL_BILLED, 0), 2) AS ALLOWED_RATE_PCT,
    DENIED_ALLOWED,
    ROUND(100.0 * DENIED_ALLOWED / NULLIF(TOTAL_ALLOWED, 0), 2) AS DENIAL_LOSS_PCT
FROM ROLLUP;

-- ---------------------------------------------------------------------------
-- Q7. [Executive] Governance posture snapshot.
-- ---------------------------------------------------------------------------
SELECT
    (SELECT COUNT(*) FROM ENCOUNTERS_SECURE)                         AS VISIBLE_ENCOUNTERS,
    (
        SELECT COUNT(*)
        FROM SNOWFLAKE_DEMO_PACK.INFORMATION_SCHEMA.POLICY_REFERENCES
        WHERE POLICY_KIND IN ('ROW_ACCESS_POLICY', 'MASKING_POLICY')
          AND REF_DATABASE_NAME = 'SNOWFLAKE_DEMO_PACK'
          AND REF_SCHEMA_NAME   = 'HEALTHCARE'
    )                                                                AS ATTACHED_POLICIES,
    CURRENT_ROLE()                                                   AS OBSERVING_ROLE,
    CURRENT_TIMESTAMP()                                              AS AS_OF;
