"""
Shared Kalibrr export core module.

Provides reusable functions for:
- Loading positions from job_positions.csv (filtered by Pooling Status)
- Kalibrr browser automation (export candidates via Playwright)
- Updating sheet_positions.csv with File Storage URLs

Used by:
- scripts/kalibrr_export_pooling.py
- scripts/kalibrr_export_dashboard.py
"""

import os
import sys
import asyncio
import re
import time
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
# NETWORK LOG HELPERS
# ======================================
def extract_upload_id_from_network(logs):
    """Extract upload ID from Kalibrr network request logs."""
    for entry in logs:
        if "candidate_uploads" in entry:
            m = re.search(r"candidate_uploads/(\d+)", entry)
            if m:
                return m.group(1)
    return None


# ======================================
# KALIBRR EXPORT (Playwright)
# ======================================
async def export_position(playwright, position_name, job_id, kaid, kb):
    """
    Export candidate CSV from Kalibrr ATS for a single position.

    Args:
        playwright: Playwright instance
        position_name: Display name of the position
        job_id: Kalibrr job ID (int)
        kaid: KAID cookie value
        kb: KB cookie value

    Returns:
        Tuple of (upload_id, csv_url) or (None, None) on failure
    """
    url = f"https://www.kalibrr.com/ats/candidates?job_id={job_id}&state_id=19"
    print(f"\n=== Memproses {position_name} ===")
    print(f"URL: {url}")

    browser = await playwright.chromium.launch(headless=True)
    context = await browser.new_context()

    # cookies login
    await context.add_cookies([
        {"name": "kaid", "value": kaid, "domain": "www.kalibrr.com", "path": "/"},
        {"name": "kb", "value": kb, "domain": "www.kalibrr.com", "path": "/"},
    ])

    page = await context.new_page()
    network_logs = []

    page.on("request", lambda req: network_logs.append(req.url))
    page.on("response", lambda res: network_logs.append(res.url))

    # Load page
    try:
        await page.goto(url, timeout=60000, wait_until="networkidle")
    except Exception as e:
        print(f"⚠️  Page load lambat, mencoba lanjut dengan domcontentloaded: {e}")
        try:
            await page.goto(url, timeout=60000, wait_until="domcontentloaded")
        except Exception as e2:
            print(f"❌ Gagal load page sama sekali: {e2}")
            await browser.close()
            return None, None

    await page.wait_for_timeout(3000)

    # Check URL and page title
    current_url = page.url
    page_title = await page.title()
    print(f"📍 Current URL: {current_url}")
    print(f"📄 Page title: {page_title}")

    # Check for login redirect
    if "login" in current_url.lower() or "signin" in current_url.lower():
        print("❌ Cookies expired — redirect ke halaman login!")
        print("   Mohon update KAID dan KB di .env / GitHub Secrets")
        debug_path = EXPORT_DIR / f"debug_login_required_{job_id}.png"
        await page.screenshot(path=str(debug_path))
        print(f"📸 Screenshot: {debug_path}")
        await browser.close()
        return None, None

    # Check for error page
    if "error" in page_title.lower() or "not found" in page_title.lower():
        print(f"❌ Halaman error: {page_title}")
        debug_path = EXPORT_DIR / f"debug_error_{job_id}.png"
        await page.screenshot(path=str(debug_path))
        print(f"📸 Screenshot: {debug_path}")
        await browser.close()
        return None, None

    # === Find and click export button ===
    labels = [
        "EXPORT ALL CANDIDATES",
        "Export All Candidates",
        "Unduh semua kandidat",
        "UNDUH SEMUA KANDIDAT",
        "Export",
        "EXPORT",
        "Download",
        "DOWNLOAD",
    ]

    button_selectors = [
        'button:has-text("Export")',
        'button:has-text("EXPORT")',
        'button:has-text("Download")',
        'button:has-text("Unduh")',
        '[data-testid*="export"]',
        '[data-testid*="download"]',
        '[data-testid*="Export"]',
        '[data-testid*="Download"]',
        '[aria-label*="export"]',
        '[aria-label*="Export"]',
        '[aria-label*="download"]',
        '[aria-label*="Download"]',
        'a:has-text("Export")',
        'a:has-text("Download")',
        '.export-button',
        '#export-button',
        'button[class*="export"]',
        'button[class*="Export"]',
        'button[class*="download"]',
        'button[class*="Download"]',
        '[role="button"]:has-text("Export")',
        '[role="button"]:has-text("Download")',
    ]

    clicked = False
    print("Menunggu tombol export muncul (max 200 detik)...")

    debug_path = EXPORT_DIR / f"debug_page_{job_id}_start.png"
    await page.screenshot(path=str(debug_path))
    print(f"📸 Debug screenshot awal: {debug_path}")

    for attempt in range(200):
        # Try text labels first
        for label in labels:
            try:
                locator = page.get_by_text(label, exact=False)
                if await locator.count() > 0:
                    await locator.first.click(timeout=1000)
                    clicked = True
                    print(f"✓ Tombol ditemukan (by text) setelah {attempt+1} detik: {label}")
                    break
            except Exception:
                pass

        if clicked:
            break

        # Try CSS/XPath selectors
        for selector in button_selectors:
            try:
                locator = page.locator(selector)
                if await locator.count() > 0:
                    await locator.first.click(timeout=1000)
                    clicked = True
                    print(f"✓ Tombol ditemukan (by selector) setelah {attempt+1} detik: {selector}")
                    break
            except Exception:
                pass

        if clicked:
            break

        if (attempt + 1) % 10 == 0:
            print(f"  ... masih menunggu ({attempt+1}/200 detik)")
            if (attempt + 1) % 30 == 0:
                debug_path = EXPORT_DIR / f"debug_page_{job_id}_{attempt+1}s.png"
                await page.screenshot(path=str(debug_path))
                print(f"📸 Debug screenshot: {debug_path}")

        await asyncio.sleep(1)

    if not clicked:
        debug_path = EXPORT_DIR / f"debug_page_{job_id}_failed.png"
        await page.screenshot(path=str(debug_path), full_page=True)
        print(f"📸 Debug screenshot (failed): {debug_path}")

        try:
            page_title = await page.title()
            print(f"📄 Page title: {page_title}")
            print(f"📍 Current URL: {page.url}")

            button_locators = await page.locator('button:visible').all()
            if button_locators:
                button_texts = []
                for btn in button_locators[:10]:
                    try:
                        text = await btn.text_content()
                        if text and text.strip():
                            button_texts.append(text.strip()[:50])
                    except Exception:
                        pass
                if button_texts:
                    print(f"📋 Visible buttons on page: {button_texts}")

            link_locators = await page.locator('a:visible').all()
            if link_locators:
                link_texts = []
                for link in link_locators[:10]:
                    try:
                        text = await link.text_content()
                        if text and text.strip() and len(text.strip()) < 100:
                            link_texts.append(text.strip()[:50])
                    except Exception:
                        pass
                if link_texts:
                    print(f"📋 Visible links on page: {link_texts}")
        except Exception as e:
            print(f"⚠️ Could not get page info: {e}")

        print("❌ Gagal menemukan tombol download setelah 200 detik.")
        await browser.close()
        return None, None

    # === Wait for upload_id ===
    print("Menunggu upload_id keluar...")
    upload_id = None

    for _ in range(200):
        upload_id = extract_upload_id_from_network(network_logs)
        if upload_id:
            break
        await asyncio.sleep(1)

    if not upload_id:
        print("Upload ID tidak ditemukan setelah 200 detik.")
        await browser.close()
        return None, None

    print("Upload ID:", upload_id)

    # === Fetch CSV URL from API ===
    print("Mengambil CSV URL dari API...")
    api_url = f"https://www.kalibrr.com/api/candidate_uploads/{upload_id}?url_only=true"

    csv_url = None
    for attempt in range(30):
        try:
            res = await page.request.get(api_url)
            csv_url = (await res.text()).replace('"', "").strip()

            if csv_url and csv_url.startswith("https://storage.googleapis.com"):
                print(f"✓ CSV URL didapat setelah {attempt+1} detik")
                break
            else:
                csv_url = None
        except Exception:
            pass

        if (attempt + 1) % 5 == 0:
            print(f"  ... masih menunggu CSV ready ({attempt+1}/30 detik)")

        await asyncio.sleep(1)

    if not csv_url:
        print("❌ Gagal mendapatkan CSV URL dari API setelah 30 detik")
        await browser.close()
        return None, None

    print("CSV URL:", csv_url)

    # === Download CSV ===
    csv_bytes = await page.request.get(csv_url)
    data = await csv_bytes.body()

    filename = f"{position_name}.csv".replace(" ", "_")
    path = EXPORT_DIR / filename

    with open(path, "wb") as f:
        f.write(data)

    print("Saved:", path)
    await browser.close()

    return upload_id, csv_url
