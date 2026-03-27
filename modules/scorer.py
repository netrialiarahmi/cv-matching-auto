import os
import re
import json
import time
import sys

# Optional streamlit import - not available in GitHub Actions
try:
    import streamlit as st
    HAS_STREAMLIT = True
except ImportError:
    HAS_STREAMLIT = False
    # Dummy decorator for @st.cache_resource when streamlit is not available
    class _DummyCache:
        def __call__(self, func):
            return func
    st = type('obj', (object,), {
        'secrets': type('obj', (object,), {'get': lambda self, key, default=None: os.getenv(key, default)})(),
        'cache_resource': _DummyCache()
    })()

from openai import OpenAI, RateLimitError

# Logging helper functions for dual-mode operation
def _log_error(message):
    """Log error message - uses st.error in Streamlit, prints to stderr otherwise"""
    if HAS_STREAMLIT:
        st.error(message)
    else:
        print(message, file=sys.stderr)

def _log_warning(message):
    """Log warning message - uses st.warning in Streamlit, prints to stderr otherwise"""
    if HAS_STREAMLIT:
        st.warning(message)
    else:
        print(message, file=sys.stderr)

def _log_info(message):
    """Log info message - uses st.info in Streamlit, prints otherwise"""
    if HAS_STREAMLIT:
        st.info(message)
    else:
        print(message)

# Constants for API configuration (Gemini-only)
GEMINI_API_BASE = "https://generativelanguage.googleapis.com/v1beta"
GEMINI_MODEL_FLASH = "gemini-2.5-flash"   # Fast model for extraction & classification
GEMINI_MODEL_PRO = "gemini-2.5-pro"       # Deep model for evaluation & scoring

# Rate limiting configuration (Gemini paid tier)
REQUEST_DELAY = 2.0  # Delay between requests in seconds (Gemini paid tier allows higher RPM)
MAX_RETRIES = 3  # Maximum number of retries for rate limit errors
RETRY_DELAY = 60  # Initial retry delay for 429 errors in seconds

# =========================
# API Key & Client Handling
# =========================
def _get_api_key():
    """Get Gemini API key from environment or Streamlit secrets."""
    key = os.getenv("GEMINI_API_KEY")
    if not key:
        try:
            key = st.secrets.get("GEMINI_API_KEY")
        except Exception:
            key = None
    
    if key:
        return key
    
    raise ValueError("❌ Missing GEMINI_API_KEY. Add it in .env or Streamlit Secrets.")

@st.cache_resource
def get_gemini_client():
    """Create and cache OpenAI client configured for Gemini API."""
    api_key = _get_api_key()
    return OpenAI(
        api_key=api_key,
        base_url=GEMINI_API_BASE
    )

# Backward-compatible alias
get_openrouter_client = get_gemini_client

def _get_model_name(step="score"):
    """Get the appropriate Gemini model name for the given pipeline step."""
    if step == "extract":
        return GEMINI_MODEL_FLASH
    return GEMINI_MODEL_PRO


# =========================
# Rate Limiting Helper
# =========================
def call_api_with_retry(client, **kwargs):
    """
    Make an API call with rate limiting and retry logic.
    
    Args:
        client: OpenAI client instance
        **kwargs: Arguments to pass to client.chat.completions.create()
    
    Returns:
        Response from the API
    
    Raises:
        Exception: If all retries fail
    """
    last_error = None
    
    for attempt in range(MAX_RETRIES):
        try:
            response = client.chat.completions.create(**kwargs)
            
            # Add delay after successful request to prevent hitting rate limit on next call
            time.sleep(REQUEST_DELAY)
            
            return response
            
        except RateLimitError as e:
            last_error = e
            error_msg = str(e)
            
            # Extract retry delay from error message if available
            retry_delay = RETRY_DELAY
            retry_match = re.search(r'\bretryDelay\s*[:\-=]?\s*["\']?(\d+)', error_msg, re.IGNORECASE)
            if retry_match:
                retry_delay = int(retry_match.group(1))
            
            # Show warning to user
            if attempt < MAX_RETRIES - 1:
                _log_warning(f"⚠️ Rate limit reached (429). Waiting {retry_delay} seconds before retry {attempt + 1}/{MAX_RETRIES}...")
                time.sleep(retry_delay)
            else:
                _log_error(f"❌ Rate limit error after {MAX_RETRIES} attempts. Please try again later.")
        
        except Exception as e:
            # For non-rate-limit errors, raise immediately
            raise e
    
    # If all retries failed, raise the last error
    if last_error:
        raise last_error
    
    raise Exception("API call failed after all retries")


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

    # 0) Strip thinking blocks from Gemini 2.5 models (<think>...</think>)
    s = re.sub(r'<think>.*?</think>', '', s, flags=re.DOTALL).strip()

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
def extract_candidate_info_from_cv(cv_text):
    """Extract candidate information from CV text using AI.
    
    DEPRECATED: Used as fallback only. New code should use extract_and_classify_cv().
    """
    if not cv_text or not cv_text.strip():
        return {
            "latest_job_title": "",
            "latest_company": "",
            "education": "",
            "university": "",
            "major": ""
        }
    
    client = get_gemini_client()
    
    # Limit CV text to ~1000 tokens (approximately 3-4 pages)
    # 1000 tokens ≈ 5000 characters for mixed English/Indonesian content
    cv_text_limited = cv_text[:5000] if len(cv_text) > 5000 else cv_text
    
    prompt = f"""
Extract the following information from this CV/resume text:
1. Latest Job Title (most recent position)
2. Latest Company (most recent workplace)
3. Education Level (e.g., S1, S2, Bachelor's, Master's, etc.)
4. University Name
5. Major/Field of Study

Rules:
- If information is not found, leave it empty
- Return ONLY a JSON object with these exact keys: latest_job_title, latest_company, education, university, major
- Do not add any explanation or extra text

CV Text:
{cv_text_limited}

Return JSON only:
"""
    
    try:
        response = call_api_with_retry(
            client,
            model=_get_model_name("extract"),
            messages=[
                {"role": "system", "content": "You are a data extraction assistant. Return only valid JSON with candidate information."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.1,
            response_format={"type": "json_object"},
            max_tokens=1000
        )
        
        output = response.choices[0].message.content.strip()
        data = _try_parse_json(output)
        
        if isinstance(data, dict):
            return {
                "latest_job_title": str(data.get("latest_job_title", "")).strip(),
                "latest_company": str(data.get("latest_company", "")).strip(),
                "education": str(data.get("education", "")).strip(),
                "university": str(data.get("university", "")).strip(),
                "major": str(data.get("major", "")).strip()
            }
        
        return {
            "latest_job_title": "",
            "latest_company": "",
            "education": "",
            "university": "",
            "major": ""
        }
        
    except Exception as e:
        _log_info(f"ℹ️ Could not extract candidate info from CV: {e}")
        return {
            "latest_job_title": "",
            "latest_company": "",
            "education": "",
            "university": "",
            "major": ""
        }


def extract_candidate_name_from_cv(cv_text):
    """Extract candidate name from CV text using AI.
    
    DEPRECATED: Used for PDF-upload flow only. New pipeline extracts name in extract_and_classify_cv().
    """
    if not cv_text or not cv_text.strip():
        return ""
    
    client = get_gemini_client()
    
    # Use first 1000 characters to find name (usually at the top of CV)
    cv_text_limited = cv_text[:1000] if len(cv_text) > 1000 else cv_text
    
    prompt = f"""
Extract the candidate's full name from this CV/resume text.

Rules:
- Return ONLY the person's full name (first name and last name)
- If the name is not found or unclear, return "Unknown Candidate"
- Do not include titles, degrees, or job positions
- Return just the name, nothing else

CV Text (beginning of resume):
{cv_text_limited}

Return only the name:
"""
    
    try:
        response = call_api_with_retry(
            client,
            model=_get_model_name("extract"),
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
        # Use info instead of warning since name extraction failure is handled gracefully
        _log_info(f"ℹ️ Could not extract name from CV, using default identifier.")
        return "Unknown Candidate"


def score_with_openrouter(cv_text, job_position, job_description, max_retries=2):
    """Legacy scoring function. Evaluates CV against job description using Gemini Pro."""
    client = get_gemini_client()

    prompt = f"""
You are a professional HR assistant. Provide the entire output in Bahasa Indonesia, , including “summary”, “strengths”, “weaknesses”, and “gaps”.. Compare the candidate's CV with the given job position and job description.

Strict rules:
• Evaluate by relevant experiences first, relevant project, relevant courses then education.
• Evaluate only experience that is relevant to the job scope. 
• Reject common false positives. Roles that are not aligned with the required industry or specialization must not be counted as relevant experience.
• Examples of unrelated roles include general retail work, store staff, penjaga toko, general sales, promotional or activation agency work, event organizer tasks, marketplace selling, and broad freelance roles that do not match the job scope.
• If the candidate has more relevant years of experience than required, classify it as "exceeds".
• If the candidate has senior or managerial roles that do not match the required level, classify them as irrelevant, not "exceeds".
• Do not treat irrelevant seniority as a strength.
• Do not count irrelevant seniority toward total relevant years.
• Exceeding relevant experience may indicate higher salary expectations.
• Preferable if the candidate is from one of the top Indonesian universities based on QS Asia rankings: Universitas Indonesia, Universitas Gadjah Mada, Institut Teknologi Bandung, Universitas Airlangga, IPB University, Universitas Padjadjaran, Institut Teknologi Sepuluh Nopember, Universitas Diponegoro, Universitas Brawijaya, Binus University, Telkom University, Universitas Andalas, and Universitas Sumatera Utara.

CRITICAL — Role vs. keyword distinction:
• Do NOT confuse a company name with actual job function. Working at a company named "Bisnis Indonesia" does NOT mean the candidate has business development experience — "Bisnis Indonesia" is the name of a media company/newspaper. Always evaluate the candidate's actual job title, responsibilities, and tasks, not the employer's name.
• Data Analyst, Data Documentation, reporting roles, and other analytical support functions are fundamentally different from Business Development roles. Data Analysts focus on internal data analysis, reporting, and documentation (backward-looking, supportive). Business Development focuses on external market strategy, identifying new opportunities, feasibility studies, client acquisition, and cross-industry analysis (forward-looking, proactive). Do NOT treat Data Analyst experience as equivalent or strongly relevant to Business Development.
• Similarly, distinguish between roles that share surface-level keywords but have different core functions. For example: "Business Analyst" (IT/system requirements) vs "Business Development" (market strategy); "Account Manager" (client servicing) vs "Account Executive" (sales/new business); "Marketing Analyst" (campaign analysis) vs "Market Research" (industry insights). Grade relevance based on actual day-to-day responsibilities, not just title overlap.
• If a candidate's experience is only tangentially related (e.g., they work in a relevant industry but in a completely different function), cap the relevance bonus accordingly. Working in media as a data analyst gives only a small industry-familiarity bonus, not a strong fit score.

You must add elaboration when:
• The candidate's recent roles are more senior but not aligned with the required responsibilities.
• The relevant experience comes only from earlier roles.
• The candidate exceeds the required years only based on relevant experience, not based on unrelated senior roles.
• The candidate's role title or company name is misleadingly similar to the target position but actual responsibilities differ significantly.

CRITICAL:
• You MUST provide ALL fields in the JSON.  
• Do NOT leave strengths, weaknesses, or gaps empty. If necessary, provide general observations.  
• You MUST respond ONLY with a valid JSON object.  
• The JSON must match this structure exactly.  
• ALL content inside the JSON must be written in Bahasa Indonesia.

Use this scoring scale when assigning the score:
• Very strong fit. 85 to 100. Candidate has direct, relevant experience in the SAME role/function AND the same or closely related industry. Tasks and responsibilities closely match the job description. Education aligns with the role. Most requirements met.
• Strong fit. 70 to 84. Candidate has direct experience in a similar role/function with substantial task overlap. Industry may differ but core competencies are transferable and proven. Education mostly aligns. Only minor requirements incomplete.
• Moderate fit. 55 to 69. Candidate has adjacent or partially related experience. Some transferable skills but core role function differs (e.g., analyst in a different specialization, or right function but wrong industry with limited overlap). Education somewhat related. Many requirements missed.
• Weak fit. 30 to 54. Candidate's experience is in a different function with only surface-level keyword overlap. Tasks not aligned with the target role's core responsibilities. Education weakly related. Core requirements missing.
• Not a fit. 0 to 29. No relevant experience. Tasks and industry unrelated. Education does not support the role. Key qualifications not met.

Important: A candidate who works in a tangentially related role (e.g., Data Analyst applying for Business Development) should NOT score above 69 unless they have demonstrated actual business development responsibilities. Industry familiarity alone (e.g., working in media but in a support/analytical role) gives a small bonus but does not push the score into "Strong fit" territory.

Respond only with a valid JSON object (no explanations or extra text) using this exact structure:
{{
"score": <integer 0-100>,
"summary": "2-3 short sentences in Bahasa Indonesia summarizing the main evaluation points",
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

=== Candidate CV (First ~1000 tokens / 3-4 pages) ===
{cv_text[:5000]}
"""

    # --- Send to API and parse response ---
    # Note: call_api_with_retry already handles rate limit retries
    # This loop is only for handling incomplete JSON responses from the model
    for attempt in range(max_retries + 1):
        try:
            response = call_api_with_retry(
                client,
                model=_get_model_name("score"),
                messages=[
                    {"role": "system", "content": "You are a professional HR assistant that evaluates candidate-job fit. Always provide complete JSON responses with all required fields."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.2,
                # Encourage strict JSON responses for models that support it
                response_format={"type": "json_object"},
                max_tokens=5000
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
                
                # If validation fails on first attempts, retry (ask the model again)
                if attempt < max_retries:
                    _log_warning(f"⚠️ Incomplete response from AI (attempt {attempt + 1}/{max_retries + 1}). Retrying...")
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
            
            # Retry if validation fails (ask the model again)
            if attempt < max_retries:
                _log_warning(f"⚠️ Could not parse AI response properly (attempt {attempt + 1}/{max_retries + 1}). Retrying...")
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
            # API errors (including rate limits) are already handled by call_api_with_retry
            # If we get here, it's an unexpected error
            _log_error(f"⚠️ Unexpected error during CV evaluation: {e}")
            return 0, f"Error evaluating candidate: {str(e)}", ["Evaluasi gagal."], ["Evaluasi gagal."], ["Evaluasi gagal."]


def score_table_data(candidate_context, job_position, job_description):
    """Score candidate based on structured table/CSV data.
    
    DEPRECATED: Not called anywhere. Kept for potential future use.
    """
    if not candidate_context or not candidate_context.strip():
        return 0
    
    client = get_gemini_client()
    
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
        response = call_api_with_retry(
            client,
            model=_get_model_name("score"),
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
        _log_warning(f"⚠️ Table data scoring failed: {e}")
        return 0


# =========================
# New 3-Step Scoring Pipeline
# =========================

# Score ceiling rules based on role classification
SCORE_CEILINGS = {
    "different": 54,   # Different function → Weak fit max
    "adjacent": 69,    # Adjacent function → Moderate fit max
}

UNIVERSITY_TOP_TIER = [
    "Universitas Indonesia", "Universitas Gadjah Mada", "Institut Teknologi Bandung",
    "Universitas Airlangga", "IPB University"
]
UNIVERSITY_STRONG = [
    "Universitas Padjadjaran", "Institut Teknologi Sepuluh Nopember",
    "Universitas Diponegoro", "Universitas Brawijaya", "Binus University"
]
UNIVERSITY_BONUS = [
    "Telkom University", "Universitas Andalas", "Universitas Sumatera Utara"
]


def extract_and_classify_cv(cv_text, csv_context, job_position, job_description):
    """Step 1: Extract structured data from CV and classify relevance using Gemini Flash.
    
    Returns dict with candidate info, work experiences with relevance classification,
    role_function_match, and industry_match.
    """
    client = get_gemini_client()
    
    cv_limited = cv_text[:5000] if len(cv_text) > 5000 else cv_text
    csv_limited = csv_context[:2000] if csv_context and len(csv_context) > 2000 else (csv_context or "")
    
    uni_list = ", ".join(UNIVERSITY_TOP_TIER + UNIVERSITY_STRONG + UNIVERSITY_BONUS)
    
    prompt = f"""You are a data extraction and classification assistant for HR screening.

Extract structured information from the candidate's CV and classify how relevant their experience is to the target job.

RULES:
- Extract ALL work experiences, not just the latest.
- For each experience, classify relevance to the target job:
  - "direct": Same role function AND related industry/tasks
  - "partial": Similar function OR transferable skills with significant overlap
  - "tangential": Same industry but different function, or same function but completely different context
  - "none": Unrelated role and industry
- role_function_match: Compare the candidate's PRIMARY career function to the target job:
  - "same": Candidate's main career is the same function as the target
  - "adjacent": Related function with transferable skills (e.g., Marketing Analyst → Business Development)
  - "different": Fundamentally different function (e.g., Data Analyst → Business Development, Reporter → Software Engineer)
- industry_match: Compare candidate's industry experience to the target role's industry:
  - "same": Same industry
  - "related": Related or overlapping industry
  - "different": Unrelated industry

CRITICAL — Avoid false positives:
- Company names are NOT job functions. "Bisnis Indonesia" is a media company, NOT business development.
- Evaluate actual responsibilities, not just title keywords.
- Data Analyst ≠ Business Development. Account Manager ≠ Account Executive. Marketing Analyst ≠ Market Researcher.

Preferred universities (QS Asia rankings): {uni_list}

Return ONLY a valid JSON object:
{{
  "candidate_name": "Full Name",
  "latest_job_title": "Most recent job title",
  "latest_company": "Most recent company",
  "education": {{
    "degree": "S1/S2/etc",
    "university": "University name",
    "major": "Field of study"
  }},
  "is_preferred_university": true/false,
  "work_experiences": [
    {{
      "title": "Job title",
      "company": "Company name",
      "duration": "Duration or date range",
      "responsibilities": "Brief summary of key tasks",
      "relevance": "direct|partial|tangential|none",
      "reasoning": "Why this relevance level"
    }}
  ],
  "total_relevant_years": 0,
  "role_function_match": "same|adjacent|different",
  "industry_match": "same|related|different"
}}

=== Target Job Position ===
{job_position}

=== Job Description ===
{job_description}

=== Candidate CV ===
{cv_limited}

=== Additional Candidate Data (from application form) ===
{csv_limited}

Return JSON only:"""

    # Retry Step 1 up to 2 attempts before giving up
    last_error = None
    for step1_attempt in range(2):
        try:
            response = call_api_with_retry(
                client,
                model=_get_model_name("extract"),
                messages=[
                    {"role": "system", "content": "You are a precise data extraction and classification assistant. Return only valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                response_format={"type": "json_object"},
                max_tokens=3000
            )
            
            output = response.choices[0].message.content
            data = _try_parse_json(output)
            
            if isinstance(data, dict):
                # Ensure required fields exist
                data.setdefault("candidate_name", "")
                data.setdefault("latest_job_title", "")
                data.setdefault("latest_company", "")
                data.setdefault("education", {"degree": "", "university": "", "major": ""})
                data.setdefault("is_preferred_university", False)
                data.setdefault("work_experiences", [])
                data.setdefault("total_relevant_years", 0)
                data.setdefault("role_function_match", "different")
                data.setdefault("industry_match", "different")
                return data
            
            # JSON parsed but not a dict — retry
            last_error = f"Parsed output is {type(data).__name__}, not dict. Raw: {repr(output[:200])}"
            if step1_attempt == 0:
                _log_info(f"ℹ️ Step 1 JSON parse issue, retrying... ({last_error})")
                time.sleep(REQUEST_DELAY)
                continue
            
        except Exception as e:
            last_error = str(e)
            if step1_attempt == 0:
                _log_info(f"ℹ️ Step 1 attempt {step1_attempt+1} failed: {e}. Retrying...")
                time.sleep(REQUEST_DELAY)
                continue
    
    _log_info(f"ℹ️ Step 1 (extract & classify) failed after 2 attempts: {last_error}")
    return None


def evaluate_and_score(classified_data, job_position, job_description):
    """Step 2: Evaluate and score the candidate using structured data via Gemini Pro.
    
    Takes the structured classification from Step 1 (NOT raw CV text) and produces
    a score with evaluation summary.
    
    Returns tuple: (score, summary, strengths, weaknesses, gaps)
    """
    client = get_gemini_client()
    
    # Format the classified data as readable text for the evaluator
    edu = classified_data.get("education", {})
    experiences_text = ""
    for exp in classified_data.get("work_experiences", []):
        experiences_text += f"\n- {exp.get('title', '')} at {exp.get('company', '')} ({exp.get('duration', '')})"
        experiences_text += f"\n  Tasks: {exp.get('responsibilities', '')}"
        experiences_text += f"\n  Relevance: {exp.get('relevance', 'none')} — {exp.get('reasoning', '')}"
    
    prompt = f"""You are a professional HR evaluator. Provide the entire output in Bahasa Indonesia.

You are given PRE-CLASSIFIED candidate data (already analyzed for relevance). Use the classifications as strong guidance for your scoring.

=== Candidate Profile ===
Name: {classified_data.get('candidate_name', 'Unknown')}
Latest Role: {classified_data.get('latest_job_title', 'N/A')} at {classified_data.get('latest_company', 'N/A')}
Education: {edu.get('degree', '')} {edu.get('major', '')} — {edu.get('university', '')}
Preferred University: {'Ya' if classified_data.get('is_preferred_university') else 'Tidak'}
Total Relevant Years: {classified_data.get('total_relevant_years', 0)}
Role Function Match: {classified_data.get('role_function_match', 'different')}
Industry Match: {classified_data.get('industry_match', 'different')}

=== Work Experiences (with relevance classification) ==={experiences_text}

=== Target Job ===
Position: {job_position}
Description: {job_description}

SCORING RULES — You MUST follow these score ceilings:
• role_function_match = "different" → Score MUST NOT exceed 54 (Weak fit)
• role_function_match = "adjacent" → Score MUST NOT exceed 69 (Moderate fit)
• role_function_match = "same" + industry_match = "different" → Score MUST NOT exceed 84
• role_function_match = "same" + industry_match = "same"/"related" → Full range 0-100

Scoring scale:
• 85-100: Very strong fit — direct relevant experience in same role AND related industry
• 70-84: Strong fit — direct experience with substantial task overlap, minor gaps only
• 55-69: Moderate fit — adjacent/partially related experience, some transferable skills
• 30-54: Weak fit — different function with surface-level keyword overlap only
• 0-29: Not a fit — no relevant experience

Additional guidance:
• Preferred university gives a small bonus (+2-5 points) within the allowed range
• Do NOT treat company name as job function
• Working in a tangentially related role (e.g., Data Analyst for Business Development position) stays in Moderate fit or below

Respond with a valid JSON object only:
{{
  "score": <integer 0-100 respecting ceilings above>,
  "summary": "2-3 sentences evaluating fit in Bahasa Indonesia",
  "strengths": ["strength 1", "strength 2", ...],
  "weaknesses": ["weakness 1", "weakness 2", ...],
  "gaps": ["gap 1", "gap 2", ...]
}}

ALL content must be in Bahasa Indonesia. Include at least 1 item per field."""

    try:
        response = call_api_with_retry(
            client,
            model=_get_model_name("score"),
            messages=[
                {"role": "system", "content": "You are a professional HR evaluator. Always respond with complete JSON. All text in Bahasa Indonesia."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.2,
            response_format={"type": "json_object"},
            max_tokens=3000
        )
        
        output = response.choices[0].message.content
        data = _try_parse_json(output)
        
        if isinstance(data, dict):
            score = _clamp_score(data.get("score", 0))
            summary = str(data.get("summary", "")).strip()
            strengths = _ensure_list_str(data.get("strengths", []))
            weaknesses = _ensure_list_str(data.get("weaknesses", []))
            gaps = _ensure_list_str(data.get("gaps", []))
            
            if not summary:
                summary = f"Evaluasi kandidat untuk posisi {job_position}."
            if not strengths:
                strengths = ["Informasi kekuatan tidak tersedia."]
            if not weaknesses:
                weaknesses = ["Informasi kelemahan tidak tersedia."]
            if not gaps:
                gaps = ["Informasi kesenjangan tidak tersedia."]
            
            return score, summary, strengths, weaknesses, gaps
        
        return 0, "Gagal memproses evaluasi.", ["Evaluasi gagal."], ["Evaluasi gagal."], ["Evaluasi gagal."]
        
    except Exception as e:
        _log_info(f"ℹ️ Step 2 (evaluate & score) failed: {e}")
        return 0, f"Error: {str(e)}", ["Evaluasi gagal."], ["Evaluasi gagal."], ["Evaluasi gagal."]


def _apply_score_ceiling(score, classified_data):
    """Apply Python-level score ceiling based on role/industry classification."""
    role_match = classified_data.get("role_function_match", "different")
    industry_match = classified_data.get("industry_match", "different")
    
    if role_match == "different":
        return min(score, SCORE_CEILINGS["different"])
    elif role_match == "adjacent":
        return min(score, SCORE_CEILINGS["adjacent"])
    elif role_match == "same" and industry_match == "different":
        return min(score, 84)
    
    return score


def score_candidate_pipeline(cv_text, csv_context, job_position, job_description):
    """Main pipeline: Extract & Classify (Flash) → Evaluate & Score (Pro) → Ceiling enforcement.
    
    Returns tuple: (score, summary, strengths, weaknesses, gaps, candidate_info)
    where candidate_info is a dict with latest_job_title, latest_company, education, university, major.
    """
    # Step 1: Extract and classify with Gemini Flash
    classified_data = extract_and_classify_cv(cv_text, csv_context, job_position, job_description)
    
    if classified_data is None:
        # Fallback to legacy scoring
        _log_info("ℹ️ Pipeline Step 1 failed, falling back to legacy scoring...")
        score, summary, strengths, weaknesses, gaps = score_with_openrouter(
            cv_text, job_position, job_description
        )
        candidate_info = extract_candidate_info_from_cv(cv_text)
        return score, summary, strengths, weaknesses, gaps, candidate_info
    
    # Step 2: Evaluate and score with Gemini Pro
    score, summary, strengths, weaknesses, gaps = evaluate_and_score(
        classified_data, job_position, job_description
    )
    
    # Step 3: Apply Python-level score ceiling
    original_score = score
    score = _apply_score_ceiling(score, classified_data)
    
    if score != original_score:
        role_match = classified_data.get("role_function_match", "")
        summary += f" [Skor disesuaikan dari {original_score} ke {score} karena role_function_match='{role_match}']"
    
    # Build candidate_info from classified data
    edu = classified_data.get("education", {})
    candidate_info = {
        "latest_job_title": str(classified_data.get("latest_job_title", "")).strip(),
        "latest_company": str(classified_data.get("latest_company", "")).strip(),
        "education": str(edu.get("degree", "")).strip(),
        "university": str(edu.get("university", "")).strip(),
        "major": str(edu.get("major", "")).strip()
    }
    
    return score, summary, strengths, weaknesses, gaps, candidate_info
