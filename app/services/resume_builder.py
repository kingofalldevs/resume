"""
Resume builder service: render structured resumes into multiple styled templates.
"""
import os
import re
from jinja2 import Template

TEMPLATE_CATALOG = [
    {"id": "modern_minimal", "label": "Modern Minimal", "desc": "Clean modern layout for general professional roles.", "base": "modern_minimal"},
    {"id": "corporate_professional", "label": "Corporate Professional", "desc": "Traditional corporate style for business and management.", "base": "corporate_professional"},
    {"id": "creative_designer", "label": "Creative Designer", "desc": "Visual-forward design for creative and product portfolios.", "base": "creative_designer"},
    {"id": "simple_ats", "label": "Simple ATS", "desc": "Highly scannable one-column resume for ATS compatibility.", "base": "simple_ats"},
    {"id": "executive_navy", "label": "Executive Navy", "desc": "Executive profile layout with navy-accent hierarchy.", "base": "corporate_professional"},
    {"id": "executive_charcoal", "label": "Executive Charcoal", "desc": "Neutral executive style with strong document contrast.", "base": "corporate_professional"},
    {"id": "elegant_serif", "label": "Elegant Serif", "desc": "Serif-based formal style for consulting and strategy roles.", "base": "modern_minimal"},
    {"id": "bold_orange", "label": "Bold Orange", "desc": "High-contrast accent style with modern visual emphasis.", "base": "creative_designer"},
    {"id": "clean_slate", "label": "Clean Slate", "desc": "Balanced professional look focused on readability.", "base": "modern_minimal"},
    {"id": "minimal_mono", "label": "Minimal Mono", "desc": "Monochrome minimal layout suitable for technical roles.", "base": "simple_ats"},
    {"id": "two_column_blue", "label": "Two Column Blue", "desc": "Structured two-column format with blue accent rails.", "base": "creative_designer"},
    {"id": "two_column_green", "label": "Two Column Green", "desc": "Two-column structure with calm green highlights.", "base": "creative_designer"},
    {"id": "premium_gold", "label": "Premium Gold", "desc": "Premium resume style with restrained gold accents.", "base": "corporate_professional"},
    {"id": "startup_modern", "label": "Startup Modern", "desc": "Sharp startup-style layout for product and growth roles.", "base": "modern_minimal"},
    {"id": "classic_black", "label": "Classic Black", "desc": "Classic black-and-white formal document presentation.", "base": "simple_ats"},
    {"id": "fresh_teal", "label": "Fresh Teal", "desc": "Contemporary teal style for modern professional branding.", "base": "modern_minimal"},
    {"id": "plum_accent", "label": "Plum Accent", "desc": "Professional layout with refined plum tone accents.", "base": "corporate_professional"},
    {"id": "soft_gray", "label": "Soft Gray", "desc": "Subtle gray styling with understated section contrast.", "base": "simple_ats"},
    {"id": "ivory_professional", "label": "Ivory Professional", "desc": "Warm paper-inspired style for polished applications.", "base": "modern_minimal"},
    {"id": "dark_sidebar", "label": "Dark Sidebar", "desc": "Sidebar-emphasis layout for skill-forward resumes.", "base": "creative_designer"},
]

TEMPLATE_BASE_MAP = {item["id"]: item["base"] for item in TEMPLATE_CATALOG}
TEMPLATES = [item["id"] for item in TEMPLATE_CATALOG]

_BASE_META = {
    "modern_minimal": {
        "category": "Modern Professional",
        "best_for": "Tech, operations, and general roles",
        "ats_score": 90,
        "highlights": [
            "Clean hierarchy for fast recruiter scanning",
            "Balanced white space and strong readability",
            "Works across junior to senior profiles",
        ],
    },
    "corporate_professional": {
        "category": "Corporate Executive",
        "best_for": "Finance, leadership, and management",
        "ats_score": 88,
        "highlights": [
            "Executive tone with formal presentation",
            "Strong section framing for achievements",
            "Great fit for leadership applications",
        ],
    },
    "creative_designer": {
        "category": "Creative Portfolio",
        "best_for": "Design, product, and brand roles",
        "ats_score": 84,
        "highlights": [
            "Distinctive visual structure and personality",
            "Supports portfolio-forward storytelling",
            "Maintains readability with style",
        ],
    },
    "simple_ats": {
        "category": "ATS Optimized",
        "best_for": "High-volume applications and strict ATS",
        "ats_score": 96,
        "highlights": [
            "Maximum ATS compatibility and parsing",
            "No-fuss structure for keyword matching",
            "Best for high-application job searches",
        ],
    },
}

_TEMPLATE_META_OVERRIDES = {
    "modern_minimal": {
        "best_for": "Software, product, and business operations",
        "highlights": [
            "Minimal visual noise, high content focus",
            "Strong readability on mobile and desktop",
            "Safe default for most industries",
        ],
    },
    "executive_navy": {
        "best_for": "Senior management and director applications",
        "ats_score": 89,
        "highlights": [
            "Authority-driven navy color language",
            "Highlights strategic leadership outcomes",
            "Great for board-facing profiles",
        ],
    },
    "executive_charcoal": {
        "best_for": "Consulting and senior professional profiles",
        "ats_score": 90,
    },
    "elegant_serif": {
        "best_for": "Legal, consulting, and strategy applications",
        "ats_score": 87,
    },
    "bold_orange": {
        "best_for": "Customer-facing and growth-focused roles",
        "ats_score": 83,
    },
    "clean_slate": {
        "best_for": "Cross-industry professionals",
        "ats_score": 91,
    },
    "minimal_mono": {
        "best_for": "Engineering and technical roles",
        "ats_score": 95,
    },
    "two_column_blue": {
        "best_for": "Analysts, PMs, and structured CV formats",
        "ats_score": 85,
    },
    "two_column_green": {
        "best_for": "Operations and sustainability-oriented roles",
        "ats_score": 86,
    },
    "premium_gold": {
        "best_for": "Executive and premium personal branding",
        "ats_score": 86,
        "highlights": [
            "Premium visual polish and presentation",
            "Excellent for high-stakes applications",
            "Strong headline and achievement framing",
        ],
    },
    "startup_modern": {
        "best_for": "Startups, growth, and product teams",
        "ats_score": 89,
    },
    "classic_black": {
        "best_for": "Formal applications and traditional employers",
        "ats_score": 94,
    },
    "fresh_teal": {
        "best_for": "Modern business and customer success roles",
        "ats_score": 88,
    },
    "plum_accent": {
        "best_for": "Leadership and specialist expert profiles",
        "ats_score": 87,
    },
    "soft_gray": {
        "best_for": "Administrative and support functions",
        "ats_score": 95,
    },
    "ivory_professional": {
        "best_for": "Consulting and polished professional branding",
        "ats_score": 88,
    },
    "dark_sidebar": {
        "best_for": "Skill-heavy and portfolio-forward resumes",
        "ats_score": 82,
    },
}


def get_template_catalog() -> list[dict]:
    """Template metadata used across dashboard and picker UIs."""
    enriched = []
    for item in TEMPLATE_CATALOG:
        base_meta = _BASE_META.get(item["base"], {})
        override = _TEMPLATE_META_OVERRIDES.get(item["id"], {})
        merged = dict(item)
        merged.update(base_meta)
        merged.update(override)
        enriched.append(merged)
    return enriched


def _ai_enhance(resume_data: dict) -> dict:
    """
    Use AI to generate a professional summary, polish experience bullets,
    optimize keywords, and write a career value statement.
    Returns dict with enhanced fields. Falls back gracefully on error.
    """
    from app.services.ai_service import _hf_json

    role = resume_data.get("role", "Professional")
    skills = resume_data.get("skills", "")
    experience_raw = resume_data.get("experience", "")
    education = resume_data.get("education", "")
    career_objective = resume_data.get("career_objective", "") or resume_data.get("abilities", "")
    job_level = resume_data.get("job_level", "")
    years_exp = resume_data.get("years_experience", "")

    system_prompt = """You are a senior resume writer. Given a candidate's raw resume data, produce polished, professional content.

Return ONLY valid JSON with these keys:
{
  "professional_summary": "A 2-3 sentence professional summary highlighting the candidate's experience, key strengths, and value proposition for the target role. Written in third-person implied (no 'I'). Include industry keywords.",
  "experience_bullets": ["Bullet 1", "Bullet 2", ...],
  "career_value": "A 2-3 sentence closing statement about the candidate's career goals and what unique value they bring to the target role. Forward-looking and specific."
}

Rules for experience_bullets:
- Each bullet MUST start with a strong action verb (Led, Managed, Developed, Implemented, etc.)
- Fix any grammar or spelling errors
- Add quantifiable impact where reasonable (without fabricating numbers)
- Optimize with ATS-friendly keywords for the target role
- Keep each bullet to 1-2 lines max
- Group related items and make them achievement-oriented
- Maintain the original meaning — do not invent new work history"""

    user_content = f"""Target Role: {role}
Career Level: {job_level}
Years of Experience: {years_exp}
Skills: {skills}
Career Objective: {career_objective}
Education: {education}

Raw Experience:
{experience_raw}"""

    try:
        data, _ = _hf_json(system_prompt, user_content, temperature=0.5)
        return {
            "professional_summary": data.get("professional_summary", ""),
            "experience_bullets": data.get("experience_bullets", []),
            "career_value": data.get("career_value", ""),
        }
    except Exception:
        # Graceful fallback — return empty so the builder uses raw data
        return {}


def _load_template(template_name: str) -> str:
    """Load template HTML by name."""
    resolved_name = TEMPLATE_BASE_MAP.get(template_name, template_name)
    path = os.path.join(os.path.dirname(__file__), "..", "templates", "resume_templates", f"{resolved_name}.html")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    return _get_fallback_template()


def _get_fallback_template() -> str:
    """Fallback ATS-safe single-column template."""
    return """
<div class="resume-container" role="document" aria-label="Resume preview">
<style>
.resume-container{max-width:860px;margin:0 auto;padding:24px;border:1px solid #f5d4bd;border-radius:12px;background:#fff;
font-family:'Inter','Segoe UI',sans-serif;color:#1f2937}
h1{margin:0;font-size:30px;color:#ff6600}
.meta{margin-top:8px;font-size:13px;color:#475569;line-height:1.5}
.section{margin-top:18px}
h2{margin:0 0 8px;font-size:13px;text-transform:uppercase;letter-spacing:.08em;color:#ff6600;border-bottom:1px solid #ffe0cc;padding-bottom:6px}
p,li{font-size:13px;line-height:1.55}
ul{margin:6px 0 0 18px}
</style>
<h1>{{ full_name }}</h1>
<div class="meta">{{ contact_line }}</div>
{% if summary %}<section class="section"><h2>Professional Summary</h2><p>{{ summary }}</p></section>{% endif %}
{% if skills %}<section class="section"><h2>Skills</h2><div>{{ skills | safe }}</div></section>{% endif %}
{% if experience %}<section class="section"><h2>Work Experience</h2><div>{{ experience | safe }}</div></section>{% endif %}
{% if education %}<section class="section"><h2>Education</h2><div>{{ education | safe }}</div></section>{% endif %}
{% if projects %}<section class="section"><h2>Projects</h2><div>{{ projects | safe }}</div></section>{% endif %}
{% if certifications %}<section class="section"><h2>Certifications</h2><div>{{ certifications | safe }}</div></section>{% endif %}
{% if career_value %}<section class="section"><h2>Career Objective</h2><p>{{ career_value }}</p></section>{% endif %}
</div>
"""


def _split_entries(text: str) -> list[str]:
    if not text:
        return []
    chunks = re.split(r"\n\s*---+\s*\n|\n{2,}", text.strip())
    return [c.strip() for c in chunks if c.strip()]


def _split_items(text: str) -> list[str]:
    if not text:
        return []
    return [p.strip() for p in re.split(r"[,;\n]+", text) if p.strip()]


def _extract_year_sort_key(date_text: str) -> int:
    if not date_text:
        return 0
    if "present" in date_text.lower():
        return 9999
    years = re.findall(r"(?:19|20)\d{2}", date_text)
    if not years:
        return 0
    return int(years[-1])


def _safe(text: str) -> str:
    return (text or "").strip()


def _normalize_bullet(line: str) -> str:
    line = re.sub(r"^[•\-–—]\s*", "", (line or "").strip())
    if not line:
        return ""
    first = re.split(r"\s+", line, maxsplit=1)[0].lower()
    strong_verbs = {
        "led", "managed", "developed", "implemented", "improved", "optimized", "designed",
        "built", "created", "launched", "coordinated", "analyzed", "delivered", "increased",
        "reduced", "streamlined", "trained", "resolved", "executed", "supported", "drove",
    }
    if first not in strong_verbs:
        line = f"Delivered {line[0].lower() + line[1:]}" if len(line) > 1 else f"Delivered {line.lower()}"
    if not re.search(r"[.!?]$", line):
        line += "."
    return line


def _parse_proficiency_and_context(skill_text: str) -> tuple[str, str, str]:
    text = (skill_text or "").strip()
    if not text:
        return "", "", ""
    # Allow formats like:
    # "Python|Advanced|Built data APIs"
    # "SQL - Intermediate - Reporting automation"
    parts = [p.strip() for p in re.split(r"\s*\|\s*|\s+-\s+", text) if p.strip()]
    if len(parts) >= 3:
        return parts[0], parts[1], " - ".join(parts[2:])
    if len(parts) == 2:
        return parts[0], parts[1], "Applied in real work deliverables and cross-team collaboration."
    return parts[0], "", "Applied in real work deliverables and cross-team collaboration."


def _render_skills_html(skills_text: str) -> str:
    raw = _split_items(skills_text)
    if not raw:
        return ""

    soft_keywords = {
        "communication", "leadership", "teamwork", "collaboration", "problem solving",
        "adaptability", "critical thinking", "time management", "negotiation", "creativity",
    }
    tool_keywords = {
        "excel", "power bi", "tableau", "jira", "figma", "photoshop", "illustrator", "canva",
        "notion", "slack", "trello", "salesforce", "quickbooks", "sap", "wordpress",
    }
    spoken_languages = {
        "english", "french", "spanish", "german", "arabic", "swahili", "twi", "ga", "hausa",
    }

    categories = {
        "Technical Skills": [],
        "Soft Skills": [],
        "Tools": [],
        "Languages": [],
    }

    for skill in raw:
        s, prof, ctx = _parse_proficiency_and_context(skill)
        if not s:
            continue
        lower = s.lower()
        if lower in spoken_languages:
            categories["Languages"].append((s, prof or "Advanced", ctx))
        elif lower in soft_keywords:
            categories["Soft Skills"].append((s, prof or "Advanced", ctx))
        elif lower in tool_keywords:
            categories["Tools"].append((s, prof or "Intermediate", ctx))
        else:
            categories["Technical Skills"].append((s, prof or "Intermediate", ctx))

    lines = []
    for section in ("Technical Skills", "Soft Skills", "Tools", "Languages"):
        entries = categories[section]
        if not entries:
            continue
        lines.append(f"<div class='skill-group'><h3>{section}</h3><ul>")
        for name, prof, ctx in entries:
            if prof and ctx:
                lines.append(f"<li><strong>{name}</strong> - <em>{prof}</em>: {ctx}</li>")
            elif prof:
                lines.append(f"<li><strong>{name}</strong> - <em>{prof}</em></li>")
            elif ctx:
                lines.append(f"<li><strong>{name}</strong>: {ctx}</li>")
            else:
                lines.append(f"<li><strong>{name}</strong></li>")
        lines.append("</ul></div>")
    return "".join(lines)


def _render_experience_html(resume_data: dict, ai_bullets: list[str]) -> str:
    entries = []
    for block in _split_entries(resume_data.get("experience", "")):
        lines = [l.strip() for l in block.splitlines() if l.strip()]
        if not lines:
            continue
        header = lines[0]
        date_match = re.search(r"\(([^)]+)\)", header)
        date_text = date_match.group(1).strip() if date_match else ""
        company = re.sub(r"\s*\([^)]*\)\s*$", "", header).strip()
        bullets = [_normalize_bullet(l) for l in lines[1:]]
        bullets = [b for b in bullets if b]
        # Skip empty entries with no company and no bullets.
        if not company and not bullets:
            continue
        entries.append(
            {
                "job_title": (resume_data.get("role") or "").strip(),
                "company": company,
                "location": (resume_data.get("location_target") or resume_data.get("country") or "").strip(),
                "dates": date_text,
                "bullets": bullets,
                "sort_key": _extract_year_sort_key(date_text),
            }
        )

    if not entries and ai_bullets:
        fallback_bullets = [_normalize_bullet(b) for b in ai_bullets[:5]]
        fallback_bullets = [b for b in fallback_bullets if b]
        if fallback_bullets:
            entries.append(
                {
                    "job_title": (resume_data.get("role") or "").strip(),
                    "company": "",
                    "location": (resume_data.get("location_target") or resume_data.get("country") or "").strip(),
                    "dates": "",
                    "bullets": fallback_bullets,
                    "sort_key": 0,
                }
            )

    entries.sort(key=lambda e: e["sort_key"], reverse=True)
    output = []
    for idx, entry in enumerate(entries, start=1):
        heading_parts = [p for p in [entry["job_title"], entry["company"]] if p]
        if not heading_parts and not entry["bullets"]:
            continue
        output.append("<article class='item'>")
        if heading_parts:
            output.append(f"<h3>{' | '.join(heading_parts)}</h3>")
        meta_parts = []
        if entry["location"]:
            meta_parts.append(entry["location"])
        if entry["dates"]:
            meta_parts.append(entry["dates"])
        if meta_parts:
            output.append(f"<p class='meta'>{' | '.join(meta_parts)}</p>")
        if entry["bullets"]:
            output.append("<ul>")
            for b in entry["bullets"]:
                output.append(f"<li>{b}</li>")
            output.append("</ul>")
        output.append("</article>")
    return "".join(output)


def _render_education_html(resume_data: dict) -> str:
    entries = _split_entries(resume_data.get("education", ""))
    if not entries:
        return ""

    output = []
    for idx, block in enumerate(entries, start=1):
        lines = [l.strip() for l in block.splitlines() if l.strip()]
        if not lines:
            continue
        first = lines[0]
        date_match = re.search(r"\(([^)]+)\)", first)
        years = date_match.group(1).strip() if date_match else ""
        institution = re.sub(r"\s*\([^)]*\)\s*$", "", first).strip()
        degree = lines[1] if len(lines) > 1 else ""
        extras = "; ".join(lines[2:]).strip()
        if not any([degree, institution, years, extras]):
            continue
        output.append("<article class='item'>")
        if degree:
            output.append(f"<h3>{degree}</h3>")
        elif institution:
            output.append(f"<h3>{institution}</h3>")
        details = []
        if degree:
            details.append(f"Degree: {degree}")
        if institution:
            details.append(f"Institution: {institution}")
        if _safe(resume_data.get("country", "")):
            details.append(f"Location: {resume_data.get('country').strip()}")
        if years:
            details.append(f"Years: {years}")
        if extras:
            details.append(f"GPA/Honors: {extras}")
        if details:
            output.append(f"<p class='meta'>{' | '.join(details)}</p>")
        output.append("</article>")
    return "".join(output)


def _render_projects_html(resume_data: dict) -> str:
    raw = resume_data.get("projects", "") or resume_data.get("relevant_coursework", "")
    items = _split_entries(raw)
    if not items:
        return ""
    output = []
    for item in items:
        parts = [p.strip() for p in item.splitlines() if p.strip()]
        if len(parts) < 2:
            continue
        name = parts[0]
        desc = parts[1]
        tech = parts[2] if len(parts) > 2 else ""
        impact = parts[3:] if len(parts) > 3 else []
        output.append("<article class='item'>")
        output.append(f"<h3>{name}</h3>")
        output.append(f"<p>{desc}</p>")
        if tech:
            output.append(f"<p class='meta'><strong>Technologies:</strong> {tech}</p>")
        if impact:
            output.append("<ul>")
            for line in impact:
                b = _normalize_bullet(line)
                if b:
                    output.append(f"<li>{b}</li>")
            output.append("</ul>")
        output.append("</article>")
    return "".join(output)


def _render_certifications_html(resume_data: dict) -> str:
    raw_entries = _split_entries(resume_data.get("certifications", ""))
    if not raw_entries:
        return ""
    output = []
    idx = 1
    for item in raw_entries:
        parts = [p.strip() for p in re.split(r"\s*\|\s*|\s*-\s*", item) if p.strip()]
        if len(parts) < 3:
            continue
        name, issuer, year = parts[0], parts[1], parts[2]
        if not all([name, issuer, year]):
            continue
        output.append("<article class='item'>")
        output.append(f"<h3>{name}</h3>")
        output.append(f"<p class='meta'>{issuer} | {year}</p>")
        output.append("</article>")
        idx += 1
    return "".join(output)


def _build_summary_text(resume_data: dict, enhanced: dict) -> str:
    role = (resume_data.get("role") or "").strip()
    years = (resume_data.get("years_experience") or "").strip()
    skills = _split_items(resume_data.get("skills", ""))
    top_strengths = ", ".join(skills[:3]) if skills else ""
    ai_summary = (enhanced.get("professional_summary") or "").strip()

    base = ai_summary
    if not base:
        parts = []
        if role and years:
            parts.append(f"{role} with {years} years of experience delivering high-quality outcomes.")
        elif role:
            parts.append(f"{role} with a track record of reliable, high-quality delivery.")
        elif years:
            parts.append(f"Professional with {years} years of practical experience across core responsibilities.")
        if top_strengths:
            parts.append(f"Core strengths include {top_strengths}.")
        if parts:
            parts.append(
                "Known for translating business goals into measurable execution and strong stakeholder value."
            )
        base = " ".join(parts).strip()
    if not base:
        return ""

    clean = re.sub(r"\s+", " ", base).strip()
    return clean


def build_resume_html(resume_data: dict, template_name: str = "modern_minimal") -> str:
    """Build final styled HTML resume from selected template."""
    enhanced = _ai_enhance(resume_data)
    template_name = template_name if template_name in TEMPLATES else "modern_minimal"
    html_template = _load_template(template_name)

    full_name = _safe(resume_data.get("name", ""))
    role = _safe(resume_data.get("role", ""))
    email = _safe(resume_data.get("email", ""))
    phone = _safe(resume_data.get("phone", ""))
    country = _safe(resume_data.get("country", ""))
    links = ", ".join(_split_items(resume_data.get("links", "")))
    summary = _build_summary_text(resume_data, enhanced)
    skills = _render_skills_html(resume_data.get("skills", ""))
    experience = _render_experience_html(resume_data, enhanced.get("experience_bullets", []))
    education = _render_education_html(resume_data)
    projects = _render_projects_html(resume_data)
    certifications = _render_certifications_html(resume_data)
    career_value = _safe(resume_data.get("career_objective", "")) or _safe(enhanced.get("career_value", ""))

    contact_parts = [p for p in [email, phone, country, links] if p]
    contact_line = " | ".join(contact_parts)

    context = {
        "full_name": full_name,
        "role": role,
        "email": email,
        "phone": phone,
        "country": country,
        "links": links,
        "contact_line": contact_line,
        "summary": summary,
        "skills": skills,
        "experience": experience,
        "education": education,
        "projects": projects,
        "certifications": certifications,
        "career_value": career_value,
    }
    return Template(html_template).render(**context)


def build_resume_text(resume_data: dict) -> str:
    """Legacy plain-text export helper."""
    summary = _build_summary_text(resume_data, _ai_enhance(resume_data))
    lines = []
    name = _safe(resume_data.get("name", ""))
    if name:
        lines.append(name.upper())
    role = _safe(resume_data.get("role", ""))
    if role:
        lines.append(role)
    contact_parts = [p for p in [_safe(resume_data.get("email", "")), _safe(resume_data.get("phone", "")), _safe(resume_data.get("country", ""))] if p]
    if contact_parts:
        lines.append(" | ".join(contact_parts))
    if summary:
        lines.extend(["", "PROFESSIONAL SUMMARY", summary])
    return "\n".join(lines).strip() + ("\n" if lines else "")
