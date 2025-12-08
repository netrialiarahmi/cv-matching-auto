# Daily CV Link Update - Technical Documentation

## Overview

Script `update_cv_links.py` dijalankan setiap hari untuk memperbarui link CV kandidat di file hasil screening per posisi **tanpa melakukan analisis ulang**.

## Apa yang Diupdate?

Script ini **hanya mengubah kolom "Resume Link"** (kolom ke-17) di dalam file hasil per posisi, seperti:
- `results_Account_Executive_Kompasiana.csv`
- `results_Product_Designer.csv`
- `results_Content_Creator.csv`
- dll.

## Format File Hasil Per Posisi

Setiap file hasil memiliki 20 kolom standar:

| No | Kolom | Deskripsi |
|----|-------|-----------|
| 1 | Candidate Name | Nama kandidat |
| 2 | Candidate Email | Email kandidat (digunakan untuk matching) |
| 3 | Phone | Nomor telepon |
| 4 | Job Position | Posisi yang dilamar |
| 5 | Match Score | Skor kecocokan (0-100) |
| 6 | AI Summary | Ringkasan analisis AI |
| 7 | Strengths | Kekuatan kandidat |
| 8 | Weaknesses | Kelemahan kandidat |
| 9 | Gaps | Gap/kekurangan |
| 10 | Latest Job Title | Jabatan terakhir |
| 11 | Latest Company | Perusahaan terakhir |
| 12 | Education | Tingkat pendidikan |
| 13 | University | Universitas |
| 14 | Major | Jurusan |
| 15 | Kalibrr Profile | Link profil Kalibrr |
| 16 | Application Link | Link aplikasi |
| **17** | **Resume Link** | **Link CV (INI YANG DIUPDATE)** |
| 18 | Recruiter Feedback | Feedback recruiter |
| 19 | Shortlisted | Status shortlist |
| 20 | Date Processed | Tanggal diproses |

## Cara Kerja Script

### 1. Load Data Posisi
```python
# Membaca sheet_positions.csv yang sudah diupdate oleh kalibrr_export.py
df = pd.read_csv("sheet_positions.csv")
```

File `sheet_positions.csv` berisi:
- Nama Posisi
- JOB_ID
- UPLOAD_ID
- **File Storage** (URL ke CSV kandidat terbaru dari Kalibrr)

### 2. Load Hasil Existing
```python
# Untuk setiap posisi, load file hasil yang sudah ada
df = pd.read_csv("results_Position_Name.csv")
```

### 3. Fetch Data Kandidat Terbaru
```python
# Download CSV dari File Storage URL
response = requests.get(file_storage_url)
fresh_candidates = pd.read_csv(BytesIO(response.content))
```

### 4. Matching Kandidat
```python
# Build mapping: email -> resume link dari data terbaru
for _, row in fresh_candidates.iterrows():
    email = row["Email Address"]
    resume_link = row["Resume Link"]
    email_to_resume_link[email] = resume_link
```

### 5. Update Resume Link
```python
# Untuk setiap kandidat di hasil existing
for idx, row in existing_results.iterrows():
    candidate_email = row["Candidate Email"]
    
    # Jika ada email yang cocok di data terbaru
    if candidate_email in email_to_resume_link:
        new_resume_link = email_to_resume_link[candidate_email]
        
        # Update HANYA kolom Resume Link
        existing_results.at[idx, "Resume Link"] = new_resume_link
```

### 6. Simpan Hasil
```python
# Simpan kembali ke file hasil yang sama
existing_results.to_csv(results_file, index=False)
```

## Yang TIDAK Diubah

Script ini **TIDAK mengubah** kolom-kolom berikut:
- Match Score (tetap sama)
- AI Summary (tetap sama)
- Strengths, Weaknesses, Gaps (tetap sama)
- Semua informasi kandidat lainnya (tetap sama)

## Kenapa Perlu Update Daily?

1. **URL Kalibrr Expire**: Link CV dari Google Storage memiliki parameter `Expires=` yang membuat URL kadaluarsa setelah beberapa waktu
2. **Hemat Biaya**: Tidak perlu call AI/LLM API lagi untuk re-analisis
3. **Hemat Waktu**: Tidak perlu download dan extract PDF lagi
4. **Data Tetap Akurat**: Resume link selalu up-to-date tanpa menghilangkan hasil analisis yang sudah ada

## Workflow Daily

```
00:00 UTC (07:00 WIB) - GitHub Actions dimulai
  ↓
Step 1: kalibrr_export.py
  - Fetch posisi dari Google Sheets
  - Export kandidat dari Kalibrr (dengan FORCE_EXPORT=true)
  - Update sheet_positions.csv dengan URL terbaru
  ↓
Step 2: update_cv_links.py (SCRIPT INI)
  - Load sheet_positions.csv
  - Untuk setiap posisi:
    * Load results_Position_Name.csv
    * Fetch kandidat terbaru dari File Storage URL
    * Match kandidat by email
    * Update HANYA Resume Link column
    * Save results_Position_Name.csv
  ↓
Step 3: Git Commit & Push
  - Commit sheet_positions.csv
  - Commit results_*.csv yang berubah
  - Push ke GitHub
```

## Example Output

```
============================================================
Processing: Content Creator
============================================================
✅ Loaded 54 existing results from results_Content_Creator.csv
📥 Fetching fresh candidate data from File Storage...
✅ Fetched 68 candidates from File Storage
📋 Found 68 candidates with resume links in fresh data

  ✓ Updated resume link for: John Doe
    Old: https://storage.googleapis.com/.../old-link.pdf?Expires=1234567890...
    New: https://storage.googleapis.com/.../new-link.pdf?Expires=9876543210...

💾 Saved 1 updated resume link(s) to results_Content_Creator.csv
   Updated column: Resume Link (column 17 in standard format)
```

## Troubleshooting

### Jika URL Expired
Script akan menampilkan warning:
```
⚠️ HTTP 403 - URL may have expired
⚠️ Could not fetch fresh candidate data for Position Name
   This may be due to expired URLs or network issues
   CV links will not be updated for this position
```

**Solusi**: Script akan retry otomatis di run berikutnya (besok).

### Jika Kolom Resume Link Tidak Ada
```
⚠️ Warning: 'Resume Link' column not found in results_Position_Name.csv
   Available columns: [list of columns]
```

**Solusi**: Ini berarti file hasil belum memiliki kolom Resume Link. Script akan skip posisi ini.

### Jika Tidak Ada Kandidat untuk Update
```
ℹ️ No resume links needed updating for Position Name
```

**Solusi**: Ini normal. Berarti semua Resume Link sudah up-to-date atau tidak ada perubahan.

## Testing

Untuk test manual:
```bash
python update_cv_links.py
```

Script akan memproses semua posisi di `sheet_positions.csv` dan update Resume Link di file hasil masing-masing.
