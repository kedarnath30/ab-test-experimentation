-- Primary (7-day) and guardrail (1-day) retention by variant
SELECT
    version,
    COUNT(*)                                          AS players,
    SUM(CAST(retention_1 AS INTEGER))                 AS retained_d1,
    ROUND(AVG(CAST(retention_1 AS DOUBLE)), 4)        AS retention_1_rate,
    SUM(CAST(retention_7 AS INTEGER))                 AS retained_d7,
    ROUND(AVG(CAST(retention_7 AS DOUBLE)), 4)        AS retention_7_rate
FROM cookie_cats
GROUP BY version
ORDER BY version;
