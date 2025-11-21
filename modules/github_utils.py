import base64
import json
import os
import requests
import pandas as pd
import streamlit as st
from io import StringIO
import time

# Expected columns for results.csv
RESULTS_COLUMNS = [
    "Candidate Name", "Candidate Email", "Phone", "Job Position",
    "Match Score", "AI Summary", "Strengths", "Weaknesses", "Gaps",
    "Latest Job Title", "Latest Company", "Education", "University", "Major",
    "Kalibrr Profile", "Application Link", "Resume Link",
    "Recruiter Feedback", "Shortlisted", "Date Processed"
]

# Network timeout for GitHub API requests (in seconds)
GITHUB_TIMEOUT = 30

# GitHub Contents API size limit for inline content (bytes)
# Files larger than this should be downloaded via raw URL
GITHUB_CONTENTS_API_SIZE_LIMIT = 1_000_000  # 1MB


def get_results_filename(job_position):
    """Generate a safe filename for storing results by job position.
    
    Args:
        job_position: The job position name
        
    Returns:
        str: Safe filename like "results_Account_Executive_VCBL.csv"
    """
    import re
    # Replace special characters with underscore using regex
    # Keep only alphanumeric, spaces, and underscores
    safe_name = re.sub(r'[^\w\s]', '', job_position)  # Remove special chars
    safe_name = re.sub(r'\s+', '_', safe_name)  # Replace spaces with underscore
    safe_name = re.sub(r'_+', '_', safe_name)  # Collapse multiple underscores
    return f"results_{safe_name}.csv"


def save_results_to_github(df, path=None, job_position=None, max_retries=3):
    """Save or update results in GitHub repo, storing each job position in a separate file.
    
    Args:
        df: DataFrame to save
        path: (Optional) Explicit path to CSV file. If not provided, uses job_position to generate filename.
        job_position: (Optional) Job position name to generate filename (e.g., "Account Executive")
        max_retries: Maximum number of retry attempts on failure
    
    Returns:
        bool: True if save was successful, False otherwise.
    """
    # Validate input DataFrame
    if df is None:
        st.error("❌ Cannot save: DataFrame is None")
        return False
    
    if df.empty:
        st.warning("⚠️ Cannot save: DataFrame is empty")
        return False
    
    # Ensure required columns exist
    required_columns = ["Candidate Name", "Job Position"]
    missing_columns = [col for col in required_columns if col not in df.columns]
    if missing_columns:
        st.error(f"❌ Cannot save: Missing required columns: {', '.join(missing_columns)}")
        return False
    
    # Determine the file path
    if path is None:
        if job_position is None:
            # If no path and no job_position, try to get it from the dataframe
            if "Job Position" in df.columns and not df.empty:
                job_position = df["Job Position"].iloc[0]
            else:
                st.error("❌ Cannot save: No path or job_position provided")
                return False
        path = get_results_filename(job_position)
    
    token = st.secrets.get("GITHUB_TOKEN")
    repo = st.secrets.get("GITHUB_REPO", "netrialiarahmi/cv-matching-auto")
    branch = st.secrets.get("GITHUB_BRANCH", "main")

    if not token:
        st.error("❌ Missing GITHUB_TOKEN in Streamlit secrets.")
        return False

    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github+json"
    }

    url = f"https://api.github.com/repos/{repo}/contents/{path}"

    # Retry loop
    for attempt in range(max_retries):
        try:
            # 1️⃣ Cek apakah file sudah ada
            r = requests.get(url, headers=headers, timeout=GITHUB_TIMEOUT)
            sha = None
            if r.status_code == 200:
                content = r.json()
                sha = content["sha"]
                file_size = content.get("size", 0)
                
                # Handle large files (>1MB) using raw URL instead of Contents API
                # GitHub Contents API excludes content field for files >1MB
                if file_size > GITHUB_CONTENTS_API_SIZE_LIMIT or "content" not in content:
                    # Use raw.githubusercontent.com for large files
                    raw_url = f"https://raw.githubusercontent.com/{repo}/{branch}/{path}"
                    r_raw = requests.get(raw_url, timeout=GITHUB_TIMEOUT)
                    if r_raw.status_code == 200:
                        existing_csv = r_raw.text
                    else:
                        st.error(f"❌ CRITICAL: Could not download large file ({file_size:,} bytes). Data loss may occur!")
                        existing_csv = None
                else:
                    # File is small enough, use Contents API
                    existing_csv = base64.b64decode(content["content"]).decode("utf-8")
                
                # Parse existing data if available
                if existing_csv:
                    try:
                        old_df = pd.read_csv(StringIO(existing_csv))
                        # Merge if old_df has data, otherwise just use new data
                        if not old_df.empty:
                            old_count = len(old_df)
                            new_count = len(df)
                            df = pd.concat([old_df, df], ignore_index=True)
                            st.info(f"📊 Merging data: {old_count} existing + {new_count} new = {len(df)} total records")
                    except pd.errors.EmptyDataError:
                        # Existing file is completely empty (no header), just use the new data
                        pass
                    except (pd.errors.ParserError, ValueError) as e:
                        # Log parsing error but continue with new data
                        if attempt == max_retries - 1:
                            st.warning(f"⚠️ Could not parse existing data (using new data only): {str(e)}")
                
                # Apply deduplication to remove duplicates (handles both merged and new-only data)
                # Use Candidate Email as unique identifier (new format) or fallback to Filename (old format)
                # Keep 'first' to preserve existing records and their shortlist status
                dedup_columns = ["Candidate Email", "Job Position"] if "Candidate Email" in df.columns else ["Filename", "Job Position"]
                if all(col in df.columns for col in dedup_columns):
                    before_dedup = len(df)
                    df.drop_duplicates(subset=dedup_columns, keep="first", inplace=True)
                    after_dedup = len(df)
                    if before_dedup > after_dedup:
                        st.info(f"🔄 Removed {before_dedup - after_dedup} duplicate(s). Final count: {after_dedup} records")
            elif r.status_code == 401:
                st.error(f"❌ GitHub authentication failed: {r.status_code} - {r.text}")
                return False
            elif r.status_code != 404:
                # 404 is expected for new files, other errors should be reported
                if attempt == max_retries - 1:
                    st.warning(f"⚠️ Could not check existing file: {r.status_code} - {r.text}")

            # 2️⃣ Encode CSV baru
            csv_bytes = df.to_csv(index=False).encode("utf-8")
            encoded = base64.b64encode(csv_bytes).decode("utf-8")

            # 3️⃣ Siapkan payload
            data = {
                "message": "📊 Update results.csv via Streamlit app",
                "content": encoded,
                "branch": branch
            }
            if sha:
                data["sha"] = sha

            # 4️⃣ Upload ke GitHub
            res = requests.put(url, headers=headers, data=json.dumps(data), timeout=GITHUB_TIMEOUT)
            if res.status_code in [200, 201]:
                return True
            elif res.status_code == 409:
                # Conflict - file was updated by someone else, retry
                if attempt < max_retries - 1:
                    time.sleep(1)  # Wait before retrying
                    continue
                else:
                    st.error(f"❌ GitHub save failed after {max_retries} attempts: File conflict")
                    return False
            else:
                if attempt == max_retries - 1:
                    st.error(f"❌ GitHub save failed: {res.status_code} - {res.text}")
                return False
                
        except requests.exceptions.Timeout:
            if attempt < max_retries - 1:
                time.sleep(2)  # Wait before retrying
                continue
            else:
                st.error(f"❌ GitHub save failed: Connection timeout after {max_retries} attempts")
                return False
        except requests.exceptions.RequestException as e:
            if attempt < max_retries - 1:
                time.sleep(2)  # Wait before retrying
                continue
            else:
                st.error(f"❌ GitHub save failed: Network error - {str(e)}")
                return False
        except Exception as e:
            if attempt == max_retries - 1:
                st.error(f"❌ Unexpected error while saving: {str(e)}")
            return False
    
    return False


def load_results_from_github(path="results.csv"):
    """Load results.csv from GitHub repo, with fallback to local file.
    
    Returns:
        pd.DataFrame: DataFrame with results, or empty DataFrame with expected columns if file is empty/not found
        None: Only if there's a critical error and no fallback is available
    """
    token = st.secrets.get("GITHUB_TOKEN")
    repo = st.secrets.get("GITHUB_REPO", "netrialiarahmi/cv-matching-auto")
    branch = st.secrets.get("GITHUB_BRANCH", "main")

    # Try to load from GitHub first
    if token:
        headers = {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github+json"
        }

        # First, check file size using Contents API
        url = f"https://api.github.com/repos/{repo}/contents/{path}?ref={branch}"
        
        try:
            r = requests.get(url, headers=headers, timeout=GITHUB_TIMEOUT)
            
            if r.status_code == 200:
                content = r.json()
                file_size = content.get("size", 0)
                
                # GitHub Contents API has a size limit for inline content
                # For files larger than this, download via raw URL instead
                if file_size > GITHUB_CONTENTS_API_SIZE_LIMIT:
                    # Use raw.githubusercontent.com for large files (no auth needed for public repos)
                    raw_url = f"https://raw.githubusercontent.com/{repo}/{branch}/{path}"
                    r_raw = requests.get(raw_url, timeout=GITHUB_TIMEOUT)
                    if r_raw.status_code == 200:
                        try:
                            df = pd.read_csv(StringIO(r_raw.text))
                            return df
                        except pd.errors.EmptyDataError:
                            return pd.DataFrame(columns=RESULTS_COLUMNS)
                        except Exception as e:
                            st.warning(f"⚠️ Failed to parse large GitHub file: {str(e)}. Trying local file.")
                            # Fall through to local file fallback
                    else:
                        st.warning(f"⚠️ Failed to download large file from GitHub ({r_raw.status_code}). Trying local file.")
                        # Fall through to local file fallback
                else:
                    # File is small enough, use Contents API
                    try:
                        decoded = base64.b64decode(content["content"]).decode("utf-8")
                        df = pd.read_csv(StringIO(decoded))
                        # Successfully loaded from GitHub
                        return df
                    except pd.errors.EmptyDataError:
                        # File exists but is completely empty (no headers, no data)
                        # Return empty DataFrame with expected columns for consistency
                        return pd.DataFrame(columns=RESULTS_COLUMNS)
                    except Exception as e:
                        st.warning(f"⚠️ Failed to parse GitHub file: {str(e)}. Trying local file.")
                        # Fall through to local file fallback
            elif r.status_code == 404:
                st.info(f"ℹ️ File not found in GitHub branch '{branch}'. Checking local file.")
                # Fall through to local file fallback
            else:
                st.warning(f"⚠️ GitHub load failed ({r.status_code}). Trying local file.")
                # Fall through to local file fallback
                
        except requests.exceptions.RequestException as e:
            st.warning(f"⚠️ Failed to connect to GitHub: {str(e)}. Trying local file.")
            # Fall through to local file fallback
    
    # Fallback to local file
    if os.path.exists(path):
        try:
            df = pd.read_csv(path)
            if not df.empty:
            return df
        except pd.errors.EmptyDataError:
            return pd.DataFrame(columns=RESULTS_COLUMNS)
        except Exception as e:
            st.error(f"❌ Failed to load local {path}: {str(e)}")
            return None
    else:
        # Neither GitHub nor local file exists - return empty DataFrame with expected columns
        return pd.DataFrame(columns=RESULTS_COLUMNS)


def load_all_results_from_github():
    """Load all results from GitHub by finding and merging all results_*.csv files.
    
    This function discovers all position-specific result files (results_*.csv) and merges them
    into a single DataFrame for the Dashboard "All" view.
    
    Returns:
        pd.DataFrame: Merged DataFrame with all results, or empty DataFrame if no files found
    """
    token = st.secrets.get("GITHUB_TOKEN")
    repo = st.secrets.get("GITHUB_REPO", "netrialiarahmi/cv-matching-auto")
    branch = st.secrets.get("GITHUB_BRANCH", "main")
    
    all_results = []
    
    # Try to get list of files from GitHub
    if token:
        headers = {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github+json"
        }
        
        # Get list of files in the repository root
        url = f"https://api.github.com/repos/{repo}/contents/?ref={branch}"
        
        try:
            r = requests.get(url, headers=headers, timeout=GITHUB_TIMEOUT)
            
            if r.status_code == 200:
                files = r.json()
                # Find all results_*.csv files
                result_files = [f["name"] for f in files if f["name"].startswith("results_") and f["name"].endswith(".csv")]
                
                if result_files:
                    st.info(f"📂 Found {len(result_files)} position file(s)")
                    
                    # Load each file
                    for filename in result_files:
                        df = load_results_from_github(path=filename)
                        if df is not None and not df.empty:
                            all_results.append(df)
                
                # Also check for legacy results.csv
                if any(f["name"] == "results.csv" for f in files):
                    df = load_results_from_github(path="results.csv")
                    if df is not None and not df.empty:
                        all_results.append(df)
                        
        except Exception as e:
            st.warning(f"⚠️ Could not list files from GitHub: {str(e)}")
    
    # Also check local directory for results_*.csv files
    try:
        import glob
        local_files = glob.glob("results_*.csv") + glob.glob("results.csv")
        for filename in local_files:
            if os.path.exists(filename):
                try:
                    df = pd.read_csv(filename)
                    if not df.empty:
                        # Check if we already loaded this file from GitHub by comparing first few rows
                        is_duplicate = False
                        for existing in all_results:
                            if len(existing) == len(df):
                                # Compare first 3 rows to check if it's the same dataset
                                if len(df) >= 3 and len(existing) >= 3:
                                    if df.head(3).equals(existing.head(3)):
                                        is_duplicate = True
                                        break
                                elif df.equals(existing):
                                    is_duplicate = True
                                    break
                        
                        if not is_duplicate:
                            all_results.append(df)
                except Exception as e:
                    st.warning(f"⚠️ Could not load local {filename}: {str(e)}")
    except Exception:
        pass  # Glob not available or other error
    
    # Merge all results
    if all_results:
        merged_df = pd.concat(all_results, ignore_index=True)
        # Remove duplicates based on email + job position
        if "Candidate Email" in merged_df.columns and "Job Position" in merged_df.columns:
            before = len(merged_df)
            merged_df.drop_duplicates(subset=["Candidate Email", "Job Position"], keep="first", inplace=True)
            after = len(merged_df)
            if before > after:
                st.info(f"🔄 Removed {before - after} duplicate(s) across files")
        return merged_df
    else:
        return pd.DataFrame(columns=RESULTS_COLUMNS)


def save_job_positions_to_github(df, path="job_positions.csv"):
    """Save or update job_positions.csv in GitHub repo.
    
    Returns:
        bool: True if save was successful, False otherwise.
    """
    token = st.secrets.get("GITHUB_TOKEN")
    repo = st.secrets.get("GITHUB_REPO", "netrialiarahmi/cv-matching-auto")
    branch = st.secrets.get("GITHUB_BRANCH", "main")

    if not token:
        st.error("❌ Missing GITHUB_TOKEN in Streamlit secrets.")
        return False

    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github+json"
    }

    url = f"https://api.github.com/repos/{repo}/contents/{path}"

    # Check if file exists
    r = requests.get(url, headers=headers)
    sha = None
    if r.status_code == 200:
        content = r.json()
        sha = content["sha"]
        existing_csv = base64.b64decode(content["content"]).decode("utf-8")
        try:
            old_df = pd.read_csv(StringIO(existing_csv))
            df = pd.concat([old_df, df], ignore_index=True)
            df.drop_duplicates(subset=["Job Position"], keep="last", inplace=True)
        except pd.errors.EmptyDataError:
            # Existing file is empty, just use the new data
            pass
    elif r.status_code == 401:
        st.error(f"❌ GitHub authentication failed: {r.status_code} - {r.text}")
        return False
    elif r.status_code != 404:
        st.warning(f"⚠️ Could not check existing file: {r.status_code} - {r.text}")

    # Encode CSV
    csv_bytes = df.to_csv(index=False).encode("utf-8")
    encoded = base64.b64encode(csv_bytes).decode("utf-8")

    # Prepare payload
    data = {
        "message": "📋 Update job_positions.csv via Streamlit app",
        "content": encoded,
        "branch": branch
    }
    if sha:
        data["sha"] = sha

    # Upload to GitHub
    res = requests.put(url, headers=headers, data=json.dumps(data))
    if res.status_code in [200, 201]:
        st.success("✅ Job positions successfully saved to GitHub!")
        return True
    else:
        st.error(f"❌ GitHub save failed: {res.status_code} - {res.text}")
        return False


def load_job_positions_from_github(path="job_positions.csv"):
    """Load job_positions.csv from GitHub repo, with fallback to local file."""
    token = st.secrets.get("GITHUB_TOKEN")
    repo = st.secrets.get("GITHUB_REPO", "netrialiarahmi/cv-matching-auto")
    branch = st.secrets.get("GITHUB_BRANCH", "main")

    # Try to load from GitHub first
    if token:
        headers = {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github+json"
        }

        url = f"https://api.github.com/repos/{repo}/contents/{path}?ref={branch}"
        
        try:
            r = requests.get(url, headers=headers, timeout=GITHUB_TIMEOUT)
            
            if r.status_code == 200:
                content = r.json()
                file_size = content.get("size", 0)
                
                # GitHub Contents API has a size limit for inline content
                # For files larger than this, download via raw URL instead
                if file_size > GITHUB_CONTENTS_API_SIZE_LIMIT:
                    # Use raw.githubusercontent.com for large files (no auth needed for public repos)
                    raw_url = f"https://raw.githubusercontent.com/{repo}/{branch}/{path}"
                    r_raw = requests.get(raw_url, timeout=GITHUB_TIMEOUT)
                    if r_raw.status_code == 200:
                        try:
                            df = pd.read_csv(StringIO(r_raw.text))
                            return df
                        except pd.errors.EmptyDataError:
                            return pd.DataFrame(columns=["Job Position", "Job Description", "Date Created"])
                        except Exception as e:
                            st.warning(f"⚠️ Failed to parse large GitHub file: {str(e)}. Trying local file.")
                            # Fall through to local file fallback
                    else:
                        st.warning(f"⚠️ Failed to download large file from GitHub ({r_raw.status_code}). Trying local file.")
                        # Fall through to local file fallback
                else:
                    # File is small enough, use Contents API
                    try:
                        decoded = base64.b64decode(content["content"]).decode("utf-8")
                        return pd.read_csv(StringIO(decoded))
                    except pd.errors.EmptyDataError:
                        # Empty file, return empty DataFrame with expected columns
                        return pd.DataFrame(columns=["Job Position", "Job Description", "Date Created"])
                    except Exception as e:
                        st.warning(f"⚠️ Failed to parse GitHub file: {str(e)}. Trying local file.")
                        # Fall through to local file fallback
            elif r.status_code == 404:
                st.info(f"ℹ️ File not found in GitHub branch '{branch}'. Checking local file.")
                # Fall through to local file fallback
            else:
                st.warning(f"⚠️ GitHub load failed ({r.status_code}). Trying local file.")
                # Fall through to local file fallback
                
        except requests.exceptions.RequestException as e:
            st.warning(f"⚠️ Failed to connect to GitHub: {str(e)}. Trying local file.")
            # Fall through to local file fallback
    
    # Fallback to local file
    if os.path.exists(path):
        try:
            df = pd.read_csv(path)
            if not df.empty:
            return df
        except pd.errors.EmptyDataError:
            return pd.DataFrame(columns=["Job Position", "Job Description", "Date Created"])
        except Exception as e:
            st.error(f"❌ Failed to load local {path}: {str(e)}")
            return None
    else:
        # Neither GitHub nor local file exists - return empty DataFrame with expected columns
        return pd.DataFrame(columns=["Job Position", "Job Description", "Date Created"])


def delete_job_position_from_github(job_position, path="job_positions.csv"):
    """Delete a specific job position from GitHub repo.
    
    Args:
        job_position (str): The job position name to delete
        path (str): Path to the CSV file in GitHub
        
    Returns:
        bool: True if delete was successful, False otherwise.
    """
    token = st.secrets.get("GITHUB_TOKEN")
    repo = st.secrets.get("GITHUB_REPO", "netrialiarahmi/cv-matching-auto")
    branch = st.secrets.get("GITHUB_BRANCH", "main")

    if not token:
        st.error("❌ Missing GITHUB_TOKEN in Streamlit secrets.")
        return False

    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github+json"
    }

    url = f"https://api.github.com/repos/{repo}/contents/{path}"

    # Load existing data
    r = requests.get(url, headers=headers)
    if r.status_code != 200:
        st.error(f"❌ Could not load job positions: {r.status_code}")
        return False
    
    content = r.json()
    sha = content["sha"]
    existing_csv = base64.b64decode(content["content"]).decode("utf-8")
    try:
        df = pd.read_csv(StringIO(existing_csv))
    except pd.errors.EmptyDataError:
        st.error(f"❌ Cannot delete from empty file")
        return False
    
    # Remove the job position
    df = df[df["Job Position"] != job_position]
    
    # Encode and save
    csv_bytes = df.to_csv(index=False).encode("utf-8")
    encoded = base64.b64encode(csv_bytes).decode("utf-8")

    data = {
        "message": f"🗑️ Delete job position: {job_position}",
        "content": encoded,
        "branch": branch,
        "sha": sha
    }

    res = requests.put(url, headers=headers, data=json.dumps(data))
    if res.status_code in [200, 201]:
        return True
    else:
        st.error(f"❌ GitHub delete failed: {res.status_code} - {res.text}")
        return False


def update_results_in_github(df, path=None, job_position=None, max_retries=3):
    """Replace the entire results file with the provided DataFrame for a specific position.
    
    This is different from save_results_to_github which appends/merges data.
    Use this when you want to update existing records (e.g., updating shortlist status).
    
    Args:
        df: DataFrame to save (replaces existing file)
        path: (Optional) Path to the CSV file in GitHub
        job_position: (Optional) Job position name to generate filename
        max_retries: Maximum number of retry attempts on failure
    
    Returns:
        bool: True if update was successful, False otherwise.
    """
    # Validate input DataFrame
    if df is None:
        st.error("❌ Cannot update: DataFrame is None")
        return False
    
    if df.empty:
        st.warning("⚠️ Cannot update: DataFrame is empty")
        return False
    
    # Determine the file path
    if path is None:
        if job_position is None:
            # If no path and no job_position, try to get it from the dataframe
            if "Job Position" in df.columns and not df.empty:
                job_position = df["Job Position"].iloc[0]
            else:
                st.error("❌ Cannot update: No path or job_position provided")
                return False
        path = get_results_filename(job_position)
    
    token = st.secrets.get("GITHUB_TOKEN")
    repo = st.secrets.get("GITHUB_REPO", "netrialiarahmi/cv-matching-auto")
    branch = st.secrets.get("GITHUB_BRANCH", "main")

    if not token:
        st.error("❌ Missing GITHUB_TOKEN in Streamlit secrets.")
        return False

    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github+json"
    }

    url = f"https://api.github.com/repos/{repo}/contents/{path}"

    # Retry loop
    for attempt in range(max_retries):
        try:
            # Get the current file SHA (required for updates)
            r = requests.get(url, headers=headers, timeout=GITHUB_TIMEOUT)
            sha = None
            if r.status_code == 200:
                content = r.json()
                sha = content["sha"]
            elif r.status_code == 401:
                st.error(f"❌ GitHub authentication failed: {r.status_code} - {r.text}")
                return False
            elif r.status_code != 404:
                if attempt == max_retries - 1:
                    st.warning(f"⚠️ Could not check existing file: {r.status_code} - {r.text}")

            # Encode CSV
            csv_bytes = df.to_csv(index=False).encode("utf-8")
            encoded = base64.b64encode(csv_bytes).decode("utf-8")

            # Prepare payload
            data = {
                "message": "📊 Update results.csv (shortlist status) via Streamlit app",
                "content": encoded,
                "branch": branch
            }
            if sha:
                data["sha"] = sha

            # Upload to GitHub
            res = requests.put(url, headers=headers, data=json.dumps(data), timeout=GITHUB_TIMEOUT)
            if res.status_code in [200, 201]:
                return True
            elif res.status_code == 409:
                # Conflict - file was updated by someone else, retry
                if attempt < max_retries - 1:
                    time.sleep(1)
                    continue
                else:
                    st.error(f"❌ GitHub update failed after {max_retries} attempts: File conflict")
                    return False
            else:
                if attempt == max_retries - 1:
                    st.error(f"❌ GitHub update failed: {res.status_code} - {res.text}")
                return False
                
        except requests.exceptions.Timeout:
            if attempt < max_retries - 1:
                time.sleep(2)
                continue
            else:
                st.error(f"❌ GitHub update failed: Connection timeout after {max_retries} attempts")
                return False
        except requests.exceptions.RequestException as e:
            if attempt < max_retries - 1:
                time.sleep(2)
                continue
            else:
                st.error(f"❌ GitHub update failed: Network error - {str(e)}")
                return False
        except Exception as e:
            if attempt == max_retries - 1:
                st.error(f"❌ Unexpected error while updating: {str(e)}")
            return False
    
    return False


def update_job_position_in_github(old_position, new_position, new_description, path="job_positions.csv"):
    """Update a specific job position in GitHub repo.
    
    Args:
        old_position (str): The original job position name
        new_position (str): The new job position name
        new_description (str): The new job description
        path (str): Path to the CSV file in GitHub
        
    Returns:
        bool: True if update was successful, False otherwise.
    """
    token = st.secrets.get("GITHUB_TOKEN")
    repo = st.secrets.get("GITHUB_REPO", "netrialiarahmi/cv-matching-auto")
    branch = st.secrets.get("GITHUB_BRANCH", "main")

    if not token:
        st.error("❌ Missing GITHUB_TOKEN in Streamlit secrets.")
        return False

    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github+json"
    }

    url = f"https://api.github.com/repos/{repo}/contents/{path}"

    # Load existing data
    r = requests.get(url, headers=headers)
    if r.status_code != 200:
        st.error(f"❌ Could not load job positions: {r.status_code}")
        return False
    
    content = r.json()
    sha = content["sha"]
    existing_csv = base64.b64decode(content["content"]).decode("utf-8")
    try:
        df = pd.read_csv(StringIO(existing_csv))
    except pd.errors.EmptyDataError:
        st.error(f"❌ Cannot update from empty file")
        return False
    
    # Update the job position
    mask = df["Job Position"] == old_position
    if mask.sum() == 0:
        st.error(f"❌ Job position '{old_position}' not found")
        return False
    
    df.loc[mask, "Job Position"] = new_position
    df.loc[mask, "Job Description"] = new_description
    df.loc[mask, "Date Created"] = pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Encode and save
    csv_bytes = df.to_csv(index=False).encode("utf-8")
    encoded = base64.b64encode(csv_bytes).decode("utf-8")

    data = {
        "message": f"✏️ Update job position: {old_position} → {new_position}",
        "content": encoded,
        "branch": branch,
        "sha": sha
    }

    res = requests.put(url, headers=headers, data=json.dumps(data))
    if res.status_code in [200, 201]:
        return True
    else:
        st.error(f"❌ GitHub update failed: {res.status_code} - {res.text}")
        return False
