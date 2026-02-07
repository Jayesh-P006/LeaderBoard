"""
GET /api/v1/leaderboard?exam_id=<id>&page=1&per_page=50

Returns the sorted leaderboard for a given exam.
- Sorted by total_score DESC, total_time_sec ASC (tie-breaker).
- Redis-cached with short TTL (configurable, default 5s).
- Supports pagination.
"""

from __future__ import annotations

import json
import logging

from flask import Blueprint, request, jsonify, current_app
from sqlalchemy import select, func

from app.extensions import db, cache
from app.models import LeaderboardSnapshot, User, Exam

leaderboard_bp = Blueprint("leaderboard", __name__)
logger = logging.getLogger(__name__)


@leaderboard_bp.route("/leaderboard", methods=["GET"])
def get_leaderboard():
    """
    GET /api/v1/leaderboard

    Query params:
      - exam_id   (required) : int
      - page      (optional) : int, default 1
      - per_page  (optional) : int, default 50, max 200
      - user_id   (optional) : int — if provided, also returns that user's entry

    Response 200:
    {
      "exam_id": 1,
      "exam_title": "Backend Challenge 2026",
      "total_participants": 842,
      "page": 1,
      "per_page": 50,
      "leaderboard": [ … ],
      "my_entry": { … } | null,
      "cached": true
    }
    """

    # ── Parse & validate query params ──────────────────────────────────
    exam_id = request.args.get("exam_id", type=int)
    if exam_id is None:
        return jsonify({"error": "exam_id query parameter is required"}), 400

    page = max(1, request.args.get("page", 1, type=int))
    per_page = min(200, max(1, request.args.get("per_page", 50, type=int)))
    requesting_user_id = request.args.get("user_id", type=int)

    # ── Try cache first ────────────────────────────────────────────────
    cache_key = f"leaderboard:exam:{exam_id}:p{page}:pp{per_page}"
    cached_data = cache.get(cache_key)

    if cached_data is not None:
        result = json.loads(cached_data)
        result["cached"] = True

        # Append requesting user's row if not on this page
        if requesting_user_id:
            result["my_entry"] = _get_user_entry(exam_id, requesting_user_id)

        return jsonify(result), 200

    # ── Cache miss → query database ────────────────────────────────────
    exam = db.session.get(Exam, exam_id)
    if exam is None:
        return jsonify({"error": f"Exam {exam_id} not found"}), 404

    # Total participants
    total_count = db.session.execute(
        select(func.count())
        .select_from(LeaderboardSnapshot)
        .where(LeaderboardSnapshot.exam_id == exam_id)
    ).scalar()

    # Paginated, sorted query
    offset = (page - 1) * per_page

    rows = db.session.execute(
        select(
            LeaderboardSnapshot,
            User.username,
            User.full_name,
        )
        .join(User, LeaderboardSnapshot.user_id == User.user_id)
        .where(LeaderboardSnapshot.exam_id == exam_id)
        .order_by(
            LeaderboardSnapshot.total_score.desc(),
            LeaderboardSnapshot.total_time_sec.asc(),
        )
        .offset(offset)
        .limit(per_page)
    ).all()

    entries = []
    for lb, username, full_name in rows:
        entries.append({
            "rank": lb.rank_position,
            "user_id": lb.user_id,
            "username": username,
            "full_name": full_name,
            "total_score": float(lb.total_score),
            "weighted_coding": float(lb.weighted_coding),
            "weighted_quiz": float(lb.weighted_quiz),
            "weighted_assessment": float(lb.weighted_assessment),
            "total_time_sec": lb.total_time_sec,
            "last_calculated_at": lb.last_calculated_at.isoformat(),
        })

    result = {
        "exam_id": exam_id,
        "exam_title": exam.title,
        "total_participants": total_count,
        "page": page,
        "per_page": per_page,
        "leaderboard": entries,
        "cached": False,
    }

    # ── Store in cache ─────────────────────────────────────────────────
    ttl = current_app.config.get("CACHE_DEFAULT_TIMEOUT", 5)
    cache.set(cache_key, json.dumps(result, default=str), timeout=ttl)

    # Append requesting user's entry
    if requesting_user_id:
        result["my_entry"] = _get_user_entry(exam_id, requesting_user_id)
    else:
        result["my_entry"] = None

    return jsonify(result), 200


@leaderboard_bp.route("/leaderboard/recalculate", methods=["POST"])
def recalculate():
    """
    POST /api/v1/leaderboard/recalculate
    Body: { "exam_id": 1 }

    Admin endpoint to force a full rank recalculation.
    """
    data = request.get_json(silent=True) or {}
    exam_id = data.get("exam_id")
    if exam_id is None:
        return jsonify({"error": "exam_id is required"}), 400

    from app.services.scoring_engine import recalculate_all_ranks
    updated = recalculate_all_ranks(exam_id)

    # Invalidate all pages for this exam
    # (simplified: we delete the base key pattern)
    cache.delete(f"leaderboard:exam:{exam_id}")

    return jsonify({
        "message": "Ranks recalculated",
        "exam_id": exam_id,
        "rows_updated": updated,
    }), 200


# ────────────────────────────────────────────────────────────────────────────
# Helpers
# ────────────────────────────────────────────────────────────────────────────

def _get_user_entry(exam_id: int, user_id: int) -> dict | None:
    """Fetch a single user's leaderboard entry (for the 'my_entry' field)."""

    row = db.session.execute(
        select(LeaderboardSnapshot, User.username, User.full_name)
        .join(User, LeaderboardSnapshot.user_id == User.user_id)
        .where(
            LeaderboardSnapshot.exam_id == exam_id,
            LeaderboardSnapshot.user_id == user_id,
        )
    ).one_or_none()

    if row is None:
        return None

    lb, username, full_name = row
    return {
        "rank": lb.rank_position,
        "user_id": lb.user_id,
        "username": username,
        "full_name": full_name,
        "total_score": float(lb.total_score),
        "weighted_coding": float(lb.weighted_coding),
        "weighted_quiz": float(lb.weighted_quiz),
        "weighted_assessment": float(lb.weighted_assessment),
        "total_time_sec": lb.total_time_sec,
        "last_calculated_at": lb.last_calculated_at.isoformat(),
    }
