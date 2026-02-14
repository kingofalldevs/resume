"""
AI service for resume enhancement and generation.
Uses Hugging Face Inference API (OpenAI-compatible router) for all AI calls.
"""
import json
import os
import re
import urllib.error
import urllib.request
from flask import current_app
from app import db
from app.models import AIUsage
from prompts import (
    RESUME_GENERATION_PROMPT,
    RESUME_WIZARD_PROMPT,
    RESUME_ENHANCER_PROMPT,
)

# Default model – officially recommended chat model on HF Inference API
_DEFAULT_MODEL = "Qwen/Qwen2.5-Coder-32B-Instruct"
_HF_API_URL = "https://router.huggingface.co/v1/chat/completions"


def _get_settings():
    """Resolve Hugging Face settings from app config or environment."""
    api_token = ""
    model = ""
    try:
        api_token = current_app.config.get("HF_API_TOKEN", "")
        model = current_app.config.get("HF_MODEL", "")
    except RuntimeError:
        pass
    if not api_token:
        api_token = os.environ.get("HF_API_TOKEN") or os.environ.get("HF_TOKEN", "")
    if not model:
        model = os.environ.get("HF_MODEL", _DEFAULT_MODEL)
    if not api_token:
        raise ValueError("HF_API_TOKEN not set")
    return api_token, model


def _track_tokens(user_id: int, tokens: int):
    """Record AI token usage for a user."""
    usage = AIUsage(user_id=user_id, tokens_used=tokens)
    db.session.add(usage)
    db.session.commit()


def _extract_json_text(raw_text: str) -> str:
    """Extract JSON object from raw model text output."""
    text = (raw_text or "").strip()
    fenced = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, flags=re.DOTALL)
    if fenced:
        return fenced.group(1).strip()
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        return text[start:end + 1]
    return text


def _hf_text(system_prompt: str, user_content: str, temperature: float = 0.6) -> tuple[str, int]:
    """Call Hugging Face router (OpenAI-compatible) and return plain text + tokens."""
    api_token, model = _get_settings()

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ],
        "max_tokens": 2048,
        "temperature": temperature,
    }
    headers = {
        "Authorization": f"Bearer {api_token}",
        "Content-Type": "application/json",
    }

    req = urllib.request.Request(
        _HF_API_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=90) as resp:
            body = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as err:
        raw = err.read().decode("utf-8", errors="replace") if hasattr(err, "read") else str(err)
        try:
            parsed = json.loads(raw)
            message = parsed.get("error", {}).get("message") or parsed.get("message") or raw
        except Exception:
            message = raw
        if err.code == 401:
            raise RuntimeError("Hugging Face API error: Invalid API token. Check your HF_API_TOKEN.") from err
        if err.code == 429:
            raise RuntimeError("Hugging Face API error: Rate limit exceeded. Please try again later.") from err
        raise RuntimeError(f"Hugging Face API error ({err.code}): {message}") from err
    except urllib.error.URLError as err:
        raise RuntimeError(f"Hugging Face API request failed: {err.reason}") from err

    text = body.get("choices", [{}])[0].get("message", {}).get("content", "")
    usage = body.get("usage", {})
    tokens = int(usage.get("total_tokens", 0) or 0)
    return text.strip(), tokens


def _hf_json(system_prompt: str, user_content: str, temperature: float = 0.6) -> tuple[dict, int]:
    """Call Hugging Face and parse JSON response."""
    guidance = (
        "\n\nReturn only valid JSON. Do not include markdown fences, extra commentary, or text before/after the JSON."
    )
    text, tokens = _hf_text(system_prompt + guidance, user_content, temperature=temperature)
    parsed = json.loads(_extract_json_text(text))
    return parsed, tokens


def enhance_section(section_type: str, content: str, user_id: int = None) -> tuple[str | None, str | None]:
    """
    Enhance a resume section with AI: professional, achievement-oriented, ATS-optimized.
    Returns (enhanced_content, error_message).
    """
    prompt = (
        "Rewrite the following resume content to be professional, achievement-oriented, "
        "and ATS-optimized. Use bullet points and action verbs. Keep it concise."
    )
    user_content = f"Section: {section_type}\n\nContent:\n{content}"

    try:
        result, tokens = _hf_text(prompt, user_content, temperature=0.6)
        if user_id:
            _track_tokens(user_id, tokens)
        return result, None
    except Exception as e:
        return None, str(e)


def get_ai_resume_review(resume_data: dict, user_id: int = None) -> tuple[dict | None, str | None]:
    """Get ATS review and suggestions for resume data."""
    system_prompt = """
    You are an expert AI Career Coach and ATS Specialist.
    Review the resume and return ONLY valid JSON using this structure:
    {
      "score": 1-100,
      "summary": "Explanation of score",
      "strengths": [],
      "weaknesses": [],
      "missing_skills": [],
      "formatting_advice": "",
      "rewritten_bullets": [
        {"original": "", "improved": ""}
      ]
    }
    """
    user_content = f"""
    Name: {resume_data.get('name')}
    Target Role: {resume_data.get('role')}
    Skills: {resume_data.get('skills')}
    Experience: {resume_data.get('experience')}
    Education: {resume_data.get('education')}
    """
    try:
        data, tokens = _hf_json(system_prompt, user_content, temperature=0.6)
        if user_id:
            _track_tokens(user_id, tokens)
        return data, None
    except Exception as e:
        return None, str(e)


def generate_tailored_resume(resume_data: dict, photo_base64: str = None, user_id: int = None) -> tuple[str | None, str | None]:
    """Generate tailored HTML resume from data."""
    ai_data = resume_data.copy()
    ai_data.pop("photo_filename", None)
    if photo_base64:
        ai_data["include_photo_placeholder"] = True

    user_content = f"Rewrite this resume for the role of {resume_data.get('role')}:\n\n{json.dumps(ai_data)}"

    try:
        content, tokens = _hf_text(RESUME_GENERATION_PROMPT, user_content, temperature=0.7)
        if photo_base64:
            content = content.replace("PHOTO_PLACEHOLDER", f"data:image/jpeg;base64,{photo_base64}")

        if user_id:
            _track_tokens(user_id, tokens)
        return content, None
    except Exception as e:
        return None, str(e)


def get_suggestions(step: int, form_data: dict, user_id: int = None) -> tuple[dict | None, str | None]:
    """Get AI suggestions for wizard step or enhancer."""
    if step in (1, 3):
        system_prompt = RESUME_WIZARD_PROMPT
        user_content = f"Current Step: {step}\nUser Data: {json.dumps(form_data)}"
    else:
        system_prompt = RESUME_ENHANCER_PROMPT
        resume_object = {
            "identity": {
                "name": form_data.get("name"),
                "target_title": form_data.get("role"),
                "job_level": form_data.get("job_level"),
                "job_location": form_data.get("location_target"),
            },
            "summary_inputs": {
                "industry": form_data.get("job_type"),
                "years_experience": form_data.get("years_experience"),
                "career_objective": form_data.get("career_objective"),
                "abilities": form_data.get("abilities"),
            },
            "experience": [
                {
                    "role": form_data.get("role"),
                    "bullet_intents": form_data.get("experience", "").split("\n"),
                    "seniority": form_data.get("job_level"),
                }
            ],
            "skills": {
                "technical_or_professional": form_data.get("skills", "").split(",") if form_data.get("skills") else [],
                "soft": [],
            },
            "optional_sections": {
                "certifications": form_data.get("certifications", "").split("\n") if form_data.get("certifications") else [],
                "relevant_coursework": form_data.get("relevant_coursework", "").split(",") if form_data.get("relevant_coursework") else [],
                "projects": [],
                "languages": [],
                "links": {},
            },
            "job_type": form_data.get("job_type"),
        }
        user_content = json.dumps(resume_object)

    try:
        data, tokens = _hf_json(system_prompt, user_content, temperature=0.7)
        if user_id:
            _track_tokens(user_id, tokens)
        return data, None
    except Exception as e:
        return None, str(e)
