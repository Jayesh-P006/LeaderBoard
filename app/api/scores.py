"""
Score Submission API

POST /api/v1/scores  — submit or update a module score
"""

from __future__ import annotations

import logging

from flask import Blueprint, request, jsonify
from marshmallow import ValidationError

from app.schemas import SubmitScoreSchema
from app.services.scoring_engine import submit_module_score

scores_bp = Blueprint("scores", __name__)
logger = logging.getLogger(__name__)

_submit_schema = SubmitScoreSchema()


@scores_bp.route("/scores", methods=["POST"])
def submit_score():
    """
    POST /api/v1/scores

    Body (JSON):
    {
      "session_id": 42,
      "module_type": "coding",           // coding | quiz | assessment
      "raw_score": 85.5,
      "max_score": 100,
      "time_spent_sec": 2400,
      "details": {                        // optional, module-specific
        "test_cases_passed": 17,
        "test_cases_total": 20,
        "time_complexity_score": 90,
        "efficiency_score": 80
      }
    }

    Response 200:
    {
      "message": "Score submitted",
      "leaderboard_entry": { … }
    }

    Concurrency guarantee:
      - Uses SERIALIZABLE isolation + SELECT … FOR UPDATE to prevent
        race conditions when N students submit simultaneously.
      - Optimistic lock retries on deadlock (up to 3 times).
    """

    # ── Validate request ───────────────────────────────────────────────
    try:
        data = _submit_schema.load(request.get_json(silent=True) or {})
    except ValidationError as err:
        return jsonify({"errors": err.messages}), 422

    # ── Process score (atomic) ─────────────────────────────────────────
    try:
        entry = submit_module_score(
            session_id=data["session_id"],
            module_type=data["module_type"],
            raw_score=data["raw_score"],
            max_score=data["max_score"],
            time_spent_sec=data["time_spent_sec"],
            details=data.get("details"),
            changed_by=0,  # In production, extract from JWT / auth context
        )

        return jsonify({
            "message": "Score submitted",
            "leaderboard_entry": entry,
        }), 200

    except ValueError as err:
        return jsonify({"error": str(err)}), 400

    except RuntimeError as err:
        logger.error("Score submission failed: %s", err)
        return jsonify({"error": "Concurrent update conflict. Please retry."}), 409

    except Exception as err:
        logger.exception("Unexpected error in score submission")
        return jsonify({"error": "Internal server error"}), 500
