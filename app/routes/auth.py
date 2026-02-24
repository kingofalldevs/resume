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
    """Auth removed; send users to dashboard."""
    flash("Authentication has been removed.", "info")
    return redirect(url_for("dashboard.index"))


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    """Auth removed; send users to dashboard."""
    flash("Authentication has been removed.", "info")
    return redirect(url_for("dashboard.index"))


@auth_bp.route("/verify-otp", methods=["GET", "POST"])
def verify_otp():
    """Auth removed; send users to dashboard."""
    flash("Authentication has been removed.", "info")
    return redirect(url_for("dashboard.index"))


@auth_bp.route("/logout")
@login_required
def logout():
    """Auth removed; send users to dashboard."""
    flash("Authentication has been removed.", "info")
    return redirect(url_for("dashboard.index"))
