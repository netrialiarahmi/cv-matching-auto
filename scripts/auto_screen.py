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
from modules.scorer import score_candidate_pipeline
from modules.github_utils import (
    load_job_positions_from_github,
    load_results_from_github,
    save_results_to_github,
    parse_kalibrr_date
)
from modules.usage_logger import log_cv_processing, print_daily_summary
import requests


def fetch_candidates_from_sheet_csv(csv_url):
    """
    Fetch candidates from CSV (local file path or remote URL).
    
    Args:
        csv_url: Local file path or direct URL to CSV file
        
    Returns:
        DataFrame or None
    """
    import pandas as pd
    
    if not csv_url or pd.isna(csv_url) or str(csv_url).strip() == '':
        print(f"   ⚠️  No CSV URL/path provided")
        return None
    
    csv_url = str(csv_url).strip()
    
    try:
        # Check if it's a local file path
        if os.path.isfile(csv_url):
            print(f"   Loading CSV from local file: {csv_url}")
            df = pd.read_csv(csv_url)
            print(f"   ✅ Successfully loaded {len(df)} candidates from local CSV")
            return df
        
        # Otherwise treat as URL
        print(f"   Downloading CSV from File Storage...")
        response = requests.get(csv_url, timeout=30)
        response.raise_for_status()
        
        from io import StringIO
        csv_content = StringIO(response.text)
        df = pd.read_csv(csv_content)
        
        print(f"   ✅ Successfully loaded {len(df)} candidates from CSV")
        return df
    except Exception as e:
        print(f"   ❌ Error loading CSV: {str(e)}")
        return None


def fetch_candidates_from_kalibrr(job_id):
    """
    Fetch candidates from Kalibrr using Playwright automation.
    This mimics the browser workflow to export candidates.
    
    Args:
        job_id: Job ID from Kalibrr (e.g., "261105")
        
    Returns:
        DataFrame or None
    """
    import pandas as pd
    import asyncio
    import os
    import re
    from playwright.async_api import async_playwright
    
    async def extract_upload_id_from_network(network_logs):
        """Extract upload ID from network logs"""
        for url in network_logs:
            match = re.search(r"candidate_uploads/(\d+)", url)
            if match:
                return match.group(1)
        return None
    
    async def fetch_with_playwright():
        """Main async function to fetch candidates"""
        kb = os.getenv("KALIBRR_KB")
        kaid = os.getenv("KALIBRR_KAID")
        
        if not kb or not kaid:
            print(f"   ❌ KALIBRR_KB or KALIBRR_KAID not found in environment variables")
            return None
        
        url = f"https://www.kalibrr.com/ats/candidates?job_id={job_id}&state_id=19"
        print(f"   Opening: {url}")
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context()
            
            # Set cookies for authentication
            await context.add_cookies([
                {"name": "kaid", "value": kaid, "domain": "www.kalibrr.com", "path": "/"},
                {"name": "kb", "value": kb, "domain": "www.kalibrr.com", "path": "/"}
            ])
            
            page = await context.new_page()
            network_logs = []
            
            page.on("request", lambda req: network_logs.append(req.url))
            page.on("response", lambda res: network_logs.append(res.url))
            
            # Load page
            try:
                await page.goto(url, timeout=60000, wait_until="networkidle")
            except Exception:
                await page.goto(url, timeout=60000, wait_until="domcontentloaded")
            
            await page.wait_for_timeout(3000)
            
            # Find and click export button
            print(f"   Looking for export button...")
            
            # Text labels to search for
            text_labels = [
                "EXPORT ALL CANDIDATES",
                "Export All Candidates",
                "Unduh semua kandidat",
                "UNDUH SEMUA KANDIDAT",
                "Export",
                "EXPORT",
                "Download",
                "DOWNLOAD"
            ]
            
            # CSS selectors
            export_button_selectors = [
                'button:has-text("Export")',
                'button:has-text("EXPORT")',
                'button:has-text("Download")',
                '[data-testid*="export"]',
                '[aria-label*="export"]',
                'a:has-text("Export")',
                'button[class*="export"]'
            ]
            
            clicked = False
            for attempt in range(60):  # Wait up to 60 seconds
                # Try text labels first
                for label in text_labels:
                    try:
                        locator = page.get_by_text(label, exact=False)
                        if await locator.count() > 0:
                            await locator.first.click(timeout=1000)
                            clicked = True
                            print(f"   ✓ Export button clicked (text: {label})")
                            break
                    except Exception:
                        pass
                
                if clicked:
                    break
                
                # Try selectors
                for selector in export_button_selectors:
                    try:
                        locator = page.locator(selector)
                        if await locator.count() > 0:
                            await locator.first.click(timeout=1000)
                            clicked = True
                            print(f"   ✓ Export button clicked (selector: {selector})")
                            break
                    except Exception:
                        pass
                
                if clicked:
                    break
                
                await asyncio.sleep(1)
            
            if not clicked:
                print(f"   ❌ Could not find export button")
                await browser.close()
                return None
            
            # Wait for upload_id in network logs
            print(f"   Waiting for upload ID...")
            upload_id = None
            for _ in range(60):
                upload_id = await extract_upload_id_from_network(network_logs)
                if upload_id:
                    break
                await asyncio.sleep(1)
            
            if not upload_id:
                print(f"   ❌ Upload ID not found")
                await browser.close()
                return None
            
            print(f"   ✓ Upload ID: {upload_id}")
            
            # Get CSV URL from API
            api_url = f"https://www.kalibrr.com/api/candidate_uploads/{upload_id}?url_only=true"
            csv_url = None
            
            for attempt in range(30):
                try:
                    res = await page.request.get(api_url)
                    csv_url = (await res.text()).replace('"', "").strip()
                    
                    if csv_url and csv_url.startswith("https://storage.googleapis.com"):
                        break
                    else:
                        csv_url = None
                except Exception:
                    pass
                
                await asyncio.sleep(1)
            
            if not csv_url:
                print(f"   ❌ Could not get CSV URL")
                await browser.close()
                return None
            
            print(f"   ✓ CSV URL obtained")
            
            # Download CSV
            csv_response = await page.request.get(csv_url)
            csv_data = await csv_response.body()
            
            await browser.close()
            
            # Parse CSV to DataFrame
            from io import BytesIO
            df = pd.read_csv(BytesIO(csv_data))
            return df
    
    try:
        # Run async function
        return asyncio.run(fetch_with_playwright())
    except Exception as e:
        print(f"   ❌ Error during Playwright fetch: {e}")
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


def screen_position(position_name, job_description, job_id, csv_url=None):
    """
    Screen new candidates for a specific position.
    
    Args:
        position_name: Name of the job position
        job_description: Full job description text
        job_id: Job ID from Kalibrr (for reference)
        csv_url: Direct CSV URL from sheet_positions.csv File Storage column
        
    Returns:
        int: Number of candidates successfully screened
    """
    print(f"\n{'='*70}")
    print(f"Position: {position_name} (Job ID: {job_id})")
    print(f"{'='*70}")
    
    try:
        # 1. Fetch candidates from pre-exported CSV in sheet_positions.csv
        print(f"📋 Loading candidates from sheet_positions.csv...")
        candidates_df = fetch_candidates_from_sheet_csv(csv_url)
        
        # Fallback: if remote URL failed, try local CSV in kalibrr_exports/
        if (candidates_df is None or candidates_df.empty) and csv_url and not os.path.isfile(str(csv_url)):
            safe_name = (position_name
                         .replace(" ", "_")
                         .replace(".", "")
                         .replace("/", "_")
                         .replace("(", "")
                         .replace(")", ""))
            local_csv = os.path.join('kalibrr_exports', f'{safe_name}.csv')
            if os.path.isfile(local_csv):
                print(f"   📂 Remote URL failed, falling back to local CSV: {local_csv}")
                candidates_df = fetch_candidates_from_sheet_csv(local_csv)
        
        if candidates_df is None or candidates_df.empty:
            print(f"⏭️  No candidates found for this position")
            return 0
        
        print(f"   Total candidates: {len(candidates_df)}")
        
        # 2. Load existing results to identify already-processed candidates
        print("🔍 Checking existing results...")
        position_results_file = get_results_filename(position_name)
        existing_results = load_results_from_github(path=position_results_file)
        
        processed_emails = set()
        if existing_results is not None and not existing_results.empty:
            # Build set of processed candidate emails (case-insensitive)
            # Ensure column is string type before using .str accessor
            email_col = existing_results["Candidate Email"].astype(str).replace('nan', pd.NA)
            processed_emails = set(
                email_col[email_col.notna()].str.lower()
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
                candidate_info = {
                    "latest_job_title": "",
                    "latest_company": "",
                    "education": "",
                    "university": "",
                    "major": ""
                }
                
                if cv_text.strip():
                    try:
                        # Use new 3-step pipeline: Extract & Classify (Flash) → Evaluate & Score (Pro) → Ceiling
                        cv_score, summary, strengths, weaknesses, gaps, candidate_info = score_candidate_pipeline(
                            cv_text, context, position_name, job_description
                        )
                        print(f"       ✓ AI Score: {cv_score}/100")
                        print(f"       ✓ Extracted candidate info from CV")
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
                    "Latest Job Title": candidate_info.get("latest_job_title") or candidate.get("Latest Job Title") or candidate.get("Jabatan Terakhir") or "",
                    "Latest Company": candidate_info.get("latest_company") or candidate.get("Latest Company") or candidate.get("Perusahaan Terakhir") or "",
                    "Education": candidate_info.get("education") or candidate.get("Tingkat Pendidikan") or candidate.get("Latest Educational Attainment") or candidate.get("Pendidikan") or "",
                    "University": candidate_info.get("university") or candidate.get("Latest School/University") or candidate.get("Universitas") or "",
                    "Major": candidate_info.get("major") or candidate.get("Latest Major/Course") or candidate.get("Jurusan") or "",
                    "Kalibrr Profile": candidate.get("Link Profil Kalibrr") or candidate.get("Kalibrr Profile Link") or candidate.get("Profil Kalibrr") or "",
                    "Application Link": candidate.get("Link Aplikasi Pekerjaan") or candidate.get("Job Application Link") or candidate.get("Tautan Lamaran") or "",
                    "Resume Link": resume_link,
                    "Recruiter Feedback": "",
                    "Shortlisted": False,
                    "Candidate Status": "",
                    "Interview Status": "",
                    "Rejection Reason": "",
                    "Date Applied": parse_kalibrr_date(
                        candidate.get("Date Application Started (mm/dd/yy hr:mn)") or
                        candidate.get("Tanggal Mulai Melamar") or
                        candidate.get("application.created_at") or ""
                    ),
                    "Date Processed": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }
                
                # Append result immediately to CSV file
                result_df = pd.DataFrame([result])
                if save_results_to_github(result_df, job_position=position_name):
                    print(f"       ✓ Appended to {position_results_file}")
                    results.append(result)
                    successfully_processed += 1
                    # Log successful CV processing
                    log_cv_processing(
                        source="github_action",
                        candidate_name=candidate_name,
                        position=position_name,
                        success=True
                    )
                else:
                    print(f"       ⚠ Failed to append result")
                    failed_count += 1
                    # Log failed CV processing
                    log_cv_processing(
                        source="github_action",
                        candidate_name=candidate_name,
                        position=position_name,
                        success=False
                    )
                
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
    if not os.getenv("GEMINI_API_KEY"):
        print("❌ ERROR: No API key found!")
        print("   Please set GEMINI_API_KEY environment variable")
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
        print(f"❌ Error loading job positions: {e}")
        return 1
    
    # 2. Filter active positions (EXCLUDE pooled positions)
    # Ensure Pooling Status column exists
    if 'Pooling Status' not in jobs_df.columns:
        jobs_df['Pooling Status'] = ''
    
    # Filter out pooled positions (case-insensitive, handle null/empty)
    # Keep only positions where Pooling Status is NOT 'Pooled'
    active_positions = jobs_df[
        (jobs_df['Pooling Status'].fillna('').astype(str).str.strip().str.lower() != 'pooled')
    ].copy()
    
    pooled_count = len(jobs_df) - len(active_positions)
    
    if active_positions.empty:
        print("   ⚠️  All positions are in pooling. No active positions to screen.")
        print(f"   Total positions: {len(jobs_df)}, Pooled: {pooled_count}")
        return 0
    
    print(f"✅ Will screen {len(active_positions)} active positions")
    if pooled_count > 0:
        print(f"   (Skipping {pooled_count} pooled position(s))")
    
    # 3. Load sheet_positions.csv to get File Storage URLs
    print(f"\n📊 Loading sheet_positions.csv for CSV URLs...")
    try:
        sheet_df = pd.read_csv('sheet_positions.csv')
        print(f"   Loaded {len(sheet_df)} positions from sheet_positions.csv\n")
    except Exception as e:
        print(f"   ⚠️  Could not load sheet_positions.csv: {e}")
        print(f"   Will proceed without File Storage URLs\n")
        sheet_df = None
    
    # 4. Screen each active position
    total_screened = 0
    positions_with_new_candidates = 0
    
    for idx, row in active_positions.iterrows():
        position_name = row['Job Position']
        job_description = row['Job Description']
        job_id = row.get('Job ID', None)
        pooling_status = row.get('Pooling Status', '')
        
        # Double-check: Skip if position is pooled (extra safety check)
        if pd.notna(pooling_status) and str(pooling_status).strip().lower() == 'pooled':
            print(f"\n⚠️  Skipping '{position_name}' - Position is in pooling")
            continue
        
        # Skip if no Job ID
        if pd.isna(job_id):
            print(f"\n⚠️  Skipping '{position_name}' - No Job ID found")
            continue
        
        # Get CSV URL from sheet_positions.csv
        csv_url = None
        if sheet_df is not None:
            match = sheet_df[sheet_df['Nama Posisi'] == position_name]
            if not match.empty:
                csv_url = match.iloc[0].get('File Storage')
        
        # Fallback: check for local CSV in kalibrr_exports/
        if not csv_url or pd.isna(csv_url) or str(csv_url).strip() == '':
            safe_name = (position_name
                         .replace(" ", "_")
                         .replace(".", "")
                         .replace("/", "_")
                         .replace("(", "")
                         .replace(")", ""))
            local_csv = os.path.join('kalibrr_exports', f'{safe_name}.csv')
            if os.path.isfile(local_csv):
                csv_url = local_csv
                print(f"   📂 Using local CSV: {local_csv}")
            else:
                print(f"\n⚠️  Skipping '{position_name}' - No File Storage URL or local CSV")
                continue
        
        try:
            screened = screen_position(position_name, job_description, job_id, csv_url)
            total_screened += screened
            if screened > 0:
                positions_with_new_candidates += 1
        except Exception as e:
            print(f"❌ Error screening position '{position_name}': {str(e)}")
            print(f"   Stack trace: {traceback.format_exc()}")
            # Continue with next position even if this one fails
            continue
    
    # Final summary
    print("\n" + "="*70)
    print("SCREENING COMPLETED")
    print("="*70)
    print(f"Total positions in job_positions.csv: {len(jobs_df)}")
    print(f"  • Active positions screened: {len(active_positions)}")
    if pooled_count > 0:
        print(f"  • Pooled positions (excluded): {pooled_count}")
    print(f"Total candidates screened: {total_screened}")
    print(f"Positions with new candidates: {positions_with_new_candidates}")
    print(f"Completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*70)
    
    # Print daily usage summary
    print_daily_summary()
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
