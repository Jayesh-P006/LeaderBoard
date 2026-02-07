"""
Leaderboard System — Application Factory
"""

import os
from flask import Flask
from flask_cors import CORS

from app.config import config_map
from app.extensions import db, migrate, cache, ma


def create_app(config_name: str | None = None) -> Flask:
    """Create and configure the Flask application."""

    if config_name is None:
        config_name = os.getenv("FLASK_ENV", "development")

    app = Flask(__name__)
    app.config.from_object(config_map[config_name])

    # ── Initialise extensions ──────────────────────────────────────────
    db.init_app(app)
    migrate.init_app(app, db)
    cache.init_app(app)
    ma.init_app(app)
    CORS(app)

    # ── Register blueprints ────────────────────────────────────────────
    from app.api.leaderboard import leaderboard_bp
    from app.api.scores import scores_bp
    from app.api.sessions import sessions_bp
    from app.api.analytics import analytics_bp

    app.register_blueprint(leaderboard_bp, url_prefix="/api/v1")
    app.register_blueprint(scores_bp, url_prefix="/api/v1")
    app.register_blueprint(sessions_bp, url_prefix="/api/v1")
    app.register_blueprint(analytics_bp, url_prefix="/api/v1")

    # ── Health check ───────────────────────────────────────────────────
    @app.route("/health")
    def health():
        return {"status": "ok"}, 200

    return app
