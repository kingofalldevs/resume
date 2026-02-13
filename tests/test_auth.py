"""
Auth route tests.
"""
import pytest
from app.models import User
from app.utils import verify_password


def test_signup_page(client):
    """Signup page loads."""
    r = client.get("/auth/signup")
    assert r.status_code == 200
    assert b"Create Account" in r.data or b"Sign Up" in r.data


def test_login_page(client):
    """Login page loads."""
    r = client.get("/auth/login")
    assert r.status_code == 200
    assert b"Login" in r.data


def test_signup_creates_user(client, db_session):
    """Signup creates user and redirects."""
    r = client.post(
        "/auth/signup",
        data={
            "full_name": "New User",
            "email": "new@example.com",
            "password": "password123",
        },
        follow_redirects=True,
    )
    assert r.status_code == 200
    user = User.query.filter_by(email="new@example.com").first()
    assert user is not None
    assert user.full_name == "New User"
    assert user.password_hash != "password123"
    assert verify_password("password123", user.password_hash)


def test_login_success_redirects_dashboard(client, db_session, user):
    """Valid login redirects to dashboard."""
    r = client.post(
        "/auth/login",
        data={"email": "test@example.com", "password": "testpass123", "remember": "on"},
        follow_redirects=False,
    )
    assert r.status_code == 302
    assert "/dashboard/" in r.headers.get("Location", "")


def test_login_rejects_external_next_redirect(client, db_session, user):
    """External next URL is rejected for security."""
    r = client.post(
        "/auth/login?next=https://evil.example/steal",
        data={"email": "test@example.com", "password": "testpass123"},
        follow_redirects=False,
    )
    assert r.status_code == 302
    assert r.headers.get("Location", "").endswith("/dashboard/")


def test_login_wrong_password_does_not_redirect(client, db_session, user):
    """Wrong password does not authenticate the user."""
    r = client.post(
        "/auth/login",
        data={"email": "test@example.com", "password": "wrong-password"},
        follow_redirects=False,
    )
    assert r.status_code == 200
    assert r.headers.get("Location") is None
