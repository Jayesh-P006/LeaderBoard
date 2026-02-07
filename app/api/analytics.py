"""
Analytics API — Detailed statistical breakdowns using window functions.

GET /api/v1/analytics/leaderboard?exam_id=<id>  — per-student analytics
GET /api/v1/analytics/summary?exam_id=<id>      — exam-wide summary stats
GET /api/v1/analytics/distribution?exam_id=<id> — score distribution buckets
GET /api/v1/analytics/modules?exam_id=<id>      — module comparative analysis
GET /api/v1/analytics/student/<user_id>?exam_id=<id> — individual student deep-dive
"""

from __future__ import annotations

import logging
from flask import Blueprint, request, jsonify
from sqlalchemy import text

from app.extensions import db, cache

analytics_bp = Blueprint("analytics", __name__)
logger = logging.getLogger(__name__)


# ────────────────────────────────────────────────────────────────────────────
# 1. Per-Student Leaderboard with Full Analytics (Window Functions)
# ────────────────────────────────────────────────────────────────────────────

@analytics_bp.route("/analytics/leaderboard", methods=["GET"])
@cache.cached(timeout=10, query_string=True)
def analytics_leaderboard():
    """
    Returns every student with 20+ analytical metrics computed via
    SQL window functions: DENSE_RANK, PERCENT_RANK, NTILE, LAG, LEAD,
    running averages, Z-scores, performance tiers, etc.
    """
    exam_id = request.args.get("exam_id", type=int)
    if exam_id is None:
        return jsonify({"error": "exam_id is required"}), 400

    page = max(1, request.args.get("page", 1, type=int))
    per_page = min(100, max(1, request.args.get("per_page", 50, type=int)))
    offset = (page - 1) * per_page

    sql = text("""
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
            ROUND(PERCENT_RANK() OVER w_score * 100, 2)     AS `percentile_rank`,
            NTILE(4) OVER w_score                            AS `quartile`,
            NTILE(10) OVER w_score                           AS `decile`,

            ROUND(AVG(lb.total_score) OVER (
                ORDER BY lb.total_score DESC
                ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
            ), 4)                                            AS running_avg,

            ROUND(AVG(lb.total_score) OVER (), 4)            AS exam_avg,
            ROUND(STDDEV_POP(lb.total_score) OVER (), 4)     AS exam_stddev,

            ROUND(lb.total_score - AVG(lb.total_score) OVER (), 4) AS deviation,

            ROUND(
                CASE WHEN STDDEV_POP(lb.total_score) OVER () > 0
                     THEN (lb.total_score - AVG(lb.total_score) OVER ())
                          / STDDEV_POP(lb.total_score) OVER ()
                     ELSE 0
                END, 4
            )                                                AS z_score,

            LAG(lb.total_score, 1) OVER w_score              AS prev_score,
            LEAD(lb.total_score, 1) OVER w_score             AS next_score,
            ROUND(lb.total_score - LAG(lb.total_score, 1) OVER w_score, 4) AS gap_above,
            ROUND(lb.total_score - LEAD(lb.total_score, 1) OVER w_score, 4) AS gap_below,

            DENSE_RANK() OVER (ORDER BY lb.weighted_coding DESC)     AS `coding_rank`,
            DENSE_RANK() OVER (ORDER BY lb.weighted_quiz DESC)       AS `quiz_rank`,
            DENSE_RANK() OVER (ORDER BY lb.weighted_assessment DESC) AS `assessment_rank`,
            DENSE_RANK() OVER (ORDER BY lb.total_time_sec ASC)       AS `speed_rank`,

            CASE
                WHEN PERCENT_RANK() OVER w_score >= 0.90 THEN 'Outstanding'
                WHEN PERCENT_RANK() OVER w_score >= 0.75 THEN 'Excellent'
                WHEN PERCENT_RANK() OVER w_score >= 0.50 THEN 'Good'
                WHEN PERCENT_RANK() OVER w_score >= 0.25 THEN 'Average'
                ELSE 'Needs Improvement'
            END                                              AS `performance_tier`,

            COUNT(*) OVER ()                                 AS `total_participants`

        FROM leaderboard_snapshot lb
        JOIN users u ON lb.user_id = u.user_id
        WHERE lb.exam_id = :exam_id
        WINDOW w_score AS (ORDER BY lb.total_score DESC, lb.total_time_sec ASC)
        ORDER BY lb.total_score DESC, lb.total_time_sec ASC
        LIMIT :limit OFFSET :offset
    """)

    rows = db.session.execute(sql, {
        "exam_id": exam_id, "limit": per_page, "offset": offset
    }).mappings().all()

    if not rows:
        return jsonify({"error": "No data found for this exam"}), 404

    entries = [dict(r) for r in rows]
    # Convert Decimal types to float for JSON serialisation
    for entry in entries:
        for k, v in entry.items():
            if hasattr(v, 'quantize'):  # Decimal
                entry[k] = float(v)

    return jsonify({
        "exam_id": exam_id,
        "page": page,
        "per_page": per_page,
        "total_participants": int(entries[0]["total_participants"]) if entries else 0,
        "data": entries,
    }), 200


# ────────────────────────────────────────────────────────────────────────────
# 2. Exam Summary Statistics
# ────────────────────────────────────────────────────────────────────────────

@analytics_bp.route("/analytics/summary", methods=["GET"])
@cache.cached(timeout=15, query_string=True)
def analytics_summary():
    """Aggregated exam-level statistics."""

    exam_id = request.args.get("exam_id", type=int)
    if exam_id is None:
        return jsonify({"error": "exam_id is required"}), 400

    sql = text("""
        SELECT
            lb.exam_id,
            e.title                                          AS exam_title,
            COUNT(*)                                         AS total_participants,
            ROUND(AVG(lb.total_score), 2)                    AS avg_score,
            ROUND(STDDEV_POP(lb.total_score), 2)             AS stddev_score,
            ROUND(MIN(lb.total_score), 2)                    AS min_score,
            ROUND(MAX(lb.total_score), 2)                    AS max_score,
            ROUND(MAX(lb.total_score) - MIN(lb.total_score), 2) AS score_range,
            ROUND(AVG(lb.weighted_coding), 2)                AS avg_coding,
            ROUND(AVG(lb.weighted_quiz), 2)                  AS avg_quiz,
            ROUND(AVG(lb.weighted_assessment), 2)            AS avg_assessment,
            ROUND(MAX(lb.weighted_coding), 2)                AS max_coding,
            ROUND(MAX(lb.weighted_quiz), 2)                  AS max_quiz,
            ROUND(MAX(lb.weighted_assessment), 2)            AS max_assessment,
            ROUND(AVG(lb.total_time_sec), 0)                 AS avg_time_sec,
            MIN(lb.total_time_sec)                           AS fastest_time_sec,
            MAX(lb.total_time_sec)                           AS slowest_time_sec,
            ROUND(
                SUM(CASE WHEN lb.total_score >= 40 THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 2
            )                                                AS pass_rate_pct,
            ROUND(
                SUM(CASE WHEN lb.total_score >= 75 THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 2
            )                                                AS distinction_rate_pct
        FROM leaderboard_snapshot lb
        JOIN exams e ON lb.exam_id = e.exam_id
        WHERE lb.exam_id = :exam_id
        GROUP BY lb.exam_id, e.title
    """)

    row = db.session.execute(sql, {"exam_id": exam_id}).mappings().one_or_none()

    if row is None:
        return jsonify({"error": "No data found"}), 404

    result = dict(row)
    for k, v in result.items():
        if hasattr(v, 'quantize'):
            result[k] = float(v)

    return jsonify(result), 200


# ────────────────────────────────────────────────────────────────────────────
# 3. Score Distribution — Histogram Buckets
# ────────────────────────────────────────────────────────────────────────────

@analytics_bp.route("/analytics/distribution", methods=["GET"])
@cache.cached(timeout=15, query_string=True)
def analytics_distribution():
    """Score distribution grouped into 10-point buckets."""

    exam_id = request.args.get("exam_id", type=int)
    if exam_id is None:
        return jsonify({"error": "exam_id is required"}), 400

    sql = text("""
        SELECT
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
            ROUND(
                COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 2
            ) AS pct_of_total,
            ROUND(AVG(lb.total_score), 2) AS avg_in_bucket,
            ROUND(AVG(lb.total_time_sec), 0) AS avg_time_in_bucket
        FROM leaderboard_snapshot lb
        WHERE lb.exam_id = :exam_id
        GROUP BY score_bucket
        ORDER BY MIN(lb.total_score) DESC
    """)

    rows = db.session.execute(sql, {"exam_id": exam_id}).mappings().all()

    buckets = []
    for r in rows:
        d = dict(r)
        for k, v in d.items():
            if hasattr(v, 'quantize'):
                d[k] = float(v)
        buckets.append(d)

    return jsonify({"exam_id": exam_id, "distribution": buckets}), 200


# ────────────────────────────────────────────────────────────────────────────
# 4. Module Comparative Analysis
# ────────────────────────────────────────────────────────────────────────────

@analytics_bp.route("/analytics/modules", methods=["GET"])
@cache.cached(timeout=15, query_string=True)
def analytics_modules():
    """Per-student module-wise analysis: strongest/weakest module, efficiency."""

    exam_id = request.args.get("exam_id", type=int)
    if exam_id is None:
        return jsonify({"error": "exam_id is required"}), 400

    sort_by = request.args.get("sort", "points_per_minute")
    allowed_sorts = {"points_per_minute", "coding_raw", "quiz_raw", "assessment_raw", "cross_module_stddev"}
    if sort_by not in allowed_sorts:
        sort_by = "points_per_minute"

    sql = text(f"""
        SELECT
            u.user_id,
            u.username,
            u.full_name,

            MAX(CASE WHEN ms.module_type = 'coding'     THEN ms.raw_score END)  AS coding_raw,
            MAX(CASE WHEN ms.module_type = 'quiz'       THEN ms.raw_score END)  AS quiz_raw,
            MAX(CASE WHEN ms.module_type = 'assessment' THEN ms.raw_score END)  AS assessment_raw,

            MAX(CASE WHEN ms.module_type = 'coding'     THEN ms.time_spent_sec END)  AS coding_time,
            MAX(CASE WHEN ms.module_type = 'quiz'       THEN ms.time_spent_sec END)  AS quiz_time,
            MAX(CASE WHEN ms.module_type = 'assessment' THEN ms.time_spent_sec END)  AS assessment_time,

            CASE
                WHEN MAX(CASE WHEN ms.module_type = 'coding' THEN ms.raw_score END) >=
                     MAX(CASE WHEN ms.module_type = 'quiz' THEN ms.raw_score END)
                 AND MAX(CASE WHEN ms.module_type = 'coding' THEN ms.raw_score END) >=
                     MAX(CASE WHEN ms.module_type = 'assessment' THEN ms.raw_score END)
                THEN 'Coding'
                WHEN MAX(CASE WHEN ms.module_type = 'quiz' THEN ms.raw_score END) >=
                     MAX(CASE WHEN ms.module_type = 'assessment' THEN ms.raw_score END)
                THEN 'Quiz'
                ELSE 'Assessment'
            END AS strongest_module,

            CASE
                WHEN MAX(CASE WHEN ms.module_type = 'coding' THEN ms.raw_score END) <=
                     MAX(CASE WHEN ms.module_type = 'quiz' THEN ms.raw_score END)
                 AND MAX(CASE WHEN ms.module_type = 'coding' THEN ms.raw_score END) <=
                     MAX(CASE WHEN ms.module_type = 'assessment' THEN ms.raw_score END)
                THEN 'Coding'
                WHEN MAX(CASE WHEN ms.module_type = 'quiz' THEN ms.raw_score END) <=
                     MAX(CASE WHEN ms.module_type = 'assessment' THEN ms.raw_score END)
                THEN 'Quiz'
                ELSE 'Assessment'
            END AS weakest_module,

            ROUND(STDDEV_POP(ms.raw_score), 2) AS cross_module_stddev,

            ROUND(
                SUM(ms.raw_score) / NULLIF(SUM(ms.time_spent_sec) / 60.0, 0), 4
            ) AS points_per_minute

        FROM exam_sessions es
        JOIN users u ON es.user_id = u.user_id
        JOIN module_scores ms ON es.session_id = ms.session_id
        WHERE es.exam_id = :exam_id
        GROUP BY u.user_id, u.username, u.full_name
        ORDER BY {sort_by} DESC
    """)

    rows = db.session.execute(sql, {"exam_id": exam_id}).mappings().all()

    data = []
    for r in rows:
        d = dict(r)
        for k, v in d.items():
            if hasattr(v, 'quantize'):
                d[k] = float(v)
        data.append(d)

    return jsonify({"exam_id": exam_id, "data": data}), 200


# ────────────────────────────────────────────────────────────────────────────
# 5. Individual Student Deep-Dive
# ────────────────────────────────────────────────────────────────────────────

@analytics_bp.route("/analytics/student/<int:user_id>", methods=["GET"])
def analytics_student(user_id: int):
    """
    Complete analytical profile for a single student:
    rank, percentile, z-score, module breakdown, comparison to peers.
    """

    exam_id = request.args.get("exam_id", type=int)
    if exam_id is None:
        return jsonify({"error": "exam_id is required"}), 400

    # Get analytics row for this student
    sql = text("""
        WITH ranked AS (
            SELECT
                u.user_id,
                u.username,
                u.full_name,
                lb.weighted_coding,
                lb.weighted_quiz,
                lb.weighted_assessment,
                lb.total_score,
                lb.total_time_sec,

                DENSE_RANK() OVER w_score                    AS `dense_rank`,
                ROUND(PERCENT_RANK() OVER w_score * 100, 2) AS `percentile_rank`,
                NTILE(4) OVER w_score                        AS `quartile`,

                ROUND(AVG(lb.total_score) OVER (), 4)        AS exam_avg,
                ROUND(STDDEV_POP(lb.total_score) OVER (), 4) AS exam_stddev,
                COUNT(*) OVER ()                             AS total_participants,

                ROUND(
                    CASE WHEN STDDEV_POP(lb.total_score) OVER () > 0
                         THEN (lb.total_score - AVG(lb.total_score) OVER ())
                              / STDDEV_POP(lb.total_score) OVER ()
                         ELSE 0
                    END, 4
                )                                            AS z_score,

                LAG(lb.total_score, 1) OVER w_score          AS score_above,
                LEAD(lb.total_score, 1) OVER w_score         AS score_below,

                DENSE_RANK() OVER (ORDER BY lb.weighted_coding DESC)     AS `coding_rank`,
                DENSE_RANK() OVER (ORDER BY lb.weighted_quiz DESC)       AS `quiz_rank`,
                DENSE_RANK() OVER (ORDER BY lb.weighted_assessment DESC) AS `assessment_rank`,
                DENSE_RANK() OVER (ORDER BY lb.total_time_sec ASC)       AS `speed_rank`,

                CASE
                    WHEN PERCENT_RANK() OVER w_score >= 0.90 THEN 'Outstanding'
                    WHEN PERCENT_RANK() OVER w_score >= 0.75 THEN 'Excellent'
                    WHEN PERCENT_RANK() OVER w_score >= 0.50 THEN 'Good'
                    WHEN PERCENT_RANK() OVER w_score >= 0.25 THEN 'Average'
                    ELSE 'Needs Improvement'
                END AS performance_tier

            FROM leaderboard_snapshot lb
            JOIN users u ON lb.user_id = u.user_id
            WHERE lb.exam_id = :exam_id
            WINDOW w_score AS (ORDER BY lb.total_score DESC, lb.total_time_sec ASC)
        )
        SELECT * FROM ranked WHERE user_id = :user_id
    """)

    row = db.session.execute(sql, {"exam_id": exam_id, "user_id": user_id}).mappings().one_or_none()

    if row is None:
        return jsonify({"error": "Student not found in this exam"}), 404

    result = dict(row)
    for k, v in result.items():
        if hasattr(v, 'quantize'):
            result[k] = float(v)

    # Fetch module details
    module_sql = text("""
        SELECT ms.module_type, ms.raw_score, ms.max_score,
               ms.time_spent_sec, ms.details
        FROM module_scores ms
        JOIN exam_sessions es ON ms.session_id = es.session_id
        WHERE es.exam_id = :exam_id AND es.user_id = :user_id
    """)
    modules = db.session.execute(module_sql, {"exam_id": exam_id, "user_id": user_id}).mappings().all()

    result["modules"] = []
    for m in modules:
        md = dict(m)
        for k, v in md.items():
            if hasattr(v, 'quantize'):
                md[k] = float(v)
        result["modules"].append(md)

    return jsonify(result), 200
