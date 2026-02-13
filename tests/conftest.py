"""
Pytest fixtures for ResumeGhana tests.
"""
import pytest
from app import app as flask_app, db
from app.models import User


@pytest.fixture
def app():
    """Provide configured application for testing."""
    flask_app.config["TESTING"] = True
    flask_app.config["WTF_CSRF_ENABLED"] = False
    return flask_app


@pytest.fixture
def client(app):
    """Create test client."""
    return app.test_client()


@pytest.fixture
def runner(app):
    """Create CLI runner."""
    return app.test_cli_runner()


@pytest.fixture
def db_session(app):
    """Create database and yield session."""
    with app.app_context():
        db.create_all()
        yield db
        db.drop_all()


@pytest.fixture
def user(db_session):
    """Create test user."""
    from app.utils import hash_password
    u = User(
        full_name="Test User",
        email="test@example.com",
        password_hash=hash_password("testpass123"),
    )
    db.session.add(u)
    db.session.commit()
    return u
