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
from playwright.async_api import async_playwright

# ======================================
# ENV
# ======================================
load_dotenv()
KAID = os.getenv("KAID")
KB = os.getenv("KB")
GSHEET_URL = os.getenv("GSHEET_URL") or "https://docs.google.com/spreadsheets/d/1Xs7qLk1_gOu4jCHiCmyo28BlRmGXIvve1npwKuYf5mw/edit?usp=sharing"
# CSV export URL for the same sheet (for fetching positions)
GSHEET_CSV_URL = os.getenv("GSHEET_CSV_URL") or "https://docs.google.com/spreadsheets/d/e/2PACX-1vRKC_5lHg9yJgGoBlkH0A-fjpjpiYu4MzO4ieEdSId5wAKS7bsLDdplXWx8944xFlHf2f9lVcUYzVcr/pub?output=csv"

if not KAID or not KB:
    print("KAID atau KB tidak ditemukan di .env")
    sys.exit(1)

# hasil export tersimpan disini
EXPORT_RESULTS = []

# ======================================
# POSITIONS - Fetched from Google Sheets
# Sheet structure:
# Row 1: Header (Nama Posisi, JOB_ID, UPLOAD_ID, File Storage)
# Row 2+: Data per position
# ======================================
def fetch_positions_from_sheet(max_retries=3):
    """
    Fetch positions and JOB_IDs from Google Sheets.
    Returns a dictionary of {position_name: job_id} and a list of row mappings.
    """
    for attempt in range(max_retries):
        try:
            print("📊 Mengambil data posisi dari Google Sheets...")
            response = requests.get(GSHEET_CSV_URL, timeout=30)
            
            if response.status_code != 200:
                if attempt < max_retries - 1:
                    print(f"⚠️ Gagal fetch (status {response.status_code}), retry...")
                    time.sleep(2)
                    continue
                print(f"❌ Gagal fetch Google Sheets (status {response.status_code})")
                return {}, []
            
            # Parse the sheet content using StringIO for proper text encoding
            sheet_df = pd.read_csv(StringIO(response.text))
            
            if sheet_df.empty:
                print("❌ Google Sheets kosong")
                return {}, []
            
            # Find the position and job_id columns
            position_column = None
            job_id_column = None
            
            if "Nama Posisi" in sheet_df.columns:
                position_column = "Nama Posisi"
            elif "Job Position" in sheet_df.columns:
                position_column = "Job Position"
            elif "Position" in sheet_df.columns:
                position_column = "Position"
            
            if "JOB_ID" in sheet_df.columns:
                job_id_column = "JOB_ID"
            elif "Job ID" in sheet_df.columns:
                job_id_column = "Job ID"
            elif "job_id" in sheet_df.columns:
                job_id_column = "job_id"
            
            if position_column is None or job_id_column is None:
                available_columns = ", ".join(sheet_df.columns)
                print(f"❌ Kolom tidak ditemukan. Kolom tersedia: {available_columns}")
                return {}, []
            
            # Build positions dictionary and row mappings
            positions = {}
            row_mappings = []  # List of (position_name, row_number)
            
            for idx, row in sheet_df.iterrows():
                position_name = row[position_column]
                job_id = row[job_id_column]
                
                # Skip rows with missing data
                if pd.isna(position_name) or pd.isna(job_id):
                    continue
                
                position_name = str(position_name).strip()
                try:
                    # Convert to float first to handle numeric strings like "260796.0" from Excel/Sheets
                    # then to int for clean integer job IDs
                    job_id = int(float(job_id))
                except (ValueError, TypeError):
                    continue
                
                positions[position_name] = job_id
                # Row number in sheet (idx + 2 because idx is 0-based and row 1 is header)
                row_mappings.append((position_name, idx + 2))
            
            print(f"✅ Berhasil mengambil {len(positions)} posisi dari Google Sheets")
            for name, jid in positions.items():
                print(f"   - {name}: {jid}")
            
            return positions, row_mappings
            
        except requests.exceptions.Timeout:
            if attempt < max_retries - 1:
                print("⚠️ Timeout, retry...")
                time.sleep(3)
                continue
            print("❌ Timeout saat mengambil data dari Google Sheets")
        except requests.exceptions.RequestException as e:
            if attempt < max_retries - 1:
                time.sleep(2)
                continue
            print(f"❌ Network error: {e}")
        except Exception as e:
            print(f"❌ Error: {e}")
    
    return {}, []


# Global variables to store positions (will be populated at runtime)
POSITIONS = {}

# ======================================
# EXPORT DIR
# ======================================
EXPORT_DIR = Path("kalibrr_exports")
EXPORT_DIR.mkdir(exist_ok=True)

# ======================================
# HELPERS
# ======================================
def extract_upload_id_from_network(logs):
    for entry in logs:
        if "candidate_uploads" in entry:
            m = re.search(r"candidate_uploads/(\d+)", entry)
            if m:
                return m.group(1)
    return None

# ======================================
# EXPORT FUNCTION
# ======================================
async def export_position(playwright, position_name, job_id):

    url = f"https://www.kalibrr.com/ats/candidates?job_id={job_id}&state_id=19"
    print(f"\n=== Memproses {position_name} ===")
    print(f"URL: {url}")

    browser = await playwright.chromium.launch(headless=True)
    context = await browser.new_context()

    # cookies login
    await context.add_cookies([
        {"name": "kaid", "value": KAID, "domain": "www.kalibrr.com", "path": "/"},
        {"name": "kb", "value": KB, "domain": "www.kalibrr.com", "path": "/"}
    ])

    page = await context.new_page()
    network_logs = []

    page.on("request", lambda req: network_logs.append(req.url))
    page.on("response", lambda res: network_logs.append(res.url))

    # Load page dengan timeout lebih lama dan wait until networkidle
    try:
        await page.goto(url, timeout=60000, wait_until="networkidle")
    except Exception as e:
        print(f"⚠️  Page load lambat, mencoba lanjut dengan domcontentloaded: {e}")
        try:
            await page.goto(url, timeout=60000, wait_until="domcontentloaded")
        except Exception as e2:
            print(f"❌ Gagal load page sama sekali: {e2}")
            await browser.close()
            return
    
    await page.wait_for_timeout(3000)

    labels = [
        "EXPORT ALL CANDIDATES",
        "Export All Candidates",
        "Unduh semua kandidat",
        "UNDUH SEMUA KANDIDAT"
    ]

    clicked = False
    print("Menunggu tombol export muncul (max 200 detik)...")
    
    # Retry sampai 200 detik untuk nunggu tombol muncul
    for attempt in range(200):
        for label in labels:
            try:
                await page.get_by_text(label).click(timeout=1000)
                clicked = True
                print(f"✓ Tombol ditemukan setelah {attempt+1} detik: {label}")
                break
            except Exception:
                pass
        
        if clicked:
            break
        
        # Print progress setiap 10 detik
        if (attempt + 1) % 10 == 0:
            print(f"  ... masih menunggu ({attempt+1}/200 detik)")
        
        await asyncio.sleep(1)
    
    if not clicked:
        print("❌ Gagal menemukan tombol download setelah 200 detik.")
        await browser.close()
        return

    # wait upload id
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
        return

    print("Upload ID:", upload_id)

    # Langsung ambil CSV URL dari API
    print("Mengambil CSV URL dari API...")
    api_url = f"https://www.kalibrr.com/api/candidate_uploads/{upload_id}?url_only=true"
    
    # Retry mechanism untuk API call (kadang butuh beberapa detik untuk ready)
    csv_url = None
    for attempt in range(30):  # Max 30 detik
        try:
            res = await page.request.get(api_url)
            csv_url = (await res.text()).replace('"', "").strip()
            
            # Cek apakah URL valid
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
        return

    print("CSV URL:", csv_url)

    # download file
    csv_bytes = await page.request.get(csv_url)
    data = await csv_bytes.body()

    filename = f"{position_name}.csv".replace(" ", "_")
    path = EXPORT_DIR / filename

    with open(path, "wb") as f:
        f.write(data)

    print("Saved:", path)

    # simpan untuk update sheets
    EXPORT_RESULTS.append([
        position_name,
        str(job_id),
        str(upload_id),
        csv_url
    ])

    await browser.close()

# ======================================
# WRITE TO GOOGLE SHEETS (Browser Automation)
# ======================================
async def write_to_gsheets(playwright, position_to_row):
    """
    Write to Google Sheets using browser automation.
    The sheet must be set to 'Anyone with the link can edit'.
    """
    print("\n=== Membuka Google Sheets ===")

    browser = await playwright.chromium.launch(headless=True)
    context = await browser.new_context(
        viewport={'width': 1920, 'height': 1080}
    )
    page = await context.new_page()
    
    await page.goto(GSHEET_URL, wait_until="networkidle")
    
    print("\nMenunggu Google Sheets terbuka...")
    
    # Tunggu sampai sheet siap - cari canvas atau grid
    try:
        # Google Sheets menggunakan canvas untuk render grid
        await page.wait_for_selector('canvas.waffle-selection-container, div.grid-container', timeout=30000)
        print("✓ Google Sheets grid loaded")
    except Exception as e:
        print(f"⚠️ Grid tidak ditemukan, mencoba lanjut: {e}")
        await page.wait_for_timeout(5000)
    
    # Screenshot awal untuk debugging (simpan di folder exports agar terupload ke artifact)
    screenshot_path = EXPORT_DIR / "gsheet_opened.png"
    await page.screenshot(path=str(screenshot_path))
    print(f"📸 Screenshot awal: {screenshot_path}")
    
    # Cek apakah sheet bisa diedit (bukan view-only)
    try:
        # Cari indikator view-only
        view_only = await page.locator('text="View only"').is_visible(timeout=2000)
        if view_only:
            print("❌ Sheet dalam mode VIEW ONLY! Tidak bisa edit.")
            print("   Pastikan sheet di-set 'Anyone with the link can edit'")
            await browser.close()
            return
    except Exception:
        pass  # Tidak ada indikator view-only, lanjut

    for name, job_id, upload_id, csv_url in EXPORT_RESULTS:
        # Get the correct row for this position
        row_num = position_to_row.get(name)
        if row_num is None:
            print(f"⚠️ Position '{name}' not found in mapping, skipping...")
            continue
            
        print(f"\nUpdating row {row_num} untuk {name}...")
        print(f"   UPLOAD_ID: {upload_id}")
        print(f"   Target: C{row_num} dan D{row_num}")
        
        try:
            # Klik pada area sheet untuk memastikan focus
            try:
                await page.click('canvas.waffle-selection-container', timeout=3000)
            except Exception:
                try:
                    await page.click('div.grid-container', timeout=3000)
                except Exception:
                    pass
            
            await page.wait_for_timeout(500)
            
            # Metode: Gunakan Ctrl+G (Go to range) untuk navigasi ke cell
            await page.keyboard.press("Control+g")
            await page.wait_for_timeout(1000)
            
            # Cari dialog "Go to range" dan isi dengan cell target
            dialog_found = False
            dialog_selectors = [
                '[role="dialog"] input[type="text"]',
                '.modal-dialog-content input',
                'input[aria-label*="range"]',
                'input[aria-label*="Range"]',
                'input.jfk-textinput',
                'input[placeholder*="range"]'
            ]
            
            for selector in dialog_selectors:
                try:
                    dialog_input = page.locator(selector).first
                    if await dialog_input.is_visible(timeout=1000):
                        # Clear existing text and type new cell reference
                        await dialog_input.click()
                        await page.keyboard.press("Control+a")
                        await dialog_input.fill(f"C{row_num}")
                        await page.wait_for_timeout(300)
                        
                        # Tekan OK button atau Enter
                        try:
                            ok_button = page.locator('button:has-text("OK"), button:has-text("Go")').first
                            if await ok_button.is_visible(timeout=500):
                                await ok_button.click()
                            else:
                                await page.keyboard.press("Enter")
                        except Exception:
                            await page.keyboard.press("Enter")
                        
                        dialog_found = True
                        print(f"   ✓ Dialog Go to range ditemukan")
                        break
                except Exception:
                    continue
            
            if not dialog_found:
                print(f"   ⚠️ Dialog Go to range tidak ditemukan, mencoba Name Box...")
                
                # Tekan Escape untuk menutup dialog yang mungkin terbuka
                await page.keyboard.press("Escape")
                await page.wait_for_timeout(500)
                
                # Coba klik Name Box (kotak yang menunjukkan cell aktif, biasanya di kiri atas)
                name_box_selectors = [
                    'input#t-name-box',
                    '[id="t-name-box"]', 
                    'input[aria-label="Name box"]',
                    '.waffle-name-box input',
                    '.name-box input'
                ]
                
                for selector in name_box_selectors:
                    try:
                        name_box = page.locator(selector).first
                        if await name_box.is_visible(timeout=1000):
                            await name_box.click()
                            await page.keyboard.press("Control+a")
                            await page.keyboard.type(f"C{row_num}", delay=30)
                            await page.keyboard.press("Enter")
                            dialog_found = True
                            print(f"   ✓ Name Box ditemukan")
                            break
                    except Exception:
                        continue
            
            if not dialog_found:
                print(f"   ⚠️ Tidak bisa navigasi ke cell, skip row {row_num}")
                error_screenshot_path = EXPORT_DIR / f"error_nav_row_{row_num}.png"
                await page.screenshot(path=str(error_screenshot_path))
                continue
            
            await page.wait_for_timeout(800)
            
            # Sekarang kita di cell C{row_num}
            # PENTING: Tekan F2 atau Enter untuk masuk ke mode edit
            await page.keyboard.press("F2")
            await page.wait_for_timeout(300)
            
            # Clear cell content dulu (Ctrl+A lalu Delete)
            await page.keyboard.press("Control+a")
            await page.keyboard.press("Delete")
            await page.wait_for_timeout(200)
            
            # Ketik upload_id
            await page.keyboard.type(str(upload_id), delay=10)
            await page.wait_for_timeout(300)
            
            # Tekan Tab untuk pindah ke kolom D dan otomatis masuk edit mode
            await page.keyboard.press("Tab")
            await page.wait_for_timeout(500)
            
            # Ketik csv_url di kolom D
            # F2 untuk masuk edit mode
            await page.keyboard.press("F2")
            await page.wait_for_timeout(200)
            await page.keyboard.press("Control+a")
            await page.keyboard.press("Delete")
            await page.wait_for_timeout(200)
            
            await page.keyboard.type(csv_url, delay=3)
            await page.wait_for_timeout(300)
            
            # Tekan Enter untuk konfirmasi dan keluar dari edit mode
            await page.keyboard.press("Enter")
            await page.wait_for_timeout(500)
            
            # Tunggu auto-save (Google Sheets auto-save dalam beberapa detik)
            await page.wait_for_timeout(2000)

            print(f"   ✓ Row {row_num} berhasil diupdate")
            
        except Exception as e:
            print(f"   ✗ Error updating row {row_num}: {e}")
            # Screenshot untuk debug
            try:
                error_screenshot_path = EXPORT_DIR / f"error_row_{row_num}.png"
                await page.screenshot(path=str(error_screenshot_path))
                print(f"   📸 Screenshot error: {error_screenshot_path}")
            except Exception:
                pass

    # Tunggu final auto-save
    print("\nMenunggu auto-save selesai...")
    await page.wait_for_timeout(5000)
    
    # Screenshot akhir untuk verifikasi (simpan di folder exports agar terupload ke artifact)
    final_screenshot_path = EXPORT_DIR / "gsheet_final.png"
    await page.screenshot(path=str(final_screenshot_path))
    print(f"\n📸 Screenshot akhir: {final_screenshot_path}")
    
    print("\n✅ Google Sheet sudah terupdate semua!")
    await browser.close()


# ======================================
# MAIN
# ======================================
async def main():
    global POSITIONS
    
    # Fetch positions from Google Sheets first
    POSITIONS, row_mappings = fetch_positions_from_sheet()
    
    if not POSITIONS:
        print("\n❌ Tidak ada posisi yang ditemukan di Google Sheets.")
        print("Pastikan sheet memiliki kolom 'Nama Posisi' dan 'JOB_ID'")
        return
    
    # Build position to row mapping
    position_to_row = {name: row for name, row in row_mappings}
    
    async with async_playwright() as pw:

        for name, job_id in POSITIONS.items():
            await export_position(pw, name, job_id)

        if not EXPORT_RESULTS:
            print("\n⚠️  Tidak ada data yang berhasil di-export.")
            return

        print("\n=== Semua export selesai. Update Google Sheets... ===")
        
        # Update Google Sheets menggunakan browser automation
        await write_to_gsheets(pw, position_to_row)

if __name__ == "__main__":
    asyncio.run(main())
