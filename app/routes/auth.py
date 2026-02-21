"""
Authentication routes: signup, login, logout.
"""
import hashlib
import hmac
import secrets
import time
from urllib.parse import urljoin, urlparse
from flask import Blueprint, render_template, redirect, url_for, request, flash, current_app, session
from flask_login import login_user, logout_user, login_required, current_user
from sqlalchemy.exc import SQLAlchemyError
from app import db
from app.models import User
from app.services.email_service import send_login_otp_email, send_signup_confirmation_email
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


def _otp_expiry_seconds() -> int:
    minutes = int(current_app.config.get("LOGIN_OTP_EXP_MINUTES", 10) or 10)
    return max(60, minutes * 60)


def _otp_max_attempts() -> int:
    attempts = int(current_app.config.get("LOGIN_OTP_MAX_ATTEMPTS", 5) or 5)
    return max(1, attempts)


def _otp_hash(email: str, otp: str) -> str:
    secret = current_app.config.get("SECRET_KEY", "")
    payload = f"{email}|{otp}".encode("utf-8")
    return hashlib.sha256(secret.encode("utf-8") + b":" + payload).hexdigest()


def _mask_email(email: str) -> str:
    if "@" not in email:
        return email
    name, domain = email.split("@", 1)
    if len(name) <= 2:
        name_mask = name[0] + "*" if name else "*"
    else:
        name_mask = name[0] + ("*" * (len(name) - 2)) + name[-1]
    return f"{name_mask}@{domain}"


def _reuse_pending_otp_if_active(user_id: int, email: str, remember: bool, next_url: str) -> bool:
    """Reuse active OTP challenge to avoid duplicate email sends."""
    pending = session.get("pending_login_otp")
    if not pending:
        return False
    now = int(time.time())
    if now > int(pending.get("expires_at", 0)):
        session.pop("pending_login_otp", None)
        return False
    if int(pending.get("attempts_left", 0)) <= 0:
        session.pop("pending_login_otp", None)
        return False
    if int(pending.get("user_id", -1)) != int(user_id):
        return False
    if (pending.get("email", "").strip().lower()) != email.strip().lower():
        return False

    pending["remember"] = bool(remember)
    pending["next_url"] = next_url or url_for("dashboard.index")
    session["pending_login_otp"] = pending
    return True


def _resolve_pending_user(pending: dict):
    """Load user for OTP verification with retry/fallback lookups."""
    user_id = pending.get("user_id")
    email = (pending.get("email") or "").strip().lower()
    try:
        if user_id is not None:
            return User.query.get(int(user_id))
        if email:
            return User.query.filter_by(email=email).first()
        return None
    except (ValueError, TypeError):
        return User.query.filter_by(email=email).first() if email else None
    except SQLAlchemyError:
        # Recover from aborted transaction/connection hiccups and retry once.
        db.session.rollback()
        db.session.remove()
        if user_id is not None:
            try:
                user = User.query.get(int(user_id))
                if user:
                    return user
            except Exception:
                db.session.rollback()
        if email:
            try:
                return User.query.filter_by(email=email).first()
            except Exception:
                db.session.rollback()
        raise


@auth_bp.route("/signup", methods=["GET", "POST"])
def signup():
    """Signup is disabled; send users to dashboard."""
    flash("Sign up is disabled. Welcome to your dashboard.", "info")
    return redirect(url_for("dashboard.index"))

    if request.method == "POST":
        # Defensive reset in case a previous DB error left session aborted.
        db.session.rollback()
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
            current_app.logger.exception("Signup email lookup failed")
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
            current_app.logger.exception("Signup commit failed")
            flash("Could not create account right now. Please try again.", "error")
            return render_template("auth/signup.html")

        # In tests, keep direct login flow to preserve existing test behavior.
        if current_app.config.get("TESTING"):
            login_user(user, remember=True)
            flash("Account created successfully!", "success")
            return redirect(url_for("dashboard.index"))

        if _reuse_pending_otp_if_active(user.id, user.email, True, url_for("dashboard.index")):
            flash("A verification code was already sent. Please use the latest code in your email.", "info")
            return redirect(url_for("auth.verify_otp"))

        otp = f"{secrets.randbelow(1000000):06d}"
        ok, err = send_login_otp_email(user.email, otp, int(_otp_expiry_seconds() / 60))
        if not ok:
            # If verification email fails, remove the just-created account
            # so unverified users are not left in a confusing state.
            try:
                db.session.delete(user)
                db.session.commit()
            except SQLAlchemyError:
                db.session.rollback()
                current_app.logger.exception("Signup rollback delete failed after OTP send failure")
            flash(err, "error")
            return render_template("auth/signup.html")

        session["pending_login_otp"] = {
            "user_id": user.id,
            "email": user.email,
            "otp_hash": _otp_hash(user.email, otp),
            "expires_at": int(time.time()) + _otp_expiry_seconds(),
            "attempts_left": _otp_max_attempts(),
            "remember": True,
            "next_url": url_for("dashboard.index"),
            "source": "signup",
        }
        flash("Account created. We sent a verification code to your email.", "info")
        return redirect(url_for("auth.verify_otp"))

    return render_template("auth/signup.html")


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    """Login is disabled; send users to dashboard."""
    flash("Sign in is disabled. Welcome to your dashboard.", "info")
    return redirect(url_for("dashboard.index"))

    if request.method == "POST":
        # Defensive reset in case a previous DB error left session aborted.
        db.session.rollback()
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
            current_app.logger.exception("Login user lookup failed")
            flash("Database error during login. Please try again.", "error")
            return render_template("auth/login.html")
        if user and verify_password(password, user.password_hash):
            next_url = request.args.get("next", "")
            if not _is_safe_redirect_url(next_url):
                next_url = url_for("dashboard.index")

            remember = _parse_remember_flag(request.form.get("remember"))
            if current_app.config.get("TESTING"):
                login_user(user, remember=remember)
                return redirect(next_url)

            if _reuse_pending_otp_if_active(user.id, user.email, remember, next_url):
                flash("A verification code was already sent. Please use the latest code in your email.", "info")
                return redirect(url_for("auth.verify_otp"))

            otp = f"{secrets.randbelow(1000000):06d}"
            ok, err = send_login_otp_email(user.email, otp, int(_otp_expiry_seconds() / 60))
            if not ok:
                flash(err, "error")
                return render_template("auth/login.html")

            session["pending_login_otp"] = {
                "user_id": user.id,
                "email": user.email,
                "otp_hash": _otp_hash(user.email, otp),
                "expires_at": int(time.time()) + _otp_expiry_seconds(),
                "attempts_left": _otp_max_attempts(),
                "remember": remember,
                "next_url": next_url,
                "source": "login",
            }
            flash("We sent a verification code to your email. Enter it to complete sign-in.", "info")
            return redirect(url_for("auth.verify_otp"))

        flash("Invalid email or password.", "error")

    return render_template("auth/login.html")


@auth_bp.route("/verify-otp", methods=["GET", "POST"])
def verify_otp():
    """OTP verification is disabled; send users to dashboard."""
    flash("Verification is disabled. Welcome to your dashboard.", "info")
    return redirect(url_for("dashboard.index"))


@auth_bp.route("/logout")
@login_required
def logout():
    """Logout is disabled in dashboard-only mode."""
    flash("Logout is disabled in dashboard-only mode.", "info")
    return redirect(url_for("dashboard.index"))
