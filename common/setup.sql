-- ---------------------------------------------------------------------------
-- common/setup.sql
-- Provision the shared database, warehouse, and role used by every demo.
-- This script is idempotent: every object is created with IF NOT EXISTS.
-- ---------------------------------------------------------------------------

USE ROLE SYSADMIN;

-- 1. Demo warehouse
--    X-Small with aggressive auto-suspend keeps per-demo cost under $2.
CREATE WAREHOUSE IF NOT EXISTS DEMO_WH
    WAREHOUSE_SIZE = 'XSMALL'
    AUTO_SUSPEND = 60
    AUTO_RESUME = TRUE
    INITIALLY_SUSPENDED = TRUE
    COMMENT = 'Shared warehouse for snowflake-demo-pack';

-- 2. Demo database
CREATE DATABASE IF NOT EXISTS SNOWFLAKE_DEMO_PACK
    DATA_RETENTION_TIME_IN_DAYS = 1
    COMMENT = 'Industry demo library (finance, retail, manufacturing, healthcare, media)';

USE DATABASE SNOWFLAKE_DEMO_PACK;

-- 3. Per-industry schemas — each demo owns a dedicated namespace
CREATE SCHEMA IF NOT EXISTS FINANCE
    COMMENT = 'Real-time fraud detection with Dynamic Tables and Cortex ML';

CREATE SCHEMA IF NOT EXISTS RETAIL
    COMMENT = '360 degree customer view with Snowpipe Streaming and Iceberg';

CREATE SCHEMA IF NOT EXISTS MANUFACTURING
    COMMENT = 'IoT predictive maintenance with Streams, Tasks, and Native Apps';

CREATE SCHEMA IF NOT EXISTS HEALTHCARE
    COMMENT = 'Governed EHR analytics with row access policies and masking';

CREATE SCHEMA IF NOT EXISTS MEDIA
    COMMENT = 'Content recommendation with Cortex Search and vector embeddings';

-- 4. Internal stages (one per schema) for synthetic-data landing
CREATE STAGE IF NOT EXISTS FINANCE.DEMO_STAGE
    FILE_FORMAT = (TYPE = 'JSON' STRIP_OUTER_ARRAY = TRUE)
    COMMENT = 'Landing zone for synthetic transaction data';

CREATE STAGE IF NOT EXISTS RETAIL.DEMO_STAGE
    FILE_FORMAT = (TYPE = 'JSON' STRIP_OUTER_ARRAY = TRUE)
    COMMENT = 'Landing zone for cross-channel customer events';

CREATE STAGE IF NOT EXISTS MANUFACTURING.DEMO_STAGE
    FILE_FORMAT = (TYPE = 'PARQUET')
    COMMENT = 'Landing zone for IoT sensor telemetry';

CREATE STAGE IF NOT EXISTS HEALTHCARE.DEMO_STAGE
    FILE_FORMAT = (TYPE = 'CSV' SKIP_HEADER = 1 FIELD_OPTIONALLY_ENCLOSED_BY = '"')
    COMMENT = 'Landing zone for de-identified EHR extracts';

CREATE STAGE IF NOT EXISTS MEDIA.DEMO_STAGE
    FILE_FORMAT = (TYPE = 'JSON' STRIP_OUTER_ARRAY = TRUE)
    COMMENT = 'Landing zone for user behavior events';

-- 5. Demo role (granted to SYSADMIN-controlled users)
USE ROLE USERADMIN;

CREATE ROLE IF NOT EXISTS DEMO_PACK_ROLE
    COMMENT = 'Unified role for operating the snowflake-demo-pack library';

USE ROLE SECURITYADMIN;
GRANT USAGE ON WAREHOUSE DEMO_WH TO ROLE DEMO_PACK_ROLE;
GRANT USAGE ON DATABASE SNOWFLAKE_DEMO_PACK TO ROLE DEMO_PACK_ROLE;
GRANT USAGE ON ALL SCHEMAS IN DATABASE SNOWFLAKE_DEMO_PACK TO ROLE DEMO_PACK_ROLE;
GRANT CREATE TABLE, CREATE VIEW, CREATE DYNAMIC TABLE, CREATE FUNCTION,
      CREATE PROCEDURE, CREATE STREAM, CREATE TASK, CREATE STAGE,
      CREATE MASKING POLICY, CREATE ROW ACCESS POLICY
    ON ALL SCHEMAS IN DATABASE SNOWFLAKE_DEMO_PACK TO ROLE DEMO_PACK_ROLE;
GRANT ROLE DEMO_PACK_ROLE TO ROLE SYSADMIN;

-- 6. Object tags (governance primitives re-used by the healthcare demo)
USE ROLE SYSADMIN;
USE DATABASE SNOWFLAKE_DEMO_PACK;
USE SCHEMA HEALTHCARE;

CREATE TAG IF NOT EXISTS PII_CLASS
    ALLOWED_VALUES 'NONE', 'LOW', 'MEDIUM', 'HIGH', 'RESTRICTED'
    COMMENT = 'Classification of personally identifiable information';

CREATE TAG IF NOT EXISTS COMPLIANCE_REGIME
    ALLOWED_VALUES 'NONE', 'GDPR', 'HIPAA', 'PCI_DSS', 'SOC2'
    COMMENT = 'Regulatory regime applicable to the tagged object';

-- 7. Sanity check
SELECT
    CURRENT_ACCOUNT()     AS ACCOUNT_LOCATOR,
    CURRENT_USER()        AS CURRENT_USER,
    CURRENT_ROLE()        AS CURRENT_ROLE,
    CURRENT_WAREHOUSE()   AS CURRENT_WAREHOUSE,
    CURRENT_DATABASE()    AS CURRENT_DATABASE,
    CURRENT_TIMESTAMP()   AS RUN_AT;
