"""
Shared Kalibrr export core module.

Provides reusable functions for:
- Loading positions from job_positions.csv (filtered by Pooling Status)
- Kalibrr API-based export (capturing kb-csrf header via Playwright)
- Updating sheet_positions.csv with local CSV paths

Used by:
- scripts/kalibrr_export_pooling.py
- scripts/kalibrr_export_dashboard.py
"""

import os
import sys
import asyncio
import json
import re
import time
from datetime import datetime
from pathlib import Path
from io import StringIO
import requests
import pandas as pd
from dotenv import load_dotenv

load_dotenv()

# ======================================
# PATHS
# ======================================
PROJECT_ROOT = Path(__file__).resolve().parent.parent
SHEET_POSITIONS_FILE = PROJECT_ROOT / "sheet_positions.csv"
JOB_POSITIONS_FILE = PROJECT_ROOT / "job_positions.csv"
EXPORT_DIR = PROJECT_ROOT / "kalibrr_exports"
EXPORT_DIR.mkdir(exist_ok=True)


# ======================================
# POSITION LOADING (from job_positions.csv)
# ======================================
def load_positions_from_job_csv(filter_pooling="all"):
    """
    Load positions from job_positions.csv, filtered by Pooling Status.

    Args:
        filter_pooling: One of:
            - "pooled"  → return only positions with Pooling Status == "Pooled"
            - "active"  → return only positions with Pooling Status != "Pooled" (or empty)
            - "all"     → return all positions (no filter)

    Returns:
        List of dicts: [{"name": str, "job_id": int, "pooling_status": str}, ...]
        Only positions with a valid Job ID are returned.
    """
    if not JOB_POSITIONS_FILE.exists():
        print(f"❌ {JOB_POSITIONS_FILE} not found")
        return []

    try:
        df = pd.read_csv(JOB_POSITIONS_FILE, dtype=str, keep_default_na=False)
    except Exception as e:
        print(f"❌ Error reading {JOB_POSITIONS_FILE}: {e}")
        return []

    positions = []
    for _, row in df.iterrows():
        name = str(row.get("Job Position", "")).strip()
        job_id_raw = str(row.get("Job ID", "")).strip()
        pooling = str(row.get("Pooling Status", "")).strip()

        if not name:
            continue

        # Parse Job ID — skip if missing or invalid
        if not job_id_raw:
            continue
        try:
            job_id = int(float(job_id_raw))
        except (ValueError, TypeError):
            continue

        # Apply pooling filter
        is_pooled = pooling.lower() == "pooled"
        if filter_pooling == "pooled" and not is_pooled:
            continue
        if filter_pooling == "active" and is_pooled:
            continue

        positions.append({
            "name": name,
            "job_id": job_id,
            "pooling_status": pooling,
        })

    return positions


def load_existing_file_storage():
    """
    Load existing File Storage URLs from sheet_positions.csv.

    Returns:
        dict: {position_name: file_storage_url}
    """
    if not SHEET_POSITIONS_FILE.exists():
        return {}

    try:
        df = pd.read_csv(SHEET_POSITIONS_FILE, dtype=str, keep_default_na=False)
        result = {}
        for _, row in df.iterrows():
            name = str(row.get("Nama Posisi", "")).strip()
            url = str(row.get("File Storage", "")).strip()
            if name and url:
                result[name] = url
        return result
    except Exception:
        return {}


# ======================================
# SHEET_POSITIONS.CSV MANAGEMENT
# ======================================
def update_sheet_positions_csv(export_results):
    """
    Update (upsert) sheet_positions.csv with export results.
    Creates a new row if the position doesn't exist yet.

    Args:
        export_results: List of [position_name, job_id, upload_id, csv_url]
    """
    if not export_results:
        return

    # Load existing or create empty DataFrame
    if SHEET_POSITIONS_FILE.exists():
        try:
            df = pd.read_csv(SHEET_POSITIONS_FILE, dtype=str, keep_default_na=False)
        except Exception:
            df = pd.DataFrame(columns=["Nama Posisi", "JOB_ID", "UPLOAD_ID", "File Storage"])
    else:
        df = pd.DataFrame(columns=["Nama Posisi", "JOB_ID", "UPLOAD_ID", "File Storage"])

    for name, job_id, upload_id, csv_url in export_results:
        mask = df["Nama Posisi"] == name
        if mask.any():
            # Update existing row
            df.loc[mask, "JOB_ID"] = str(job_id) if job_id else ""
            df.loc[mask, "UPLOAD_ID"] = str(upload_id) if upload_id else ""
            df.loc[mask, "File Storage"] = str(csv_url) if csv_url else ""
        else:
            # Insert new row
            new_row = pd.DataFrame([{
                "Nama Posisi": name,
                "JOB_ID": str(job_id) if job_id else "",
                "UPLOAD_ID": str(upload_id) if upload_id else "",
                "File Storage": str(csv_url) if csv_url else "",
            }])
            df = pd.concat([df, new_row], ignore_index=True)

    # Ensure stable dtypes
    df = df.astype({
        "Nama Posisi": "string",
        "JOB_ID": "string",
        "UPLOAD_ID": "string",
        "File Storage": "string",
    })
    df.to_csv(SHEET_POSITIONS_FILE, index=False)
    print(f"✅ Updated {SHEET_POSITIONS_FILE} with {len(export_results)} export result(s)")


# ======================================
# COLUMN NORMALIZATION (API → Kalibrr UI CSV format)
# ======================================
COLUMN_RENAME = {
    "first_name": "First Name",
    "last_name": "Last Name",
    "email": "Email Address",
    "mobile_number": "Mobile Number",
    "resume": "Link Resume",
    "education_level": "Latest Educational Attainment",
    "education_school": "Latest School/University",
    "education_fields": "Latest Major/Course",
    "relevant_work.job_title": "Latest Job Title",
    "relevant_work.company_name": "Latest Company",
}


def _iso_to_kalibrr_date(iso_str):
    """Convert ISO 8601 date to Kalibrr's mm/dd/yy HH:MM format.
    
    Example: '2025-09-29T05:26:25.017968+00:00' → '09/29/25 05:26'
    """
    if not iso_str or not isinstance(iso_str, str):
        return ""
    try:
        # Parse ISO 8601 — handle timezone offset
        dt_str = iso_str.split(".")[0].split("+")[0]  # Strip microseconds and tz
        dt = datetime.strptime(dt_str, "%Y-%m-%dT%H:%M:%S")
        return dt.strftime("%m/%d/%y %H:%M")
    except (ValueError, IndexError):
        return str(iso_str)


def _normalize_export_df(df, job_id):
    """Normalize API export DataFrame to match Kalibrr UI CSV column format.
    
    Renames columns to match what the pipeline expects,
    converts ISO dates, and constructs profile/application URLs.
    """
    # Rename columns to match Kalibrr UI export format
    df = df.rename(columns=COLUMN_RENAME)
    
    # Convert relative resume paths to full URLs
    if "Link Resume" in df.columns:
        df["Link Resume"] = df["Link Resume"].apply(
            lambda r: f"https://www.kalibrr.com{r}" if isinstance(r, str) and r.startswith("/api/") else r
        )
    
    # Convert application.created_at ISO → mm/dd/yy HH:MM format
    if "application.created_at" in df.columns:
        df["Date Application Started (mm/dd/yy hr:mn)"] = df["application.created_at"].apply(_iso_to_kalibrr_date)
    
    # Construct Kalibrr profile URL from user_id
    if "id" in df.columns:
        df["Link Profil Kalibrr"] = df["id"].apply(
            lambda uid: f"https://www.kalibrr.com/profile/{uid}" if pd.notna(uid) else ""
        )
    
    # Construct job application link from user_id + job_id
    if "id" in df.columns:
        df["Link Aplikasi Pekerjaan"] = df["id"].apply(
            lambda uid: f"https://www.kalibrr.com/ats/candidates/{uid}?job_id={job_id}" if pd.notna(uid) else ""
        )
    
    # Construct combined "Nama" field
    if "First Name" in df.columns and "Last Name" in df.columns:
        df["Nama"] = (df["First Name"].fillna("") + " " + df["Last Name"].fillna("")).str.strip()
    
    return df


# ======================================
# KALIBRR EXPORT (API-based via Playwright)
# ======================================
async def export_position(playwright, position_name, job_id, kaid, kb):
    """
    Export candidate data from Kalibrr ATS for a single position using the API.

    Uses Playwright to load the ATS page, captures the kb-csrf header from
    intercepted POST requests, then paginates the /api/ats/candidates endpoint.
    Results are normalized to match the Kalibrr UI CSV export format.

    Args:
        playwright: Playwright instance
        position_name: Display name of the position
        job_id: Kalibrr job ID (int)
        kaid: KAID cookie value
        kb: KB cookie value

    Returns:
        Tuple of (candidate_count_str, csv_path_str) on success,
        or (None, None) on failure.
    """
    state_id = 19  # "New Applicant" / "Applications" state
    url = f"https://www.kalibrr.com/ats/candidates?job_id={job_id}&state_id={state_id}"
    print(f"\n=== Memproses {position_name} ===")
    print(f"URL: {url}")

    browser = await playwright.chromium.launch(headless=True)
    context = await browser.new_context()

    # Inject auth cookies
    await context.add_cookies([
        {"name": "kaid", "value": kaid, "domain": "www.kalibrr.com", "path": "/"},
        {"name": "kb", "value": kb, "domain": "www.kalibrr.com", "path": "/"},
    ])

    page = await context.new_page()

    # ---- Capture POST request headers (to discover kb-csrf) ----
    captured_headers = {}
    post_url = None
    post_body = None

    async def capture_request(request):
        nonlocal captured_headers, post_url, post_body
        if "/api/ats/candidates" in request.url and request.method == "POST":
            try:
                headers = await request.all_headers()
                captured_headers = headers
                post_url = request.url
                post_body = request.post_data
            except Exception:
                pass

    page.on("request", capture_request)

    # Load ATS page to trigger the initial API request
    try:
        await page.goto(url, timeout=60000, wait_until="networkidle")
    except Exception as e:
        print(f"⚠️  Page load lambat: {e}")
        try:
            await page.goto(url, timeout=60000, wait_until="domcontentloaded")
        except Exception as e2:
            print(f"❌ Gagal load page: {e2}")
            await browser.close()
            return None, None

    await page.wait_for_timeout(5000)

    # Check for login redirect
    current_url = page.url
    if "login" in current_url.lower() or "signin" in current_url.lower():
        print("❌ Cookies expired — redirect ke halaman login!")
        print("   Mohon update KAID dan KB di .env / GitHub Secrets")
        await browser.close()
        return None, None

    # Verify we captured the kb-csrf header
    if not captured_headers:
        print("❌ Tidak ada POST request yang ter-capture. kb-csrf header tidak ditemukan.")
        await browser.close()
        return None, None

    csrf_value = captured_headers.get("kb-csrf", "")
    if csrf_value:
        print(f"✓ kb-csrf header captured: {csrf_value[:20]}...")
    else:
        print("⚠️  kb-csrf header kosong, tetap mencoba paginate...")

    # ---- Build replay headers (skip HTTP/2 pseudo-headers) ----
    replay_headers = {}
    for k, v in captured_headers.items():
        if not k.startswith(":"):
            replay_headers[k] = v

    # ---- Paginate the API ----
    payload = json.loads(post_body) if post_body else {
        "limit": 30, "offset": 0,
        "sort_field": "relevance", "sort_direction": "desc",
        "job_id": int(job_id), "state_id": state_id, "filters": {}
    }

    all_candidates = []
    offset = 0
    limit = 100
    total = None
    api_url = post_url or "https://www.kalibrr.com/api/ats/candidates"

    print(f"📥 Memulai pagination API...")
    while True:
        payload["offset"] = offset
        payload["limit"] = limit

        try:
            resp = await context.request.post(
                api_url,
                headers=replay_headers,
                data=json.dumps(payload),
            )
        except Exception as e:
            print(f"   ❌ Request error at offset {offset}: {e}")
            break

        if resp.status != 200:
            body_text = await resp.text()
            print(f"   ❌ HTTP {resp.status} at offset {offset}: {body_text[:200]}")
            break

        data = await resp.json()
        count = data.get("count", 0)
        objects = data.get("objects", [])

        if total is None:
            total = count
            print(f"   Total candidates pada server: {total}")

        if not objects:
            break

        all_candidates.extend(objects)
        offset += len(objects)
        print(f"   Fetched {len(all_candidates)}/{total}")

        if len(all_candidates) >= total:
            break

        await asyncio.sleep(0.5)

    await browser.close()

    if not all_candidates:
        print(f"❌ Tidak ada candidate yang berhasil diambil untuk {position_name}")
        return None, None

    print(f"✓ Total fetched: {len(all_candidates)} candidates")

    # ---- Flatten nested JSON to flat dict ----
    rows = []
    for c in all_candidates:
        row = {}
        for k, v in c.items():
            if isinstance(v, dict):
                for k2, v2 in v.items():
                    if not isinstance(v2, (dict, list)):
                        row[f"{k}.{k2}"] = v2
            elif isinstance(v, list):
                row[k] = json.dumps(v, default=str) if v else ""
            else:
                row[k] = v
        rows.append(row)

    df = pd.DataFrame(rows)

    # ---- Normalize columns to match Kalibrr UI CSV format ----
    df = _normalize_export_df(df, job_id)

    # ---- Save CSV ----
    safe_name = (position_name
                 .replace(" ", "_")
                 .replace(".", "")
                 .replace("/", "_")
                 .replace("(", "")
                 .replace(")", ""))
    csv_path = EXPORT_DIR / f"{safe_name}.csv"
    df.to_csv(csv_path, index=False)

    print(f"✅ Saved: {csv_path} ({len(df)} rows, {len(df.columns)} columns)")
    return str(len(df)), str(csv_path)
