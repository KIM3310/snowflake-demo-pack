-- ---------------------------------------------------------------------------
-- demos/05-media-content-recommendation/01-setup.sql
-- Creates the Media schema objects for the content recommendation demo.
--
-- Feature set exercised here:
--   * VECTOR data type
--   * SNOWFLAKE.CORTEX.EMBED_TEXT_768
--   * Cortex Search Service over the catalog
--   * Snowpipe Streaming landing for user events
--   * Dynamic Tables maintaining per-user preference vectors
-- ---------------------------------------------------------------------------

USE ROLE SYSADMIN;
USE WAREHOUSE DEMO_WH;
USE DATABASE SNOWFLAKE_DEMO_PACK;
USE SCHEMA MEDIA;

-- 1. Catalog of content
CREATE OR REPLACE TABLE CONTENT_CATALOG (
    CONTENT_ID           STRING        NOT NULL,
    TITLE                STRING,
    CONTENT_TYPE         STRING,
    GENRE                STRING,
    RUNTIME_MINUTES      NUMBER(5, 0),
    RELEASE_YEAR         NUMBER(5, 0),
    DESCRIPTION          STRING,
    LOCALE               STRING,
    CREATED_AT           TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
    CONSTRAINT PK_CONTENT_CATALOG PRIMARY KEY (CONTENT_ID)
)
COMMENT = 'Master catalog of titles with free-text descriptions';

-- 2. Content embeddings (VECTOR column)
CREATE OR REPLACE TABLE CONTENT_EMBEDDINGS (
    CONTENT_ID           STRING        NOT NULL,
    TITLE                STRING,
    GENRE                STRING,
    DESCRIPTION          STRING,
    EMBEDDING            VECTOR(FLOAT, 768),
    MODEL_NAME           STRING,
    GENERATED_AT         TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
    CONSTRAINT PK_CONTENT_EMBEDDINGS PRIMARY KEY (CONTENT_ID)
)
COMMENT = 'Per-title embedding produced by SNOWFLAKE.CORTEX.EMBED_TEXT_768';

-- 3. Procedure to refresh embeddings from the catalog
--    In a live run, this is called after the catalog loader inserts new rows.
CREATE OR REPLACE PROCEDURE REFRESH_CONTENT_EMBEDDINGS()
RETURNS STRING
LANGUAGE SQL
AS
$$
BEGIN
    MERGE INTO CONTENT_EMBEDDINGS AS TGT
    USING (
        SELECT
            C.CONTENT_ID,
            C.TITLE,
            C.GENRE,
            C.DESCRIPTION,
            SNOWFLAKE.CORTEX.EMBED_TEXT_768('snowflake-arctic-embed-m', C.DESCRIPTION) AS EMBEDDING,
            'snowflake-arctic-embed-m' AS MODEL_NAME
        FROM CONTENT_CATALOG AS C
        LEFT JOIN CONTENT_EMBEDDINGS AS E USING (CONTENT_ID)
        WHERE E.CONTENT_ID IS NULL
    ) AS SRC
    ON TGT.CONTENT_ID = SRC.CONTENT_ID
    WHEN NOT MATCHED THEN INSERT (CONTENT_ID, TITLE, GENRE, DESCRIPTION, EMBEDDING, MODEL_NAME)
        VALUES (SRC.CONTENT_ID, SRC.TITLE, SRC.GENRE, SRC.DESCRIPTION, SRC.EMBEDDING, SRC.MODEL_NAME);
    RETURN 'OK';
END;
$$;

-- 4. User events landing
CREATE OR REPLACE TABLE USER_EVENTS (
    EVENT_ID             STRING        NOT NULL,
    USER_ID              STRING        NOT NULL,
    CONTENT_ID           STRING,
    CONTENT_TYPE         STRING,
    GENRE                STRING,
    EVENT_TYPE           STRING,
    WATCH_DURATION_MS    NUMBER(18, 0),
    EVENT_TIMESTAMP      TIMESTAMP_NTZ NOT NULL,
    DEVICE_TYPE          STRING,
    LOCALE               STRING,
    INGEST_TIMESTAMP     TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
    CONSTRAINT PK_USER_EVENTS PRIMARY KEY (EVENT_ID)
)
CLUSTER BY (EVENT_TIMESTAMP, USER_ID)
COMMENT = 'Append-only user-behavior events from client devices';

-- 5. Dynamic Table: per-user preference vector
--    Averages the embeddings of the most recent 10 plays per user.
--    VECTOR arithmetic at aggregate level uses VECTOR functions; at refresh
--    time we compute the centroid via the per-row sum / count pattern.
CREATE OR REPLACE DYNAMIC TABLE USER_RECENT_PLAYS
    TARGET_LAG = '10 minutes'
    WAREHOUSE = DEMO_WH
AS
SELECT
    USER_ID,
    CONTENT_ID,
    EVENT_TIMESTAMP,
    ROW_NUMBER() OVER (PARTITION BY USER_ID ORDER BY EVENT_TIMESTAMP DESC) AS PLAY_RANK
FROM USER_EVENTS
WHERE EVENT_TYPE IN ('PLAY_START', 'PLAY_COMPLETE')
QUALIFY PLAY_RANK <= 10
COMMENT = 'The 10 most recent plays per user';

CREATE OR REPLACE DYNAMIC TABLE USER_PREFERENCE_VECTOR
    TARGET_LAG = '10 minutes'
    WAREHOUSE = DEMO_WH
AS
SELECT
    P.USER_ID,
    SNOWFLAKE.CORTEX.EMBED_TEXT_768(
        'snowflake-arctic-embed-m',
        LISTAGG(COALESCE(C.DESCRIPTION, ''), ' ')
            WITHIN GROUP (ORDER BY P.EVENT_TIMESTAMP DESC)
    )                                       AS PREFERENCE_VECTOR,
    COUNT(*)                                AS PLAYS_INCLUDED,
    MAX(P.EVENT_TIMESTAMP)                  AS LAST_REFRESH_AT
FROM USER_RECENT_PLAYS AS P
LEFT JOIN CONTENT_CATALOG AS C USING (CONTENT_ID)
GROUP BY P.USER_ID
COMMENT = 'Centroid preference embedding per user, refreshed every 10 minutes';

-- 6. Recommendations view: cosine similarity between user centroid and catalog
CREATE OR REPLACE VIEW RECOMMENDATIONS_VIEW AS
SELECT
    U.USER_ID,
    C.CONTENT_ID,
    C.TITLE,
    C.GENRE,
    C.DESCRIPTION,
    VECTOR_COSINE_SIMILARITY(C.EMBEDDING, U.PREFERENCE_VECTOR) AS SIMILARITY
FROM USER_PREFERENCE_VECTOR AS U
CROSS JOIN CONTENT_EMBEDDINGS AS C
WHERE C.CONTENT_ID NOT IN (
    SELECT P.CONTENT_ID FROM USER_RECENT_PLAYS AS P WHERE P.USER_ID = U.USER_ID
)
QUALIFY ROW_NUMBER() OVER (PARTITION BY U.USER_ID ORDER BY SIMILARITY DESC) <= 20
COMMENT = 'Top-20 content recommendations per user based on preference-vector similarity';

-- 7. Cortex Search service over the catalog
--    Creates an indexed semantic search over the DESCRIPTION column.
CREATE OR REPLACE CORTEX SEARCH SERVICE CONTENT_SEARCH
    ON DESCRIPTION
    ATTRIBUTES TITLE, GENRE, CONTENT_TYPE, RELEASE_YEAR, LOCALE
    WAREHOUSE = DEMO_WH
    TARGET_LAG = '5 minutes'
    AS (
        SELECT CONTENT_ID, TITLE, GENRE, CONTENT_TYPE, RELEASE_YEAR, LOCALE, DESCRIPTION
        FROM CONTENT_CATALOG
    );

-- 8. Object tag for governance (shared tag vocabulary with Healthcare demo)
USE SCHEMA HEALTHCARE;
ALTER VIEW SNOWFLAKE_DEMO_PACK.MEDIA.RECOMMENDATIONS_VIEW
    SET TAG PII_CLASS = 'MEDIUM',
            COMPLIANCE_REGIME = 'GDPR';
USE SCHEMA MEDIA;

-- 9. Feedback table (signals sent back from the Streamlit app)
CREATE OR REPLACE TABLE RECOMMENDATION_FEEDBACK (
    FEEDBACK_ID          STRING        DEFAULT UUID_STRING(),
    USER_ID              STRING        NOT NULL,
    CONTENT_ID           STRING        NOT NULL,
    RATING               NUMBER(2, 0),
    CLICK_THROUGH        BOOLEAN,
    FEEDBACK_TIMESTAMP   TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
    CONSTRAINT PK_RECOMMENDATION_FEEDBACK PRIMARY KEY (FEEDBACK_ID)
)
COMMENT = 'Explicit user feedback for future reranker training';

-- End of 01-setup.sql
