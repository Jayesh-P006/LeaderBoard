"""
API Integration Tests — Leaderboard, Scores, Sessions endpoints.
"""

from __future__ import annotations

import json

import pytest

from app import create_app
from app.extensions import db
from app.models import User, Exam, ExamSession


@pytest.fixture()
def client():
    app = create_app("testing")
    with app.app_context():
        db.create_all()
        yield app.test_client()
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def seeded_client(client):
    """Pre-populate with an admin, an exam, a user, and a session."""

    from app.extensions import db as _db
    from flask import current_app

    admin = User(
        username="admin", email="admin@test.com",
        full_name="Admin User", password_hash="x", role="admin",
    )
    _db.session.add(admin)
    _db.session.flush()

    exam = Exam(
        title="Test Exam",
        weight_coding=50, weight_quiz=30, weight_assessment=20,
        max_score_coding=100, max_score_quiz=100, max_score_assessment=100,
        status="active", created_by=admin.user_id,
    )
    _db.session.add(exam)
    _db.session.flush()

    candidate = User(
        username="candidate1", email="c1@test.com",
        full_name="Candidate One", password_hash="x",
    )
    _db.session.add(candidate)
    _db.session.flush()

    session = ExamSession(
        exam_id=exam.exam_id, user_id=candidate.user_id, status="in_progress",
    )
    _db.session.add(session)
    _db.session.commit()

    return {
        "client": client,
        "exam_id": exam.exam_id,
        "user_id": candidate.user_id,
        "session_id": session.session_id,
    }


class TestScoresAPI:

    def test_submit_score_success(self, seeded_client):
        c = seeded_client
        resp = c["client"].post("/api/v1/scores", json={
            "session_id": c["session_id"],
            "module_type": "coding",
            "raw_score": 85,
            "max_score": 100,
            "time_spent_sec": 2400,
            "details": {"test_cases_passed": 17, "test_cases_total": 20},
        })
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["leaderboard_entry"]["total_score"] > 0

    def test_submit_score_validation_error(self, seeded_client):
        c = seeded_client
        resp = c["client"].post("/api/v1/scores", json={
            "session_id": c["session_id"],
            "module_type": "invalid_module",
            "raw_score": 85,
            "max_score": 100,
            "time_spent_sec": 2400,
        })
        assert resp.status_code == 422

    def test_raw_score_exceeds_max(self, seeded_client):
        c = seeded_client
        resp = c["client"].post("/api/v1/scores", json={
            "session_id": c["session_id"],
            "module_type": "quiz",
            "raw_score": 150,
            "max_score": 100,
            "time_spent_sec": 500,
        })
        assert resp.status_code == 422


class TestLeaderboardAPI:

    def test_leaderboard_empty(self, seeded_client):
        c = seeded_client
        resp = c["client"].get(f"/api/v1/leaderboard?exam_id={c['exam_id']}")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["total_participants"] == 0

    def test_leaderboard_after_score(self, seeded_client):
        c = seeded_client
        # Submit a score first
        c["client"].post("/api/v1/scores", json={
            "session_id": c["session_id"],
            "module_type": "coding",
            "raw_score": 70,
            "max_score": 100,
            "time_spent_sec": 1800,
        })

        resp = c["client"].get(f"/api/v1/leaderboard?exam_id={c['exam_id']}")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["total_participants"] == 1
        assert data["leaderboard"][0]["rank"] == 1

    def test_leaderboard_requires_exam_id(self, seeded_client):
        c = seeded_client
        resp = c["client"].get("/api/v1/leaderboard")
        assert resp.status_code == 400


class TestSessionsAPI:

    def test_create_session(self, seeded_client):
        c = seeded_client

        # Create a new user for a fresh session
        from app.extensions import db as _db
        new_user = User(
            username="candidate2", email="c2@test.com",
            full_name="Candidate Two", password_hash="x",
        )
        _db.session.add(new_user)
        _db.session.commit()

        resp = c["client"].post("/api/v1/sessions", json={
            "exam_id": c["exam_id"],
            "user_id": new_user.user_id,
        })
        assert resp.status_code == 201

    def test_duplicate_session_rejected(self, seeded_client):
        c = seeded_client
        resp = c["client"].post("/api/v1/sessions", json={
            "exam_id": c["exam_id"],
            "user_id": c["user_id"],
        })
        assert resp.status_code == 409

    def test_finish_session(self, seeded_client):
        c = seeded_client
        resp = c["client"].patch(f"/api/v1/sessions/{c['session_id']}/finish")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["total_time_sec"] >= 0
