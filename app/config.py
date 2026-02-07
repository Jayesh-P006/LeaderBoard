"""
Leaderboard System — Application Configuration
"""

import os
from dotenv import load_dotenv

load_dotenv()


class BaseConfig:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key")

    # SQLAlchemy
    SQLALCHEMY_DATABASE_URI = os.getenv(
        "DATABASE_URL",
        "mysql+pymysql://root:jpassword@127.0.0.1:3306/leaderboard_db",
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_size": 20,
        "max_overflow": 40,
        "pool_pre_ping": True,       # auto-reconnect on stale connections
        "pool_recycle": 1800,        # recycle connections every 30 min
        "isolation_level": "SERIALIZABLE",  # strongest isolation for score writes
    }

    # Redis / Caching
    REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    CACHE_TYPE = "RedisCache"
    CACHE_REDIS_URL = REDIS_URL
    CACHE_DEFAULT_TIMEOUT = int(os.getenv("LEADERBOARD_CACHE_TTL", 5))

    # Scoring defaults
    DEFAULT_WEIGHT_CODING = float(os.getenv("DEFAULT_WEIGHT_CODING", 50))
    DEFAULT_WEIGHT_QUIZ = float(os.getenv("DEFAULT_WEIGHT_QUIZ", 30))
    DEFAULT_WEIGHT_ASSESSMENT = float(os.getenv("DEFAULT_WEIGHT_ASSESSMENT", 20))


class DevelopmentConfig(BaseConfig):
    DEBUG = True
    # Use simple in-memory cache for dev (no Redis required)
    CACHE_TYPE = "SimpleCache"
    SQLALCHEMY_ENGINE_OPTIONS = {
        **BaseConfig.SQLALCHEMY_ENGINE_OPTIONS,
        "echo": False,  # set True to log all SQL
    }


class ProductionConfig(BaseConfig):
    DEBUG = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        **BaseConfig.SQLALCHEMY_ENGINE_OPTIONS,
        "pool_size": 50,
        "max_overflow": 100,
    }


class TestingConfig(BaseConfig):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    SQLALCHEMY_ENGINE_OPTIONS = {}


config_map = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "testing": TestingConfig,
}
