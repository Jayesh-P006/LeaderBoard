-- ============================================================================
-- MOCK DATA: 100 Students + Exam Sessions + Module Scores + Leaderboard
-- Run AFTER schema.sql
-- ============================================================================

USE leaderboard_db;

-- ────────────────────────────────────────────────────────────────────────────
-- 1. ADMIN USER
-- ────────────────────────────────────────────────────────────────────────────
INSERT INTO users (username, email, full_name, password_hash, role)
VALUES ('admin_master', 'admin@leaderboard.io', 'System Admin', SHA2('admin123', 256), 'admin');

SET @admin_id = LAST_INSERT_ID();


-- ────────────────────────────────────────────────────────────────────────────
-- 2. EXAM DEFINITION
-- ────────────────────────────────────────────────────────────────────────────
INSERT INTO exams (
    title, description, duration_minutes,
    weight_coding, weight_quiz, weight_assessment,
    max_score_coding, max_score_quiz, max_score_assessment,
    status, starts_at, ends_at, created_by
) VALUES (
    'Backend Engineering Challenge 2026',
    'Full-stack backend assessment covering coding, quizzes, and system design',
    180,
    50.00, 30.00, 20.00,
    100.00, 100.00, 100.00,
    'active',
    '2026-02-07 09:00:00',
    '2026-02-07 12:00:00',
    @admin_id
);

SET @exam_id = LAST_INSERT_ID();


-- ────────────────────────────────────────────────────────────────────────────
-- 3. 100 CANDIDATE USERS
-- ────────────────────────────────────────────────────────────────────────────
-- Using a stored procedure for clean generation

DELIMITER //

DROP PROCEDURE IF EXISTS seed_candidates //

CREATE PROCEDURE seed_candidates()
BEGIN
    DECLARE i INT DEFAULT 1;
    DECLARE v_user_id BIGINT;
    DECLARE v_session_id BIGINT;
    DECLARE v_coding_score DECIMAL(10,2);
    DECLARE v_quiz_score DECIMAL(10,2);
    DECLARE v_assess_score DECIMAL(10,2);
    DECLARE v_coding_time INT;
    DECLARE v_quiz_time INT;
    DECLARE v_assess_time INT;
    DECLARE v_total_time INT;
    DECLARE v_start_time DATETIME;
    DECLARE v_finish_time DATETIME;

    -- First name and last name pools
    DECLARE v_first_names VARCHAR(2000) DEFAULT 'Aarav,Aditi,Aisha,Akash,Amit,Ananya,Arjun,Bhavya,Chetan,Deepa,Divya,Esha,Gaurav,Harsh,Ishaan,Jaya,Kabir,Kavya,Lakshmi,Manish,Meera,Neha,Nikhil,Omkar,Pallavi,Pranav,Priya,Rahul,Rajesh,Ravi,Ritika,Rohan,Roshni,Sahil,Sakshi,Sameer,Sandeep,Sanjay,Sapna,Shreya,Simran,Sneha,Sonal,Suresh,Tanvi,Tushar,Uday,Varun,Vidya,Vikas,Vinay,Vivek,Yash,Zara,Aditya,Anjali,Ashish,Bharat,Chandra,Daksh,Ekta,Farhan,Gauri,Hemant,Isha,Jai,Karan,Lavanya,Madhav,Nandini,Pooja,Riya,Shubham,Tanya,Uma,Vikram,Waris,Yamini,Zeenat,Abhi,Bela,Chirag,Diya,Eshwar,Fatima,Girish,Hema,Irfan,Janaki,Kunal,Leela,Mohit,Namrata,Ojas,Parul,Raghav,Siddharth,Trisha,Ujjwal,Vani,Waseem,Xena,Yogesh,Zubin';

    WHILE i <= 100 DO
        SET v_start_time = DATE_ADD('2026-02-07 09:00:00', INTERVAL FLOOR(RAND() * 600) SECOND);

        -- Generate realistic scores with normal-ish distribution
        SET v_coding_score  = ROUND(GREATEST(10, LEAST(100, 55 + (RAND() * 50 - 10) + (RAND() * 20 - 10))), 2);
        SET v_quiz_score    = ROUND(GREATEST(15, LEAST(100, 60 + (RAND() * 45 - 10) + (RAND() * 15 - 5))), 2);
        SET v_assess_score  = ROUND(GREATEST(20, LEAST(100, 50 + (RAND() * 55 - 10) + (RAND() * 20 - 10))), 2);

        -- Generate realistic time spent (seconds)
        SET v_coding_time  = FLOOR(1800 + RAND() * 3600);   -- 30-90 min
        SET v_quiz_time    = FLOOR(600 + RAND() * 1800);      -- 10-40 min
        SET v_assess_time  = FLOOR(1200 + RAND() * 2400);     -- 20-60 min
        SET v_total_time   = v_coding_time + v_quiz_time + v_assess_time;
        SET v_finish_time  = DATE_ADD(v_start_time, INTERVAL v_total_time SECOND);

        -- Insert user
        INSERT INTO users (username, email, full_name, password_hash, role)
        VALUES (
            CONCAT('student_', LPAD(i, 3, '0')),
            CONCAT('student', i, '@campus.edu'),
            CONCAT(
                SUBSTRING_INDEX(SUBSTRING_INDEX(v_first_names, ',', 1 + (i - 1) % 100), ',', -1),
                ' ',
                CASE (i % 20)
                    WHEN 0 THEN 'Sharma' WHEN 1 THEN 'Patel' WHEN 2 THEN 'Singh'
                    WHEN 3 THEN 'Kumar' WHEN 4 THEN 'Gupta' WHEN 5 THEN 'Reddy'
                    WHEN 6 THEN 'Joshi' WHEN 7 THEN 'Verma' WHEN 8 THEN 'Nair'
                    WHEN 9 THEN 'Mehta' WHEN 10 THEN 'Shah' WHEN 11 THEN 'Rao'
                    WHEN 12 THEN 'Desai' WHEN 13 THEN 'Iyer' WHEN 14 THEN 'Khan'
                    WHEN 15 THEN 'Das' WHEN 16 THEN 'Mishra' WHEN 17 THEN 'Pillai'
                    WHEN 18 THEN 'Chatterjee' WHEN 19 THEN 'Banerjee'
                END
            ),
            SHA2(CONCAT('pass_student_', i), 256),
            'candidate'
        );

        SET v_user_id = LAST_INSERT_ID();

        -- Insert exam session
        INSERT INTO exam_sessions (exam_id, user_id, started_at, finished_at, total_time_sec, status, version)
        VALUES (@exam_id, v_user_id, v_start_time, v_finish_time, v_total_time, 'submitted', 1);

        SET v_session_id = LAST_INSERT_ID();

        -- Insert module scores
        -- CODING
        INSERT INTO module_scores (session_id, module_type, raw_score, max_score, time_spent_sec, details, version)
        VALUES (
            v_session_id, 'coding', v_coding_score, 100.00, v_coding_time,
            JSON_OBJECT(
                'test_cases_passed', FLOOR(v_coding_score / 5),
                'test_cases_total', 20,
                'time_complexity_score', ROUND(v_coding_score * 0.9 + RAND() * 10, 1),
                'efficiency_score', ROUND(v_coding_score * 0.85 + RAND() * 15, 1),
                'lines_of_code', FLOOR(50 + RAND() * 200)
            ),
            1
        );

        -- QUIZ
        INSERT INTO module_scores (session_id, module_type, raw_score, max_score, time_spent_sec, details, version)
        VALUES (
            v_session_id, 'quiz', v_quiz_score, 100.00, v_quiz_time,
            JSON_OBJECT(
                'correct', FLOOR(v_quiz_score / 4),
                'total', 25,
                'unanswered', FLOOR(RAND() * 3),
                'negatives', ROUND(-1 * RAND() * 3, 2)
            ),
            1
        );

        -- ASSESSMENT
        INSERT INTO module_scores (session_id, module_type, raw_score, max_score, time_spent_sec, details, version)
        VALUES (
            v_session_id, 'assessment', v_assess_score, 100.00, v_assess_time,
            JSON_OBJECT(
                'auto_score', ROUND(v_assess_score * 0.7, 2),
                'manual_score', ROUND(v_assess_score * 0.3, 2),
                'rubric_coverage', CONCAT(FLOOR(60 + RAND() * 40), '%')
            ),
            1
        );

        -- Upsert leaderboard_snapshot
        INSERT INTO leaderboard_snapshot (
            exam_id, user_id, session_id,
            weighted_coding, weighted_quiz, weighted_assessment,
            total_score, total_time_sec, rank_position, last_calculated_at
        ) VALUES (
            @exam_id, v_user_id, v_session_id,
            ROUND((v_coding_score / 100) * 50, 4),
            ROUND((v_quiz_score / 100) * 30, 4),
            ROUND((v_assess_score / 100) * 20, 4),
            ROUND((v_coding_score / 100) * 50 + (v_quiz_score / 100) * 30 + (v_assess_score / 100) * 20, 4),
            v_total_time,
            0,   -- rank will be computed next
            NOW()
        );

        SET i = i + 1;
    END WHILE;
END //

DELIMITER ;

-- Execute the seeding procedure
CALL seed_candidates();
DROP PROCEDURE IF EXISTS seed_candidates;


-- ────────────────────────────────────────────────────────────────────────────
-- 4. COMPUTE RANKS USING DENSE_RANK WITH TIE-BREAKER
-- ────────────────────────────────────────────────────────────────────────────
UPDATE leaderboard_snapshot AS lb
INNER JOIN (
    SELECT snapshot_id,
           DENSE_RANK() OVER (
               ORDER BY total_score DESC,
                        total_time_sec ASC
           ) AS new_rank
    FROM   leaderboard_snapshot
    WHERE  exam_id = @exam_id
) AS ranked ON lb.snapshot_id = ranked.snapshot_id
SET lb.rank_position = ranked.new_rank
WHERE lb.exam_id = @exam_id;


-- ════════════════════════════════════════════════════════════════════════════
-- 5. ANALYTICAL WINDOW QUERIES — Detailed Statistics
-- ════════════════════════════════════════════════════════════════════════════

-- ┌──────────────────────────────────────────────────────────────────────────┐
-- │  VIEW: v_leaderboard_analytics                                          │
-- │  Comprehensive analytical view with 15+ window functions                │
-- └──────────────────────────────────────────────────────────────────────────┘

DROP VIEW IF EXISTS v_leaderboard_analytics;

CREATE VIEW v_leaderboard_analytics AS
SELECT
    -- ── Identity ──────────────────────────────────────────────────────
    u.user_id,
    u.username,
    u.full_name,
    lb.exam_id,

    -- ── Raw Scores ───────────────────────────────────────────────────
    lb.weighted_coding,
    lb.weighted_quiz,
    lb.weighted_assessment,
    lb.total_score,
    lb.total_time_sec,

    -- ── RANKING FUNCTIONS ────────────────────────────────────────────
    -- Dense Rank (no gaps on ties)
    DENSE_RANK() OVER w_score                        AS dense_rank,

    -- Standard Rank (gaps on ties)
    RANK() OVER w_score                              AS standard_rank,

    -- Row Number (unique, no ties)
    ROW_NUMBER() OVER w_score                        AS row_num,

    -- Percentile Rank: what % of students scored BELOW this student
    ROUND(
        PERCENT_RANK() OVER w_score * 100, 2
    )                                                AS percentile_rank,

    -- NTILE: divide students into quartiles (1=top 25%, 4=bottom 25%)
    NTILE(4) OVER w_score                            AS quartile,

    -- NTILE(10): decile grouping
    NTILE(10) OVER w_score                           AS decile,

    -- ── AGGREGATE WINDOWS ────────────────────────────────────────────
    -- Running average up to current rank
    ROUND(
        AVG(lb.total_score) OVER (ORDER BY lb.total_score DESC
            ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW), 4
    )                                                AS running_avg_score,

    -- Cumulative sum of scores
    ROUND(
        SUM(lb.total_score) OVER (ORDER BY lb.total_score DESC
            ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW), 4
    )                                                AS cumulative_score_sum,

    -- Global stats
    ROUND(AVG(lb.total_score) OVER (), 4)            AS exam_avg_score,
    ROUND(STDDEV_POP(lb.total_score) OVER (), 4)     AS exam_stddev_score,
    MAX(lb.total_score) OVER ()                      AS exam_max_score,
    MIN(lb.total_score) OVER ()                      AS exam_min_score,
    COUNT(*) OVER ()                                 AS total_participants,

    -- ── DEVIATION FROM MEAN ──────────────────────────────────────────
    ROUND(
        lb.total_score - AVG(lb.total_score) OVER (), 4
    )                                                AS deviation_from_mean,

    -- Z-Score: how many std deviations from the mean
    ROUND(
        CASE WHEN STDDEV_POP(lb.total_score) OVER () > 0
             THEN (lb.total_score - AVG(lb.total_score) OVER ())
                  / STDDEV_POP(lb.total_score) OVER ()
             ELSE 0
        END, 4
    )                                                AS z_score,

    -- ── LAG / LEAD — comparison with neighbours ─────────────────────
    -- Score of the student ranked just above
    LAG(lb.total_score, 1) OVER w_score              AS prev_rank_score,

    -- Score of the student ranked just below
    LEAD(lb.total_score, 1) OVER w_score             AS next_rank_score,

    -- Gap to student above
    ROUND(
        lb.total_score - LAG(lb.total_score, 1) OVER w_score, 4
    )                                                AS gap_to_above,

    -- Gap to student below
    ROUND(
        lb.total_score - LEAD(lb.total_score, 1) OVER w_score, 4
    )                                                AS gap_to_below,

    -- ── MODULE-SPECIFIC RANKINGS ─────────────────────────────────────
    DENSE_RANK() OVER (ORDER BY lb.weighted_coding DESC)     AS coding_rank,
    DENSE_RANK() OVER (ORDER BY lb.weighted_quiz DESC)       AS quiz_rank,
    DENSE_RANK() OVER (ORDER BY lb.weighted_assessment DESC) AS assessment_rank,

    -- ── TIME-BASED ANALYTICS ─────────────────────────────────────────
    DENSE_RANK() OVER (ORDER BY lb.total_time_sec ASC)       AS speed_rank,
    ROUND(AVG(lb.total_time_sec) OVER (), 0)                  AS avg_time_sec,

    ROUND(
        lb.total_time_sec - AVG(lb.total_time_sec) OVER (), 0
    )                                                AS time_deviation_sec,

    -- ── PERFORMANCE TIER ─────────────────────────────────────────────
    CASE
        WHEN PERCENT_RANK() OVER w_score >= 0.90 THEN 'Outstanding'
        WHEN PERCENT_RANK() OVER w_score >= 0.75 THEN 'Excellent'
        WHEN PERCENT_RANK() OVER w_score >= 0.50 THEN 'Good'
        WHEN PERCENT_RANK() OVER w_score >= 0.25 THEN 'Average'
        ELSE 'Needs Improvement'
    END                                              AS performance_tier,

    lb.last_calculated_at

FROM leaderboard_snapshot lb
JOIN users u ON lb.user_id = u.user_id

WINDOW w_score AS (
    ORDER BY lb.total_score DESC, lb.total_time_sec ASC
);


-- ┌──────────────────────────────────────────────────────────────────────────┐
-- │  VIEW: v_exam_summary_stats                                             │
-- │  Aggregated exam-level statistics                                       │
-- └──────────────────────────────────────────────────────────────────────────┘

DROP VIEW IF EXISTS v_exam_summary_stats;

CREATE VIEW v_exam_summary_stats AS
SELECT
    lb.exam_id,
    e.title AS exam_title,
    COUNT(*)                                         AS total_participants,

    -- Score distribution
    ROUND(AVG(lb.total_score), 2)                    AS avg_score,
    ROUND(STDDEV_POP(lb.total_score), 2)             AS stddev_score,
    ROUND(MIN(lb.total_score), 2)                    AS min_score,
    ROUND(MAX(lb.total_score), 2)                    AS max_score,
    ROUND(MAX(lb.total_score) - MIN(lb.total_score), 2) AS score_range,

    -- Module-wise averages
    ROUND(AVG(lb.weighted_coding), 2)                AS avg_coding,
    ROUND(AVG(lb.weighted_quiz), 2)                  AS avg_quiz,
    ROUND(AVG(lb.weighted_assessment), 2)            AS avg_assessment,

    -- Module-wise max
    ROUND(MAX(lb.weighted_coding), 2)                AS max_coding,
    ROUND(MAX(lb.weighted_quiz), 2)                  AS max_quiz,
    ROUND(MAX(lb.weighted_assessment), 2)             AS max_assessment,

    -- Time stats
    ROUND(AVG(lb.total_time_sec), 0)                 AS avg_time_sec,
    MIN(lb.total_time_sec)                           AS fastest_time_sec,
    MAX(lb.total_time_sec)                           AS slowest_time_sec,

    -- Pass rate (assuming 40% = passing)
    ROUND(
        SUM(CASE WHEN lb.total_score >= 40 THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 2
    )                                                AS pass_rate_pct,

    -- Quartile boundaries
    ROUND(
        (SELECT lb2.total_score FROM leaderboard_snapshot lb2
         WHERE lb2.exam_id = lb.exam_id
         ORDER BY lb2.total_score ASC
         LIMIT 1 OFFSET FLOOR(COUNT(*) * 0.25)), 2
    )                                                AS q1_score,

    ROUND(
        (SELECT lb2.total_score FROM leaderboard_snapshot lb2
         WHERE lb2.exam_id = lb.exam_id
         ORDER BY lb2.total_score ASC
         LIMIT 1 OFFSET FLOOR(COUNT(*) * 0.75)), 2
    )                                                AS q3_score

FROM leaderboard_snapshot lb
JOIN exams e ON lb.exam_id = e.exam_id
GROUP BY lb.exam_id, e.title;


-- ┌──────────────────────────────────────────────────────────────────────────┐
-- │  VIEW: v_module_comparative_analysis                                    │
-- │  Per-student module-wise analysis with cross-module comparison          │
-- └──────────────────────────────────────────────────────────────────────────┘

DROP VIEW IF EXISTS v_module_comparative_analysis;

CREATE VIEW v_module_comparative_analysis AS
SELECT
    u.user_id,
    u.username,
    u.full_name,
    es.exam_id,

    -- Raw scores
    MAX(CASE WHEN ms.module_type = 'coding'     THEN ms.raw_score END)  AS coding_raw,
    MAX(CASE WHEN ms.module_type = 'quiz'       THEN ms.raw_score END)  AS quiz_raw,
    MAX(CASE WHEN ms.module_type = 'assessment' THEN ms.raw_score END)  AS assessment_raw,

    -- Time per module
    MAX(CASE WHEN ms.module_type = 'coding'     THEN ms.time_spent_sec END)  AS coding_time,
    MAX(CASE WHEN ms.module_type = 'quiz'       THEN ms.time_spent_sec END)  AS quiz_time,
    MAX(CASE WHEN ms.module_type = 'assessment' THEN ms.time_spent_sec END)  AS assessment_time,

    -- Strongest module
    CASE
        WHEN MAX(CASE WHEN ms.module_type = 'coding'     THEN ms.raw_score END) >=
             MAX(CASE WHEN ms.module_type = 'quiz'       THEN ms.raw_score END)
         AND MAX(CASE WHEN ms.module_type = 'coding'     THEN ms.raw_score END) >=
             MAX(CASE WHEN ms.module_type = 'assessment' THEN ms.raw_score END)
        THEN 'Coding'
        WHEN MAX(CASE WHEN ms.module_type = 'quiz'       THEN ms.raw_score END) >=
             MAX(CASE WHEN ms.module_type = 'assessment' THEN ms.raw_score END)
        THEN 'Quiz'
        ELSE 'Assessment'
    END AS strongest_module,

    -- Weakest module
    CASE
        WHEN MAX(CASE WHEN ms.module_type = 'coding'     THEN ms.raw_score END) <=
             MAX(CASE WHEN ms.module_type = 'quiz'       THEN ms.raw_score END)
         AND MAX(CASE WHEN ms.module_type = 'coding'     THEN ms.raw_score END) <=
             MAX(CASE WHEN ms.module_type = 'assessment' THEN ms.raw_score END)
        THEN 'Coding'
        WHEN MAX(CASE WHEN ms.module_type = 'quiz'       THEN ms.raw_score END) <=
             MAX(CASE WHEN ms.module_type = 'assessment' THEN ms.raw_score END)
        THEN 'Quiz'
        ELSE 'Assessment'
    END AS weakest_module,

    -- Score consistency (std dev across modules — lower = more consistent)
    ROUND(STDDEV_POP(ms.raw_score), 2) AS cross_module_stddev,

    -- Efficiency: points per minute
    ROUND(
        SUM(ms.raw_score) / NULLIF(SUM(ms.time_spent_sec) / 60.0, 0), 4
    ) AS points_per_minute

FROM exam_sessions es
JOIN users u ON es.user_id = u.user_id
JOIN module_scores ms ON es.session_id = ms.session_id
GROUP BY u.user_id, u.username, u.full_name, es.exam_id;


-- ┌──────────────────────────────────────────────────────────────────────────┐
-- │  VIEW: v_score_distribution_buckets                                     │
-- │  Histogram-style bucketing of scores                                    │
-- └──────────────────────────────────────────────────────────────────────────┘

DROP VIEW IF EXISTS v_score_distribution_buckets;

CREATE VIEW v_score_distribution_buckets AS
SELECT
    lb.exam_id,
    CASE
        WHEN lb.total_score >= 90 THEN '90-100'
        WHEN lb.total_score >= 80 THEN '80-89'
        WHEN lb.total_score >= 70 THEN '70-79'
        WHEN lb.total_score >= 60 THEN '60-69'
        WHEN lb.total_score >= 50 THEN '50-59'
        WHEN lb.total_score >= 40 THEN '40-49'
        WHEN lb.total_score >= 30 THEN '30-39'
        ELSE 'Below 30'
    END AS score_bucket,
    COUNT(*) AS student_count,
    ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM leaderboard_snapshot lb2 WHERE lb2.exam_id = lb.exam_id), 2) AS pct_of_total,
    ROUND(AVG(lb.total_time_sec), 0) AS avg_time_in_bucket
FROM leaderboard_snapshot lb
GROUP BY lb.exam_id,
    CASE
        WHEN lb.total_score >= 90 THEN '90-100'
        WHEN lb.total_score >= 80 THEN '80-89'
        WHEN lb.total_score >= 70 THEN '70-79'
        WHEN lb.total_score >= 60 THEN '60-69'
        WHEN lb.total_score >= 50 THEN '50-59'
        WHEN lb.total_score >= 40 THEN '40-49'
        WHEN lb.total_score >= 30 THEN '30-39'
        ELSE 'Below 30'
    END
ORDER BY
    CASE
        WHEN lb.total_score >= 90 THEN 1
        WHEN lb.total_score >= 80 THEN 2
        WHEN lb.total_score >= 70 THEN 3
        WHEN lb.total_score >= 60 THEN 4
        WHEN lb.total_score >= 50 THEN 5
        WHEN lb.total_score >= 40 THEN 6
        WHEN lb.total_score >= 30 THEN 7
        ELSE 8
    END;


-- ════════════════════════════════════════════════════════════════════════════
-- 6. SAMPLE QUERIES — run these to verify
-- ════════════════════════════════════════════════════════════════════════════

-- Top 10 with full analytics
-- SELECT * FROM v_leaderboard_analytics WHERE exam_id = @exam_id ORDER BY dense_rank LIMIT 10;

-- Exam summary stats
-- SELECT * FROM v_exam_summary_stats;

-- Score distribution histogram
-- SELECT * FROM v_score_distribution_buckets WHERE exam_id = @exam_id;

-- Module comparison — who's best at what
-- SELECT * FROM v_module_comparative_analysis WHERE exam_id = @exam_id ORDER BY points_per_minute DESC LIMIT 10;

-- Students in top 10% (Outstanding tier)
-- SELECT * FROM v_leaderboard_analytics WHERE exam_id = @exam_id AND performance_tier = 'Outstanding';

SELECT CONCAT('✓ Seeded ', COUNT(*), ' students successfully') AS status FROM leaderboard_snapshot;
