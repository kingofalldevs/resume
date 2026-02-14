"""
Pytest fixtures for ResumeGhana tests.
"""
import os
import pytest
from app import app as flask_app, db
from app.models import User


@pytest.fixture(scope="session")
def app():
    """Provide configured application for testing."""
    database_url = os.environ.get("TEST_DATABASE_URL") or os.environ.get("DATABASE_URL")
    if not database_url:
        raise ValueError("TEST_DATABASE_URL or DATABASE_URL must be set for tests")
    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql://", 1)

    flask_app.config.update(
        TESTING=True,
        WTF_CSRF_ENABLED=False,
        SQLALCHEMY_DATABASE_URI=database_url,
    )

    with flask_app.app_context():
        db.session.remove()
        db.drop_all()
        db.create_all()

    yield flask_app

    with flask_app.app_context():
        db.session.remove()
        db.drop_all()


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
        db.session.remove()
        db.create_all()
        yield db
        db.session.remove()
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
