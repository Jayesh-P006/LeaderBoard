"""
Shared Flask extensions — instantiated once, initialised in create_app().
"""

from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_caching import Cache
from flask_marshmallow import Marshmallow

db = SQLAlchemy()
migrate = Migrate()
cache = Cache()
ma = Marshmallow()
