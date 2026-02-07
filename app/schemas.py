"""
Marshmallow schemas for request validation and response serialisation.
"""

from marshmallow import Schema, fields, validate, validates_schema, ValidationError


# ────────────────────────────────────────────────────────────────────────────
# Request Schemas
# ────────────────────────────────────────────────────────────────────────────

class SubmitScoreSchema(Schema):
    """POST /api/v1/scores — submit a module score."""

    session_id = fields.Integer(required=True, strict=True)
    module_type = fields.String(
        required=True,
        validate=validate.OneOf(["coding", "quiz", "assessment"]),
    )
    raw_score = fields.Float(required=True, validate=validate.Range(min=0))
    max_score = fields.Float(required=True, validate=validate.Range(min=0.01))
    time_spent_sec = fields.Integer(required=True, validate=validate.Range(min=0))
    details = fields.Dict(load_default=None)

    @validates_schema
    def validate_score_range(self, data, **kwargs):
        if data["raw_score"] > data["max_score"]:
            raise ValidationError(
                "raw_score cannot exceed max_score",
                field_name="raw_score",
            )


class CreateSessionSchema(Schema):
    """POST /api/v1/sessions — start an exam session."""

    exam_id = fields.Integer(required=True, strict=True)
    user_id = fields.Integer(required=True, strict=True)


class FinishSessionSchema(Schema):
    """PATCH /api/v1/sessions/<id>/finish"""
    pass  # no body required


# ────────────────────────────────────────────────────────────────────────────
# Response Schemas
# ────────────────────────────────────────────────────────────────────────────

class LeaderboardEntrySchema(Schema):
    rank = fields.Integer()
    user_id = fields.Integer()
    username = fields.String()
    full_name = fields.String()
    total_score = fields.Float()
    weighted_coding = fields.Float()
    weighted_quiz = fields.Float()
    weighted_assessment = fields.Float()
    total_time_sec = fields.Integer()
    last_calculated_at = fields.DateTime()


class LeaderboardResponseSchema(Schema):
    exam_id = fields.Integer()
    exam_title = fields.String()
    total_participants = fields.Integer()
    leaderboard = fields.List(fields.Nested(LeaderboardEntrySchema))
    cached = fields.Boolean()


class ModuleScoreResponseSchema(Schema):
    score_id = fields.Integer()
    module_type = fields.String()
    raw_score = fields.Float()
    max_score = fields.Float()
    time_spent_sec = fields.Integer()
    details = fields.Dict()


class SessionResponseSchema(Schema):
    session_id = fields.Integer()
    exam_id = fields.Integer()
    user_id = fields.Integer()
    status = fields.String()
    started_at = fields.DateTime()
    finished_at = fields.DateTime(allow_none=True)
    total_time_sec = fields.Integer()
    module_scores = fields.List(fields.Nested(ModuleScoreResponseSchema))
