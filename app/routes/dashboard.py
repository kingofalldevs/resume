"""
Dashboard routes: view resumes, create new, usage stats, book interview, chat expert.
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, Response
from flask_login import login_required, current_user
from app import db
from app.models import Resume, AIUsage
from app.services.email_service import send_interview_booking_to_team, send_expert_talk_to_team
from app.services.resume_builder import TEMPLATES, get_template_catalog
from sqlalchemy import func
import html

dashboard_bp = Blueprint("dashboard", __name__)


def _template_palette(index: int) -> tuple[str, str, str]:
    hue = (index * 29) % 360
    primary = f"hsl({hue}, 62%, 38%)"
    secondary = f"hsl({(hue + 24) % 360}, 38%, 92%)"
    text = f"hsl({(hue + 8) % 360}, 20%, 24%)"
    return primary, secondary, text


def _build_template_preview_svg(template_name: str, label: str, index: int) -> str:
    primary, secondary, text = _template_palette(index)
    name = "AKOSUA MENSAH"
    role = "Senior Operations Manager"
    safe_label = html.escape(label)
    layout = index % 4

    if layout == 0:
        body = f"""
        <rect x="24" y="24" width="852" height="1240" rx="12" fill="#ffffff" stroke="#dbe4ee"/>
        <rect x="24" y="24" width="852" height="122" rx="12" fill="{primary}"/>
        <text x="52" y="86" font-size="34" font-weight="700" fill="#ffffff">{name}</text>
        <text x="52" y="118" font-size="16" fill="#f5f7fa">{role}</text>
        <text x="52" y="146" font-size="12" fill="#e8eef5">{safe_label}</text>
        <rect x="52" y="192" width="360" height="10" rx="5" fill="{primary}"/>
        <rect x="52" y="214" width="780" height="8" rx="4" fill="#94a3b8"/>
        <rect x="52" y="230" width="750" height="8" rx="4" fill="#a8b4c3"/>
        <rect x="52" y="246" width="700" height="8" rx="4" fill="#b6c0cd"/>
        <rect x="52" y="292" width="240" height="9" rx="4" fill="{primary}"/>
        <rect x="52" y="314" width="780" height="7" rx="3.5" fill="#8b98a8"/>
        <rect x="52" y="328" width="750" height="7" rx="3.5" fill="#99a5b3"/>
        <rect x="52" y="342" width="770" height="7" rx="3.5" fill="#aab4c0"/>
        <rect x="52" y="372" width="780" height="7" rx="3.5" fill="#8b98a8"/>
        <rect x="52" y="386" width="735" height="7" rx="3.5" fill="#aab4c0"/>
        <rect x="52" y="432" width="220" height="9" rx="4" fill="{primary}"/>
        <rect x="52" y="454" width="330" height="7" rx="3.5" fill="#95a2b2"/>
        <rect x="52" y="468" width="310" height="7" rx="3.5" fill="#a9b4c2"/>
        <rect x="52" y="482" width="320" height="7" rx="3.5" fill="#bac3cf"/>
        <rect x="450" y="454" width="382" height="7" rx="3.5" fill="#95a2b2"/>
        <rect x="450" y="468" width="360" height="7" rx="3.5" fill="#a9b4c2"/>
        <rect x="450" y="482" width="375" height="7" rx="3.5" fill="#bac3cf"/>
        """
    elif layout == 1:
        body = f"""
        <rect x="24" y="24" width="852" height="1240" rx="12" fill="#ffffff" stroke="#dbe4ee"/>
        <rect x="24" y="24" width="248" height="1240" rx="12" fill="{primary}"/>
        <text x="48" y="84" font-size="24" font-weight="700" fill="#ffffff">AKOSUA</text>
        <text x="48" y="112" font-size="24" font-weight="700" fill="#ffffff">MENSAH</text>
        <text x="48" y="138" font-size="12" fill="#e8eef5">{safe_label}</text>
        <rect x="48" y="186" width="180" height="8" rx="4" fill="#ffffff"/>
        <rect x="48" y="202" width="168" height="7" rx="3.5" fill="#d6e0ec"/>
        <rect x="48" y="216" width="176" height="7" rx="3.5" fill="#e5edf6"/>
        <rect x="48" y="266" width="160" height="8" rx="4" fill="#ffffff"/>
        <rect x="48" y="282" width="176" height="7" rx="3.5" fill="#d6e0ec"/>
        <rect x="48" y="296" width="172" height="7" rx="3.5" fill="#e5edf6"/>
        <rect x="304" y="72" width="480" height="10" rx="5" fill="{primary}"/>
        <rect x="304" y="98" width="528" height="8" rx="4" fill="#8795a7"/>
        <rect x="304" y="114" width="508" height="8" rx="4" fill="#9aa6b5"/>
        <rect x="304" y="130" width="512" height="8" rx="4" fill="#b1bbc8"/>
        <rect x="304" y="184" width="250" height="9" rx="4" fill="{primary}"/>
        <rect x="304" y="206" width="528" height="7" rx="3.5" fill="#8692a2"/>
        <rect x="304" y="220" width="500" height="7" rx="3.5" fill="#97a3b2"/>
        <rect x="304" y="234" width="520" height="7" rx="3.5" fill="#a7b1bf"/>
        <rect x="304" y="264" width="528" height="7" rx="3.5" fill="#8692a2"/>
        <rect x="304" y="278" width="480" height="7" rx="3.5" fill="#a7b1bf"/>
        """
    elif layout == 2:
        body = f"""
        <rect x="24" y="24" width="852" height="1240" rx="12" fill="{secondary}" stroke="#dbe4ee"/>
        <rect x="56" y="56" width="788" height="1176" rx="10" fill="#ffffff"/>
        <rect x="56" y="56" width="788" height="100" rx="10" fill="{primary}"/>
        <text x="88" y="102" font-size="30" font-weight="700" fill="#ffffff">{name}</text>
        <text x="88" y="130" font-size="14" fill="#ecf3fb">{role} • {safe_label}</text>
        <rect x="88" y="188" width="220" height="9" rx="4" fill="{primary}"/>
        <rect x="88" y="210" width="724" height="7" rx="3.5" fill="#8e9bac"/>
        <rect x="88" y="224" width="690" height="7" rx="3.5" fill="#a3afbc"/>
        <rect x="88" y="238" width="714" height="7" rx="3.5" fill="#b1bcc8"/>
        <rect x="88" y="284" width="220" height="9" rx="4" fill="{primary}"/>
        <rect x="88" y="306" width="220" height="7" rx="3.5" fill="#8e9bac"/>
        <rect x="88" y="320" width="210" height="7" rx="3.5" fill="#a3afbc"/>
        <rect x="88" y="334" width="212" height="7" rx="3.5" fill="#b1bcc8"/>
        <rect x="350" y="306" width="462" height="7" rx="3.5" fill="#8e9bac"/>
        <rect x="350" y="320" width="430" height="7" rx="3.5" fill="#a3afbc"/>
        <rect x="350" y="334" width="452" height="7" rx="3.5" fill="#b1bcc8"/>
        <rect x="350" y="368" width="462" height="7" rx="3.5" fill="#8e9bac"/>
        <rect x="350" y="382" width="442" height="7" rx="3.5" fill="#a3afbc"/>
        """
    else:
        body = f"""
        <rect x="24" y="24" width="852" height="1240" rx="12" fill="#ffffff" stroke="#dbe4ee"/>
        <rect x="56" y="56" width="788" height="40" rx="6" fill="{primary}"/>
        <text x="72" y="82" font-size="18" font-weight="700" fill="#ffffff">{safe_label}</text>
        <text x="636" y="82" font-size="13" fill="#e7eef7">{name}</text>
        <rect x="56" y="126" width="300" height="11" rx="5" fill="{text}"/>
        <rect x="56" y="146" width="206" height="8" rx="4" fill="{primary}"/>
        <rect x="56" y="186" width="788" height="1" fill="#d8e1eb"/>
        <rect x="56" y="210" width="190" height="8" rx="4" fill="{primary}"/>
        <rect x="56" y="230" width="760" height="7" rx="3.5" fill="#8c98a8"/>
        <rect x="56" y="244" width="742" height="7" rx="3.5" fill="#a2adbb"/>
        <rect x="56" y="258" width="710" height="7" rx="3.5" fill="#b2bcc8"/>
        <rect x="56" y="300" width="170" height="8" rx="4" fill="{primary}"/>
        <rect x="56" y="320" width="350" height="7" rx="3.5" fill="#8c98a8"/>
        <rect x="56" y="334" width="330" height="7" rx="3.5" fill="#a2adbb"/>
        <rect x="438" y="320" width="378" height="7" rx="3.5" fill="#8c98a8"/>
        <rect x="438" y="334" width="360" height="7" rx="3.5" fill="#a2adbb"/>
        <rect x="438" y="348" width="372" height="7" rx="3.5" fill="#b2bcc8"/>
        """

    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="900" height="1280" viewBox="0 0 900 1280" role="img" aria-label="{html.escape(template_name)} resume template preview">{body}</svg>"""


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
    selected_template = session.get("preferred_template", "modern_minimal")
    if selected_template not in TEMPLATES:
        selected_template = "modern_minimal"
    template_catalog = get_template_catalog()
    return render_template(
        "dashboard/index.html",
        resumes=resumes,
        total_tokens=int(total_tokens),
        selected_template=selected_template,
        template_catalog=template_catalog,
    )


@dashboard_bp.route("/template/select", methods=["POST"])
@login_required
def select_template():
    """Persist preferred resume template from dashboard gallery."""
    template_name = (request.form.get("template_name") or "").strip()
    if template_name not in TEMPLATES:
        flash("That template is unavailable. Please choose another one.", "error")
        return redirect(url_for("dashboard.index"))
    session["preferred_template"] = template_name
    flash("Template selected. Continue to builder to create your resume.", "success")
    return redirect(url_for("resume.builder", template=template_name))


@dashboard_bp.route("/template-preview/<template_name>.svg")
@login_required
def template_preview(template_name: str):
    """Serve real template preview image for dashboard/picker cards."""
    catalog = get_template_catalog()
    by_id = {tpl["id"]: (idx, tpl) for idx, tpl in enumerate(catalog)}
    if template_name not in by_id:
        return Response("Not found", status=404)
    idx, tpl = by_id[template_name]
    svg = _build_template_preview_svg(template_name=template_name, label=tpl["label"], index=idx)
    return Response(svg, mimetype="image/svg+xml")


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
