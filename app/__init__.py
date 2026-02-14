"""
ResumeGhana - AI-powered resume builder.
Single-app Flask initialization (no factory pattern).
"""
import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect
from sqlalchemy.exc import SQLAlchemyError

try:
    from dotenv import load_dotenv
except Exception:  # pragma: no cover
    load_dotenv = None


db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()
csrf = CSRFProtect()


def _fallback_load_env(env_path: str):
    """Load .env file without python-dotenv dependency."""
    if not os.path.exists(env_path):
        return
    try:
        with open(env_path, "r", encoding="utf-8") as f:
            for raw in f:
                line = raw.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if key and key not in os.environ:
                    os.environ[key] = value
    except Exception:
        # Keep startup resilient even if .env is malformed.
        pass


# Load .env for local/dev runs (Render/prod uses real env vars).
_base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if load_dotenv is not None:
    load_dotenv(os.path.join(_base, ".env"), override=False)
else:
    _fallback_load_env(os.path.join(_base, ".env"))

app = Flask(__name__, template_folder=os.path.join(_base, "templates"), static_folder=os.path.join(_base, "static"))

# Load config (config.py at project root)
import sys
if _base not in sys.path:
    sys.path.insert(0, _base)
from config import Config
app.config.from_object(Config)

# Ensure upload folder exists
os.makedirs(app.config.get("UPLOAD_FOLDER", "uploads"), exist_ok=True)

# Initialize extensions
db.init_app(app)
migrate.init_app(app, db)
login_manager.init_app(app)
csrf.init_app(app)
login_manager.login_view = "auth.login"
login_manager.login_message = "Please log in to access this page."

from app.models import User


@login_manager.user_loader
def load_user(user_id):
    try:
        return User.query.get(int(user_id))
    except (ValueError, TypeError, SQLAlchemyError):
        # Avoid full-page 500s when DB is temporarily unavailable
        # or an invalid user id is present in session.
        db.session.rollback()
        return None


# Register blueprints
from app.routes.auth import auth_bp
from app.routes.dashboard import dashboard_bp
from app.routes.resume import resume_bp
from app.routes.ai import ai_bp
from app.routes.landing import landing_bp

app.register_blueprint(landing_bp)  # Includes "/" index
app.register_blueprint(auth_bp, url_prefix="/auth")
app.register_blueprint(dashboard_bp, url_prefix="/dashboard")
app.register_blueprint(resume_bp)
app.register_blueprint(ai_bp, url_prefix="/api")
csrf.exempt(ai_bp)  # API uses JSON, auth via session

def _safe_create_all():
    """Best-effort table creation for new environments."""
    with app.app_context():
        try:
            db.create_all()
        except SQLAlchemyError:
            db.session.rollback()


_safe_create_all()
