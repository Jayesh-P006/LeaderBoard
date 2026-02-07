-- Analytical Views — run separately after seed_mock_data.sql
USE leaderboard_db;

DROP VIEW IF EXISTS v_leaderboard_analytics;

CREATE VIEW v_leaderboard_analytics AS
SELECT
    u.user_id,
    u.username,
    u.full_name,
    lb.exam_id,
    lb.weighted_coding,
    lb.weighted_quiz,
    lb.weighted_assessment,
    lb.total_score,
    lb.total_time_sec,
    DENSE_RANK() OVER w_score                        AS `dense_rank`,
    RANK() OVER w_score                              AS `standard_rank`,
    ROW_NUMBER() OVER w_score                        AS `row_num`,
    ROUND(PERCENT_RANK() OVER w_score * 100, 2)      AS `percentile_rank`,
    NTILE(4) OVER w_score                            AS `quartile`,
    NTILE(10) OVER w_score                           AS `decile`,
    ROUND(AVG(lb.total_score) OVER (ORDER BY lb.total_score DESC ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW), 4) AS running_avg_score,
    ROUND(SUM(lb.total_score) OVER (ORDER BY lb.total_score DESC ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW), 4) AS cumulative_score_sum,
    ROUND(AVG(lb.total_score) OVER (), 4)            AS exam_avg_score,
    ROUND(STDDEV_POP(lb.total_score) OVER (), 4)     AS exam_stddev_score,
    MAX(lb.total_score) OVER ()                      AS exam_max_score,
    MIN(lb.total_score) OVER ()                      AS exam_min_score,
    COUNT(*) OVER ()                                 AS total_participants,
    ROUND(lb.total_score - AVG(lb.total_score) OVER (), 4) AS deviation_from_mean,
    ROUND(
        CASE WHEN STDDEV_POP(lb.total_score) OVER () > 0
             THEN (lb.total_score - AVG(lb.total_score) OVER ()) / STDDEV_POP(lb.total_score) OVER ()
             ELSE 0
        END, 4
    ) AS z_score,
    LAG(lb.total_score, 1) OVER w_score              AS prev_rank_score,
    LEAD(lb.total_score, 1) OVER w_score             AS next_rank_score,
    ROUND(lb.total_score - LAG(lb.total_score, 1) OVER w_score, 4)  AS gap_to_above,
    ROUND(lb.total_score - LEAD(lb.total_score, 1) OVER w_score, 4) AS gap_to_below,
    DENSE_RANK() OVER (ORDER BY lb.weighted_coding DESC)     AS `coding_rank`,
    DENSE_RANK() OVER (ORDER BY lb.weighted_quiz DESC)       AS `quiz_rank`,
    DENSE_RANK() OVER (ORDER BY lb.weighted_assessment DESC) AS `assessment_rank`,
    DENSE_RANK() OVER (ORDER BY lb.total_time_sec ASC)       AS `speed_rank`,
    ROUND(AVG(lb.total_time_sec) OVER (), 0)                 AS avg_time_sec,
    ROUND(lb.total_time_sec - AVG(lb.total_time_sec) OVER (), 0) AS time_deviation_sec,
    CASE
        WHEN PERCENT_RANK() OVER w_score >= 0.90 THEN 'Outstanding'
        WHEN PERCENT_RANK() OVER w_score >= 0.75 THEN 'Excellent'
        WHEN PERCENT_RANK() OVER w_score >= 0.50 THEN 'Good'
        WHEN PERCENT_RANK() OVER w_score >= 0.25 THEN 'Average'
        ELSE 'Needs Improvement'
    END AS performance_tier,
    lb.last_calculated_at
FROM leaderboard_snapshot lb
JOIN users u ON lb.user_id = u.user_id
WINDOW w_score AS (ORDER BY lb.total_score DESC, lb.total_time_sec ASC);
