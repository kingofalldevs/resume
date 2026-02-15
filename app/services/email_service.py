"""
Central SendGrid email service for transactional emails.
"""
from __future__ import annotations

import html
from typing import Tuple

from flask import current_app


def _settings() -> dict:
    return {
        "api_key": (current_app.config.get("SENDGRID_API_KEY", "") or "").strip(),
        # Keep sender identity consistent with authenticated domain.
        "from_email": "team@resumeghana.com",
        "from_name": (current_app.config.get("SENDGRID_FROM_NAME", "ResumeGhana") or "ResumeGhana").strip(),
        "reply_to": "team@resumeghana.com",
        "list_unsub_url": (current_app.config.get("EMAIL_LIST_UNSUBSCRIBE_URL", "") or "").strip(),
    }


def send_transactional_email(
    *,
    to_email: str,
    subject: str,
    text_body: str,
    html_body: str = "",
    category: str = "transactional",
) -> Tuple[bool, str]:
    """Send transactional email via SendGrid with deliverability-friendly defaults."""
    cfg = _settings()
    if not cfg["api_key"] or not cfg["from_email"]:
        return False, "SendGrid is not configured. Set SENDGRID_API_KEY and SENDGRID_FROM_EMAIL."

    try:
        from sendgrid import SendGridAPIClient
        from sendgrid.helpers.mail import (
            Mail,
            Email,
            To,
            ReplyTo,
            Header,
            Category,
            TrackingSettings,
            ClickTracking,
            OpenTracking,
            SubscriptionTracking,
        )
    except Exception:
        return False, "SendGrid SDK is not installed. Add `sendgrid` to requirements."

    message = Mail(
        from_email=Email(cfg["from_email"], cfg["from_name"]),
        to_emails=To(to_email),
        subject=subject,
        plain_text_content=text_body,
        html_content=html_body or None,
    )

    # Explicit reply-to for mailbox consistency.
    reply_to = cfg["reply_to"] or cfg["from_email"]
    message.reply_to = ReplyTo(reply_to, cfg["from_name"])

    # Use category for SendGrid analytics/segmentation.
    if category:
        message.add_category(Category(category))

    # Transactional best-practice: disable click/open/subscription tracking.
    ts = TrackingSettings()
    ts.click_tracking = ClickTracking(enable=False, enable_text=False)
    ts.open_tracking = OpenTracking(enable=False)
    ts.subscription_tracking = SubscriptionTracking(enable=False)
    message.tracking_settings = ts

    if cfg["list_unsub_url"]:
        message.add_header(Header("List-Unsubscribe", f"<{cfg['list_unsub_url']}>"))

    try:
        response = SendGridAPIClient(cfg["api_key"]).send(message)
        status = int(response.status_code)
        if status >= 400:
            if status == 403:
                return False, "SendGrid rejected the sender (403). Ensure team@resumeghana.com is allowed under your verified domain and API key permissions."
            return False, f"SendGrid rejected email ({status})."
        return True, ""
    except Exception as exc:
        text = str(exc)
        if "403" in text:
            return False, "SendGrid 403 Forbidden. Verify sender identity/domain auth and key permissions for Mail Send."
        return False, f"Failed to send email: {exc}"


def send_login_otp_email(to_email: str, otp: str, expiry_minutes: int) -> Tuple[bool, str]:
    subject = "Your ResumeGhana login verification code"
    text = (
        "Use this one-time code to complete your ResumeGhana login:\n\n"
        f"{otp}\n\n"
        f"This code expires in {expiry_minutes} minutes.\n"
        "If this was not you, please ignore this email."
    )
    html = (
        "<p>Use this one-time code to complete your ResumeGhana login:</p>"
        f"<p style='font-size:22px;font-weight:700;letter-spacing:2px;'>{otp}</p>"
        f"<p>This code expires in {expiry_minutes} minutes.</p>"
        "<p>If this was not you, please ignore this email.</p>"
    )
    return send_transactional_email(
        to_email=to_email,
        subject=subject,
        text_body=text,
        html_body=html,
        category="login_otp",
    )


def send_signup_confirmation_email(to_email: str, full_name: str = "") -> Tuple[bool, str]:
    subject = "Welcome to ResumeGhana"
    greeting = f"Hi {full_name}," if full_name else "Hi,"
    text = (
        f"{greeting}\n\n"
        "Your account has been successfully verified.\n"
        "You can now build, save, and export your resume.\n\n"
        "Best,\nResumeGhana Team"
    )
    html = (
        f"<p>{greeting}</p>"
        "<p>Your account has been successfully verified.</p>"
        "<p>You can now build, save, and export your resume.</p>"
        "<p>Best,<br>ResumeGhana Team</p>"
    )
    return send_transactional_email(
        to_email=to_email,
        subject=subject,
        text_body=text,
        html_body=html,
        category="signup_confirmation",
    )


def send_password_reset_email(to_email: str, reset_link: str) -> Tuple[bool, str]:
    subject = "ResumeGhana password reset instructions"
    text = (
        "We received a request to reset your password.\n\n"
        f"Reset your password: {reset_link}\n\n"
        "If you did not request this, ignore this email."
    )
    html = (
        "<p>We received a request to reset your password.</p>"
        f"<p><a href='{reset_link}'>Reset your password</a></p>"
        "<p>If you did not request this, ignore this email.</p>"
    )
    return send_transactional_email(
        to_email=to_email,
        subject=subject,
        text_body=text,
        html_body=html,
        category="password_reset",
    )


def send_interview_booking_to_team(
    *,
    user_name: str,
    user_email: str,
    company: str,
    job_role: str,
    preferred_date: str,
    preferred_time: str,
    phone: str,
    notes: str = "",
) -> Tuple[bool, str]:
    """Send interview booking request to team@resumeghana.com via SendGrid."""
    subject = f"New Interview Booking: {job_role} — {user_name}"
    text = (
        f"A new interview booking request has been submitted.\n\n"
        f"User: {user_name} <{user_email}>\n"
        f"Company/Job: {company}\n"
        f"Role Applying For: {job_role}\n"
        f"Preferred Date: {preferred_date}\n"
        f"Preferred Time: {preferred_time}\n"
        f"Phone: {phone}\n"
    )
    if notes:
        text += f"\nNotes:\n{notes}\n"

    html_content = (
        "<p><strong>New interview booking request</strong></p>"
        f"<p><strong>User:</strong> {html.escape(user_name)} &lt;<a href='mailto:{html.escape(user_email)}'>{html.escape(user_email)}</a>&gt;</p>"
        f"<p><strong>Company/Job:</strong> {html.escape(company)}</p>"
        f"<p><strong>Role Applying For:</strong> {html.escape(job_role)}</p>"
        f"<p><strong>Preferred Date:</strong> {html.escape(preferred_date)}<br>"
        f"<strong>Preferred Time:</strong> {html.escape(preferred_time)}</p>"
        f"<p><strong>Phone:</strong> <a href='tel:{html.escape(phone)}'>{html.escape(phone)}</a></p>"
    )
    if notes:
        safe_notes = html.escape(notes).replace("\n", "<br>")
        html_content += f"<p><strong>Notes:</strong><br>{safe_notes}</p>"

    return send_transactional_email(
        to_email="team@resumeghana.com",
        subject=subject,
        text_body=text,
        html_body=html_content,
        category="interview_booking",
    )


def send_interview_notification_email(to_email: str, role: str, when_text: str, details: str = "") -> Tuple[bool, str]:
    subject = f"Interview update: {role}"
    text = (
        "You have a new interview update.\n\n"
        f"Role: {role}\n"
        f"When: {when_text}\n"
        f"{details}\n\n"
        "Good luck,\nResumeGhana Team"
    )
    html = (
        "<p>You have a new interview update.</p>"
        f"<p><strong>Role:</strong> {role}<br><strong>When:</strong> {when_text}</p>"
        f"<p>{details}</p>"
        "<p>Good luck,<br>ResumeGhana Team</p>"
    )
    return send_transactional_email(
        to_email=to_email,
        subject=subject,
        text_body=text,
        html_body=html,
        category="interview_notification",
    )
