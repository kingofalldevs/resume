"""
Dashboard routes: view resumes, create new, usage stats, book interview, chat expert.
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from app import db
from app.models import Resume, AIUsage
from app.services.email_service import send_interview_booking_to_team, send_expert_talk_to_team
from sqlalchemy import func

dashboard_bp = Blueprint("dashboard", __name__)


@dashboard_bp.route("/")
@login_required
def index():
    """Dashboard home: resume cards and usage stats."""
    resumes = Resume.query.filter_by(user_id=current_user.id).order_by(Resume.updated_at.desc()).limit(20).all()
    total_tokens = (
        db.session.query(func.sum(AIUsage.tokens_used))
        .filter(AIUsage.user_id == current_user.id)
        .scalar()
        or 0
    )
    return render_template(
        "dashboard/index.html",
        resumes=resumes,
        total_tokens=int(total_tokens),
    )


@dashboard_bp.route("/book-interview", methods=["GET", "POST"])
@login_required
def book_interview():
    """Book a mock interview / consultation session."""
    if request.method == "POST":
        company = (request.form.get("company") or "").strip()
        job_role = (request.form.get("job_role") or "").strip()
        preferred_date = (request.form.get("preferred_date") or "").strip()
        preferred_time = (request.form.get("preferred_time") or "").strip()
        phone = (request.form.get("phone") or "").strip()
        notes = (request.form.get("notes") or "").strip()

        if not company or not job_role or not preferred_date or not preferred_time or not phone:
            flash("Please fill in all required fields: company, job role, preferred date, time, and phone.", "error")
            return render_template("dashboard/book_interview.html")

        ok, err = send_interview_booking_to_team(
            user_name=current_user.full_name or "User",
            user_email=current_user.email,
            company=company,
            job_role=job_role,
            preferred_date=preferred_date,
            preferred_time=preferred_time,
            phone=phone,
            notes=notes,
        )
        if not ok:
            flash(f"Could not send your request: {err}. Please try again or contact us directly.", "error")
            return render_template("dashboard/book_interview.html")

        flash(
            "Your interview request has been received! Our team will contact you within 24–48 hours to confirm your session.",
            "success",
        )
        return redirect(url_for("dashboard.index"))

    return render_template("dashboard/book_interview.html")


@dashboard_bp.route("/chat-expert", methods=["GET", "POST"])
@login_required
def chat_expert():
    """Chat with a career expert (form submission)."""
    if request.method == "POST":
        topic = (request.form.get("topic") or "").strip()
        message = (request.form.get("message") or "").strip()

        if not message:
            flash("Please enter your question or message.", "error")
            return render_template("dashboard/chat_expert.html")

        ok, err = send_expert_talk_to_team(
            user_name=current_user.full_name or "User",
            user_email=current_user.email,
            topic=topic,
            message=message,
        )
        if not ok:
            flash(f"Could not send your message: {err}. Please try again or contact us directly.", "error")
            return render_template("dashboard/chat_expert.html")

        flash(
            "Your message has been sent! A career expert will respond within 24 hours.",
            "success",
        )
        return redirect(url_for("dashboard.index"))

    return render_template("dashboard/chat_expert.html")
