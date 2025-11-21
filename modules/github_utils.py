import base64
import json
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

def save_results_to_github(df, path="results.csv", max_retries=3):
    """Save or update results.csv in GitHub repo (root level) with retry logic.
    
    Args:
        df: DataFrame to save
        path: Path to the CSV file in GitHub
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
    
    token = st.secrets.get("GITHUB_TOKEN")
    repo = st.secrets.get("GITHUB_REPO", "netrialiarahmi/cv-matching-gemini")
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
                existing_csv = base64.b64decode(content["content"]).decode("utf-8")
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
                        st.warning(f"⚠️ Could not parse existing data (using new data only): {str(e)}")
                
                # Apply deduplication to remove duplicates (handles both merged and new-only data)
                # Use Candidate Email as unique identifier (new format) or fallback to Filename (old format)
                dedup_columns = ["Candidate Email", "Job Position"] if "Candidate Email" in df.columns else ["Filename", "Job Position"]
                if all(col in df.columns for col in dedup_columns):
                    df.drop_duplicates(subset=dedup_columns, keep="last", inplace=True)
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
    """Load results.csv from GitHub repo.
    
    Returns:
        pd.DataFrame: DataFrame with results, or empty DataFrame with expected columns if file is empty/not found
        None: Only if there's an authentication or connection error
    """
    token = st.secrets.get("GITHUB_TOKEN")
    repo = st.secrets.get("GITHUB_REPO", "netrialiarahmi/cv-matching-gemini")
    branch = st.secrets.get("GITHUB_BRANCH", "main")

    if not token:
        st.error("❌ Missing GITHUB_TOKEN in Streamlit secrets.")
        return None

    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github+json"
    }

    url = f"https://api.github.com/repos/{repo}/contents/{path}?ref={branch}"
    
    try:
        r = requests.get(url, headers=headers, timeout=GITHUB_TIMEOUT)
    except requests.exceptions.RequestException as e:
        st.error(f"❌ Failed to connect to GitHub: {str(e)}")
        return None

    if r.status_code == 200:
        content = r.json()
        decoded = base64.b64decode(content["content"]).decode("utf-8")
        try:
            df = pd.read_csv(StringIO(decoded))
            # Successfully loaded - return the dataframe even if it's empty (has headers but no data)
            return df
        except pd.errors.EmptyDataError:
            # File exists but is completely empty (no headers, no data)
            # Return empty DataFrame with expected columns for consistency
            return pd.DataFrame(columns=RESULTS_COLUMNS)
        except Exception as e:
            st.error(f"❌ Failed to parse results.csv: {str(e)}")
            return None
    elif r.status_code == 404:
        # File doesn't exist yet - return empty DataFrame with expected columns
        return pd.DataFrame(columns=RESULTS_COLUMNS)
    else:
        st.error(f"❌ GitHub load failed: {r.status_code} - {r.text}")
        return None


def save_job_positions_to_github(df, path="job_positions.csv"):
    """Save or update job_positions.csv in GitHub repo.
    
    Returns:
        bool: True if save was successful, False otherwise.
    """
    token = st.secrets.get("GITHUB_TOKEN")
    repo = st.secrets.get("GITHUB_REPO", "netrialiarahmi/cv-matching-gemini")
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
    """Load job_positions.csv from GitHub repo."""
    token = st.secrets.get("GITHUB_TOKEN")
    repo = st.secrets.get("GITHUB_REPO", "netrialiarahmi/cv-matching-gemini")
    branch = st.secrets.get("GITHUB_BRANCH", "main")

    if not token:
        st.error("❌ Missing GITHUB_TOKEN in Streamlit secrets.")
        return None

    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github+json"
    }

    url = f"https://api.github.com/repos/{repo}/contents/{path}?ref={branch}"
    r = requests.get(url, headers=headers)

    if r.status_code == 200:
        content = r.json()
        decoded = base64.b64decode(content["content"]).decode("utf-8")
        try:
            return pd.read_csv(StringIO(decoded))
        except pd.errors.EmptyDataError:
            # Empty file, return empty DataFrame with expected columns
            return pd.DataFrame(columns=["Job Position", "Job Description", "Date Created"])
    elif r.status_code == 404:
        return pd.DataFrame(columns=["Job Position", "Job Description", "Date Created"])
    else:
        st.error(f"❌ GitHub load failed: {r.status_code} - {r.text}")
        return None


def delete_job_position_from_github(job_position, path="job_positions.csv"):
    """Delete a specific job position from GitHub repo.
    
    Args:
        job_position (str): The job position name to delete
        path (str): Path to the CSV file in GitHub
        
    Returns:
        bool: True if delete was successful, False otherwise.
    """
    token = st.secrets.get("GITHUB_TOKEN")
    repo = st.secrets.get("GITHUB_REPO", "netrialiarahmi/cv-matching-gemini")
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


def update_results_in_github(df, path="results.csv", max_retries=3):
    """Replace the entire results.csv file with the provided DataFrame.
    
    This is different from save_results_to_github which appends/merges data.
    Use this when you want to update existing records (e.g., updating shortlist status).
    
    Args:
        df: DataFrame to save (replaces existing file)
        path: Path to the CSV file in GitHub
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
    
    token = st.secrets.get("GITHUB_TOKEN")
    repo = st.secrets.get("GITHUB_REPO", "netrialiarahmi/cv-matching-gemini")
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
    repo = st.secrets.get("GITHUB_REPO", "netrialiarahmi/cv-matching-gemini")
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
