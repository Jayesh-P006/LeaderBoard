"""
SQLAlchemy ORM Models — mirrors database/schema.sql
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import (
    String, Text, Enum, Integer, BigInteger, Boolean,
    DateTime, Numeric, JSON, ForeignKey, UniqueConstraint,
    Index, CheckConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions import db


# ────────────────────────────────────────────────────────────────────────────
# Helpers
# ────────────────────────────────────────────────────────────────────────────
def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ────────────────────────────────────────────────────────────────────────────
# 1. User
# ────────────────────────────────────────────────────────────────────────────
class User(db.Model):
    __tablename__ = "users"

    user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    full_name: Mapped[str] = mapped_column(String(128), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(
        Enum("candidate", "admin", "moderator", name="user_role"),
        default="candidate", nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, onupdate=_utcnow, nullable=False)

    # Relationships
    sessions: Mapped[list["ExamSession"]] = relationship(back_populates="user", lazy="dynamic")

    def __repr__(self) -> str:
        return f"<User {self.username}>"


# ────────────────────────────────────────────────────────────────────────────
# 2. Exam
# ────────────────────────────────────────────────────────────────────────────
class Exam(db.Model):
    __tablename__ = "exams"

    exam_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    duration_minutes: Mapped[int] = mapped_column(Integer, default=120, nullable=False)

    # Configurable weights (must sum to 100)
    weight_coding: Mapped[float] = mapped_column(Numeric(5, 2), default=50.00, nullable=False)
    weight_quiz: Mapped[float] = mapped_column(Numeric(5, 2), default=30.00, nullable=False)
    weight_assessment: Mapped[float] = mapped_column(Numeric(5, 2), default=20.00, nullable=False)

    max_score_coding: Mapped[float] = mapped_column(Numeric(10, 2), default=100.00, nullable=False)
    max_score_quiz: Mapped[float] = mapped_column(Numeric(10, 2), default=100.00, nullable=False)
    max_score_assessment: Mapped[float] = mapped_column(Numeric(10, 2), default=100.00, nullable=False)

    status: Mapped[str] = mapped_column(
        Enum("draft", "scheduled", "active", "completed", "archived", name="exam_status"),
        default="draft", nullable=False,
    )
    starts_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    ends_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    created_by: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.user_id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, onupdate=_utcnow, nullable=False)

    # Relationships
    sessions: Mapped[list["ExamSession"]] = relationship(back_populates="exam", lazy="dynamic")

    __table_args__ = (
        CheckConstraint(
            "weight_coding + weight_quiz + weight_assessment = 100.00",
            name="chk_weights",
        ),
    )

    def __repr__(self) -> str:
        return f"<Exam {self.title}>"


# ────────────────────────────────────────────────────────────────────────────
# 3. Exam Session
# ────────────────────────────────────────────────────────────────────────────
class ExamSession(db.Model):
    __tablename__ = "exam_sessions"

    session_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    exam_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("exams.exam_id"), nullable=False)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.user_id"), nullable=False)

    started_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime)

    total_time_sec: Mapped[Optional[int]] = mapped_column(Integer, default=0)

    status: Mapped[str] = mapped_column(
        Enum("in_progress", "submitted", "timed_out", "disqualified", name="session_status"),
        default="in_progress", nullable=False,
    )

    # Optimistic locking version
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, onupdate=_utcnow, nullable=False)

    # Relationships
    exam: Mapped["Exam"] = relationship(back_populates="sessions")
    user: Mapped["User"] = relationship(back_populates="sessions")
    module_scores: Mapped[list["ModuleScore"]] = relationship(
        back_populates="session", lazy="joined", cascade="all, delete-orphan",
    )

    __table_args__ = (
        UniqueConstraint("exam_id", "user_id", name="uq_exam_user"),
        Index("idx_session_status", "status"),
    )

    def __repr__(self) -> str:
        return f"<ExamSession exam={self.exam_id} user={self.user_id}>"


# ────────────────────────────────────────────────────────────────────────────
# 4. Module Score
# ────────────────────────────────────────────────────────────────────────────
class ModuleScore(db.Model):
    __tablename__ = "module_scores"

    score_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("exam_sessions.session_id"), nullable=False)
    module_type: Mapped[str] = mapped_column(
        Enum("coding", "quiz", "assessment", name="module_type_enum"),
        nullable=False,
    )

    raw_score: Mapped[float] = mapped_column(Numeric(10, 2), default=0.00, nullable=False)
    max_score: Mapped[float] = mapped_column(Numeric(10, 2), default=100.00, nullable=False)
    time_spent_sec: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    details: Mapped[Optional[dict]] = mapped_column(JSON)

    # Optimistic locking version
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, onupdate=_utcnow, nullable=False)

    # Relationships
    session: Mapped["ExamSession"] = relationship(back_populates="module_scores")

    __table_args__ = (
        UniqueConstraint("session_id", "module_type", name="uq_session_module"),
    )

    def __repr__(self) -> str:
        return f"<ModuleScore session={self.session_id} type={self.module_type}>"


# ────────────────────────────────────────────────────────────────────────────
# 5. Leaderboard Snapshot
# ────────────────────────────────────────────────────────────────────────────
class LeaderboardSnapshot(db.Model):
    __tablename__ = "leaderboard_snapshot"

    snapshot_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    exam_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("exams.exam_id"), nullable=False)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.user_id"), nullable=False)
    session_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("exam_sessions.session_id"), nullable=False)

    weighted_coding: Mapped[float] = mapped_column(Numeric(10, 4), default=0.0, nullable=False)
    weighted_quiz: Mapped[float] = mapped_column(Numeric(10, 4), default=0.0, nullable=False)
    weighted_assessment: Mapped[float] = mapped_column(Numeric(10, 4), default=0.0, nullable=False)

    total_score: Mapped[float] = mapped_column(Numeric(10, 4), default=0.0, nullable=False)
    total_time_sec: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    rank_position: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    last_calculated_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False)

    # Relationships
    user: Mapped["User"] = relationship()
    session: Mapped["ExamSession"] = relationship()

    __table_args__ = (
        UniqueConstraint("exam_id", "user_id", name="uq_lb_exam_user"),
        Index("idx_lb_rank", "exam_id", "total_score", "total_time_sec"),
    )

    def __repr__(self) -> str:
        return f"<Leaderboard exam={self.exam_id} rank={self.rank_position} user={self.user_id}>"


# ────────────────────────────────────────────────────────────────────────────
# 6. Score Audit Log
# ────────────────────────────────────────────────────────────────────────────
class ScoreAuditLog(db.Model):
    __tablename__ = "score_audit_log"

    log_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("exam_sessions.session_id"), nullable=False)
    module_type: Mapped[str] = mapped_column(
        Enum("coding", "quiz", "assessment", name="audit_module_type"),
        nullable=False,
    )
    old_score: Mapped[Optional[float]] = mapped_column(Numeric(10, 2))
    new_score: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    changed_by: Mapped[int] = mapped_column(BigInteger, nullable=False)
    change_reason: Mapped[Optional[str]] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False)

    def __repr__(self) -> str:
        return f"<AuditLog session={self.session_id} module={self.module_type}>"
