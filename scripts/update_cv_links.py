"""
Update CV links in existing results from sheet_positions.csv
without re-analyzing the CVs.

This script is designed to run daily after kalibrr_export scripts
in the GitHub Actions workflow.

Usage:
    python scripts/update_cv_links.py                   # process ALL positions
    python scripts/update_cv_links.py --mode pooling     # only pooled positions
    python scripts/update_cv_links.py --mode dashboard   # only active (non-pooled) positions

Workflow:
1. kalibrr_export_dashboard.py or kalibrr_export_pooling.py runs first
   and fetches fresh File Storage URLs from Kalibrr
2. This script then runs and updates CV links in existing screening results

What this script does:
1. Loads sheet_positions.csv with latest File Storage URLs
2. (Optional) Cross-references job_positions.csv to filter by Pooling Status
3. Downloads candidate data from each File Storage URL
4. Matches candidates by email with existing results
5. Updates ONLY the Resume Link field in existing results
6. Saves updated results back to position-specific CSV files

What this script DOES NOT do:
- Does NOT re-score candidates
- Does NOT re-analyze CVs
- Does NOT call any AI/LLM APIs
- Does NOT change any fields except "Resume Link"

This ensures that CV links stay current (Kalibrr URLs expire) without the
computational overhead and cost of re-analyzing candidates.
"""

import os
import sys
import time
import argparse
import pandas as pd
import requests
from io import BytesIO
from pathlib import Path
import re


# Constants
SHEET_POSITIONS_FILE = "sheet_positions.csv"
JOB_POSITIONS_FILE = "job_positions.csv"
RESULTS_DIR = "results"


def load_sheet_positions():
    """Load the sheet_positions.csv file with updated File Storage URLs."""
    if not os.path.exists(SHEET_POSITIONS_FILE):
        print(f"❌ {SHEET_POSITIONS_FILE} not found")
        return None
    
    try:
        df = pd.read_csv(SHEET_POSITIONS_FILE)
        print(f"✅ Loaded {len(df)} positions from {SHEET_POSITIONS_FILE}")
        return df
    except Exception as e:
        print(f"❌ Error loading {SHEET_POSITIONS_FILE}: {e}")
        return None


def fetch_candidates_from_file_storage(file_storage_url, max_retries=3):
    """Download and parse candidate CSV from File Storage URL."""
    for attempt in range(max_retries):
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Accept': 'text/csv,application/csv,text/plain,*/*'
            }
            response = requests.get(str(file_storage_url).strip(), headers=headers, timeout=30)
            
            if response.status_code != 200:
                if attempt < max_retries - 1:
                    time.sleep(2)
                    continue
                # Show status code for debugging
                print(f"⚠️ HTTP {response.status_code} - URL may have expired")
                return None
            
            candidates_df = pd.read_csv(BytesIO(response.content))
            return candidates_df
            
        except requests.exceptions.Timeout:
            if attempt < max_retries - 1:
                time.sleep(3)
                continue
            print(f"⚠️ Timeout fetching candidates")
            return None
        except Exception as e:
            if attempt < max_retries - 1:
                time.sleep(2)
                continue
            print(f"⚠️ Error fetching candidates: {e}")
            return None
    
    return None


def _truncate_str(s, max_len):
    """Truncate string to max length with ellipsis."""
    s_str = str(s)
    return f"{s_str[:max_len]}..." if len(s_str) > max_len else s_str


def get_column_value(row, english_name, indonesian_name, default=''):
    """Get column value supporting both English and Indonesian column names."""
    if english_name in row and pd.notna(row.get(english_name)):
        return row.get(english_name, default)
    return row.get(indonesian_name, default)


def load_existing_results(position_name):
    """Load existing results for a specific position."""
    # Generate the position-specific filename
    safe_name = re.sub(r'[^\w\s-]', '', position_name)
    safe_name = re.sub(r'[-\s]+', '_', safe_name)
    results_file = os.path.join(RESULTS_DIR, f"results_{safe_name}.csv")
    
    if not os.path.exists(results_file):
        print(f"ℹ️ No existing results file found: {results_file}")
        return None, results_file
    
    try:
        df = pd.read_csv(results_file)
        print(f"✅ Loaded {len(df)} existing results from {results_file}")
        return df, results_file
    except Exception as e:
        print(f"❌ Error loading {results_file}: {e}")
        return None, results_file


def update_cv_links_for_position(position_name, file_storage_url):
    """
    Update CV links for a specific position.
    
    Args:
        position_name: Name of the job position
        file_storage_url: URL to fetch fresh candidate data
    
    Returns:
        Number of updated candidates
    """
    print(f"\n{'='*60}")
    print(f"Processing: {position_name}")
    print(f"{'='*60}")
    
    # Load existing results for this position
    existing_results, results_file = load_existing_results(position_name)
    
    if existing_results is None or existing_results.empty:
        print(f"⏭️ Skipping {position_name} - no existing results to update")
        return 0
    
    # Fetch fresh candidate data from File Storage
    print(f"📥 Fetching fresh candidate data from File Storage...")
    fresh_candidates = fetch_candidates_from_file_storage(file_storage_url)
    
    if fresh_candidates is None or fresh_candidates.empty:
        print(f"⚠️ Could not fetch fresh candidate data for {position_name}")
        print(f"   This may be due to expired URLs or network issues")
        print(f"   CV links will not be updated for this position")
        return 0
    
    print(f"✅ Fetched {len(fresh_candidates)} candidates from File Storage")
    
    # Build a mapping of email -> resume link from fresh data
    email_to_resume_link = {}
    
    for _, row in fresh_candidates.iterrows():
        email = get_column_value(row, "Email Address", "Alamat Email", "").strip()
        resume_link = get_column_value(row, "Resume Link", "Link Resume", "")
        
        if email and resume_link:
            email_to_resume_link[email.lower()] = resume_link
    
    print(f"📋 Found {len(email_to_resume_link)} candidates with resume links in fresh data")
    
    # Verify Resume Link column exists in existing results
    if "Resume Link" not in existing_results.columns:
        print(f"⚠️ Warning: 'Resume Link' column not found in {results_file}")
        print(f"   Available columns: {list(existing_results.columns)}")
        return 0
    
    # Update resume links in existing results
    updated_count = 0
    
    for idx, row in existing_results.iterrows():
        candidate_email = str(row.get("Candidate Email", "")).strip().lower()
        
        if candidate_email in email_to_resume_link:
            new_resume_link = email_to_resume_link[candidate_email]
            old_resume_link = row.get("Resume Link", "")
            
            # Only update if the link has changed
            if new_resume_link != old_resume_link:
                existing_results.at[idx, "Resume Link"] = new_resume_link
                updated_count += 1
                candidate_name = row.get('Candidate Name', 'Unknown')
                print(f"  ✓ Updated resume link for: {candidate_name}")
                print(f"    Old: {_truncate_str(old_resume_link, 80)}")
                print(f"    New: {_truncate_str(new_resume_link, 80)}")
    
    # Save updated results back to file
    if updated_count > 0:
        try:
            # Save ALL existing columns (preserve any additional columns that might exist)
            existing_results.to_csv(results_file, index=False)
            
            print(f"💾 Saved {updated_count} updated resume link(s) to {results_file}")
            print(f"   Updated column: Resume Link")
        except Exception as e:
            print(f"❌ Error saving results: {e}")
            return 0
    else:
        print(f"ℹ️ No resume links needed updating for {position_name}")
    
    return updated_count


def _load_allowed_positions(mode):
    """
    Load the set of allowed position names based on --mode flag.
    Cross-references job_positions.csv for Pooling Status.

    Args:
        mode: "pooling", "dashboard", or None (all)

    Returns:
        set of position names to process, or None if no filter
    """
    if mode is None:
        return None  # no filtering

    if not os.path.exists(JOB_POSITIONS_FILE):
        print(f"⚠️ {JOB_POSITIONS_FILE} not found — processing all positions")
        return None

    try:
        df = pd.read_csv(JOB_POSITIONS_FILE, dtype=str, keep_default_na=False)
    except Exception as e:
        print(f"⚠️ Error reading {JOB_POSITIONS_FILE}: {e} — processing all positions")
        return None

    allowed = set()
    for _, row in df.iterrows():
        name = str(row.get("Job Position", "")).strip()
        pooling = str(row.get("Pooling Status", "")).strip().lower()
        if not name:
            continue

        is_pooled = pooling == "pooled"
        if mode == "pooling" and is_pooled:
            allowed.add(name)
        elif mode == "dashboard" and not is_pooled:
            allowed.add(name)

    print(f"📋 Mode '{mode}': {len(allowed)} posisi yang akan diproses")
    return allowed


def main():
    """Main function to update CV links for all positions."""
    # Parse CLI arguments
    parser = argparse.ArgumentParser(description="Update CV links in screening results")
    parser.add_argument(
        "--mode",
        choices=["pooling", "dashboard"],
        default=None,
        help="Filter positions: 'pooling' (pooled only), 'dashboard' (active only), omit for all",
    )
    args = parser.parse_args()

    mode_label = args.mode or "all"
    print("="*60)
    print(f"CV Link Update Script  [mode: {mode_label}]")
    print("Updates resume links without re-analyzing CVs")
    print("="*60)

    # Load allowed positions based on mode
    allowed_positions = _load_allowed_positions(args.mode)

    # Load sheet positions
    sheet_positions = load_sheet_positions()
    
    if sheet_positions is None or sheet_positions.empty:
        print("❌ No positions found in sheet_positions.csv")
        return 1
    
    # Find positions with File Storage URLs
    total_updated = 0
    total_positions = 0
    
    for _, row in sheet_positions.iterrows():
        position_name = row.get("Nama Posisi", "")
        file_storage_url = row.get("File Storage", "")
        
        # Skip if no position name or no File Storage URL
        if pd.isna(position_name) or not str(position_name).strip():
            continue
        
        position_name = str(position_name).strip()

        # Apply mode filter
        if allowed_positions is not None and position_name not in allowed_positions:
            continue

        if pd.isna(file_storage_url) or not str(file_storage_url).strip():
            print(f"\n⏭️ Skipping {position_name} - no File Storage URL")
            continue
        
        total_positions += 1
        updated_count = update_cv_links_for_position(position_name, file_storage_url)
        total_updated += updated_count
    
    # Summary
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    print(f"Mode: {mode_label}")
    print(f"Positions processed: {total_positions}")
    print(f"Total CV links updated: {total_updated}")
    print("="*60)
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
