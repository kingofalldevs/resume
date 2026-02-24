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


def _svg_lines(x, y, widths, color="#9aa6b2", height=6, gap=10, rx=3):
    rows = []
    for w in widths:
        rows.append(_svg_rect(x, y, w, height, color, rx=rx))
        y += height + gap
    return "".join(rows), y


def _svg_text_lines(x, y, lines, size=24, fill="#64748b", gap=10):
    """Draw multiple lines of readable text; return final y."""
    out = []
    for line in lines:
        out.append(_svg_text(x, y, line[:80] if len(line) > 80 else line, size=size, fill=fill))
        y += size + gap
    return "".join(out), y


# Reference-style placeholder content (like "Clean", "Impact", "Classic" examples)
_PREVIEW_NAME = "YOUR NAME"
_PREVIEW_JOB_TITLE = "JOB TITLE"
_PREVIEW_CONTACT = "Address, City  •  Phone  •  email@example.com"
_PREVIEW_SUMMARY_LINE1 = "Click or tap here to edit text or use AI writing assistant."
_PREVIEW_SUMMARY_LINE2 = "Summarize your experience and what you bring to the role in 2–3 sentences."
_PREVIEW_EXP_JOB = "Job Title"
_PREVIEW_EXP_COMBO = "Company - City, ST"
_PREVIEW_EXP_DATES = "Jan 2023 - Jan 2024"
_PREVIEW_EXP_BULLETS = [
    "• Describe your key achievements and responsibilities here.",
    "• Use bullet points and numbers where possible.",
    "• Keep each point clear and impactful.",
]
_PREVIEW_EDU_DEGREE = "Degree Title"
_PREVIEW_EDU_SCHOOL = "University Name - City, ST"
_PREVIEW_EDU_DATES = "Jan 2020 - Jan 2023"
_PREVIEW_SKILLS = ["Microsoft Word Expert", "Microsoft PowerPoint Advanced"]
_PREVIEW_LANGUAGES = ["Spanish", "Mandarin Chinese"]
_PREVIEW_LANGUAGES_PROF = ["Spanish (advanced)", "Mandarin Chinese (intermediate)"]
_PREVIEW_REFERENCES = "Available on request"
_PREVIEW_WEB_SOCIAL = "LinkedIn  •  Twitter"


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
        # Initials circle (Impact-style)
        svg.append(_svg_rect(54, 48, 52, 52, "#ffffff", rx=26))
        svg.append(_svg_text(80, 82, "YN", size=24, weight=700, fill=primary, anchor="middle"))
        svg.append(_svg_text(54, 118, _PREVIEW_NAME, size=24, weight=700, fill="#ffffff"))
        svg.append(_svg_text(54, 138, _PREVIEW_JOB_TITLE, size=15, fill="#dbeafe"))
        svg.append(_svg_rect(54, 158, 165, 1, "#dbeafe"))
        svg.append(_svg_text(54, 182, "SKILLS", size=15, weight=700, fill="#ffffff"))
        for i, sk in enumerate(_PREVIEW_SKILLS):
            svg.append(_svg_text(54, 200 + i * 24, sk, size=24, fill="#e2e8f0"))
        svg.append(_svg_text(54, 244, "LANGUAGES", size=15, weight=700, fill="#ffffff"))
        for i, lang in enumerate(_PREVIEW_LANGUAGES):
            svg.append(_svg_text(54, 262 + i * 24, lang, size=24, fill="#e2e8f0"))
        svg.append(_svg_text(54, 298, "WEB & SOCIAL", size=15, weight=700, fill="#ffffff"))
        svg.append(_svg_text(54, 316, _PREVIEW_WEB_SOCIAL[:28], size=24, fill="#cbd5e1"))
        svg.append(_svg_text(54, 342, "REFERENCES", size=15, weight=700, fill="#ffffff"))
        svg.append(_svg_text(54, 360, _PREVIEW_REFERENCES, size=24, fill="#e2e8f0"))
        svg.append(_svg_text(286, 84, "SUMMARY", size=15, weight=700, fill=primary))
        txt, y = _svg_text_lines(286, 98, [_PREVIEW_SUMMARY_LINE1[:62], _PREVIEW_SUMMARY_LINE2[:60]], size=24, fill=muted, gap=10)
        svg.append(txt)
        svg.append(_svg_text(286, y + 22, "EXPERIENCE", size=15, weight=700, fill=primary))
        y += 40
        svg.append(_svg_text(286, y, _PREVIEW_EXP_JOB, size=24, weight=600, fill=accent))
        y += 20
        svg.append(_svg_text(286, y, _PREVIEW_EXP_COMBO, size=24, fill=muted))
        y += 20
        svg.append(_svg_text(286, y, _PREVIEW_EXP_DATES, size=24, fill=muted))
        y += 20
        txt, y = _svg_text_lines(286, y, _PREVIEW_EXP_BULLETS[:2], size=17, fill=muted, gap=6)
        svg.append(txt)
        y += 26
        svg.append(_svg_text(286, y, _PREVIEW_EXP_JOB, size=24, weight=600, fill=accent))
        y += 20
        svg.append(_svg_text(286, y, _PREVIEW_EXP_COMBO, size=24, fill=muted))
        y += 20
        svg.append(_svg_text(286, y, _PREVIEW_EXP_DATES, size=24, fill=muted))
        y += 20
        svg.append(_svg_text(286, y, "EDUCATION", size=15, weight=700, fill=primary))
        y += 20
        svg.append(_svg_text(286, y, _PREVIEW_EDU_DEGREE, size=24, weight=600, fill=accent))
        y += 20
        svg.append(_svg_text(286, y, _PREVIEW_EDU_SCHOOL, size=24, fill=muted))
        y += 20
        svg.append(_svg_text(286, y, _PREVIEW_EDU_DATES, size=24, fill=muted))

    elif layout == "split":
        svg.append(_svg_rect(22, 20, 856, 130, primary, rx=14))
        svg.append(_svg_text(56, 90, _PREVIEW_NAME, size=36, weight=800, fill="#ffffff"))
        svg.append(_svg_text(56, 118, _PREVIEW_JOB_TITLE, size=24, fill="#eef2ff"))
        svg.append(_svg_text(56, 138, _PREVIEW_CONTACT[:55], size=24, fill="#e2e8f0"))
        svg.append(_svg_rect(56, 182, 372, 1050, "#ffffff", rx=10, stroke="#e2e8f0"))
        svg.append(_svg_rect(448, 182, 396, 1050, "#ffffff", rx=10, stroke="#e2e8f0"))
        svg.append(_svg_text(78, 216, "SUMMARY", size=15, weight=700, fill=primary))
        txt, y = _svg_text_lines(78, 230, [_PREVIEW_SUMMARY_LINE1[:48], _PREVIEW_SUMMARY_LINE2[:46]], size=24, fill=muted, gap=10)
        svg.append(txt)
        svg.append(_svg_text(78, y + 26, "SKILLS", size=15, weight=700, fill=primary))
        y += 44
        for sk in _PREVIEW_SKILLS:
            svg.append(_svg_text(78, y, sk, size=24, fill=ink))
            y += 22
        svg.append(_svg_text(78, y + 8, "LANGUAGES", size=15, weight=700, fill=primary))
        y += 26
        for lang in _PREVIEW_LANGUAGES:
            svg.append(_svg_text(78, y, lang, size=24, fill=muted))
            y += 24
        svg.append(_svg_text(78, y + 8, "REFERENCES", size=15, weight=700, fill=primary))
        y += 26
        svg.append(_svg_text(78, y, _PREVIEW_REFERENCES, size=24, fill=muted))
        svg.append(_svg_text(470, 216, "EXPERIENCE", size=15, weight=700, fill=primary))
        y = 230
        svg.append(_svg_text(470, y, _PREVIEW_EXP_JOB, size=24, weight=600, fill=accent))
        y += 20
        svg.append(_svg_text(470, y, _PREVIEW_EXP_COMBO, size=24, fill=muted))
        y += 20
        svg.append(_svg_text(470, y, _PREVIEW_EXP_DATES, size=24, fill=muted))
        y += 20
        txt, y = _svg_text_lines(470, y, _PREVIEW_EXP_BULLETS[:2], size=17, fill=muted, gap=6)
        svg.append(txt)
        y += 28
        svg.append(_svg_text(470, y, _PREVIEW_EXP_JOB, size=24, weight=600, fill=accent))
        y += 20
        svg.append(_svg_text(470, y, _PREVIEW_EXP_COMBO, size=24, fill=muted))
        y += 20
        svg.append(_svg_text(470, y, _PREVIEW_EXP_DATES, size=24, fill=muted))
        y += 28
        svg.append(_svg_text(470, y, "EDUCATION", size=15, weight=700, fill=primary))
        y += 20
        svg.append(_svg_text(470, y, _PREVIEW_EDU_DEGREE, size=24, weight=600, fill=accent))
        y += 20
        svg.append(_svg_text(470, y, _PREVIEW_EDU_SCHOOL, size=24, fill=muted))
        y += 20
        svg.append(_svg_text(470, y, _PREVIEW_EDU_DATES, size=24, fill=muted))

    elif layout == "executive":
        svg.append(_svg_rect(22, 20, 856, 160, "#ffffff", rx=14))
        svg.append(_svg_rect(22, 20, 856, 54, primary, rx=14))
        svg.append(_svg_text(52, 55, safe_label, size=17, weight=700, fill="#ffffff"))
        svg.append(_svg_text(52, 116, _PREVIEW_NAME, size=36, weight=800, fill=ink))
        svg.append(_svg_text(52, 148, _PREVIEW_JOB_TITLE, size=24, fill="#475569"))
        svg.append(_svg_rect(620, 92, 228, 70, "#f8fafc", rx=8, stroke="#d9e2ec"))
        svg.append(_svg_text(640, 108, "Address, City", size=24, fill="#64748b"))
        svg.append(_svg_text(640, 124, "Phone", size=24, fill="#64748b"))
        svg.append(_svg_text(640, 140, "email@example.com", size=24, fill="#64748b"))
        svg.append(_svg_rect(52, 198, 796, 2, accent, rx=1))
        svg.append(_svg_text(52, 188, _PREVIEW_CONTACT, size=24, fill="#64748b"))
        y = 228
        svg.append(_svg_text(52, y, "SUMMARY", size=15, weight=700, fill=primary))
        y += 20
        txt, y = _svg_text_lines(52, y, [_PREVIEW_SUMMARY_LINE1[:78], _PREVIEW_SUMMARY_LINE2[:76]], size=24, fill=muted, gap=10)
        svg.append(txt)
        y += 24
        svg.append(_svg_text(52, y, "EXPERIENCE", size=15, weight=700, fill=primary))
        y += 20
        svg.append(_svg_text(52, y, _PREVIEW_EXP_JOB, size=24, weight=600, fill=accent))
        y += 20
        svg.append(_svg_text(52, y, _PREVIEW_EXP_COMBO, size=24, fill=muted))
        y += 20
        svg.append(_svg_text(52, y, _PREVIEW_EXP_DATES, size=24, fill=muted))
        y += 20
        txt, y = _svg_text_lines(52, y, _PREVIEW_EXP_BULLETS[:2], size=24, fill=muted, gap=6)
        svg.append(txt)
        y += 26
        svg.append(_svg_text(52, y, _PREVIEW_EXP_JOB, size=24, weight=600, fill=accent))
        y += 20
        svg.append(_svg_text(52, y, _PREVIEW_EXP_COMBO, size=24, fill=muted))
        y += 20
        svg.append(_svg_text(52, y, _PREVIEW_EXP_DATES, size=24, fill=muted))
        y += 30
        svg.append(_svg_text(52, y, "EDUCATION", size=15, weight=700, fill=primary))
        y += 20
        svg.append(_svg_text(52, y, _PREVIEW_EDU_DEGREE, size=24, weight=600, fill=accent))
        y += 20
        svg.append(_svg_text(52, y, _PREVIEW_EDU_SCHOOL, size=24, fill=muted))
        y += 20
        svg.append(_svg_text(52, y, _PREVIEW_EDU_DATES, size=24, fill=muted))
        y += 44
        svg.append(_svg_text(52, y, "SKILLS", size=15, weight=700, fill=primary))
        y += 20
        for sk in _PREVIEW_SKILLS:
            svg.append(_svg_text(52, y, sk, size=24, fill=ink))
            y += 20
        y += 10
        svg.append(_svg_text(52, y, "REFERENCES", size=15, weight=700, fill=primary))
        y += 20
        svg.append(_svg_text(52, y, _PREVIEW_REFERENCES, size=24, fill=muted))

    elif layout == "clean":
        svg.append(_svg_rect(22, 20, 856, 1240, "#ffffff", rx=14, stroke="#d6dee8"))
        svg.append(_svg_text(450, 86, _PREVIEW_NAME, size=42, weight=800, fill=ink, anchor="middle"))
        svg.append(_svg_text(450, 114, _PREVIEW_JOB_TITLE, size=24, fill="#475569", anchor="middle"))
        svg.append(_svg_text(450, 134, _PREVIEW_CONTACT[:70], size=24, fill="#64748b", anchor="middle"))
        svg.append(_svg_rect(52, 148, 796, 1, accent))
        y = 178
        svg.append(_svg_text(52, y, "SUMMARY", size=15, weight=700, fill=primary))
        y += 20
        txt, y = _svg_text_lines(52, y, [_PREVIEW_SUMMARY_LINE1[:78], _PREVIEW_SUMMARY_LINE2[:76]], size=24, fill=muted, gap=6)
        svg.append(txt)
        y += 22
        svg.append(_svg_text(52, y, "EXPERIENCE", size=15, weight=700, fill=primary))
        y += 20
        svg.append(_svg_text(52, y, _PREVIEW_EXP_JOB, size=24, weight=600, fill=accent))
        y += 20
        svg.append(_svg_text(52, y, _PREVIEW_EXP_COMBO, size=24, fill=muted))
        y += 20
        svg.append(_svg_text(52, y, _PREVIEW_EXP_DATES, size=24, fill=muted))
        y += 20
        txt, y = _svg_text_lines(52, y, _PREVIEW_EXP_BULLETS[:2], size=24, fill=muted, gap=6)
        svg.append(txt)
        y += 28
        svg.append(_svg_text(52, y, _PREVIEW_EXP_JOB, size=24, weight=600, fill=accent))
        y += 20
        svg.append(_svg_text(52, y, _PREVIEW_EXP_COMBO, size=24, fill=muted))
        y += 20
        svg.append(_svg_text(52, y, _PREVIEW_EXP_DATES, size=24, fill=muted))
        y += 20
        txt, y = _svg_text_lines(52, y, _PREVIEW_EXP_BULLETS[:2], size=24, fill=muted, gap=6)
        svg.append(txt)
        y += 26
        svg.append(_svg_text(52, y, "EDUCATION", size=15, weight=700, fill=primary))
        y += 20
        svg.append(_svg_text(52, y, _PREVIEW_EDU_DEGREE, size=24, weight=600, fill=accent))
        y += 20
        svg.append(_svg_text(52, y, _PREVIEW_EDU_SCHOOL, size=24, fill=muted))
        y += 20
        svg.append(_svg_text(52, y, _PREVIEW_EDU_DATES, size=24, fill=muted))
        y += 44
        svg.append(_svg_text(52, y, "SKILLS", size=15, weight=700, fill=primary))
        y += 20
        svg.append(_svg_text(52, y, "  ·  ".join(_PREVIEW_SKILLS), size=24, fill=muted))
        y += 34
        svg.append(_svg_text(52, y, "LANGUAGES", size=15, weight=700, fill=primary))
        y += 20
        svg.append(_svg_text(52, y, "  ·  ".join(_PREVIEW_LANGUAGES_PROF), size=24, fill=muted))
        y += 34
        svg.append(_svg_text(52, y, "REFERENCES", size=15, weight=700, fill=primary))
        y += 20
        svg.append(_svg_text(52, y, _PREVIEW_REFERENCES, size=24, fill=muted))

    else:  # topbar
        svg.append(_svg_rect(22, 20, 856, 1240, "#ffffff", rx=14, stroke="#d6dee8"))
        svg.append(_svg_rect(22, 20, 856, 116, primary, rx=14))
        svg.append(_svg_text(52, 78, _PREVIEW_NAME, size=36, weight=800, fill="#ffffff"))
        svg.append(_svg_text(52, 104, _PREVIEW_JOB_TITLE, size=24, fill="#e2e8f0"))
        svg.append(_svg_text(640, 104, safe_label, size=15, fill="#e2e8f0"))
        svg.append(_svg_text(52, 122, _PREVIEW_CONTACT[:72], size=24, fill="#d1d5db"))
        y = 168
        svg.append(_svg_text(52, y, "SUMMARY", size=15, weight=700, fill=primary))
        y += 20
        txt, y = _svg_text_lines(52, y, [_PREVIEW_SUMMARY_LINE1[:78], _PREVIEW_SUMMARY_LINE2[:76]], size=24, fill=muted, gap=6)
        svg.append(txt)
        y += 24
        svg.append(_svg_text(52, y, "EXPERIENCE", size=15, weight=700, fill=primary))
        y += 20
        svg.append(_svg_text(52, y, _PREVIEW_EXP_JOB, size=24, weight=600, fill=accent))
        y += 20
        svg.append(_svg_text(52, y, _PREVIEW_EXP_COMBO, size=24, fill=muted))
        y += 20
        svg.append(_svg_text(52, y, _PREVIEW_EXP_DATES, size=24, fill=muted))
        y += 20
        txt, y = _svg_text_lines(52, y, _PREVIEW_EXP_BULLETS[:2], size=24, fill=muted, gap=6)
        svg.append(txt)
        y += 28
        svg.append(_svg_text(52, y, _PREVIEW_EXP_JOB, size=24, weight=600, fill=accent))
        y += 20
        svg.append(_svg_text(52, y, _PREVIEW_EXP_COMBO, size=24, fill=muted))
        y += 20
        svg.append(_svg_text(52, y, _PREVIEW_EXP_DATES, size=24, fill=muted))
        y += 28
        svg.append(_svg_text(52, y, "EDUCATION", size=15, weight=700, fill=primary))
        y += 20
        svg.append(_svg_text(52, y, _PREVIEW_EDU_DEGREE, size=24, weight=600, fill=accent))
        y += 20
        svg.append(_svg_text(52, y, _PREVIEW_EDU_SCHOOL, size=24, fill=muted))
        y += 20
        svg.append(_svg_text(52, y, _PREVIEW_EDU_DATES, size=24, fill=muted))
        y += 66
        svg.append(_svg_text(52, y, "SKILLS", size=15, weight=700, fill=primary))
        y += 20
        for sk in _PREVIEW_SKILLS:
            svg.append(_svg_text(52, y, sk, size=24, fill=ink))
            y += 20
        y += 14
        svg.append(_svg_text(52, y, "REFERENCES", size=15, weight=700, fill=primary))
        y += 20
        svg.append(_svg_text(52, y, _PREVIEW_REFERENCES, size=24, fill=muted))

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
