import os
import re
import json
import streamlit as st
from openai import OpenAI

# Constants for OpenRouter
OPENROUTER_API_BASE = "https://openrouter.ai/api/v1"
DEFAULT_MODEL = "google/gemini-2.5-pro"
OPENROUTER_REFERRER = "https://github.com/netrialiarahmi/cv-matching-gemini"
OPENROUTER_TITLE = "AI CV Matching System"

# =========================
# API Key & Client Handling
# =========================
def _get_api_key():
    key = os.getenv("OPENROUTER_API_KEY")
    if not key and hasattr(st, "secrets"):
        key = st.secrets.get("OPENROUTER_API_KEY")
    if not key:
        raise ValueError("❌ Missing OPENROUTER_API_KEY. Add it in Streamlit Secrets.")
    return key

@st.cache_resource
def get_openrouter_client():
    """Create and cache OpenAI client configured for OpenRouter."""
    api_key = _get_api_key()
    client = OpenAI(
        api_key=api_key,
        base_url=OPENROUTER_API_BASE,
        default_headers={
            "HTTP-Referer": OPENROUTER_REFERRER,
            "X-Title": OPENROUTER_TITLE
        }
    )
    return client


# =========================
# Helpers
# =========================
def _strip_code_fences(text: str) -> str:
    """Remove ```json ... ``` or ``` ... ``` fences if present."""
    if not isinstance(text, str):
        return ""
    s = text.strip()
    m = re.match(r"^```(?:json)?\s*(.*?)\s*```$", s, re.DOTALL | re.IGNORECASE)
    if m:
        return m.group(1).strip()
    return s

def _try_parse_json(text: str):
    """Try hard to parse a JSON object from the model output."""
    if not text:
        return None
    s = _strip_code_fences(text).strip()

    # 1) Try direct parse
    try:
        return json.loads(s)
    except Exception:
        pass

    # 2) Try extracting the outermost {...}
    start = s.find("{")
    end = s.rfind("}")
    if start != -1 and end != -1 and end > start:
        candidate = s[start:end + 1]
        try:
            return json.loads(candidate)
        except Exception:
            pass

    return None

def _ensure_list_str(value):
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    return []

def _clamp_score(value):
    try:
        n = int(value)
    except Exception:
        n = 0
    return max(0, min(100, n))


# =========================
# Main Scoring Function
# =========================
def score_with_openrouter(cv_text, job_position, job_description):
    """Send CV, job position, and JD to OpenRouter (Gemini 2.5 Pro) and return structured evaluation."""
    client = get_openrouter_client()

    prompt = f"""
You are a professional HR assistant. Compare the candidate's CV with the given job position and job description.

Strict rules:
• Evaluate only experience that is relevant to the job scope.
• If the candidate has more relevant years of experience than required, classify it as “exceeds”.
• If the candidate has senior or managerial roles that do not match the required level, classify them as irrelevant, not “exceeds”.
• Do not treat irrelevant seniority as a strength.
• Do not count irrelevant seniority toward total relevant years.
• Exceeding relevant experience may indicate higher salary expectations.

You must add elaboration when:
• The candidate’s recent roles are more senior but not aligned with the required responsibilities.
• The relevant experience comes only from earlier roles.
• The candidate exceeds the required years only based on relevant experience, not based on unrelated senior roles.

Respond only with a valid JSON object (no explanations or extra text) using this exact structure:
{{
"score": <integer 0-100>,
"summary": "2-3 short sentences in English summarizing the main evaluation points",
"strengths": ["strength 1", "strength 2", ...],
"weaknesses": ["weakness 1", "weakness 2", ...],
"gaps": ["gap 1", "gap 2", ...]
}}

Instructions:
• "score": integer 0 to 100.
• "summary": 2-3 concise sentences explaining fit and main factors behind the score.
• "strengths": up to 5 relevant advantages.
• "weaknesses": up to 5 limitations.
• "gaps": up to 5 missing requirements.
• Use elaboration when assessing senior roles that are no longer aligned with the AE level.
• Prioritize match strictly based on the job description.

=== Job Position ===
{job_position}

=== Job Description ===
{job_description}

=== Candidate CV (truncated) ===
{cv_text[:5000]}
"""

    # --- Send to OpenRouter ---
    try:
        response = client.chat.completions.create(
            model=DEFAULT_MODEL,
            messages=[
                {"role": "system", "content": "You are a professional HR assistant that evaluates candidate-job fit."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.2,
            # Encourage strict JSON responses for models that support it
            response_format={"type": "json_object"},
        )

        output = response.choices[0].message.content

        # First, try to parse JSON directly
        data = _try_parse_json(output)

        if isinstance(data, dict):
            score = _clamp_score(data.get("score", 0))
            summary = str(data.get("summary", "")).strip()
            strengths = _ensure_list_str(data.get("strengths", []))
            weaknesses = _ensure_list_str(data.get("weaknesses", []))
            gaps = _ensure_list_str(data.get("gaps", []))

            return score, summary, strengths, weaknesses, gaps

        # Fallback: very defensive extraction if JSON parsing failed
        # Try to extract arrays from JSON-like blocks
        def _extract_json_array(key: str):
            m = re.search(rf'"{key}"\s*:\s*\[(.*?)\]', output, re.DOTALL | re.IGNORECASE)
            if m:
                arr_text = "[" + m.group(1) + "]"
                try:
                    arr = json.loads(arr_text)
                    return _ensure_list_str(arr)
                except Exception:
                    pass
            return []

        score_match = re.search(r'"?score"?\s*[:\-]?\s*(\d{1,3})', output, re.IGNORECASE)
        score = _clamp_score(score_match.group(1) if score_match else 0)

        # Try to grab summary string literal
        summary = ""
        msum = re.search(r'"summary"\s*:\s*"(?P<val>(?:\\.|[^"\\])*)"', output, re.DOTALL | re.IGNORECASE)
        if msum:
            # Unescape common JSON escapes
            summary = msum.group("val").encode("utf-8").decode("unicode_escape").strip()
        if not summary:
            # Last resort: use raw output
            summary = output.strip()

        strengths = _extract_json_array("strengths")
        weaknesses = _extract_json_array("weaknesses")
        gaps = _extract_json_array("gaps")

        return score, summary, strengths, weaknesses, gaps

    except Exception as e:
        st.error(f"⚠️ OpenRouter request failed: {e}")
        return 0, f"[Error] {e}", [], [], []
