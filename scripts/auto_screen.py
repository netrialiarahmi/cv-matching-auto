#!/usr/bin/env python3
"""
Automated CV Screening Script
Runs daily via GitHub Actions at 7 AM WIB (00:30 UTC) to process new candidates.

Process:
1. Load active job positions from job_positions.csv
2. For each position, fetch candidate data from Google Sheets
3. Check existing results to skip already-processed candidates
4. Download CVs, extract text, and score with Gemini AI
5. Append new screening results to position-specific CSV files
6. Commit changes back to GitHub

This script includes error handling per position to ensure one failure
doesn't block processing of other positions.
"""

import os
import sys
import pandas as pd
from datetime import datetime
import traceback

# Add project root to Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.candidate_processor import (
    fetch_candidates_from_google_sheets,
    build_candidate_context,
    get_candidate_identifier,
    extract_resume_from_url
)
from modules.extractor import extract_text_from_pdf
from modules.scorer import score_with_openrouter
from modules.github_utils import (
    load_job_positions_from_github,
    load_results_from_github,
    save_results_to_github
)


def fetch_candidates_from_file_storage(position_name):
    """
    Fetch candidates from File Storage URL (updated by weekly export workflow).
    This reads from sheet_positions.csv to get the File Storage URL.
    
    Args:
        position_name: Name of the job position
        
    Returns:
        DataFrame or None
    """
    import pandas as pd
    import requests
    from io import BytesIO
    
    try:
        # Read sheet_positions.csv to get File Storage URL
        sheet_positions = pd.read_csv("sheet_positions.csv")
        
        # Find the position
        position_row = sheet_positions[sheet_positions["Nama Posisi"] == position_name]
        
        if position_row.empty:
            print(f"   Position '{position_name}' not found in sheet_positions.csv")
            return None
        
        file_storage_url = position_row.iloc[0].get("File Storage")
        
        if pd.isna(file_storage_url) or not str(file_storage_url).strip():
            print(f"   No File Storage URL found for this position")
            print(f"   (Run weekly-export workflow first to populate File Storage URLs)")
            return None
        
        # Fetch candidates from File Storage URL
        response = requests.get(file_storage_url, timeout=30)
        
        if response.status_code != 200:
            print(f"   Failed to fetch from File Storage (HTTP {response.status_code})")
            return None
        
        # Parse CSV
        candidates_df = pd.read_csv(BytesIO(response.content))
        return candidates_df
        
    except FileNotFoundError:
        print(f"   sheet_positions.csv not found")
        print(f"   (Run weekly-export workflow first to generate this file)")
        return None
    except Exception as e:
        print(f"   Error fetching from File Storage: {e}")
        return None


def get_results_filename(job_position):
    """Generate results filename for a specific job position."""
    # Replace special characters with underscores, remove parentheses
    safe_name = (job_position
                 .replace("(", "")
                 .replace(")", "")
                 .replace("/", "_")
                 .replace("\\", "_")
                 .replace(" ", "_"))
    return f"results/results_{safe_name}.csv"


def screen_position(position_name, job_description):
    """
    Screen new candidates for a specific position.
    
    Args:
        position_name: Name of the job position
        job_description: Full job description text
        
    Returns:
        int: Number of candidates successfully screened
    """
    print(f"\n{'='*70}")
    print(f"Position: {position_name}")
    print(f"{'='*70}")
    
    try:
        # 1. Fetch candidates from File Storage (updated by weekly export workflow)
        print("📋 Fetching candidates from File Storage...")
        candidates_df = fetch_candidates_from_file_storage(position_name)
        
        if candidates_df is None or candidates_df.empty:
            print(f"⏭️  No candidates found for this position")
            return 0
        
        print(f"   Found {len(candidates_df)} total candidates from File Storage")
        
        # 2. Load existing results to identify already-processed candidates
        print("🔍 Checking existing results...")
        position_results_file = get_results_filename(position_name)
        existing_results = load_results_from_github(path=position_results_file)
        
        processed_emails = set()
        if existing_results is not None and not existing_results.empty:
            # Build set of processed candidate emails (case-insensitive)
            processed_emails = set(
                existing_results[existing_results["Candidate Email"].notna()]["Candidate Email"].str.lower()
            )
            print(f"   Found {len(processed_emails)} already-processed candidates")
        else:
            print(f"   No existing results found (first run for this position)")
        
        # 3. Filter new candidates only (by email OR by name+phone if no email)
        new_candidates = []
        skipped_candidates = []  # Track skipped candidates for reporting
        
        # Also track by name+phone for candidates without email
        processed_name_phone = set()
        if existing_results is not None and not existing_results.empty:
            for _, row in existing_results.iterrows():
                name = row.get("Candidate Name", "")
                phone = row.get("Phone", "")
                if pd.notna(name) and pd.notna(phone) and str(name).strip() and str(phone).strip():
                    key = f"{str(name).strip().lower()}_{str(phone).strip()}"
                    processed_name_phone.add(key)
        
        for idx, row in candidates_df.iterrows():
            # Kalibrr export column names: "Alamat Email", etc.
            candidate_email = (
                row.get("Alamat Email") or 
                row.get("Email Address") or 
                row.get("Email Pelamar") or 
                row.get("Candidate Email") or 
                row.get("Email", "")
            )
            
            # Get candidate name for reporting
            first_name = row.get("Nama Depan") or row.get("First Name") or ""
            last_name = row.get("Nama Belakang") or row.get("Last Name") or ""
            candidate_name = f"{first_name} {last_name}".strip()
            if not candidate_name:
                candidate_name = row.get("Candidate Name", "") or row.get("Name", "") or "Unknown"
            
            # Check by email first
            if pd.notna(candidate_email) and str(candidate_email).strip():
                email_lower = str(candidate_email).strip().lower()
                if email_lower in processed_emails:
                    skipped_candidates.append(candidate_name)
                    continue
            else:
                # No email, check by name+phone
                candidate_phone = (
                    row.get("Nomor Handphone") or
                    row.get("Phone Number") or
                    row.get("Telepon") or
                    row.get("Phone", "")
                )
                
                if pd.notna(candidate_name) and pd.notna(candidate_phone):
                    name_phone_key = f"{str(candidate_name).strip().lower()}_{str(candidate_phone).strip()}"
                    if name_phone_key in processed_name_phone:
                        skipped_candidates.append(candidate_name)
                        continue
            
            new_candidates.append(row)
        
        if skipped_candidates:
            print(f"\n   ⏩ Skipping {len(skipped_candidates)} already-analyzed candidates:")
            # Show first 10 names, then "and X more..."
            for i, name in enumerate(skipped_candidates[:10]):
                print(f"      • {name}")
            if len(skipped_candidates) > 10:
                print(f"      ... and {len(skipped_candidates) - 10} more")
        
        if not new_candidates:
            print(f"\n✅ All {len(candidates_df)} candidates already analyzed (no new candidates to screen)")
            return 0
        
        print(f"\n🚀 Starting screening for {len(new_candidates)} new candidates")
        print(f"   ({len(skipped_candidates)} already analyzed, {len(new_candidates)} remaining)\n")
        
        # 4. Process each new candidate
        results = []
        successfully_processed = 0
        failed_count = 0
        
        for idx, candidate in enumerate(new_candidates, 1):
            try:
                # Extract candidate info from Kalibrr export columns
                first_name = candidate.get("Nama Depan") or candidate.get("First Name") or ""
                last_name = candidate.get("Nama Belakang") or candidate.get("Last Name") or ""
                candidate_name = f"{first_name} {last_name}".strip()
                if not candidate_name:
                    candidate_name = candidate.get("Nama") or candidate.get("Name") or "Unknown"
                
                candidate_email = (
                    candidate.get("Alamat Email") or 
                    candidate.get("Email Address") or 
                    candidate.get("Email Pelamar") or 
                    candidate.get("Candidate Email") or 
                    candidate.get("Email", "")
                )
                
                print(f"   [{idx}/{len(new_candidates)}] Processing: {candidate_name}")
                
                # Download and extract CV
                # Kalibrr export uses "Link Resume" (not "Resume Link")
                resume_link = (
                    candidate.get("Link Resume") or 
                    candidate.get("Resume Link") or 
                    candidate.get("Tautan Resume") or 
                    candidate.get("Resume", "")
                )
                
                cv_text = ""
                if pd.notna(resume_link) and str(resume_link).strip():
                    try:
                        # Extract CV with minimal retry (fail fast on errors)
                        cv_text = extract_resume_from_url(resume_link)
                        if cv_text:
                            print(f"       ✓ CV extracted ({len(cv_text)} characters)")
                        else:
                            print(f"       ⚠ CV extraction failed - skipping to next candidate")
                    except KeyboardInterrupt:
                        # Allow manual interruption
                        raise
                    except Exception as e:
                        # Catch all errors including MuPDF/parsing issues
                        print(f"       ⚠ CV extraction error - skipping to next candidate")
                        # Continue processing without CV text
                        cv_text = ""
                else:
                    print(f"       ⚠ No resume link available")
                
                # Build candidate context from CSV data
                context = build_candidate_context(candidate)
                
                # Score with AI (Gemini)
                cv_score = 0
                summary = "No resume available"
                strengths = []
                weaknesses = []
                gaps = []
                
                if cv_text.strip():
                    try:
                        cv_score, summary, strengths, weaknesses, gaps = score_with_openrouter(
                            cv_text, position_name, job_description
                        )
                        print(f"       ✓ AI Score: {cv_score}/100")
                    except Exception as e:
                        print(f"       ❌ AI scoring error: {str(e)}")
                        summary = f"Scoring failed: {str(e)}"
                
                # Build result row
                result = {
                    "Candidate Name": candidate_name,
                    "Candidate Email": candidate_email,
                    "Phone": candidate.get("Nomor Handphone") or candidate.get("Mobile Number") or candidate.get("Telp") or candidate.get("Phone") or "",
                    "Job Position": position_name,
                    "Match Score": cv_score,
                    "AI Summary": summary,
                    "Strengths": "; ".join(strengths) if strengths else "",
                    "Weaknesses": "; ".join(weaknesses) if weaknesses else "",
                    "Gaps": "; ".join(gaps) if gaps else "",
                    "Latest Job Title": candidate.get("Latest Job Title") or candidate.get("Jabatan Terakhir") or "",
                    "Latest Company": candidate.get("Latest Company") or candidate.get("Perusahaan Terakhir") or "",
                    "Education": candidate.get("Tingkat Pendidikan") or candidate.get("Latest Educational Attainment") or candidate.get("Pendidikan") or "",
                    "University": candidate.get("Latest School/University") or candidate.get("Universitas") or "",
                    "Major": candidate.get("Latest Major/Course") or candidate.get("Jurusan") or "",
                    "Kalibrr Profile": candidate.get("Link Profil Kalibrr") or candidate.get("Kalibrr Profile Link") or candidate.get("Profil Kalibrr") or "",
                    "Application Link": candidate.get("Link Aplikasi Pekerjaan") or candidate.get("Job Application Link") or candidate.get("Tautan Lamaran") or "",
                    "Resume Link": resume_link,
                    "Recruiter Feedback": "",
                    "Shortlisted": False,
                    "Candidate Status": "",
                    "Interview Status": "",
                    "Rejection Reason": "",
                    "Date Processed": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }
                
                # Append result immediately to CSV file
                result_df = pd.DataFrame([result])
                if save_results_to_github(result_df, job_position=position_name):
                    print(f"       ✓ Appended to {position_results_file}")
                    results.append(result)
                    successfully_processed += 1
                else:
                    print(f"       ⚠ Failed to append result")
                    failed_count += 1
                
            except KeyboardInterrupt:
                # Allow manual interruption
                print(f"\n⚠️  Processing interrupted by user")
                raise
            except Exception as e:
                error_msg = str(e)[:150]  # Truncate very long error messages
                print(f"       ❌ Skipping candidate due to error: {error_msg}")
                if "MuPDF" in str(e) or "fitz" in str(e):
                    print(f"       (PDF parsing error - candidate will be skipped)")
                failed_count += 1
                # Continue to next candidate - don't let one failure stop the whole process
                continue
        
        # Summary for this position (results already saved individually)
        print(f"\n📊 Position Summary:")
        print(f"   • Total candidates found: {len(candidates_df)}")
        print(f"   • Already analyzed (skipped): {len(skipped_candidates)}")
        print(f"   • New candidates screened: {successfully_processed}")
        if failed_count > 0:
            print(f"   • Failed to process: {failed_count}")
        print(f"   • Total analyzed to date: {len(skipped_candidates) + successfully_processed}")
        
        return successfully_processed
        
    except Exception as e:
        print(f"❌ Error screening position '{position_name}': {str(e)}")
        print(f"   Stack trace: {traceback.format_exc()}")
        return 0


def main():
    """Main entry point for automated screening."""
    print("="*70)
    print("AUTOMATED CV SCREENING")
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*70)
    
    # Check for required API keys
    if not os.getenv("GEMINI_API_KEY") and not os.getenv("OPENROUTER_API_KEY"):
        print("❌ ERROR: No API key found!")
        print("   Please set GEMINI_API_KEY or OPENROUTER_API_KEY environment variable")
        return 1
    
    # 1. Load job positions
    print("\n📂 Loading job positions...")
    try:
        jobs_df = load_job_positions_from_github()
        if jobs_df is None or jobs_df.empty:
            print("❌ No job positions found in job_positions.csv")
            return 1
        
        print(f"   Found {len(jobs_df)} total positions")
    except Exception as e:
        print(f"❌ Error loading job positions: {str(e)}")
        return 1
    
    # 2. Use all positions (we don't check Pooling Status since that's only in sheet_positions.csv)
    active_jobs = jobs_df.copy()
    print(f"✅ Will screen all {len(active_jobs)} positions")
    
    # 3. Screen each active position
    total_screened = 0
    successful_positions = 0
    failed_positions = 0
    
    for idx, job in active_jobs.iterrows():
        position_name = job["Job Position"]
        job_description = job.get("Job Description", "")
        
        if not job_description:
            print(f"\n⚠️  Skipping '{position_name}': No job description available")
            continue
        
        try:
            count = screen_position(position_name, job_description)
            total_screened += count
            if count > 0:
                successful_positions += 1
        except Exception as e:
            print(f"\n❌ Unexpected error screening '{position_name}': {str(e)}")
            print(f"   Stack trace: {traceback.format_exc()}")
            failed_positions += 1
            continue
    
    # 4. Final summary
    print("\n" + "="*70)
    print("SCREENING COMPLETED")
    print("="*70)
    print(f"Total candidates screened: {total_screened}")
    print(f"Positions with new candidates: {successful_positions}")
    if failed_positions > 0:
        print(f"Positions with errors: {failed_positions}")
    print(f"Completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*70)
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
