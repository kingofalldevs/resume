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


_TEMPLATE_PREVIEW_STYLES = {
    "modern_minimal": {"layout": "topbar", "primary": "#1f2937", "secondary": "#f8fafc", "accent": "#ff6600"},
    "corporate_professional": {"layout": "executive", "primary": "#0f3a5d", "secondary": "#f4f8fc", "accent": "#1d4f7a"},
    "creative_designer": {"layout": "split", "primary": "#7c2d12", "secondary": "#fff7ed", "accent": "#ff6600"},
    "simple_ats": {"layout": "clean", "primary": "#111827", "secondary": "#ffffff", "accent": "#4b5563"},
    "executive_navy": {"layout": "executive", "primary": "#1e3a8a", "secondary": "#eff6ff", "accent": "#2563eb"},
    "executive_charcoal": {"layout": "executive", "primary": "#374151", "secondary": "#f9fafb", "accent": "#111827"},
    "elegant_serif": {"layout": "topbar", "primary": "#6b4f2a", "secondary": "#fffaf2", "accent": "#8a6a3d"},
    "bold_orange": {"layout": "split", "primary": "#ff6600", "secondary": "#fff7ed", "accent": "#c2410c"},
    "clean_slate": {"layout": "clean", "primary": "#1f2937", "secondary": "#f8fafc", "accent": "#334155"},
    "minimal_mono": {"layout": "clean", "primary": "#111111", "secondary": "#fafafa", "accent": "#525252"},
    "two_column_blue": {"layout": "sidebar", "primary": "#1d4ed8", "secondary": "#eff6ff", "accent": "#1e40af"},
    "two_column_green": {"layout": "sidebar", "primary": "#0f766e", "secondary": "#f0fdfa", "accent": "#115e59"},
    "premium_gold": {"layout": "executive", "primary": "#92400e", "secondary": "#fff7ed", "accent": "#b45309"},
    "startup_modern": {"layout": "topbar", "primary": "#0f172a", "secondary": "#f8fafc", "accent": "#2563eb"},
    "classic_black": {"layout": "clean", "primary": "#0a0a0a", "secondary": "#ffffff", "accent": "#3f3f46"},
    "fresh_teal": {"layout": "split", "primary": "#0f766e", "secondary": "#f0fdfa", "accent": "#14b8a6"},
    "plum_accent": {"layout": "topbar", "primary": "#6d28d9", "secondary": "#f5f3ff", "accent": "#7c3aed"},
    "soft_gray": {"layout": "clean", "primary": "#4b5563", "secondary": "#f9fafb", "accent": "#6b7280"},
    "ivory_professional": {"layout": "executive", "primary": "#8a5a2b", "secondary": "#fffdf7", "accent": "#b7791f"},
    "dark_sidebar": {"layout": "sidebar", "primary": "#0f172a", "secondary": "#f8fafc", "accent": "#334155"},
}


def _svg_rect(x, y, width, height, fill, rx=0, stroke=None, stroke_width=1):
    stroke_attr = f' stroke="{stroke}" stroke-width="{stroke_width}"' if stroke else ""
    return f'<rect x="{x}" y="{y}" width="{width}" height="{height}" rx="{rx}" fill="{fill}"{stroke_attr}/>'


def _svg_text(x, y, text, size=12, weight=400, fill="#111827", anchor="start"):
    return f'<text x="{x}" y="{y}" font-size="{size}" font-weight="{weight}" fill="{fill}" text-anchor="{anchor}" font-family="Inter, Arial, sans-serif">{html.escape(text)}</text>'


def _svg_lines(x, y, widths, color="#9aa6b2", height=6, gap=8, rx=3):
    rows = []
    for w in widths:
        rows.append(_svg_rect(x, y, w, height, color, rx=rx))
        y += height + gap
    return "".join(rows), y


def _build_template_preview_svg(template_name: str, label: str, index: int) -> str:
    style = _TEMPLATE_PREVIEW_STYLES.get(
        template_name,
        {
            "layout": "topbar" if index % 2 == 0 else "clean",
            "primary": "#1f2937",
            "secondary": "#f8fafc",
            "accent": "#ff6600",
        },
    )

    layout = style["layout"]
    primary = style["primary"]
    secondary = style["secondary"]
    accent = style["accent"]
    safe_label = html.escape(label)
    ink = "#1f2937"
    muted = "#94a3b8"

    svg = [
        '<svg xmlns="http://www.w3.org/2000/svg" width="900" height="1280" viewBox="0 0 900 1280" role="img" aria-label="Resume preview image">',
        _svg_rect(0, 0, 900, 1280, "#eef2f7"),
        _svg_rect(22, 20, 856, 1240, secondary, rx=14, stroke="#d6dee8"),
    ]

    if layout == "sidebar":
        svg.append(_svg_rect(22, 20, 230, 1240, primary, rx=14))
        svg.append(_svg_rect(252, 20, 626, 1240, "#ffffff", rx=0))
        svg.append(_svg_text(54, 88, "AKOSUA", size=27, weight=800, fill="#ffffff"))
        svg.append(_svg_text(54, 120, "MENSAH", size=27, weight=800, fill="#ffffff"))
        svg.append(_svg_text(54, 148, "Senior Operations Manager", size=12, fill="#dbeafe"))
        svg.append(_svg_text(54, 170, safe_label, size=11, fill="#e2e8f0"))
        svg.append(_svg_rect(54, 202, 165, 1, "#dbeafe"))
        svg.append(_svg_text(54, 230, "CONTACT", size=11, weight=700, fill="#ffffff"))
        lines, _ = _svg_lines(54, 245, [152, 165, 142], color="#cbd5e1", height=6, gap=9)
        svg.append(lines)
        svg.append(_svg_text(54, 316, "SKILLS", size=11, weight=700, fill="#ffffff"))
        svg.append(_svg_rect(54, 330, 146, 7, "#ffffff", rx=3))
        svg.append(_svg_rect(54, 346, 124, 7, "#e2e8f0", rx=3))
        svg.append(_svg_rect(54, 362, 136, 7, "#ffffff", rx=3))
        svg.append(_svg_rect(54, 378, 112, 7, "#e2e8f0", rx=3))
        svg.append(_svg_text(286, 84, "PROFESSIONAL SUMMARY", size=11, weight=700, fill=primary))
        lines, y = _svg_lines(286, 98, [542, 522, 540], color=muted)
        svg.append(lines)
        svg.append(_svg_text(286, y + 20, "EXPERIENCE", size=11, weight=700, fill=primary))
        y += 34
        for _ in range(3):
            svg.append(_svg_rect(286, y, 182, 7, accent, rx=3))
            y += 14
            lines, y = _svg_lines(286, y, [546, 524, 548], color=muted)
            svg.append(lines)
            y += 18
        svg.append(_svg_text(286, y, "EDUCATION", size=11, weight=700, fill=primary))
        y += 14
        lines, _ = _svg_lines(286, y, [382, 350, 368], color=muted)
        svg.append(lines)

    elif layout == "split":
        svg.append(_svg_rect(22, 20, 856, 130, primary, rx=14))
        svg.append(_svg_text(56, 90, "AKOSUA MENSAH", size=34, weight=800, fill="#ffffff"))
        svg.append(_svg_text(56, 122, "Senior Operations Manager", size=15, fill="#eef2ff"))
        svg.append(_svg_text(56, 145, safe_label, size=12, fill="#e2e8f0"))
        svg.append(_svg_rect(56, 182, 372, 1050, "#ffffff", rx=10, stroke="#e2e8f0"))
        svg.append(_svg_rect(448, 182, 396, 1050, "#ffffff", rx=10, stroke="#e2e8f0"))
        svg.append(_svg_text(78, 216, "PROFILE", size=11, weight=700, fill=primary))
        lines, y = _svg_lines(78, 230, [324, 306, 318], color=muted)
        svg.append(lines)
        svg.append(_svg_text(78, y + 24, "SKILLS", size=11, weight=700, fill=primary))
        y += 38
        for w in [210, 250, 200, 238, 198]:
            svg.append(_svg_rect(78, y, w, 8, accent, rx=4))
            y += 16
        svg.append(_svg_text(470, 216, "EXPERIENCE", size=11, weight=700, fill=primary))
        y = 230
        for _ in range(4):
            svg.append(_svg_rect(470, y, 240, 7, accent, rx=3))
            y += 14
            lines, y = _svg_lines(470, y, [338, 322, 346], color=muted)
            svg.append(lines)
            y += 20
        svg.append(_svg_text(470, y, "EDUCATION", size=11, weight=700, fill=primary))
        y += 14
        lines, _ = _svg_lines(470, y, [332, 316, 336], color=muted)
        svg.append(lines)

    elif layout == "executive":
        svg.append(_svg_rect(22, 20, 856, 160, "#ffffff", rx=14))
        svg.append(_svg_rect(22, 20, 856, 54, primary, rx=14))
        svg.append(_svg_text(52, 55, safe_label, size=13, weight=700, fill="#ffffff"))
        svg.append(_svg_text(52, 116, "AKOSUA MENSAH", size=35, weight=800, fill=ink))
        svg.append(_svg_text(52, 148, "Senior Operations Manager", size=14, fill="#475569"))
        svg.append(_svg_rect(620, 92, 228, 70, "#f8fafc", rx=8, stroke="#d9e2ec"))
        lines, _ = _svg_lines(640, 112, [186, 174, 160], color="#94a3b8", height=6, gap=8)
        svg.append(lines)
        svg.append(_svg_rect(52, 198, 796, 2, accent, rx=1))
        y = 228
        svg.append(_svg_text(52, y, "PROFESSIONAL SUMMARY", size=11, weight=700, fill=primary))
        y += 12
        lines, y = _svg_lines(52, y, [786, 760, 772], color=muted)
        svg.append(lines)
        y += 20
        svg.append(_svg_text(52, y, "EXPERIENCE", size=11, weight=700, fill=primary))
        y += 12
        for _ in range(4):
            svg.append(_svg_rect(52, y, 280, 8, accent, rx=4))
            y += 14
            lines, y = _svg_lines(52, y, [782, 760, 770], color=muted)
            svg.append(lines)
            y += 18
        svg.append(_svg_text(52, y, "EDUCATION", size=11, weight=700, fill=primary))
        y += 14
        lines, _ = _svg_lines(52, y, [482, 460, 470], color=muted)
        svg.append(lines)

    elif layout == "clean":
        svg.append(_svg_rect(22, 20, 856, 1240, "#ffffff", rx=14, stroke="#d6dee8"))
        svg.append(_svg_text(450, 86, "AKOSUA MENSAH", size=36, weight=800, fill=ink, anchor="middle"))
        svg.append(_svg_text(450, 114, "Senior Operations Manager", size=14, fill="#475569", anchor="middle"))
        svg.append(_svg_text(450, 136, safe_label, size=11, fill="#64748b", anchor="middle"))
        svg.append(_svg_rect(52, 156, 796, 1, accent))
        y = 188
        for title, widths in [
            ("SUMMARY", [782, 760, 772]),
            ("EXPERIENCE", [782, 770, 756, 770, 744]),
            ("EDUCATION", [520, 500, 480]),
            ("SKILLS", [420, 398, 372]),
        ]:
            svg.append(_svg_text(52, y, title, size=11, weight=700, fill=primary))
            y += 12
            lines, y = _svg_lines(52, y, widths, color=muted)
            svg.append(lines)
            y += 18

    else:  # topbar
        svg.append(_svg_rect(22, 20, 856, 1240, "#ffffff", rx=14, stroke="#d6dee8"))
        svg.append(_svg_rect(22, 20, 856, 116, primary, rx=14))
        svg.append(_svg_text(52, 78, "AKOSUA MENSAH", size=32, weight=800, fill="#ffffff"))
        svg.append(_svg_text(52, 104, "Senior Operations Manager", size=14, fill="#e2e8f0"))
        svg.append(_svg_text(640, 104, safe_label, size=11, fill="#e2e8f0"))
        y = 168
        svg.append(_svg_text(52, y, "SUMMARY", size=11, weight=700, fill=primary))
        y += 12
        lines, y = _svg_lines(52, y, [780, 760, 772], color=muted)
        svg.append(lines)
        y += 20
        svg.append(_svg_text(52, y, "EXPERIENCE", size=11, weight=700, fill=primary))
        y += 12
        for _ in range(3):
            svg.append(_svg_rect(52, y, 260, 8, accent, rx=3))
            y += 14
            lines, y = _svg_lines(52, y, [782, 760, 774], color=muted)
            svg.append(lines)
            y += 18
        svg.append(_svg_text(52, y, "EDUCATION", size=11, weight=700, fill=primary))
        y += 12
        lines, _ = _svg_lines(52, y, [452, 430, 445], color=muted)
        svg.append(lines)

    svg.append("</svg>")
    return "".join(svg)


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


@dashboard_bp.route("/pricing")
@login_required
def pricing():
    """Simple pricing page for core services."""
    return render_template("dashboard/pricing.html")


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
