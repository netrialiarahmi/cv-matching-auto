import base64
import json
import requests
import pandas as pd
import streamlit as st
from io import StringIO

def save_results_to_github(df, path="results.csv"):
    """Save or update results.csv in GitHub repo (root level).
    
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

    # 1️⃣ Cek apakah file sudah ada
    r = requests.get(url, headers=headers)
    sha = None
    if r.status_code == 200:
        content = r.json()
        sha = content["sha"]
        existing_csv = base64.b64decode(content["content"]).decode("utf-8")
        old_df = pd.read_csv(StringIO(existing_csv))
        df = pd.concat([old_df, df], ignore_index=True)
        # Use Candidate Email as unique identifier (new format) or fallback to Filename (old format)
        dedup_columns = ["Candidate Email", "Job Position"] if "Candidate Email" in df.columns else ["Filename", "Job Position"]
        df.drop_duplicates(subset=dedup_columns, keep="last", inplace=True)
    elif r.status_code == 401:
        st.error(f"❌ GitHub authentication failed: {r.status_code} - {r.text}")
        return False
    elif r.status_code != 404:
        # 404 is expected for new files, other errors should be reported
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
    res = requests.put(url, headers=headers, data=json.dumps(data))
    if res.status_code in [200, 201]:
        st.success("✅ Results successfully saved to GitHub!")
        return True
    else:
        st.error(f"❌ GitHub save failed: {res.status_code} - {res.text}")
        return False


def load_results_from_github(path="results.csv"):
    """Load results.csv from GitHub repo."""
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
        return pd.read_csv(StringIO(decoded))
    elif r.status_code == 404:
        st.warning("⚠️ No results.csv found in GitHub repository yet.")
        return None
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
        old_df = pd.read_csv(StringIO(existing_csv))
        df = pd.concat([old_df, df], ignore_index=True)
        df.drop_duplicates(subset=["Job Position"], keep="last", inplace=True)
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
        return pd.read_csv(StringIO(decoded))
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
    df = pd.read_csv(StringIO(existing_csv))
    
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
    df = pd.read_csv(StringIO(existing_csv))
    
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
