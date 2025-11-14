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
        df.drop_duplicates(subset=["Filename", "Job Position"], keep="last", inplace=True)
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
