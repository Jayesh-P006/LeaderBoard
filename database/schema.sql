-- ============================================================================
-- LEADERBOARD SYSTEM — DATABASE SCHEMA
-- Engine  : MySQL 8.0+ (InnoDB for full ACID compliance)
-- Author  : Senior Backend Architect
-- ============================================================================

-- ────────────────────────────────────────────────────────────────────────────
-- 1. USERS
-- ────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS users (
    user_id         BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    username        VARCHAR(64)  NOT NULL UNIQUE,
    email           VARCHAR(255) NOT NULL UNIQUE,
    full_name       VARCHAR(128) NOT NULL,
    password_hash   VARCHAR(255) NOT NULL,
    role            ENUM('candidate', 'admin', 'moderator') NOT NULL DEFAULT 'candidate',
    is_active       BOOLEAN      NOT NULL DEFAULT TRUE,
    created_at      DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    INDEX idx_users_role (role),
    INDEX idx_users_active (is_active)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- ────────────────────────────────────────────────────────────────────────────
-- 2. EXAMS — master definition of each examination
-- ────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS exams (
    exam_id             BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    title               VARCHAR(255)  NOT NULL,
    description         TEXT,
    duration_minutes    INT UNSIGNED  NOT NULL DEFAULT 120,

    -- Configurable weights (must sum to 100)
    weight_coding       DECIMAL(5,2)  NOT NULL DEFAULT 50.00,
    weight_quiz         DECIMAL(5,2)  NOT NULL DEFAULT 30.00,
    weight_assessment   DECIMAL(5,2)  NOT NULL DEFAULT 20.00,

    max_score_coding    DECIMAL(10,2) NOT NULL DEFAULT 100.00,
    max_score_quiz      DECIMAL(10,2) NOT NULL DEFAULT 100.00,
    max_score_assessment DECIMAL(10,2) NOT NULL DEFAULT 100.00,

    status              ENUM('draft', 'scheduled', 'active', 'completed', 'archived')
                        NOT NULL DEFAULT 'draft',
    starts_at           DATETIME,
    ends_at             DATETIME,
    created_by          BIGINT UNSIGNED NOT NULL,
    created_at          DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at          DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    CONSTRAINT fk_exams_creator FOREIGN KEY (created_by) REFERENCES users(user_id),
    CONSTRAINT chk_weights CHECK (weight_coding + weight_quiz + weight_assessment = 100.00),

    INDEX idx_exams_status (status),
    INDEX idx_exams_starts (starts_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- ────────────────────────────────────────────────────────────────────────────
-- 3. EXAM SESSIONS — one row per candidate per exam attempt
-- ────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS exam_sessions (
    session_id      BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    exam_id         BIGINT UNSIGNED NOT NULL,
    user_id         BIGINT UNSIGNED NOT NULL,

    started_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    finished_at     DATETIME NULL,

    -- Total wall-clock seconds the candidate spent (updated on finish)
    total_time_sec  INT UNSIGNED NOT NULL DEFAULT 0,

    status          ENUM('in_progress', 'submitted', 'timed_out', 'disqualified')
                    NOT NULL DEFAULT 'in_progress',

    -- Snapshot version counter for optimistic locking
    version         INT UNSIGNED NOT NULL DEFAULT 1,

    created_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    CONSTRAINT fk_session_exam FOREIGN KEY (exam_id)  REFERENCES exams(exam_id),
    CONSTRAINT fk_session_user FOREIGN KEY (user_id)  REFERENCES users(user_id),
    UNIQUE KEY uq_exam_user (exam_id, user_id),       -- one session per candidate per exam

    INDEX idx_session_status (status),
    INDEX idx_session_user   (user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- ────────────────────────────────────────────────────────────────────────────
-- 4. MODULE SCORES — per-module breakdown for each session
--    module_type: 'coding' | 'quiz' | 'assessment'
-- ────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS module_scores (
    score_id        BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    session_id      BIGINT UNSIGNED NOT NULL,
    module_type     ENUM('coding', 'quiz', 'assessment') NOT NULL,

    -- Raw score earned in this module (0 .. max_score_<module> of exam)
    raw_score       DECIMAL(10,2) NOT NULL DEFAULT 0.00,

    -- Maximum possible score for this module (denormalised for fast queries)
    max_score       DECIMAL(10,2) NOT NULL DEFAULT 100.00,

    -- Time spent on this specific module (seconds)
    time_spent_sec  INT UNSIGNED NOT NULL DEFAULT 0,

    -- Detailed breakdown (JSON blob for flexibility)
    --   coding  → { "test_cases_passed": 8, "test_cases_total": 10,
    --               "time_complexity_score": 90, "efficiency_score": 85 }
    --   quiz    → { "correct": 18, "total": 20, "negatives": -0.5 }
    --   assess  → { "auto_score": 70, "manual_score": null }
    details         JSON,

    -- Optimistic lock
    version         INT UNSIGNED NOT NULL DEFAULT 1,

    created_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    CONSTRAINT fk_modscore_session FOREIGN KEY (session_id) REFERENCES exam_sessions(session_id),
    UNIQUE KEY uq_session_module (session_id, module_type),

    INDEX idx_modscore_type (module_type)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- ────────────────────────────────────────────────────────────────────────────
-- 5. LEADERBOARD SNAPSHOT — materialised view of rankings per exam
--    Updated transactionally whenever a score changes.
-- ────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS leaderboard_snapshot (
    snapshot_id         BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    exam_id             BIGINT UNSIGNED NOT NULL,
    user_id             BIGINT UNSIGNED NOT NULL,
    session_id          BIGINT UNSIGNED NOT NULL,

    -- Weighted scores per module
    weighted_coding     DECIMAL(10,4) NOT NULL DEFAULT 0.0000,
    weighted_quiz       DECIMAL(10,4) NOT NULL DEFAULT 0.0000,
    weighted_assessment DECIMAL(10,4) NOT NULL DEFAULT 0.0000,

    -- Aggregated total  = Σ weighted module scores
    total_score         DECIMAL(10,4) NOT NULL DEFAULT 0.0000,

    -- Tie-breaker: lower is better
    total_time_sec      INT UNSIGNED  NOT NULL DEFAULT 0,

    -- Computed rank within this exam
    rank_position       INT UNSIGNED  NOT NULL DEFAULT 0,

    last_calculated_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_lb_exam    FOREIGN KEY (exam_id)    REFERENCES exams(exam_id),
    CONSTRAINT fk_lb_user    FOREIGN KEY (user_id)    REFERENCES users(user_id),
    CONSTRAINT fk_lb_session FOREIGN KEY (session_id) REFERENCES exam_sessions(session_id),
    UNIQUE KEY uq_lb_exam_user (exam_id, user_id),

    -- The money index: fast sorted retrieval for the GET /leaderboard query
    INDEX idx_lb_rank (exam_id, total_score DESC, total_time_sec ASC)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- ────────────────────────────────────────────────────────────────────────────
-- 6. SCORE AUDIT LOG — append-only history of every score mutation
--    Guarantees traceability and rollback capability.
-- ────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS score_audit_log (
    log_id          BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    session_id      BIGINT UNSIGNED NOT NULL,
    module_type     ENUM('coding', 'quiz', 'assessment') NOT NULL,
    old_score       DECIMAL(10,2),
    new_score       DECIMAL(10,2) NOT NULL,
    changed_by      BIGINT UNSIGNED NOT NULL,     -- user_id or system account
    change_reason   VARCHAR(255),
    created_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_audit_session FOREIGN KEY (session_id) REFERENCES exam_sessions(session_id),

    INDEX idx_audit_session (session_id),
    INDEX idx_audit_ts      (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
