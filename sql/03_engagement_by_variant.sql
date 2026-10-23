-- Engagement (game rounds in first 14 days) by variant, raw and with the
-- single extreme outlier (sum_gamerounds = 49,854) removed
WITH flagged AS (
    SELECT *, sum_gamerounds > 10000 AS is_outlier FROM cookie_cats
)
SELECT
    version,
    COUNT(*)                                                     AS players,
    ROUND(AVG(sum_gamerounds), 2)                                AS mean_rounds_raw,
    ROUND(AVG(sum_gamerounds) FILTER (WHERE NOT is_outlier), 2)  AS mean_rounds_clean,
    MEDIAN(sum_gamerounds)                                       AS median_rounds,
    QUANTILE_CONT(sum_gamerounds, 0.95)                          AS p95_rounds,
    MAX(sum_gamerounds)                                          AS max_rounds,
    ROUND(AVG(CAST(sum_gamerounds = 0 AS DOUBLE)), 4)            AS share_zero_rounds
FROM flagged
GROUP BY version
ORDER BY version;
