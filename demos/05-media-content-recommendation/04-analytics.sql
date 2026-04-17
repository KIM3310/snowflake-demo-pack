-- ---------------------------------------------------------------------------
-- demos/05-media-content-recommendation/04-analytics.sql
-- Product and business queries for the recommendation demo.
-- ---------------------------------------------------------------------------

USE ROLE SYSADMIN;
USE WAREHOUSE DEMO_WH;
USE DATABASE SNOWFLAKE_DEMO_PACK;
USE SCHEMA MEDIA;

-- ---------------------------------------------------------------------------
-- Q1. [Product] Semantic search over the catalog.
--     Returns top-5 titles that are thematically similar to a free-text query.
-- ---------------------------------------------------------------------------
SELECT
    RESULT_VALUE:CONTENT_ID::STRING  AS CONTENT_ID,
    RESULT_VALUE:TITLE::STRING        AS TITLE,
    RESULT_VALUE:GENRE::STRING        AS GENRE,
    RESULT_VALUE:RELEASE_YEAR::NUMBER AS RELEASE_YEAR,
    RESULT_VALUE:DESCRIPTION::STRING  AS DESCRIPTION
FROM TABLE(
    CORTEX_SEARCH(
        'CONTENT_SEARCH',
        OBJECT_CONSTRUCT(
            'query', 'tense political drama set in Seoul with a female lead',
            'limit', 5
        )
    )
) AS T (RESULT_VALUE);

-- ---------------------------------------------------------------------------
-- Q2. [Personalization] Top-10 recommendations for a sampled user.
-- ---------------------------------------------------------------------------
SELECT *
FROM RECOMMENDATIONS_VIEW
WHERE USER_ID = (
    SELECT USER_ID
    FROM USER_PREFERENCE_VECTOR
    ORDER BY PLAYS_INCLUDED DESC
    LIMIT 1
)
ORDER BY SIMILARITY DESC
LIMIT 10;

-- ---------------------------------------------------------------------------
-- Q3. [Catalog Ops] Cold-start coverage — new titles discoverable via search.
-- ---------------------------------------------------------------------------
SELECT
    C.RELEASE_YEAR,
    COUNT(*)                             AS TITLES,
    SUM(CASE WHEN E.PLAYS > 0 THEN 1 ELSE 0 END)        AS TITLES_WITH_PLAYS,
    SUM(CASE WHEN EM.CONTENT_ID IS NOT NULL THEN 1 ELSE 0 END) AS TITLES_WITH_EMBEDDING
FROM CONTENT_CATALOG AS C
LEFT JOIN (
    SELECT CONTENT_ID, COUNT(*) AS PLAYS
    FROM USER_EVENTS
    WHERE EVENT_TYPE IN ('PLAY_START', 'PLAY_COMPLETE')
    GROUP BY CONTENT_ID
) AS E USING (CONTENT_ID)
LEFT JOIN CONTENT_EMBEDDINGS AS EM USING (CONTENT_ID)
GROUP BY C.RELEASE_YEAR
ORDER BY C.RELEASE_YEAR DESC;

-- ---------------------------------------------------------------------------
-- Q4. [Content Ops] Genre affinity by locale.
-- ---------------------------------------------------------------------------
SELECT
    LOCALE,
    GENRE,
    COUNT(*)                             AS EVENT_COUNT,
    SUM(CASE WHEN EVENT_TYPE = 'PLAY_COMPLETE' THEN 1 ELSE 0 END) AS COMPLETES,
    ROUND(
        SUM(CASE WHEN EVENT_TYPE = 'PLAY_COMPLETE' THEN 1 ELSE 0 END)::FLOAT
            / NULLIF(COUNT(*), 0),
        3
    )                                    AS COMPLETION_RATE
FROM USER_EVENTS
GROUP BY LOCALE, GENRE
ORDER BY LOCALE, COMPLETION_RATE DESC;

-- ---------------------------------------------------------------------------
-- Q5. [Growth] Engagement funnel per device.
-- ---------------------------------------------------------------------------
SELECT
    DEVICE_TYPE,
    SUM(CASE WHEN EVENT_TYPE = 'IMPRESSION' THEN 1 ELSE 0 END)  AS IMPRESSIONS,
    SUM(CASE WHEN EVENT_TYPE = 'PLAY_START' THEN 1 ELSE 0 END)  AS PLAY_STARTS,
    SUM(CASE WHEN EVENT_TYPE = 'PLAY_COMPLETE' THEN 1 ELSE 0 END) AS PLAY_COMPLETES,
    SUM(CASE WHEN EVENT_TYPE = 'SKIP' THEN 1 ELSE 0 END)         AS SKIPS
FROM USER_EVENTS
GROUP BY DEVICE_TYPE
ORDER BY IMPRESSIONS DESC;

-- ---------------------------------------------------------------------------
-- Q6. [ML Ops] Embedding coverage and freshness.
-- ---------------------------------------------------------------------------
SELECT
    COUNT(*)                                              AS EMBEDDED_TITLES,
    (SELECT COUNT(*) FROM CONTENT_CATALOG)                AS TOTAL_TITLES,
    ROUND(
        100.0 * COUNT(*) / NULLIF((SELECT COUNT(*) FROM CONTENT_CATALOG), 0),
        2
    )                                                     AS PCT_EMBEDDED,
    MIN(GENERATED_AT)                                     AS OLDEST_EMBEDDING,
    MAX(GENERATED_AT)                                     AS NEWEST_EMBEDDING
FROM CONTENT_EMBEDDINGS;

-- ---------------------------------------------------------------------------
-- Q7. [Executive] Headline recommendation quality KPI.
-- ---------------------------------------------------------------------------
SELECT
    COUNT(DISTINCT USER_ID)                                AS USERS_WITH_RECS,
    ROUND(AVG(SIMILARITY), 3)                              AS AVG_TOP_REC_SIMILARITY,
    ROUND(AVG(CASE WHEN SIMILARITY >= 0.75 THEN 1.0 ELSE 0.0 END), 3) AS PCT_HIGH_CONFIDENCE
FROM RECOMMENDATIONS_VIEW
WHERE SIMILARITY IS NOT NULL;
