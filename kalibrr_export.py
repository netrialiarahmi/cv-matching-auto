import os
import asyncio
import re
from pathlib import Path
from dotenv import load_dotenv
from playwright.async_api import async_playwright

# ======================================
# ENV
# ======================================
load_dotenv()
KAID = os.getenv("KAID")
KB = os.getenv("KB")

if not KAID or not KB:
    print("KAID atau KB tidak ditemukan di .env")
    exit()

# ======================================
# GOOGLE SHEETS
# ======================================
GSHEET_URL = "https://docs.google.com/spreadsheets/d/1Xs7qLk1_gOu4jCHiCmyo28BlRmGXIvve1npwKuYf5mw/edit"

# hasil export tersimpan disini
EXPORT_RESULTS = []

# ======================================
# POSITIONS (urutan row)
# Sheet structure:
# Row 1: Header (Nama Posisi, JOB_ID, UPLOAD_ID, File Storage)
# Row 2+: Data per position
# ======================================
POSITIONS = {
    "Account Executive Kompasiana": 260796,
    "Account Executive Pasangiklan.com": 256571,
    "Account Executive VCBL": 259102,
    "Account Executive KOMPAScom": 260574,
    "Sales Group Head (VCBL)": 261105,
    "Data Reliability Admin": 261144
}

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

def extract_csv_from_network(logs):
    """
    Mencari URL CSV yang valid dari network logs.
    Filter out URL analytics dan ambil hanya URL storage GCS yang sebenarnya.
    """
    for entry in logs:
        # Skip URL analytics
        if "analytics.google.com" in entry:
            continue
        
        # Cari URL yang benar-benar mengarah ke storage.googleapis.com
        if "job-csv-exports" in entry and "storage.googleapis.com" in entry:
            # Pastikan ini adalah URL utama, bukan parameter dari URL lain
            if entry.startswith("https://storage.googleapis.com"):
                return entry
    return None

# ======================================
# EXPORT FUNCTION
# ======================================
async def export_position(playwright, position_name, job_id):

    url = f"https://www.kalibrr.com/ats/candidates?job_id={job_id}&state_id=19"
    print(f"\n=== Memproses {position_name} ===")
    print(f"URL: {url}")

    browser = await playwright.chromium.launch(headless=False)
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
            except:
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
        except:
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
# WRITE TO GOOGLE SHEETS
# ======================================
async def write_to_gsheets(playwright):
    print("\n=== Membuka Google Sheets ===")

    # Gunakan persistent context agar login tersimpan
    user_data_dir = Path("./playwright_google_data")
    user_data_dir.mkdir(exist_ok=True)
    
    browser = await playwright.chromium.launch_persistent_context(
        user_data_dir=str(user_data_dir),
        headless=False
    )

    # Gunakan tab yang sudah ada
    page = browser.pages[0] if browser.pages else await browser.new_page()
    
    await page.goto(GSHEET_URL)
    
    print("\nMenunggu Google Sheets terbuka...")
    print("💡 Jika diminta login, silakan login ke Google dulu")
    print("💡 Setelah sheets terbuka penuh, tekan ENTER di terminal ini")
    
    # Tunggu user confirm kalau sheets sudah siap
    input("\n👉 Tekan ENTER setelah Google Sheets terbuka dan siap diedit... ")

    # Build a mapping of position name to row number
    # Based on the POSITIONS dictionary order (which matches sheet row order)
    position_to_row = {}
    row_num = 2  # Start from row 2 (row 1 is header)
    for position_name in POSITIONS.keys():
        position_to_row[position_name] = row_num
        row_num += 1

    for result in EXPORT_RESULTS:
        position_name, job_id, upload_id, csv_url = result
        
        # Get the correct row for this position
        target_row = position_to_row.get(position_name)
        if target_row is None:
            print(f"⚠️ Position '{position_name}' not found in mapping, skipping...")
            continue
            
        print(f"\nUpdating row {target_row} untuk {position_name}...")
        
        try:
            # Ke cell A1 dulu untuk reset posisi
            await page.keyboard.press("Control+Home")
            await page.wait_for_timeout(500)
            
            # Gunakan Name Box untuk navigasi langsung ke cell
            # Click pada Name Box (area yang menampilkan alamat cell, biasanya di kiri atas)
            # Atau gunakan Ctrl+G / F5 untuk Go To dialog
            
            # Method 1: Gunakan F5 (Go To) yang lebih reliable
            await page.keyboard.press("F5")
            await page.wait_for_timeout(500)
            
            # Ketik cell address untuk UPLOAD_ID (kolom C)
            await page.keyboard.type(f"C{target_row}")
            await page.keyboard.press("Enter")
            await page.wait_for_timeout(500)
            
            # Ketik upload_id
            await page.keyboard.type(str(upload_id))
            await page.keyboard.press("Tab")  # Tab ke kolom D (File Storage)
            await page.wait_for_timeout(300)
            
            # Ketik csv_url
            await page.keyboard.type(csv_url)
            await page.keyboard.press("Enter")
            await page.wait_for_timeout(500)

            print(f"✓ Row {target_row} berhasil diupdate")
            
        except Exception as e:
            print(f"✗ Error updating row {target_row}: {e}")
            # Screenshot untuk debug
            try:
                await page.screenshot(path=f"error_row_{target_row}.png")
                print(f"  Screenshot disimpan: error_row_{target_row}.png")
            except:
                pass

    print("\n✅ Google Sheet sudah terupdate semua!")
    await page.wait_for_timeout(2000)
    await browser.close()


# ======================================
# MAIN
# ======================================
async def main():
    async with async_playwright() as pw:

        for name, job_id in POSITIONS.items():
            await export_position(pw, name, job_id)

        if not EXPORT_RESULTS:
            print("\n⚠️  Tidak ada data yang berhasil di-export.")
            return

        print("\n=== Semua export selesai. Update Google Sheets... ===")
        await write_to_gsheets(pw)

if __name__ == "__main__":
    asyncio.run(main())
