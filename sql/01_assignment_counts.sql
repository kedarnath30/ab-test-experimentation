-- Players per variant and share of traffic (input to the SRM check)
SELECT
    version,
    COUNT(*)                                        AS players,
    ROUND(COUNT(*) * 1.0 / SUM(COUNT(*)) OVER (), 4) AS traffic_share
FROM cookie_cats
GROUP BY version
ORDER BY version;
