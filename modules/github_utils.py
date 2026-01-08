import base64
import json
import os
import sys
import requests
import pandas as pd
from io import StringIO
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

# Try to import streamlit, but it's optional (for GitHub Actions compatibility)
try:
    import streamlit as st
    HAS_STREAMLIT = True
except ImportError:
    HAS_STREAMLIT = False
    # Create a dummy st object with cache_data decorator for non-Streamlit environments
    class _DummyCache:
        def __call__(self, *args, **kwargs):
            def decorator(func):
                return func
            return decorator
    
    st = type('obj', (object,), {
        'cache_data': _DummyCache()
    })()


def _get_config(key, default=None):
    """
    Get configuration value from environment variables or Streamlit secrets.
    Checks environment variables first (for GitHub Actions), then falls back to Streamlit secrets.
    
    Args:
        key: Configuration key name
        default: Default value if key not found
        
    Returns:
        Configuration value or default
    """
    # First check environment variables (for GitHub Actions)
    value = os.environ.get(key)
    if value is not None:
        return value
    
    # Fall back to Streamlit secrets (for Streamlit app)
    if HAS_STREAMLIT:
        try:
            return st.secrets.get(key, default)
        except Exception:
            return default
    
    return default


def _log_error(message):
    """Log error message. Uses Streamlit if available, otherwise prints to stderr."""
    if HAS_STREAMLIT:
        st.error(message)
    else:
        print(f"ERROR: {message}", file=sys.stderr)


def _log_warning(message):
    """Log warning message. Uses Streamlit if available, otherwise prints to stderr."""
    if HAS_STREAMLIT:
        st.warning(message)
    else:
        print(f"WARNING: {message}", file=sys.stderr)


def _log_success(message):
    """Log success message. Uses Streamlit if available, otherwise prints to stdout."""
    if HAS_STREAMLIT:
        st.success(message)
    else:
        print(f"SUCCESS: {message}")


def _log_info(message):
    """Log info message. Uses Streamlit if available, otherwise prints to stdout."""
    if HAS_STREAMLIT:
        st.info(message)
    else:
        print(f"INFO: {message}")

# Expected columns for results.csv
RESULTS_COLUMNS = [
    "Candidate Name", "Candidate Email", "Phone", "Job Position",
    "Match Score", "AI Summary", "Strengths", "Weaknesses", "Gaps",
    "Latest Job Title", "Latest Company", "Education", "University", "Major",
    "Kalibrr Profile", "Application Link", "Resume Link",
    "Recruiter Feedback", "Shortlisted", "Candidate Status", "Interview Status", "Rejection Reason", "Date Processed"
]

# Network timeout for GitHub API requests (in seconds)
GITHUB_TIMEOUT = 30

# GitHub Contents API size limit for inline content (bytes)
# Files larger than this should be downloaded via raw URL
GITHUB_CONTENTS_API_SIZE_LIMIT = 1_000_000  # 1MB

# Maximum number of parallel downloads for fetching CSV files
MAX_PARALLEL_DOWNLOADS = 8

# Results directory path
RESULTS_DIR = "results"


def _deduplicate_candidates(df):
    """Deduplicate candidates while handling empty emails properly.
    
    For rows with valid emails: deduplicates by email + job position.
    For rows without emails: deduplicates by candidate name + phone + job position.
    Preserves original row order.
    
    Args:
        df: DataFrame with candidate data
        
    Returns:
        pd.DataFrame: Deduplicated DataFrame with original order preserved
    """
    if df.empty:
        return df
    
    if "Candidate Email" in df.columns and "Job Position" in df.columns:
        # Reset index to ensure consistent indexing for order preservation
        df = df.reset_index(drop=True)
        
        # Separate rows with valid emails from those without
        has_email = df["Candidate Email"].notna() & (df["Candidate Email"] != "")
        
        # Get indices to keep from rows with emails
        df_with_email = df.loc[has_email]
        if not df_with_email.empty:
            keep_email_indices = df_with_email.drop_duplicates(
                subset=["Candidate Email", "Job Position"], keep="first"
            ).index.tolist()
        else:
            keep_email_indices = []
        
        # Get indices to keep from rows without emails (use candidate name + phone instead)
        df_without_email = df.loc[~has_email]
        if not df_without_email.empty:
            if "Candidate Name" in df.columns and "Phone" in df.columns:
                # Use name + phone for better deduplication
                keep_name_indices = df_without_email.drop_duplicates(
                    subset=["Candidate Name", "Phone", "Job Position"], keep="first"
                ).index.tolist()
            elif "Candidate Name" in df.columns:
                # Fallback to name only if phone not available
                keep_name_indices = df_without_email.drop_duplicates(
                    subset=["Candidate Name", "Job Position"], keep="first"
                ).index.tolist()
            else:
                # No deduplication possible without email or name
                keep_name_indices = df_without_email.index.tolist()
        else:
            keep_name_indices = []
        
        # Combine indices and sort to preserve original order
        all_keep_indices = sorted(keep_email_indices + keep_name_indices)
        return df.loc[all_keep_indices].reset_index(drop=True)
    
    elif "Filename" in df.columns and "Job Position" in df.columns:
        return df.drop_duplicates(subset=["Filename", "Job Position"], keep="first")
    
    return df


def get_results_filename(job_position):
    """Generate a safe filename for storing results by job position.
    
    Args:
        job_position: The job position name
        
    Returns:
        str: Safe filename like "results/results_Account_Executive_VCBL.csv"
    """
    import re
    # Replace special characters with underscore using regex
    # Keep only alphanumeric, spaces, and underscores
    safe_name = re.sub(r'[^\w\s]', '', job_position)  # Remove special chars
    safe_name = re.sub(r'\s+', '_', safe_name)  # Replace spaces with underscore
    safe_name = re.sub(r'_+', '_', safe_name)  # Collapse multiple underscores
    return f"{RESULTS_DIR}/results_{safe_name}.csv"


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
        _log_error("❌ Cannot save: DataFrame is None")
        return False
    
    if df.empty:
        _log_warning("⚠️ Cannot save: DataFrame is empty")
        return False
    
    # Ensure required columns exist
    required_columns = ["Candidate Name", "Job Position"]
    missing_columns = [col for col in required_columns if col not in df.columns]
    if missing_columns:
        _log_error(f"❌ Cannot save: Missing required columns: {', '.join(missing_columns)}")
        return False
    
    # Determine the file path
    if path is None:
        if job_position is None:
            # If no path and no job_position, try to get it from the dataframe
            if "Job Position" in df.columns and not df.empty:
                job_position = df["Job Position"].iloc[0]
            else:
                _log_error("❌ Cannot save: No path or job_position provided")
                return False
        path = get_results_filename(job_position)
    
    token = _get_config("GITHUB_TOKEN")
    repo = _get_config("GITHUB_REPO", "netrialiarahmi/cv-matching-auto")
    branch = _get_config("GITHUB_BRANCH", "main")

    if not token:
        _log_error("❌ Missing GITHUB_TOKEN in Streamlit secrets.")
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
                        _log_error(f"❌ CRITICAL: Could not download large file ({file_size:,} bytes). Data loss may occur!")
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
                            df = pd.concat([old_df, df], ignore_index=True)
                    except pd.errors.EmptyDataError:
                        # Existing file is completely empty (no header), just use the new data
                        pass
                    except (pd.errors.ParserError, ValueError) as e:
                        # Log parsing error but continue with new data
                        if attempt == max_retries - 1:
                            _log_warning(f"⚠️ Could not parse existing data (using new data only): {str(e)}")
                
                # Apply deduplication to remove duplicates (handles both merged and new-only data)
                # Keep 'first' to preserve existing records and their shortlist status
                df = _deduplicate_candidates(df)
            elif r.status_code == 401:
                _log_error(f"❌ GitHub authentication failed: {r.status_code} - {r.text}")
                return False
            elif r.status_code != 404:
                # 404 is expected for new files, other errors should be reported
                if attempt == max_retries - 1:
                    _log_warning(f"⚠️ Could not check existing file: {r.status_code} - {r.text}")

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
                    _log_error(f"❌ GitHub save failed after {max_retries} attempts: File conflict")
                    return False
            else:
                if attempt == max_retries - 1:
                    _log_error(f"❌ GitHub save failed: {res.status_code} - {res.text}")
                return False
                
        except requests.exceptions.Timeout:
            if attempt < max_retries - 1:
                time.sleep(2)  # Wait before retrying
                continue
            else:
                _log_error(f"❌ GitHub save failed: Connection timeout after {max_retries} attempts")
                return False
        except requests.exceptions.RequestException as e:
            if attempt < max_retries - 1:
                time.sleep(2)  # Wait before retrying
                continue
            else:
                _log_error(f"❌ GitHub save failed: Network error - {str(e)}")
                return False
        except Exception as e:
            if attempt == max_retries - 1:
                _log_error(f"❌ Unexpected error while saving: {str(e)}")
            return False
    
    return False


def load_results_from_github(path="results.csv"):
    """Load results.csv from GitHub repo, with fallback to local file.
    
    Returns:
        pd.DataFrame: DataFrame with results, or empty DataFrame with expected columns if file is empty/not found
        None: Only if there's a critical error and no fallback is available
    """
    token = _get_config("GITHUB_TOKEN")
    repo = _get_config("GITHUB_REPO", "netrialiarahmi/cv-matching-auto")
    branch = _get_config("GITHUB_BRANCH", "main")

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
                            _log_warning(f"⚠️ Failed to parse large GitHub file: {str(e)}. Trying local file.")
                            # Fall through to local file fallback
                    else:
                        _log_warning(f"⚠️ Failed to download large file from GitHub ({r_raw.status_code}). Trying local file.")
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
                    except Exception:
                        # Fall through to local file fallback
                        pass
            elif r.status_code == 404:
                # File not found in GitHub branch, fall through to local file fallback
                pass
            else:
                # GitHub load failed, fall through to local file fallback
                pass
                
        except requests.exceptions.RequestException:
            # Failed to connect to GitHub, fall through to local file fallback
            pass
    
    # Fallback to local file
    if os.path.exists(path):
        try:
            df = pd.read_csv(path)
            if not df.empty:
                return df
        except pd.errors.EmptyDataError:
            return pd.DataFrame(columns=RESULTS_COLUMNS)
        except Exception:
            return None
    else:
        # Neither GitHub nor local file exists - return empty DataFrame with expected columns
        return pd.DataFrame(columns=RESULTS_COLUMNS)


def _fetch_csv_from_url(session, url, timeout):
    """Helper function to fetch a single CSV from a URL.
    
    Args:
        session: requests.Session object for connection reuse
        url: URL to fetch
        timeout: Request timeout in seconds
        
    Returns:
        pd.DataFrame or None if fetch fails
    """
    try:
        resp = session.get(url, timeout=timeout)
        if resp.status_code == 200:
            try:
                csv_text = resp.text
                df = pd.read_csv(StringIO(csv_text))
                # Ensure expected columns exist
                for col in RESULTS_COLUMNS:
                    if col not in df.columns:
                        df[col] = ""
                return df
            except (pd.errors.EmptyDataError, pd.errors.ParserError):
                # CSV is empty or malformed
                return None
        return None
    except (requests.exceptions.RequestException, requests.exceptions.Timeout):
        # Network error or timeout - skip this file
        return None


@st.cache_data(ttl=300)  # Cache for 5 minutes
def load_all_results_from_github():
    """Load all results from GitHub by finding and merging all results_*.csv files.
    
    Optimizations:
    - Uses st.cache_data to cache results for 5 minutes (prevents re-fetching on every rerun)
    - Uses download_url (raw) directly to avoid extra API calls
    - Downloads CSVs in parallel using ThreadPoolExecutor to reduce latency
    - Uses a session for TCP connection reuse
    
    This function discovers all position-specific result files (results/results_*.csv) and merges them
    into a single DataFrame for the Dashboard "All" view.
    
    Returns:
        pd.DataFrame: Merged DataFrame with all results, or empty DataFrame if no files found
    """
    token = _get_config("GITHUB_TOKEN")
    repo = _get_config("GITHUB_REPO", "netrialiarahmi/cv-matching-auto")
    branch = _get_config("GITHUB_BRANCH", "main")
    
    headers = {}
    if token:
        headers = {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github+json"
        }
    
    # Get list of files in the results/ directory
    url = f"https://api.github.com/repos/{repo}/contents/{RESULTS_DIR}?ref={branch}"
    
    try:
        r = requests.get(url, headers=headers, timeout=GITHUB_TIMEOUT)
        if r.status_code != 200:
            return pd.DataFrame(columns=RESULTS_COLUMNS)
        files = r.json()
    except Exception:
        return pd.DataFrame(columns=RESULTS_COLUMNS)
    
    # Collect download URLs for all results_*.csv files
    download_tasks = []
    for item in files:
        name = item.get("name", "")
        if name.startswith("results_") and name.endswith(".csv"):
            # Prefer direct download_url (raw) to avoid extra API calls
            download_url = item.get("download_url")
            if download_url:
                download_tasks.append(download_url)
    
    if not download_tasks:
        return pd.DataFrame(columns=RESULTS_COLUMNS)
    
    # Create session to reuse TCP connections
    session = requests.Session()
    if headers.get("Authorization"):
        session.headers.update({"Authorization": headers["Authorization"]})
    
    dfs = []
    
    # Parallel fetch for better performance
    max_workers = min(MAX_PARALLEL_DOWNLOADS, len(download_tasks))
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_url = {
            executor.submit(_fetch_csv_from_url, session, url, GITHUB_TIMEOUT): url 
            for url in download_tasks
        }
        for future in as_completed(future_to_url):
            try:
                df = future.result()
                if df is not None and not df.empty:
                    dfs.append(df)
            except Exception:
                # Silently skip failed downloads - the file may be malformed or inaccessible
                continue
    
    if not dfs:
        return pd.DataFrame(columns=RESULTS_COLUMNS)
    
    merged = pd.concat(dfs, ignore_index=True, sort=False)
    
    # Remove duplicates while handling empty emails properly
    try:
        merged = _deduplicate_candidates(merged)
    except Exception:
        # If deduplication fails, return the merged data without deduplication
        pass
    
    return merged


@st.cache_data(ttl=300)  # Cache for 5 minutes
def load_results_for_position(job_position):
    """Load results for a specific job position from GitHub.
    
    This is more efficient than load_all_results_from_github when filtering by position,
    as it only downloads the single file for that position.
    
    Args:
        job_position: The job position name to load results for
        
    Returns:
        pd.DataFrame: DataFrame with results for the position, or empty DataFrame if not found
    """
    filename = get_results_filename(job_position)
    df = load_results_from_github(path=filename)
    if df is None:
        return pd.DataFrame(columns=RESULTS_COLUMNS)
    return df


def clear_results_cache():
    """Clear the cached results data.
    
    Call this after saving new results to ensure the dashboard shows fresh data.
    """
    load_all_results_from_github.clear()
    load_results_for_position.clear()


def save_job_positions_to_github(df, path="job_positions.csv"):
    """Save or update job_positions.csv in GitHub repo.
    
    Returns:
        bool: True if save was successful, False otherwise.
    """
    token = _get_config("GITHUB_TOKEN")
    repo = _get_config("GITHUB_REPO", "netrialiarahmi/cv-matching-auto")
    branch = _get_config("GITHUB_BRANCH", "main")

    if not token:
        _log_error("❌ Missing GITHUB_TOKEN in Streamlit secrets.")
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
            
            # Ensure Job ID column exists in both dataframes
            if "Job ID" not in old_df.columns:
                old_df["Job ID"] = ""
            
            if "Job ID" not in df.columns:
                df["Job ID"] = ""
            
            # Merge the dataframes
            df = pd.concat([old_df, df], ignore_index=True)
            
            # Remove duplicates:
            # - For rows WITH Job ID: deduplicate by Job ID
            # - For rows WITHOUT Job ID: deduplicate by Job Position name
            # This prevents losing old positions that don't have Job IDs yet
            
            # Separate rows with and without Job ID
            has_job_id = df["Job ID"].notna() & (df["Job ID"] != "")
            
            # Deduplicate rows WITH Job ID
            df_with_id = df[has_job_id].copy()
            if not df_with_id.empty:
                df_with_id = df_with_id.drop_duplicates(subset=["Job ID"], keep="first")
            
            # Deduplicate rows WITHOUT Job ID by Job Position name
            df_without_id = df[~has_job_id].copy()
            if not df_without_id.empty:
                df_without_id = df_without_id.drop_duplicates(subset=["Job Position"], keep="first")
            
            # Combine back
            df = pd.concat([df_with_id, df_without_id], ignore_index=True)
            
            # Check for duplicate active (non-pooled) Job Position names with different IDs
            # This allows pooled positions to have same name as active positions
            active_positions = df[df.get('Pooling Status', '') != 'Pooled']
            duplicate_active_positions = active_positions[active_positions.duplicated(subset=["Job Position"], keep=False)]
            if not duplicate_active_positions.empty:
                _log_warning(f"⚠️ Found duplicate active job position names: {', '.join(duplicate_active_positions['Job Position'].unique())}")
            
            # Log info about pooled positions with same names (this is allowed)
            pooled_positions = df[df.get('Pooling Status', '') == 'Pooled']
            if not pooled_positions.empty and not active_positions.empty:
                same_name_pooled = set(pooled_positions['Job Position'].unique()) & set(active_positions['Job Position'].unique())
                if same_name_pooled:
                    _log_info(f"ℹ️ Positions with both active and pooled versions: {', '.join(same_name_pooled)}")
                
        except pd.errors.EmptyDataError:
            # Existing file is empty, just use the new data
            # Ensure Job ID column exists
            if "Job ID" not in df.columns:
                df["Job ID"] = ""
    elif r.status_code == 401:
        _log_error(f"❌ GitHub authentication failed: {r.status_code} - {r.text}")
        return False
    elif r.status_code != 404:
        _log_warning(f"⚠️ Could not check existing file: {r.status_code} - {r.text}")

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
        _log_success("✅ Job positions successfully saved to GitHub!")
        return True
    else:
        _log_error(f"❌ GitHub save failed: {res.status_code} - {res.text}")
        return False


def load_job_positions_from_github(path="job_positions.csv"):
    """Load job_positions.csv from GitHub repo, with fallback to local file."""
    token = _get_config("GITHUB_TOKEN")
    repo = _get_config("GITHUB_REPO", "netrialiarahmi/cv-matching-auto")
    branch = _get_config("GITHUB_BRANCH", "main")

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
                            _log_warning(f"⚠️ Failed to parse large GitHub file: {str(e)}. Trying local file.")
                            # Fall through to local file fallback
                    else:
                        _log_warning(f"⚠️ Failed to download large file from GitHub ({r_raw.status_code}). Trying local file.")
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
                        _log_warning(f"⚠️ Failed to parse GitHub file: {str(e)}. Trying local file.")
                        # Fall through to local file fallback
            elif r.status_code == 404:
                # File not found in GitHub branch, fall through to local file fallback
                pass
            else:
                # GitHub load failed, fall through to local file fallback
                pass
                
        except requests.exceptions.RequestException:
            # Failed to connect to GitHub, fall through to local file fallback
            pass
    
    # Fallback to local file
    if os.path.exists(path):
        try:
            df = pd.read_csv(path)
            if not df.empty:
                return df
        except pd.errors.EmptyDataError:
            return pd.DataFrame(columns=["Job Position", "Job Description", "Date Created"])
        except Exception:
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
    token = _get_config("GITHUB_TOKEN")
    repo = _get_config("GITHUB_REPO", "netrialiarahmi/cv-matching-auto")
    branch = _get_config("GITHUB_BRANCH", "main")

    if not token:
        _log_error("❌ Missing GITHUB_TOKEN in Streamlit secrets.")
        return False

    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github+json"
    }

    url = f"https://api.github.com/repos/{repo}/contents/{path}"

    # Load existing data
    r = requests.get(url, headers=headers)
    if r.status_code != 200:
        _log_error(f"❌ Could not load job positions: {r.status_code}")
        return False
    
    content = r.json()
    sha = content["sha"]
    existing_csv = base64.b64decode(content["content"]).decode("utf-8")
    try:
        df = pd.read_csv(StringIO(existing_csv))
    except pd.errors.EmptyDataError:
        _log_error(f"❌ Cannot delete from empty file")
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
        _log_error(f"❌ GitHub delete failed: {res.status_code} - {res.text}")
        return False


def update_results_in_github(df, path=None, job_position=None, max_retries=3, silent=False):
    """Replace the entire results file with the provided DataFrame for a specific position.
    
    This is different from save_results_to_github which appends/merges data.
    Use this when you want to update existing records (e.g., updating shortlist status).
    
    Args:
        df: DataFrame to save (replaces existing file)
        path: (Optional) Path to the CSV file in GitHub
        job_position: (Optional) Job position name to generate filename
        max_retries: Maximum number of retry attempts on failure
        silent: (Optional) If True, suppresses error messages for better performance
    
    Returns:
        bool: True if update was successful, False otherwise.
    """
    # Validate input DataFrame
    if df is None:
        if not silent:
            _log_error("❌ Cannot update: DataFrame is None")
        return False
    
    if df.empty:
        if not silent:
            _log_warning("⚠️ Cannot update: DataFrame is empty")
        return False
    
    # Determine the file path
    if path is None:
        if job_position is None:
            # If no path and no job_position, try to get it from the dataframe
            if "Job Position" in df.columns and not df.empty:
                job_position = df["Job Position"].iloc[0]
            else:
                if not silent:
                    _log_error("❌ Cannot update: No path or job_position provided")
                return False
        path = get_results_filename(job_position)
    
    token = _get_config("GITHUB_TOKEN")
    repo = _get_config("GITHUB_REPO", "netrialiarahmi/cv-matching-auto")
    branch = _get_config("GITHUB_BRANCH", "main")

    if not token:
        if not silent:
            _log_error("❌ Missing GITHUB_TOKEN in Streamlit secrets.")
        return False

    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github+json"
    }

    url = f"https://api.github.com/repos/{repo}/contents/{path}"

    # Pre-encode CSV outside the retry loop for efficiency
    csv_bytes = df.to_csv(index=False).encode("utf-8")
    encoded = base64.b64encode(csv_bytes).decode("utf-8")

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
                if not silent:
                    _log_error(f"❌ GitHub authentication failed: {r.status_code} - {r.text}")
                return False
            elif r.status_code != 404:
                if attempt == max_retries - 1 and not silent:
                    _log_warning(f"⚠️ Could not check existing file: {r.status_code} - {r.text}")

            # Prepare payload with timestamp for better tracking
            data = {
                "message": f"📊 Update candidate status ({path}) - {time.strftime('%Y-%m-%d %H:%M:%S')}",
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
                # Conflict - file was updated by someone else, retry with exponential backoff
                if attempt < max_retries - 1:
                    time.sleep(0.5 * (2 ** attempt))  # Exponential backoff: 0.5s, 1s, 2s
                    continue
                else:
                    if not silent:
                        _log_error(f"❌ GitHub update failed after {max_retries} attempts: File conflict")
                    return False
            else:
                if attempt == max_retries - 1 and not silent:
                    _log_error(f"❌ GitHub update failed: {res.status_code} - {res.text}")
                return False
                
        except requests.exceptions.Timeout:
            if attempt < max_retries - 1:
                time.sleep(0.5 * (2 ** attempt))  # Exponential backoff
                continue
            else:
                if not silent:
                    _log_error(f"❌ GitHub update failed: Connection timeout after {max_retries} attempts")
                return False
        except requests.exceptions.RequestException as e:
            if attempt < max_retries - 1:
                time.sleep(0.5 * (2 ** attempt))  # Exponential backoff
                continue
            else:
                if not silent:
                    _log_error(f"❌ GitHub update failed: Network error - {str(e)}")
                return False
        except Exception as e:
            if attempt == max_retries - 1 and not silent:
                _log_error(f"❌ Unexpected error while updating: {str(e)}")
            return False
    
    return False


def update_job_position_in_github(old_position, new_position, new_description, new_job_id=None, path="job_positions.csv"):
    """Update a specific job position in GitHub repo.
    
    Args:
        old_position (str): The original job position name
        new_position (str): The new job position name
        new_description (str): The new job description
        new_job_id (str): The new Job ID (optional)
        path (str): Path to the CSV file in GitHub
        
    Returns:
        bool: True if update was successful, False otherwise.
    """
    token = _get_config("GITHUB_TOKEN")
    repo = _get_config("GITHUB_REPO", "netrialiarahmi/cv-matching-auto")
    branch = _get_config("GITHUB_BRANCH", "main")

    if not token:
        _log_error("❌ Missing GITHUB_TOKEN in Streamlit secrets.")
        return False

    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github+json"
    }

    url = f"https://api.github.com/repos/{repo}/contents/{path}"

    # Load existing data
    r = requests.get(url, headers=headers)
    if r.status_code != 200:
        _log_error(f"❌ Could not load job positions: {r.status_code}")
        return False
    
    content = r.json()
    sha = content["sha"]
    existing_csv = base64.b64decode(content["content"]).decode("utf-8")
    try:
        df = pd.read_csv(StringIO(existing_csv))
    except pd.errors.EmptyDataError:
        _log_error(f"❌ Cannot update from empty file")
        return False
    
    # Update the job position
    mask = df["Job Position"] == old_position
    if mask.sum() == 0:
        _log_error(f"❌ Job position '{old_position}' not found")
        return False
    
    df.loc[mask, "Job Position"] = new_position
    df.loc[mask, "Job Description"] = new_description
    
    # Update Job ID if provided
    if new_job_id is not None:
        if "Job ID" not in df.columns:
            df["Job ID"] = ""
        df.loc[mask, "Job ID"] = new_job_id
    
    # Keep the original Date Created, add Last Modified
    if "Last Modified" not in df.columns:
        df["Last Modified"] = ""
    df.loc[mask, "Last Modified"] = pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S")
    
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
        _log_error(f"❌ GitHub update failed: {res.status_code} - {res.text}")
        return False


def toggle_job_pooling_status(job_position, pooling_status, path="job_positions.csv"):
    """Toggle pooling status for a specific job position.
    
    Args:
        job_position (str): The job position name
        pooling_status (str): "Pooled" or "" (empty for unpool)
        path (str): Path to the CSV file in GitHub
        
    Returns:
        bool: True if update was successful, False otherwise.
    """
    token = _get_config("GITHUB_TOKEN")
    repo = _get_config("GITHUB_REPO", "netrialiarahmi/cv-matching-auto")
    branch = _get_config("GITHUB_BRANCH", "main")

    if not token:
        _log_error("❌ Missing GITHUB_TOKEN in Streamlit secrets.")
        return False

    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github+json"
    }

    url = f"https://api.github.com/repos/{repo}/contents/{path}"

    # Load existing data
    r = requests.get(url, headers=headers)
    if r.status_code != 200:
        _log_error(f"❌ Failed to load job positions: {r.status_code}")
        return False

    content = r.json()
    sha = content["sha"]
    existing_csv = base64.b64decode(content["content"]).decode("utf-8")
    
    try:
        df = pd.read_csv(StringIO(existing_csv))
    except pd.errors.EmptyDataError:
        _log_error("❌ Job positions file is empty")
        return False
    
    # Ensure Pooling Status column exists
    if "Pooling Status" not in df.columns:
        df["Pooling Status"] = ""
    
    # Find and update the job position
    mask = df["Job Position"] == job_position
    if mask.sum() == 0:
        _log_error(f"❌ Job position '{job_position}' not found")
        return False
    
    df.loc[mask, "Pooling Status"] = pooling_status
    
    # Encode and save
    csv_bytes = df.to_csv(index=False).encode("utf-8")
    encoded = base64.b64encode(csv_bytes).decode("utf-8")

    data = {
        "message": f"📦 Toggle pooling status for: {job_position}",
        "content": encoded,
        "branch": branch,
        "sha": sha
    }

    res = requests.put(url, headers=headers, data=json.dumps(data))
    if res.status_code in [200, 201]:
        return True
    else:
        _log_error(f"❌ GitHub update failed: {res.status_code} - {res.text}")
        return False
