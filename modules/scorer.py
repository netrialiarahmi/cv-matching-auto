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
def extract_candidate_name_from_cv(cv_text):
    """Extract candidate name from CV text using AI."""
    if not cv_text or not cv_text.strip():
        return ""
    
    client = get_openrouter_client()
    
    prompt = f"""
Extract the candidate's full name from this CV/resume text.

Rules:
- Return ONLY the person's full name (first name and last name)
- If the name is not found or unclear, return "Unknown Candidate"
- Do not include titles, degrees, or job positions
- Return just the name, nothing else

CV Text (first 1000 characters):
{cv_text[:1000]}

Return only the name:
"""
    
    try:
        response = client.chat.completions.create(
            model=DEFAULT_MODEL,
            messages=[
                {"role": "system", "content": "You are a name extraction assistant. Return only the candidate's full name."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.1,
            max_tokens=2048
        )
        
        name = response.choices[0].message.content.strip()
        # Clean up common artifacts
        name = name.replace('"', '').replace("'", '').strip()
        
        # If name is too long or contains weird patterns, return Unknown
        if len(name) > 100 or '\n' in name:
            return "Unknown Candidate"
        
        return name if name else "Unknown Candidate"
        
    except Exception as e:
        return "Unknown Candidate"


def score_with_openrouter(cv_text, job_position, job_description, max_retries=2):
    """Send CV, job position, and JD to OpenRouter (Gemini 2.5 Pro) and return structured evaluation."""
    client = get_openrouter_client()

    prompt = f"""
You are a professional HR assistant. Provide Explanation in Bahasa Indonesia. Compare the candidate's CV with the given job position and job description.

Strict rules:
• Evaluate only experience that is relevant to the job scope.
• If the candidate has more relevant years of experience than required, classify it as "exceeds".
• If the candidate has senior or managerial roles that do not match the required level, classify them as irrelevant, not "exceeds".
• Do not treat irrelevant seniority as a strength.
• Do not count irrelevant seniority toward total relevant years.
• Exceeding relevant experience may indicate higher salary expectations.

You must add elaboration when:
• The candidate's recent roles are more senior but not aligned with the required responsibilities.
• The relevant experience comes only from earlier roles.
• The candidate exceeds the required years only based on relevant experience, not based on unrelated senior roles.

CRITICAL: You MUST provide ALL fields in your response. Never leave strengths, weaknesses, or gaps empty.
If you cannot find specific strengths/weaknesses/gaps, provide at least one general observation for each.

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
• "strengths": MUST include at least 1 item, up to 5 relevant advantages.
• "weaknesses": MUST include at least 1 item, up to 5 limitations.
• "gaps": MUST include at least 1 item, up to 5 missing requirements.
• Use elaboration when assessing senior roles that are no longer aligned with.
• Prioritize match strictly based on the job description.

=== Job Position ===
{job_position}

=== Job Description ===
{job_description}

=== Candidate CV ===
{cv_text[:4000]}
"""

    # --- Send to OpenRouter with retry logic ---
    for attempt in range(max_retries + 1):
        try:
            response = client.chat.completions.create(
                model=DEFAULT_MODEL,
                messages=[
                    {"role": "system", "content": "You are a professional HR assistant that evaluates candidate-job fit. Always provide complete JSON responses with all required fields."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.2,
                # Encourage strict JSON responses for models that support it
                response_format={"type": "json_object"},
                max_tokens=3000
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

                # Validate that we have meaningful data
                if summary and len(strengths) > 0 and len(weaknesses) > 0 and len(gaps) > 0:
                    return score, summary, strengths, weaknesses, gaps
                
                # If validation fails on first attempts, retry
                if attempt < max_retries:
                    continue
                
                # On final attempt, provide defaults for empty fields
                if not summary:
                    summary = f"Candidate evaluation for {job_position} position."
                if len(strengths) == 0:
                    strengths = ["Informasi kekuatan tidak tersedia dari analisis CV."]
                if len(weaknesses) == 0:
                    weaknesses = ["Informasi kelemahan tidak tersedia dari analisis CV."]
                if len(gaps) == 0:
                    gaps = ["Informasi kesenjangan tidak tersedia dari analisis CV."]
                
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
                # Try to extract any text that looks like a summary
                summary_alt = re.search(r'"summary"\s*:\s*"([^"]+)"', output, re.IGNORECASE)
                if summary_alt:
                    summary = summary_alt.group(1).strip()

            strengths = _extract_json_array("strengths")
            weaknesses = _extract_json_array("weaknesses")
            gaps = _extract_json_array("gaps")
            
            # Validate extracted data
            if summary and len(strengths) > 0 and len(weaknesses) > 0 and len(gaps) > 0:
                return score, summary, strengths, weaknesses, gaps
            
            # Retry if validation fails
            if attempt < max_retries:
                continue
            
            # Provide defaults on final attempt
            if not summary:
                summary = f"Candidate evaluation for {job_position} position. Score: {score}"
            if len(strengths) == 0:
                strengths = ["Informasi kekuatan tidak tersedia dari analisis CV."]
            if len(weaknesses) == 0:
                weaknesses = ["Informasi kelemahan tidak tersedia dari analisis CV."]
            if len(gaps) == 0:
                gaps = ["Informasi kesenjangan tidak tersedia dari analisis CV."]

            return score, summary, strengths, weaknesses, gaps

        except Exception as e:
            if attempt < max_retries:
                continue  # Retry on error
            st.error(f"⚠️ OpenRouter request failed after {max_retries + 1} attempts: {e}")
            return 0, f"Error evaluating candidate: {str(e)}", ["Evaluasi gagal."], ["Evaluasi gagal."], ["Evaluasi gagal."]


def score_table_data(candidate_context, job_position, job_description):
    """
    Score candidate based on structured table/CSV data.
    This evaluates the structured information from the CSV independently from the CV.
    Returns a score from 0-100.
    """
    if not candidate_context or not candidate_context.strip():
        return 0
    
    client = get_openrouter_client()
    
    prompt = f"""
You are an HR evaluator AI. Evaluate the candidate's structured data against the job requirements.

Focus on:
- Work experience relevance (job titles, companies, duration)
- Education match (degree level, major, university)
- Career progression and job level alignment
- Data completeness and quality

Respond only with a valid JSON object:
{{
"score": <integer 0-100>
}}

Guidelines:
- 90-100: Excellent match in all areas
- 70-89: Strong match with minor gaps
- 50-69: Moderate match, some concerns
- 30-49: Weak match, significant gaps
- 0-29: Poor match, major misalignment

=== Job Position ===
{job_position}

=== Job Description ===
{job_description}

=== Candidate Structured Data ===
{candidate_context}
"""

    try:
        response = client.chat.completions.create(
            model=DEFAULT_MODEL,
            messages=[
                {"role": "system", "content": "You are an HR evaluator AI that scores candidate data quality and job fit."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.2,
            response_format={"type": "json_object"},
            max_tokens=2048
        )
        
        output = response.choices[0].message.content
        data = _try_parse_json(output)
        
        if isinstance(data, dict):
            score = _clamp_score(data.get("score", 0))
            return score
        
        # Fallback: try to extract score
        score_match = re.search(r'"?score"?\s*[:\-]?\s*(\d{1,3})', output, re.IGNORECASE)
        score = _clamp_score(score_match.group(1) if score_match else 0)
        return score
        
    except Exception as e:
        st.warning(f"⚠️ Table data scoring failed: {e}")
        return 0
