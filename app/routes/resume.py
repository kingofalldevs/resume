"""
Resume routes: builder, template picker, save, view, download.
"""
import os
import base64
import secrets
import json
import io
import urllib.error
import urllib.request
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, current_app, jsonify, make_response
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from pypdf import PdfReader

from app import db
from app.models import Resume, ResumeSection
from app.services.resume_builder import build_resume_html, TEMPLATES, get_template_catalog

resume_bp = Blueprint("resume", __name__)

PAYSTACK_AMOUNT_GHS = 10
PAYSTACK_AMOUNT_PESEWAS = PAYSTACK_AMOUNT_GHS * 100


def _extract_text_from_pdf(file):
    """Extract text from uploaded PDF."""
    try:
        reader = PdfReader(file)
        return "\n".join(p.extract_text() or "" for p in reader.pages)
    except Exception:
        return ""


def _parse_resume_text(text):
    """Parse resume text with AI and return structured data."""
    from app.services.ai_service import get_suggestions
    # Simple fallback - in production you'd use a dedicated parse API
    return {
        "name": "",
        "role": "",
        "skills": text[:500] if text else "",
        "experience": text[500:1500] if len(text) > 500 else text,
        "education": text[1500:] if len(text) > 1500 else "",
    }


def _save_resume_record(resume_data: dict, user_id: int):
    """Persist resume_data to DB and return created Resume."""
    title = f"Resume - {resume_data.get('role', 'Untitled')}"
    template_name = resume_data.get("template_name", "modern_minimal")
    resume = Resume(user_id=user_id, title=title, template_name=template_name)
    db.session.add(resume)
    db.session.flush()

    sections_data = [
        ("personal", {"name": resume_data.get("name"), "email": resume_data.get("email"), "phone": resume_data.get("phone"), "country": resume_data.get("country"), "links": resume_data.get("links"), "role": resume_data.get("role")}),
        ("summary", {"raw": resume_data.get("career_objective", "") or resume_data.get("abilities", "")}),
        ("experience", {"raw": resume_data.get("experience", "")}),
        ("education", {"raw": resume_data.get("education", "")}),
        ("skills", {"raw": resume_data.get("skills", "")}),
    ]
    for section_type, content in sections_data:
        db.session.add(ResumeSection(resume_id=resume.id, section_type=section_type, content=content))

    db.session.commit()
    return resume


def _paystack_secret_key() -> str:
    """Get Paystack secret key from config or environment."""
    key = current_app.config.get("PAYSTACK_SECRET_KEY", "") or os.environ.get("PAYSTACK_SECRET_KEY", "")
    return key.strip()


def _paystack_headers(secret_key: str, include_json: bool = False) -> dict:
    """Build Paystack headers with a browser-like User-Agent.

    Some edge filters reject generic python-urllib requests that omit User-Agent.
    """
    headers = {
        "Authorization": f"Bearer {secret_key}",
        "User-Agent": "Mozilla/5.0 (compatible; ResumeGhana/1.0; +https://resumeghana.local)",
        "Accept": "application/json",
    }
    if include_json:
        headers["Content-Type"] = "application/json"
    return headers


def _paystack_initialize(email: str, reference: str, callback_url: str, action: str):
    """Initialize Paystack transaction and return authorization URL."""
    secret_key = _paystack_secret_key()
    if not secret_key:
        raise RuntimeError("PAYSTACK_SECRET_KEY not set")

    payload = {
        "email": email,
        "amount": PAYSTACK_AMOUNT_PESEWAS,
        "currency": "GHS",
        "reference": reference,
        "callback_url": callback_url,
        "metadata": {
            "user_id": current_user.id,
            "action": action,
        },
    }
    req = urllib.request.Request(
        "https://api.paystack.co/transaction/initialize",
        data=json.dumps(payload).encode("utf-8"),
        headers=_paystack_headers(secret_key, include_json=True),
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as err:
        raw = err.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Paystack initialize failed ({err.code}): {raw}") from err
    except urllib.error.URLError as err:
        raise RuntimeError(f"Paystack initialize request failed: {err.reason}") from err

    if not body.get("status") or not body.get("data", {}).get("authorization_url"):
        raise RuntimeError(body.get("message") or "Paystack initialize failed")
    return body["data"]["authorization_url"]


def _paystack_verify(reference: str):
    """Verify Paystack transaction by reference."""
    secret_key = _paystack_secret_key()
    if not secret_key:
        raise RuntimeError("PAYSTACK_SECRET_KEY not set")
    req = urllib.request.Request(
        f"https://api.paystack.co/transaction/verify/{reference}",
        headers=_paystack_headers(secret_key),
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as err:
        raw = err.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Paystack verification failed ({err.code}): {raw}") from err
    except urllib.error.URLError as err:
        raise RuntimeError(f"Paystack verification request failed: {err.reason}") from err

    if not body.get("status"):
        raise RuntimeError(body.get("message") or "Paystack verification failed")
    return body.get("data", {})


def _build_download_response(resume_data: dict, resume_id: int | None = None):
    """Create downloadable PDF response for a resume."""
    filename_base = (resume_data.get("name") or "resume").strip().replace(" ", "_")
    filename = f"{filename_base}_resume.pdf"
    template_name = resume_data.get("template_name", "modern_minimal")
    html_fragment = build_resume_html(resume_data, template_name)
    html_doc = (
        "<!DOCTYPE html><html><head><meta charset='utf-8'></head>"
        f"<body>{html_fragment}</body></html>"
    )

    try:
        from xhtml2pdf import pisa  # Lazy import to avoid hard dependency at app boot.
    except Exception as exc:
        raise RuntimeError(
            "PDF engine is not installed. Please install xhtml2pdf and restart the server."
        ) from exc

    pdf_buffer = io.BytesIO()
    result = pisa.CreatePDF(src=html_doc, dest=pdf_buffer, encoding="utf-8")
    if getattr(result, "err", 0):
        raise RuntimeError("Could not generate PDF from resume content.")

    response = make_response(pdf_buffer.getvalue())
    response.headers["Content-Type"] = "application/pdf"
    response.headers["Content-Disposition"] = f'attachment; filename="{filename}"'
    if resume_id is not None:
        response.headers["X-Resume-Id"] = str(resume_id)
    return response


@resume_bp.route("/build", methods=["GET", "POST"])
@login_required
def builder():
    """Multi-step resume builder (6 steps including template choice)."""
    if request.method == "POST":
        resume_data = {}
        if "resume_file" in request.files:
            file = request.files["resume_file"]
            if file.filename:
                text = _extract_text_from_pdf(file)
                if text:
                    resume_data = _parse_resume_text(text)

        if not resume_data:
            experience = request.form.get("experience")
            if not experience:
                parts = []
                for i in range(5):
                    co = request.form.get(f"experience_{i}_company", "").strip()
                    yr = request.form.get(f"experience_{i}_years", "").strip()
                    desc = request.form.get(f"experience_{i}_description", "").strip()
                    if co or yr or desc:
                        parts.append(f"{co} ({yr})\n{desc}")
                experience = "\n\n---\n\n".join(parts)
            education = request.form.get("education")
            if not education:
                edu_parts = []
                for i in range(5):
                    sch = request.form.get(f"education_{i}_school", "").strip()
                    dur = request.form.get(f"education_{i}_duration", "").strip()
                    sk = request.form.get(f"education_{i}_skills", "").strip()
                    if sch or dur or sk:
                        edu_parts.append(f"{sch} ({dur})\n{sk}")
                education = "\n\n---\n\n".join(edu_parts)
            resume_data = {
                "name": request.form.get("name"),
                "phone": request.form.get("phone"),
                "email": request.form.get("email"),
                "country": request.form.get("country"),
                "job_type": request.form.get("job_type"),
                "job_level": request.form.get("job_level"),
                "years_experience": request.form.get("years_experience"),
                "location_target": request.form.get("location_target"),
                "functional_focus": request.form.get("functional_focus"),
                "role": request.form.get("role"),
                "skills": request.form.get("skills"),
                "abilities": request.form.get("abilities"),
                "career_objective": request.form.get("career_objective"),
                "experience": experience,
                "education": education,
                "certifications": request.form.get("certifications"),
                "relevant_coursework": request.form.get("relevant_coursework"),
                "links": request.form.get("links"),
            }
            if "profile_photo" in request.files:
                photo = request.files["profile_photo"]
                if photo.filename:
                    fn = secure_filename(photo.filename)
                    photo.save(os.path.join(current_app.config["UPLOAD_FOLDER"], fn))
                    resume_data["photo_filename"] = fn

        template_name = request.form.get("template_name", session.get("preferred_template", "modern_minimal"))
        if template_name not in TEMPLATES:
            template_name = "modern_minimal"
        resume_data["template_name"] = template_name
        session["preferred_template"] = template_name

        if not resume_data.get("skills") or not resume_data.get("experience"):
            flash("Please provide at least Skills and Experience.", "error")
            return redirect(url_for("resume.builder"))

        session["resume_data"] = resume_data
        return redirect(url_for("resume.template_picker"))

    selected_template = request.args.get("template", session.get("preferred_template", "modern_minimal"))
    if selected_template not in TEMPLATES:
        selected_template = "modern_minimal"
    session["preferred_template"] = selected_template
    return render_template("builder.html", templates=TEMPLATES, selected_template=selected_template)


@resume_bp.route("/templates")
@login_required
def template_picker():
    """Show template picker after resume form is filled."""
    resume_data = session.get("resume_data")
    if not resume_data:
        flash("Please fill in your resume details first.", "error")
        return redirect(url_for("resume.builder"))

    template_catalog = get_template_catalog()
    selected_template = resume_data.get("template_name", session.get("preferred_template", "modern_minimal"))
    if selected_template not in TEMPLATES:
        selected_template = "modern_minimal"
    return render_template(
        "template_picker.html",
        templates=TEMPLATES,
        template_catalog=template_catalog,
        selected_template=selected_template,
        resume_name=resume_data.get("name", "Your Resume"),
    )


@resume_bp.route("/templates/preview", methods=["POST"])
@login_required
def template_preview():
    """AJAX endpoint: render resume with a given template and return HTML."""
    resume_data = session.get("resume_data")
    if not resume_data:
        return jsonify({"error": "No resume data in session."}), 400

    data = request.get_json() or {}
    template_name = data.get("template_name", "modern_minimal")
    if template_name not in TEMPLATES:
        template_name = "modern_minimal"

    html = build_resume_html(resume_data, template_name)
    return jsonify({"html": html})


@resume_bp.route("/templates/select", methods=["POST"])
@login_required
def template_select():
    """Final template selection: render preview and wait for paid action."""
    resume_data = session.get("resume_data")
    if not resume_data:
        flash("Session expired. Please start over.", "error")
        return redirect(url_for("resume.builder"))

    template_name = request.form.get("template_name", "modern_minimal")
    if template_name not in TEMPLATES:
        template_name = "modern_minimal"

    resume_data["template_name"] = template_name
    session["resume_data"] = resume_data
    session["preferred_template"] = template_name

    # Render with chosen template and show
    html = build_resume_html(resume_data, template_name)
    flash("Preview ready. Choose Save or Download to continue to payment.", "info")
    return render_template("tailored.html", content=html, resume_id=None)


@resume_bp.route("/save", methods=["POST"])
@login_required
def save():
    """Legacy endpoint: redirect to paid checkout save flow."""
    return redirect(url_for("resume.checkout", action="save"))


@resume_bp.route("/checkout")
@login_required
def checkout():
    """Checkout/download flow removed; only save remains."""
    resume_data = session.get("resume_data")
    if not resume_data:
        flash("No resume data available. Please build your resume first.", "error")
        return redirect(url_for("resume.builder"))

    action = request.args.get("action", "save").strip().lower()
    if action != "save":
        flash("Download flow has been removed.", "info")
        return redirect(url_for("dashboard.index"))

    template_name = resume_data.get("template_name", "modern_minimal")
    html = build_resume_html(resume_data, template_name)
    public_key = current_app.config.get("PAYSTACK_PUBLIC_KEY", "") or os.environ.get("PAYSTACK_PUBLIC_KEY", "")
    return render_template(
        "pricing_checkout.html",
        content=html,
        action=action,
        amount_ghs=PAYSTACK_AMOUNT_GHS,
        paystack_public_key=public_key,
    )


@resume_bp.route("/checkout/start", methods=["POST"])
@login_required
def checkout_start():
    """Initialize Paystack for save action only."""
    resume_data = session.get("resume_data")
    if not resume_data:
        flash("No resume data available. Please build your resume first.", "error")
        return redirect(url_for("resume.builder"))

    action = request.form.get("action", "save").strip().lower()
    if action != "save":
        flash("Download flow has been removed.", "info")
        return redirect(url_for("dashboard.index"))

    email = (resume_data.get("email") or current_user.email or "").strip()
    if not email:
        flash("A valid email is required to process payment.", "error")
        return redirect(url_for("resume.checkout", action=action))

    reference = f"rg_{current_user.id}_{secrets.token_hex(8)}"
    callback_url = url_for("resume.checkout_callback", _external=True)
    try:
        authorization_url = _paystack_initialize(email=email, reference=reference, callback_url=callback_url, action=action)
    except Exception as e:
        flash(f"Could not start payment: {e}", "error")
        return redirect(url_for("resume.checkout", action=action))

    session["pending_payment"] = {"reference": reference, "action": action}
    return redirect(authorization_url)


@resume_bp.route("/checkout/callback")
@login_required
def checkout_callback():
    """Handle Paystack callback and complete save only."""
    reference = (request.args.get("reference") or request.args.get("trxref") or "").strip()
    pending = session.get("pending_payment") or {}
    expected_ref = pending.get("reference", "")
    action = (pending.get("action") or "save").strip().lower()
    if action != "save":
        flash("Invalid callback action.", "error")
        return redirect(url_for("dashboard.index"))

    if not reference or not expected_ref or reference != expected_ref:
        flash("Invalid or expired payment reference. Please try again.", "error")
        return redirect(url_for("resume.checkout", action=action))

    try:
        payment_data = _paystack_verify(reference)
    except Exception as e:
        flash(f"Payment verification failed: {e}", "error")
        return redirect(url_for("resume.checkout", action=action))

    if payment_data.get("status") != "success":
        flash("Payment was not successful. Please try again.", "error")
        return redirect(url_for("resume.checkout", action=action))

    if int(payment_data.get("amount", 0) or 0) < PAYSTACK_AMOUNT_PESEWAS:
        flash("Payment amount is incomplete. Please contact support.", "error")
        return redirect(url_for("resume.checkout", action=action))

    # Extra ownership check: payment metadata must belong to current user.
    metadata = payment_data.get("metadata") or {}
    metadata_user_id = metadata.get("user_id")
    if metadata_user_id is not None:
        try:
            if int(metadata_user_id) != int(current_user.id):
                flash("Payment user mismatch detected. Please try again.", "error")
                return redirect(url_for("resume.checkout", action=action))
        except (TypeError, ValueError):
            flash("Invalid payment metadata. Please try again.", "error")
            return redirect(url_for("resume.checkout", action=action))

    resume_data = session.get("resume_data")
    if not resume_data:
        flash("Session expired after payment. Please rebuild your resume.", "error")
        return redirect(url_for("resume.builder"))

    session.pop("pending_payment", None)
    if action == "save":
        resume = _save_resume_record(resume_data, current_user.id)
        flash("Payment successful. Resume saved to dashboard.", "success")
        return redirect(url_for("resume.view", id=resume.id))

    flash("Invalid callback action.", "error")
    return redirect(url_for("dashboard.index"))


def _resume_to_data(resume):
    """Build resume_data dict from Resume model for template rendering."""
    data = {"name": resume.title, "role": "", "email": "", "phone": "", "country": "", "links": "", "career_objective": "", "experience": "", "education": "", "skills": ""}
    for sec in resume.sections:
        c = sec.content or {}
        if sec.section_type == "personal":
            data["name"] = c.get("name", data["name"])
            data["role"] = c.get("role", "")
            data["email"] = c.get("email", "")
            data["phone"] = c.get("phone", "")
            data["country"] = c.get("country", "")
            data["links"] = c.get("links", "")
        elif sec.section_type == "summary":
            data["career_objective"] = c.get("raw", c.get("text", ""))
        else:
            data[sec.section_type] = c.get("raw", c.get("text", ""))
    return data


@resume_bp.route("/resume/<int:id>")
@login_required
def view(id):
    """View a saved resume."""
    resume = Resume.query.filter_by(id=id, user_id=current_user.id).first_or_404()
    data = _resume_to_data(resume)
    html = build_resume_html(data, resume.template_name)
    return render_template("tailored.html", content=html, resume_id=resume.id)


@resume_bp.route("/resume/<int:id>/download")
@login_required
def download(id):
    """Download flow removed."""
    flash("Download has been removed from this app.", "info")
    return redirect(url_for("dashboard.index"))


# Legacy route for PDF upload from landing
@resume_bp.route("/build/upload", methods=["POST"])
def build_upload():
    """Handle PDF upload from landing."""
    return redirect(url_for("resume.builder"))
