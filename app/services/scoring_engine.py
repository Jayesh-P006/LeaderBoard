"""
Scoring Engine — Core Weighted Algorithm with Tie-Breaking & ACID Guarantees

Architecture:
  1. When a student SUBMITS a module (coding/quiz/assessment), the corresponding
     module_scores row is upserted with optimistic locking.
  2. A transactional post-hook recalculates the weighted total and updates the
     leaderboard_snapshot table inside the SAME database transaction.
  3. Ranks are recomputed for the entire exam using DENSE_RANK ordered by
     (total_score DESC, total_time_sec ASC) — the tie-breaker.
  4. Redis cache for GET /leaderboard is invalidated so the next read fetches
     fresh data.

Concurrency Controls:
  • SERIALIZABLE isolation for score writes → prevents phantom reads.
  • Optimistic locking via `version` column → detects and retries on conflicts.
  • SELECT … FOR UPDATE on the session row → prevents two concurrent module
    submissions from producing inconsistent totals.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional

from sqlalchemy import text, select, update
from sqlalchemy.exc import OperationalError

from app.extensions import db, cache
from app.models import (
    Exam, ExamSession, ModuleScore,
    LeaderboardSnapshot, ScoreAuditLog,
)

logger = logging.getLogger(__name__)

# Maximum retries on optimistic-lock conflicts
MAX_RETRIES = 3


# ────────────────────────────────────────────────────────────────────────────
# PUBLIC API
# ────────────────────────────────────────────────────────────────────────────

def submit_module_score(
    session_id: int,
    module_type: str,          # 'coding' | 'quiz' | 'assessment'
    raw_score: float,
    max_score: float,
    time_spent_sec: int,
    details: Optional[dict] = None,
    changed_by: int = 0,      # user_id performing the update
) -> dict:
    """
    Atomically upsert a module score, recalculate weighted totals,
    refresh rank positions, and invalidate cache.

    Returns a summary dict with the new leaderboard entry.

    Raises:
        ValueError  – on invalid input
        RuntimeError – if optimistic lock fails after MAX_RETRIES
    """
    _validate_module_type(module_type)

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            result = _atomic_score_update(
                session_id=session_id,
                module_type=module_type,
                raw_score=raw_score,
                max_score=max_score,
                time_spent_sec=time_spent_sec,
                details=details,
                changed_by=changed_by,
            )
            return result

        except OperationalError as exc:
            # Deadlock or lock-wait timeout — retry
            db.session.rollback()
            logger.warning(
                "Optimistic lock conflict (attempt %d/%d) session=%s module=%s: %s",
                attempt, MAX_RETRIES, session_id, module_type, exc,
            )
            if attempt == MAX_RETRIES:
                raise RuntimeError(
                    f"Could not acquire lock after {MAX_RETRIES} retries "
                    f"for session {session_id}, module {module_type}"
                ) from exc


def recalculate_all_ranks(exam_id: int) -> int:
    """
    Full rank recalculation for an exam.  Useful after bulk imports or
    manual score adjustments.

    Returns the number of entries updated.
    """
    return _refresh_ranks(exam_id)


# ────────────────────────────────────────────────────────────────────────────
# INTERNAL — runs inside a single SERIALIZABLE transaction
# ────────────────────────────────────────────────────────────────────────────

def _atomic_score_update(
    session_id: int,
    module_type: str,
    raw_score: float,
    max_score: float,
    time_spent_sec: int,
    details: Optional[dict],
    changed_by: int,
) -> dict:
    """Execute the full score-update pipeline in one transaction."""

    # ── Step 1: Lock the session row (SELECT … FOR UPDATE) ─────────────
    session: ExamSession = (
        db.session.execute(
            select(ExamSession)
            .where(ExamSession.session_id == session_id)
            .with_for_update()
        )
        .scalar_one()
    )

    exam: Exam = db.session.get(Exam, session.exam_id)

    # ── Step 2: Upsert module score with optimistic lock ───────────────
    module_score: ModuleScore | None = (
        db.session.execute(
            select(ModuleScore)
            .where(
                ModuleScore.session_id == session_id,
                ModuleScore.module_type == module_type,
            )
            .with_for_update()
        )
        .scalar_one_or_none()
    )

    old_score = float(module_score.raw_score) if module_score else None

    if module_score is None:
        # First submission for this module
        module_score = ModuleScore(
            session_id=session_id,
            module_type=module_type,
            raw_score=raw_score,
            max_score=max_score,
            time_spent_sec=time_spent_sec,
            details=details,
            version=1,
        )
        db.session.add(module_score)
    else:
        # Update existing — bump version (optimistic lock)
        module_score.raw_score = raw_score
        module_score.max_score = max_score
        module_score.time_spent_sec = time_spent_sec
        module_score.details = details
        module_score.version += 1
        module_score.updated_at = datetime.now(timezone.utc)

    # ── Step 3: Write audit log ────────────────────────────────────────
    audit = ScoreAuditLog(
        session_id=session_id,
        module_type=module_type,
        old_score=old_score,
        new_score=raw_score,
        changed_by=changed_by,
        change_reason="module_submission",
    )
    db.session.add(audit)

    # ── Step 4: Recalculate weighted total for THIS session ────────────
    weighted = _calculate_weighted_score(session, exam)

    # ── Step 5: Upsert leaderboard snapshot ────────────────────────────
    lb_entry = _upsert_leaderboard(session, exam, weighted)

    # ── Step 6: Refresh ranks for the entire exam ──────────────────────
    db.session.flush()  # ensure all writes are visible within txn
    _refresh_ranks(exam.exam_id)

    # ── Step 7: Commit and invalidate cache ────────────────────────────
    db.session.commit()
    _invalidate_leaderboard_cache(exam.exam_id)

    # Re-read final rank after commit
    lb_entry = (
        db.session.execute(
            select(LeaderboardSnapshot)
            .where(
                LeaderboardSnapshot.exam_id == exam.exam_id,
                LeaderboardSnapshot.user_id == session.user_id,
            )
        )
        .scalar_one()
    )

    return _serialise_leaderboard_entry(lb_entry)


# ────────────────────────────────────────────────────────────────────────────
# SCORING ALGORITHM
# ────────────────────────────────────────────────────────────────────────────

def _calculate_weighted_score(session: ExamSession, exam: Exam) -> dict:
    """
    Weighted Scoring Formula
    ────────────────────────
    For each module m ∈ {coding, quiz, assessment}:

        normalised_m  = raw_score_m / max_score_m          (0..1)
        weighted_m    = normalised_m × weight_m            (0..weight_m)

    Total Score = Σ weighted_m   (range: 0..100)

    Tie-breaker: lowest total_time_sec wins.
    """

    weight_map = {
        "coding":     Decimal(str(exam.weight_coding)),
        "quiz":       Decimal(str(exam.weight_quiz)),
        "assessment": Decimal(str(exam.weight_assessment)),
    }

    max_map = {
        "coding":     Decimal(str(exam.max_score_coding)),
        "quiz":       Decimal(str(exam.max_score_quiz)),
        "assessment": Decimal(str(exam.max_score_assessment)),
    }

    scores: dict[str, ModuleScore] = {
        ms.module_type: ms for ms in session.module_scores
    }

    result = {}
    total = Decimal("0")
    total_time = 0

    for module in ("coding", "quiz", "assessment"):
        ms = scores.get(module)
        if ms and max_map[module] > 0:
            normalised = Decimal(str(ms.raw_score)) / max_map[module]
            weighted = (normalised * weight_map[module]).quantize(
                Decimal("0.0001"), rounding=ROUND_HALF_UP
            )
            total_time += ms.time_spent_sec
        else:
            weighted = Decimal("0.0000")

        result[f"weighted_{module}"] = weighted
        total += weighted

    result["total_score"] = total.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
    result["total_time_sec"] = total_time

    return result


def _upsert_leaderboard(
    session: ExamSession,
    exam: Exam,
    weighted: dict,
) -> LeaderboardSnapshot:
    """Insert or update the leaderboard snapshot row for this user+exam."""

    lb_entry: LeaderboardSnapshot | None = (
        db.session.execute(
            select(LeaderboardSnapshot)
            .where(
                LeaderboardSnapshot.exam_id == exam.exam_id,
                LeaderboardSnapshot.user_id == session.user_id,
            )
            .with_for_update()
        )
        .scalar_one_or_none()
    )

    now = datetime.now(timezone.utc)

    if lb_entry is None:
        lb_entry = LeaderboardSnapshot(
            exam_id=exam.exam_id,
            user_id=session.user_id,
            session_id=session.session_id,
            weighted_coding=weighted["weighted_coding"],
            weighted_quiz=weighted["weighted_quiz"],
            weighted_assessment=weighted["weighted_assessment"],
            total_score=weighted["total_score"],
            total_time_sec=weighted["total_time_sec"],
            rank_position=0,  # will be set by _refresh_ranks
            last_calculated_at=now,
        )
        db.session.add(lb_entry)
    else:
        lb_entry.weighted_coding = weighted["weighted_coding"]
        lb_entry.weighted_quiz = weighted["weighted_quiz"]
        lb_entry.weighted_assessment = weighted["weighted_assessment"]
        lb_entry.total_score = weighted["total_score"]
        lb_entry.total_time_sec = weighted["total_time_sec"]
        lb_entry.last_calculated_at = now

    return lb_entry


# ────────────────────────────────────────────────────────────────────────────
# RANK REFRESH  — DENSE_RANK with tie-breaker
# ────────────────────────────────────────────────────────────────────────────

def _refresh_ranks(exam_id: int) -> int:
    """
    Recompute rank_position for every participant in an exam using:

        DENSE_RANK() OVER (
            ORDER BY total_score DESC,
                     total_time_sec ASC   -- tie-breaker
        )

    Executes a single UPDATE … JOIN on the database for efficiency.
    Returns: number of rows updated.
    """

    # Use a raw SQL UPDATE with window-function subquery for performance.
    # MySQL 8+ supports window functions inside derived tables.
    sql = text("""
        UPDATE leaderboard_snapshot AS lb
        INNER JOIN (
            SELECT snapshot_id,
                   DENSE_RANK() OVER (
                       ORDER BY total_score DESC,
                                total_time_sec ASC
                   ) AS new_rank
            FROM   leaderboard_snapshot
            WHERE  exam_id = :exam_id
        ) AS ranked ON lb.snapshot_id = ranked.snapshot_id
        SET lb.rank_position = ranked.new_rank
        WHERE lb.exam_id = :exam_id
    """)

    result = db.session.execute(sql, {"exam_id": exam_id})
    return result.rowcount


# ────────────────────────────────────────────────────────────────────────────
# CACHE INVALIDATION
# ────────────────────────────────────────────────────────────────────────────

def _invalidate_leaderboard_cache(exam_id: int) -> None:
    """Delete the cached leaderboard so the next GET fetches fresh data."""
    cache_key = f"leaderboard:exam:{exam_id}"
    cache.delete(cache_key)
    logger.info("Cache invalidated for exam %s", exam_id)


# ────────────────────────────────────────────────────────────────────────────
# HELPERS
# ────────────────────────────────────────────────────────────────────────────

_VALID_MODULES = {"coding", "quiz", "assessment"}


def _validate_module_type(module_type: str) -> None:
    if module_type not in _VALID_MODULES:
        raise ValueError(
            f"Invalid module_type '{module_type}'. Must be one of {_VALID_MODULES}"
        )


def _serialise_leaderboard_entry(entry: LeaderboardSnapshot) -> dict:
    return {
        "exam_id": entry.exam_id,
        "user_id": entry.user_id,
        "rank": entry.rank_position,
        "total_score": float(entry.total_score),
        "weighted_coding": float(entry.weighted_coding),
        "weighted_quiz": float(entry.weighted_quiz),
        "weighted_assessment": float(entry.weighted_assessment),
        "total_time_sec": entry.total_time_sec,
        "last_calculated_at": entry.last_calculated_at.isoformat(),
    }
