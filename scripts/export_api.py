"""Direct Kalibrr API export — no browser needed."""
import os
import sys
import time
import requests
import pandas as pd
from dotenv import load_dotenv

load_dotenv('.env')

POSITION = "Account Executive Pasangiklan.com"
JOB_ID = 256571

def main():
    kaid = os.getenv("KAID", "").strip().strip('"')
    kb = os.getenv("KB", "").strip().strip('"')
    
    if not kaid or not kb:
        print("ERROR: KAID or KB missing from .env")
        return 1
    
    print(f"Exporting: {POSITION} (JOB_ID: {JOB_ID})")
    
    cookies = {"kaid": kaid, "kb": kb}
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Referer": f"https://www.kalibrr.com/ats/candidates?job_id={JOB_ID}&state_id=19",
        "Origin": "https://www.kalibrr.com",
        "X-Requested-With": "XMLHttpRequest"
    }
    
    # Step 1: Get CSRF token from the candidates page
    session = requests.Session()
    session.cookies.update(cookies)
    
    page_url = f"https://www.kalibrr.com/ats/candidates?job_id={JOB_ID}&state_id=19"
    print(f"Getting CSRF token from: {page_url}")
    r = session.get(page_url, headers={
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        "Accept": "text/html"
    }, timeout=30)
    print(f"  Page status: {r.status_code}")
    
    # Extract CSRF token from cookies or page content
    csrf_token = session.cookies.get("csrf_token") or session.cookies.get("_csrf") or session.cookies.get("XSRF-TOKEN")
    
    if not csrf_token:
        # Try to find in page HTML
        import re
        csrf_match = re.search(r'csrf[_-]token["\s:=]+["\']([^"\']+)', r.text, re.IGNORECASE)
        if csrf_match:
            csrf_token = csrf_match.group(1)
        else:
            # Try meta tag
            csrf_match = re.search(r'<meta\s+name=["\']csrf-token["\']\s+content=["\']([^"\']+)', r.text, re.IGNORECASE)
            if csrf_match:
                csrf_token = csrf_match.group(1)
    
    print(f"  CSRF token: {csrf_token[:20]}..." if csrf_token else "  CSRF token: NOT FOUND")
    print(f"  Session cookies: {list(session.cookies.keys())}")
    
    # Step 2: Try export with session (has cookies + CSRF)
    export_headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Referer": page_url,
        "Origin": "https://www.kalibrr.com",
        "X-Requested-With": "XMLHttpRequest"
    }
    if csrf_token:
        export_headers["X-CSRF-Token"] = csrf_token
        export_headers["X-XSRF-TOKEN"] = csrf_token
    
    export_url = f"https://www.kalibrr.com/kjs/ats/job/{JOB_ID}/candidate_exports"
    print(f"\nTriggering export: POST {export_url}")
    r = session.post(export_url, headers=export_headers, json={"state_id": 19}, timeout=30)
    print(f"  Status: {r.status_code}")
    print(f"  Body: {r.text[:300]}")
    
    if r.status_code in [200, 201, 202]:
        data = r.json()
        upload_id = data.get("id") or data.get("upload_id")
        if upload_id:
            print(f"  Upload ID: {upload_id}")
            return poll_and_download(upload_id, cookies, export_headers)
    
    # Alternative: try /kjs/ats/candidates/export
    export_url2 = "https://www.kalibrr.com/kjs/ats/candidates/export"
    print(f"\nTrying alternative: POST {export_url2}")
    r = session.post(export_url2, headers=export_headers, json={"job_id": JOB_ID, "state_id": 19}, timeout=30)
    print(f"  Status: {r.status_code}")
    print(f"  Body: {r.text[:300]}")
    
    if r.status_code in [200, 201, 202]:
        data = r.json()
        upload_id = data.get("id") or data.get("upload_id")
        if upload_id:
            return poll_and_download(upload_id, cookies, export_headers)
    
    print("\nExport API failed. Try manual export from Kalibrr ATS.")
    return 1


def poll_and_download(upload_id, cookies, headers):
    poll_url = f"https://www.kalibrr.com/api/candidate_uploads/{upload_id}?url_only=true"
    print(f"\nPolling: {poll_url}")
    
    for i in range(60):
        time.sleep(5)
        r = requests.get(poll_url, cookies=cookies, headers=headers)
        if r.status_code == 200:
            csv_url = r.text.replace('"', '').strip()
            if csv_url.startswith("https://storage.googleapis.com"):
                print(f"CSV URL ready: {csv_url[:80]}...")
                return download_csv(csv_url, upload_id)
            print(f"  Polling ({(i+1)*5}s)...")
        else:
            print(f"  Poll error: {r.status_code}")
    
    print("Timeout")
    return 1


def download_csv(csv_url, upload_id):
    print("Downloading CSV...")
    r = requests.get(csv_url)
    if r.status_code != 200:
        print(f"Download failed: {r.status_code}")
        return 1
    
    safe_name = POSITION.replace(" ", "_").replace(".", "").replace("/", "_")
    filepath = f"data/raw/{safe_name}.csv"
    os.makedirs("data/raw", exist_ok=True)
    with open(filepath, "w") as f:
        f.write(r.text)
    
    df = pd.read_csv(filepath)
    print(f"Downloaded: {filepath} ({len(df)} candidates)")
    print(f"Columns: {list(df.columns)[:8]}...")
    
    # Update sheet_positions.csv
    sheet_path = "data/sheet_positions.csv"
    if os.path.exists(sheet_path):
        sheet_df = pd.read_csv(sheet_path)
    else:
        sheet_df = pd.DataFrame(columns=["Nama Posisi", "JOB_ID", "UPLOAD_ID", "File Storage"])
    
    mask = sheet_df["Nama Posisi"] == POSITION
    if mask.any():
        sheet_df.loc[mask, "JOB_ID"] = JOB_ID
        sheet_df.loc[mask, "UPLOAD_ID"] = upload_id or ""
        sheet_df.loc[mask, "File Storage"] = csv_url
    else:
        new_row = pd.DataFrame([{"Nama Posisi": POSITION, "JOB_ID": JOB_ID, "UPLOAD_ID": upload_id or "", "File Storage": csv_url}])
        sheet_df = pd.concat([sheet_df, new_row], ignore_index=True)
    
    sheet_df.to_csv(sheet_path, index=False)
    print(f"Updated {sheet_path}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
