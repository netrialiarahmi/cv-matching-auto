# Scoring Pipeline Architecture

## Overview

The CV matching system uses a **3-step AI pipeline** to evaluate candidates against job descriptions. This replaces the previous single-pass scoring approach, providing more accurate and explainable results.

```
Step 0: Smart Text Extraction (local, no AI)
  PDF → extract_text_from_pdf() → clean_cv_text() → cleaned text
  CSV row → build_candidate_context() → structured context

Step 1: Extract & Classify (gemini-2.5-flash)
  Cleaned CV + CSV context + JD → structured candidate profile with relevance classification

Step 2: Evaluate & Score (gemini-2.5-pro)
  Structured profile from Step 1 + JD → score + evaluation summary

Step 3: Score Ceiling Enforcement (Python, no AI)
  Apply hard caps based on role_function_match and industry_match
```

## Model Strategy

| Step | Model | Purpose | Temperature |
|------|-------|---------|-------------|
| 1 - Extract & Classify | `gemini-2.5-flash` | Fast structured extraction, relevance classification | 0.1 |
| 2 - Evaluate & Score | `gemini-2.5-pro` | Deep reasoning for evaluation and scoring | 0.2 |

**API calls per candidate: 2** (down from 3 in the previous architecture)

## Step Details

### Step 0: Smart Text Extraction

**Module:** `modules/extractor.py`

- `extract_text_from_pdf()` — Extracts text via PyMuPDF, max 50 pages
- `clean_cv_text()` — Removes PDF noise (page numbers, decorators, excess whitespace)
- `build_candidate_context()` — Formats CSV/application data into structured text

**Character limits:** CV text truncated to 5000 chars, CSV context to 2000 chars for API calls.

### Step 1: Extract & Classify

**Function:** `extract_and_classify_cv(cv_text, csv_context, job_position, job_description)`

**Input:** Cleaned CV text + CSV context + job description

**Output JSON:**
```json
{
  "candidate_name": "Full Name",
  "latest_job_title": "Most recent position",
  "latest_company": "Most recent company",
  "education": {"degree": "S1", "university": "...", "major": "..."},
  "is_preferred_university": true/false,
  "work_experiences": [
    {
      "title": "Job title",
      "company": "Company",
      "duration": "2 years",
      "responsibilities": "Key tasks",
      "relevance": "direct|partial|tangential|none",
      "reasoning": "Why this classification"
    }
  ],
  "total_relevant_years": 3,
  "role_function_match": "same|adjacent|different",
  "industry_match": "same|related|different"
}
```

**Key classifications:**
- `role_function_match` — Is the candidate's career function the same as the target role?
- `industry_match` — Does the candidate's industry experience align?
- Per-experience `relevance` — How relevant is each individual work experience?

### Step 2: Evaluate & Score

**Function:** `evaluate_and_score(classified_data, job_position, job_description)`

**Input:** Structured JSON from Step 1 (NOT raw CV text)

**Output:** `(score, summary, strengths, weaknesses, gaps)` — all in Bahasa Indonesia

**Scoring scale:**
| Range | Classification | Description |
|-------|---------------|-------------|
| 85-100 | Very strong fit | Direct relevant experience, same role AND related industry |
| 70-84 | Strong fit | Substantial task overlap, minor gaps |
| 55-69 | Moderate fit | Adjacent/partially related, transferable skills |
| 30-54 | Weak fit | Different function, surface-level overlap only |
| 0-29 | Not a fit | No relevant experience |

### Step 3: Score Ceiling Enforcement

**Function:** `_apply_score_ceiling(score, classified_data)`

Hard Python-level caps that override AI scoring:

| Condition | Maximum Score |
|-----------|--------------|
| `role_function_match == "different"` | 54 |
| `role_function_match == "adjacent"` | 69 |
| `role_function_match == "same"` + `industry_match == "different"` | 84 |
| `role_function_match == "same"` + `industry_match == "same"/"related"` | 100 (no cap) |

When a ceiling is applied, the summary is appended with the adjustment note.

## University Preference

Candidates from these universities receive a small bonus (+2-5 points within allowed range):

**Top Tier:** Universitas Indonesia, UGM, ITB, Unair, IPB

**Strong:** Unpad, ITS, Undip, UB, Binus

**Bonus:** Telkom University, Universitas Andalas, USU

## Fallback Behavior

If Step 1 fails (e.g., API error, unparseable response), the pipeline falls back to the legacy `score_with_openrouter()` + `extract_candidate_info_from_cv()` functions, which still use Gemini Pro directly.

## Case Study: Haratwadi Handoko

**Before (single-pass scoring):** Score 78 for Business Development Analyst
- AI confused company name "Bisnis Indonesia" (media company) with business development experience
- Data Analyst role textually matched BusDev keywords but functionally different

**After (3-step pipeline):** Expected score 55-65
- Step 1 correctly classifies: `role_function_match: "different"` (Data Analyst ≠ Business Development)
- Step 3 caps score at max 54 due to "different" classification
- Result: accurate evaluation reflecting actual fit

## Rate Limiting

- Delay between requests: 2.0 seconds (Gemini paid tier)
- Max retries on 429 errors: 3
- Retry delay: 60 seconds (or as specified in error response)
