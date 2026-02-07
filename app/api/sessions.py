"""
Session Management API

POST   /api/v1/sessions            — start a new exam session
GET    /api/v1/sessions/<id>       — get session details
PATCH  /api/v1/sessions/<id>/finish — mark session as submitted
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from flask import Blueprint, request, jsonify
from marshmallow import ValidationError
from sqlalchemy import select

from app.extensions import db
from app.models import ExamSession, Exam, ModuleScore
from app.schemas import CreateSessionSchema, SessionResponseSchema

sessions_bp = Blueprint("sessions", __name__)
logger = logging.getLogger(__name__)

_create_schema = CreateSessionSchema()
_session_response = SessionResponseSchema()


@sessions_bp.route("/sessions", methods=["POST"])
def create_session():
    """
    POST /api/v1/sessions
    Body: { "exam_id": 1, "user_id": 42 }

    Creates a new exam session. Enforces one session per user per exam.
    """

    try:
        data = _create_schema.load(request.get_json(silent=True) or {})
    except ValidationError as err:
        return jsonify({"errors": err.messages}), 422

    # Check exam exists and is active
    exam = db.session.get(Exam, data["exam_id"])
    if exam is None:
        return jsonify({"error": "Exam not found"}), 404
    if exam.status != "active":
        return jsonify({"error": f"Exam is not active (status: {exam.status})"}), 400

    # Check for existing session
    existing = db.session.execute(
        select(ExamSession).where(
            ExamSession.exam_id == data["exam_id"],
            ExamSession.user_id == data["user_id"],
        )
    ).scalar_one_or_none()

    if existing:
        return jsonify({
            "error": "Session already exists",
            "session_id": existing.session_id,
        }), 409

    session = ExamSession(
        exam_id=data["exam_id"],
        user_id=data["user_id"],
        status="in_progress",
    )
    db.session.add(session)
    db.session.commit()

    return jsonify({
        "message": "Session created",
        "session_id": session.session_id,
        "started_at": session.started_at.isoformat(),
    }), 201


@sessions_bp.route("/sessions/<int:session_id>", methods=["GET"])
def get_session(session_id: int):
    """GET /api/v1/sessions/<id> — returns session with module scores."""

    session = db.session.get(ExamSession, session_id)
    if session is None:
        return jsonify({"error": "Session not found"}), 404

    return jsonify(_session_response.dump(session)), 200


@sessions_bp.route("/sessions/<int:session_id>/finish", methods=["PATCH"])
def finish_session(session_id: int):
    """
    PATCH /api/v1/sessions/<id>/finish

    Marks the session as submitted and records the finish time.
    Triggers a final leaderboard recalculation for this user.
    """

    session: ExamSession | None = (
        db.session.execute(
            select(ExamSession)
            .where(ExamSession.session_id == session_id)
            .with_for_update()
        )
        .scalar_one_or_none()
    )

    if session is None:
        return jsonify({"error": "Session not found"}), 404

    if session.status != "in_progress":
        return jsonify({
            "error": f"Session cannot be finished (current status: {session.status})"
        }), 400

    now = datetime.now(timezone.utc)
    session.finished_at = now
    session.total_time_sec = int((now - session.started_at).total_seconds())
    session.status = "submitted"
    session.version += 1

    db.session.commit()

    # Trigger final score + rank recalculation
    from app.services.scoring_engine import recalculate_all_ranks, _invalidate_leaderboard_cache
    recalculate_all_ranks(session.exam_id)
    _invalidate_leaderboard_cache(session.exam_id)

    return jsonify({
        "message": "Session submitted",
        "session_id": session.session_id,
        "finished_at": session.finished_at.isoformat(),
        "total_time_sec": session.total_time_sec,
    }), 200
