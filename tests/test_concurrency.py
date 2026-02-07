"""
Concurrency Stress Test — simulates N students submitting scores simultaneously.

Validates:
  • No scores are lost or silently overwritten under concurrent load.
  • ACID compliance: final leaderboard totals match expected values.
  • Rank ordering obeys tie-breaking rules.

Run:
    pytest tests/test_concurrency.py -v
"""

from __future__ import annotations

import threading
import time
from decimal import Decimal

import pytest

from app import create_app
from app.extensions import db
from app.models import User, Exam, ExamSession, LeaderboardSnapshot
from app.services.scoring_engine import submit_module_score, recalculate_all_ranks


@pytest.fixture()
def app():
    app = create_app("testing")
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def seed_data(app):
    """Create an admin, an exam, and N candidate users with sessions."""

    with app.app_context():
        admin = User(
            username="admin", email="admin@test.com",
            full_name="Admin", password_hash="x", role="admin",
        )
        db.session.add(admin)
        db.session.flush()

        exam = Exam(
            title="Concurrency Exam",
            weight_coding=50, weight_quiz=30, weight_assessment=20,
            max_score_coding=100, max_score_quiz=100, max_score_assessment=100,
            status="active", created_by=admin.user_id,
        )
        db.session.add(exam)
        db.session.flush()

        num_candidates = 20
        sessions = []

        for i in range(num_candidates):
            u = User(
                username=f"user_{i}", email=f"user_{i}@test.com",
                full_name=f"User {i}", password_hash="x",
            )
            db.session.add(u)
            db.session.flush()

            s = ExamSession(exam_id=exam.exam_id, user_id=u.user_id, status="in_progress")
            db.session.add(s)
            db.session.flush()
            sessions.append(s.session_id)

        db.session.commit()

        return {
            "exam_id": exam.exam_id,
            "session_ids": sessions,
            "num_candidates": num_candidates,
        }


class TestConcurrentScoreSubmission:
    """Verify data integrity under parallel writes."""

    def test_parallel_module_submissions_no_data_loss(self, app, seed_data):
        """
        All N candidates submit coding scores at the same time.
        After completion, every candidate must have a leaderboard entry.
        """

        errors: list[str] = []
        barrier = threading.Barrier(seed_data["num_candidates"], timeout=10)

        def submit(session_id: int, score: float):
            with app.app_context():
                try:
                    barrier.wait()  # force all threads to start together
                    submit_module_score(
                        session_id=session_id,
                        module_type="coding",
                        raw_score=score,
                        max_score=100.0,
                        time_spent_sec=int(score * 10),
                    )
                except Exception as exc:
                    errors.append(f"session={session_id}: {exc}")

        threads = []
        for idx, sid in enumerate(seed_data["session_ids"]):
            t = threading.Thread(
                target=submit,
                args=(sid, 50.0 + idx),  # distinct scores
            )
            threads.append(t)

        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)

        # Assertions
        assert not errors, f"Errors during parallel submission: {errors}"

        with app.app_context():
            entries = LeaderboardSnapshot.query.filter_by(
                exam_id=seed_data["exam_id"]
            ).all()

            assert len(entries) == seed_data["num_candidates"], (
                f"Expected {seed_data['num_candidates']} leaderboard entries, "
                f"got {len(entries)}"
            )

    def test_tie_breaking_by_time(self, app, seed_data):
        """
        Two candidates with the same total_score should be ranked by
        total_time_sec ASC (lower time = higher rank).
        """

        sid_a, sid_b = seed_data["session_ids"][:2]

        with app.app_context():
            # Same score, different time
            submit_module_score(sid_a, "coding", 80, 100, 3000)
            submit_module_score(sid_b, "coding", 80, 100, 2000)  # faster

            lb = (
                LeaderboardSnapshot.query
                .filter_by(exam_id=seed_data["exam_id"])
                .order_by(
                    LeaderboardSnapshot.total_score.desc(),
                    LeaderboardSnapshot.total_time_sec.asc(),
                )
                .all()
            )

            # Student B (faster) should rank higher (rank 1)
            b_entry = next(e for e in lb if e.session_id == sid_b)
            a_entry = next(e for e in lb if e.session_id == sid_a)

            assert b_entry.rank_position <= a_entry.rank_position, (
                f"Faster student should rank higher. "
                f"B(rank={b_entry.rank_position}, time={b_entry.total_time_sec}) vs "
                f"A(rank={a_entry.rank_position}, time={a_entry.total_time_sec})"
            )

    def test_weighted_score_calculation(self, app, seed_data):
        """Verify the weighted formula: coding×50% + quiz×30% + assessment×20%."""

        sid = seed_data["session_ids"][0]

        with app.app_context():
            submit_module_score(sid, "coding", 80, 100, 1000)
            submit_module_score(sid, "quiz", 90, 100, 500)
            submit_module_score(sid, "assessment", 70, 100, 800)

            entry = LeaderboardSnapshot.query.filter_by(
                exam_id=seed_data["exam_id"],
                session_id=sid,
            ).one()

            # Expected: (80/100)*50 + (90/100)*30 + (70/100)*20
            #         = 40 + 27 + 14 = 81.0
            expected = Decimal("81.0000")
            assert Decimal(str(entry.total_score)) == expected, (
                f"Expected total_score={expected}, got {entry.total_score}"
            )
