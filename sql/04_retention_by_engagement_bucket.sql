-- 7-day retention by engagement bucket and variant: where does the gap come from?
-- Buckets are defined around the two gate positions (level 30 vs level 40).
SELECT
    CASE
        WHEN sum_gamerounds = 0   THEN '0'
        WHEN sum_gamerounds < 30  THEN '1-29'
        WHEN sum_gamerounds < 40  THEN '30-39'
        WHEN sum_gamerounds < 100 THEN '40-99'
        ELSE '100+'
    END                                           AS rounds_bucket,
    version,
    COUNT(*)                                      AS players,
    ROUND(AVG(CAST(retention_7 AS DOUBLE)), 4)    AS retention_7_rate
FROM cookie_cats
GROUP BY rounds_bucket, version
ORDER BY MIN(sum_gamerounds), version;
