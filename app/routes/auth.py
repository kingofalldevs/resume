"""
Authentication routes: signup, login, logout.
"""
from urllib.parse import urljoin, urlparse
from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_user, logout_user, login_required, current_user
from sqlalchemy.exc import SQLAlchemyError
from app import db
from app.models import User
from app.utils import hash_password, verify_password

auth_bp = Blueprint("auth", __name__)


def _is_safe_redirect_url(target: str) -> bool:
    """Allow redirects only to local URLs."""
    if not target:
        return False
    ref_url = urlparse(request.host_url)
    test_url = urlparse(urljoin(request.host_url, target))
    return test_url.scheme in ("http", "https") and ref_url.netloc == test_url.netloc


def _parse_remember_flag(value) -> bool:
    """Parse remember-me form values safely."""
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in {"1", "true", "on", "yes"}


@auth_bp.route("/signup", methods=["GET", "POST"])
def signup():
    """User registration."""
    if current_user.is_authenticated:
        return redirect(url_for("dashboard.index"))

    if request.method == "POST":
        full_name = request.form.get("full_name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        # Validation
        if not full_name or not email or not password:
            flash("Please fill in all fields.", "error")
            return render_template("auth/signup.html")

        if len(password) < 8:
            flash("Password must be at least 8 characters.", "error")
            return render_template("auth/signup.html")

        try:
            if User.query.filter_by(email=email).first():
                flash("An account with that email already exists.", "error")
                return render_template("auth/signup.html")
        except SQLAlchemyError:
            db.session.rollback()
            flash("Database error while checking email. Please try again.", "error")
            return render_template("auth/signup.html")

        user = User(
            full_name=full_name,
            email=email,
            password_hash=hash_password(password),
        )
        try:
            db.session.add(user)
            db.session.commit()
        except SQLAlchemyError:
            db.session.rollback()
            flash("Could not create account right now. Please try again.", "error")
            return render_template("auth/signup.html")
        login_user(user, remember=True)
        flash("Account created successfully!", "success")
        return redirect(url_for("dashboard.index"))

    return render_template("auth/signup.html")


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    """User login."""
    if request.method == "GET" and current_user.is_authenticated:
        return redirect(url_for("dashboard.index"))

    if request.method == "POST":
        # Force fresh auth evaluation so stale remembered sessions
        # never look like a successful password login.
        if current_user.is_authenticated:
            logout_user()

        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        try:
            user = User.query.filter_by(email=email).first()
        except SQLAlchemyError:
            db.session.rollback()
            flash("Database error during login. Please try again.", "error")
            return render_template("auth/login.html")
        if user and verify_password(password, user.password_hash):
            login_user(user, remember=_parse_remember_flag(request.form.get("remember")))
            next_url = request.args.get("next", "")
            if not _is_safe_redirect_url(next_url):
                next_url = url_for("dashboard.index")
            return redirect(next_url)

        flash("Invalid email or password.", "error")

    return render_template("auth/login.html")


@auth_bp.route("/logout")
@login_required
def logout():
    """User logout."""
    logout_user()
    flash("You have been logged out.", "info")
    return redirect(url_for("landing.index"))
