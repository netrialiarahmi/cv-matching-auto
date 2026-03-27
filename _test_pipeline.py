"""Quick pipeline test: process 2 candidates from the local Kalibrr export."""
import sys
import os
import pandas as pd
from datetime import datetime

sys.path.insert(0, '.')
from dotenv import load_dotenv
load_dotenv()

from modules.candidate_processor import build_candidate_context, extract_resume_from_url
from modules.scorer import score_candidate_pipeline
from modules.github_utils import parse_kalibrr_date

# Load CSV
csv_path = 'kalibrr_exports/Account_Executive_Pasangiklancom.csv'
df = pd.read_csv(csv_path)
print(f"Loaded {len(df)} candidates from {csv_path}")

# Get job description 
jobs_df = pd.read_csv('job_positions.csv')
row = jobs_df[jobs_df['Job Position'].str.contains('Pasangiklan', na=False)].iloc[0]
position_name = row['Job Position']
job_description = row['Job Description']
print(f"Position: {position_name}")
print(f"JD length: {len(str(job_description))} chars")

# Test with first 2 candidates that have resumes
tested = 0
for idx, candidate in df.iterrows():
    if tested >= 2:
        break
    
    resume_link = candidate.get("Link Resume") or candidate.get("Resume", "")
    if not resume_link or pd.isna(resume_link) or not str(resume_link).strip():
        continue
    
    # Get name
    first_name = candidate.get("First Name") or candidate.get("first_name") or ""
    last_name = candidate.get("Last Name") or candidate.get("last_name") or ""
    name = f"{first_name} {last_name}".strip() or "Unknown"
    email = candidate.get("Email Address") or candidate.get("email") or ""
    
    # Date Applied
    date_applied = parse_kalibrr_date(
        candidate.get("Date Application Started (mm/dd/yy hr:mn)") or
        candidate.get("application.created_at") or ""
    )
    
    print(f"\n{'='*60}")
    print(f"[{tested+1}] {name} ({email})")
    print(f"    Date Applied: {date_applied}")
    print(f"    Resume: {resume_link}")
    
    # Download CV
    try:
        cv_text = extract_resume_from_url(str(resume_link))
        if cv_text:
            print(f"    CV extracted: {len(cv_text)} chars")
        else:
            print(f"    CV extraction failed, skipping")
            continue
    except Exception as e:
        print(f"    CV error: {e}, skipping")
        continue
    
    # Build context from CSV data
    context = build_candidate_context(candidate)
    print(f"    CSV context: {len(context)} chars")
    
    # Run scoring pipeline
    try:
        score, summary, strengths, weaknesses, gaps, info = score_candidate_pipeline(
            cv_text, context, position_name, job_description
        )
        print(f"    Score: {score}/100")
        print(f"    Summary: {summary[:150]}...")
        print(f"    Strengths: {strengths[:2] if strengths else 'None'}")
        print(f"    Info: job_title={info.get('latest_job_title')}, company={info.get('latest_company')}")
        print(f"    Date Applied (parsed): {date_applied}")
        tested += 1
    except Exception as e:
        print(f"    Scoring error: {e}")
        import traceback
        traceback.print_exc()
        tested += 1

print(f"\n{'='*60}")
print(f"Pipeline test complete: {tested} candidates processed")
