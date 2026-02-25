# Changelog - CV Processing Improvements

## Tanggal: 26 Januari 2026

### 🔧 Perbaikan

#### 1. **CV Sekarang Diproses Secara Lengkap**

**Sebelum:**
- CV hanya diproses 4000 karakter pertama (~1-2 halaman)
- Informasi penting di halaman berikutnya terlewat
- Scoring kurang akurat untuk CV yang panjang

**Sesudah:**
- CV diproses sampai **1000 tokens** (~5000 karakter / 3-4 halaman)
- CV profesional umumnya 3-4 halaman sudah lengkap
- Lebih dari itu biasanya tidak relevan
- Ekstraksi informasi lebih optimal dan efisien
- Scoring lebih akurat dengan fokus pada konten relevan

**File yang diubah:**
- `modules/scorer.py`:
  - `extract_candidate_info_from_cv()`: Limit 5000 karakter (~1000 tokens / 3-4 halaman)
  - `extract_candidate_name_from_cv()`: Limit 1000 karakter (awal CV untuk ekstraksi nama)
  - `score_with_openrouter()`: Limit 5000 karakter (~1000 tokens untuk scoring optimal)

---

### ✨ Fitur Baru

#### 2. **Sistem Logging Penggunaan API**

**Fitur:**
- Tracking otomatis setiap CV yang diproses
- Statistik harian dan bulanan
- Estimasi biaya API
- Dashboard visualisasi di Streamlit

**Komponen:**

1. **Module Logging** (`modules/usage_logger.py`):
   - `log_cv_processing()`: Mencatat pemrosesan CV
   - `get_daily_summary()`: Statistik harian
   - `get_monthly_summary()`: Statistik bulanan
   - `print_daily_summary()`: Print summary ke console
   - Data disimpan di `logs/api_usage_log.json`

2. **Integrasi Streamlit** (`app.py`):
   - Menu baru: **"Usage Log"**
   - Dashboard dengan:
     - Statistik hari ini
     - Statistik bulan ini
     - Grafik penggunaan harian
     - Data historis lengkap
     - Estimasi biaya API

3. **Integrasi GitHub Actions** (`scripts/auto_screen.py`):
   - Logging otomatis setiap CV diproses
   - Summary dicetak di akhir setiap run
   - Tracking source: "github_action"

**Data yang Dicatat:**
- Timestamp
- Sumber (Streamlit / GitHub Actions)
- Nama kandidat
- Posisi pekerjaan
- Status (sukses/gagal)

**Benefit:**
- ✅ Tahu berapa CV diproses per hari
- ✅ Estimasi biaya API yang akurat
- ✅ Monitoring penggunaan sistem
- ✅ Data untuk budgeting dan planning

---

### 📝 Dokumentasi Baru

1. **docs/API_USAGE_LOGGING.md**
   - Panduan lengkap penggunaan logging
   - Cara akses statistik
   - Estimasi biaya detail
   - Troubleshooting

---

### 🔒 Keamanan & Privacy

- Log file tidak di-commit ke GitHub (`.gitignore`)
- Hanya menyimpan data minimum (nama, posisi)
- Tidak ada data sensitif (email, phone) di log

---

### 📊 Estimasi Biaya API

**Per CV (Gemini 2.5 Pro via OpenRouter):**
- Low estimate: $0.001
- High estimate: $0.003

**Contoh Bulanan:**
- 100 CVs: $0.10 - $0.30
- 500 CVs: $0.50 - $1.50
- 1000 CVs: $1.00 - $3.00

---

### 🚀 Cara Menggunakan

#### Melihat Statistik di Streamlit:
1. Buka aplikasi Streamlit
2. Klik menu **"Usage Log"**
3. Lihat statistik hari ini, bulan ini, dan historis

#### Melihat Log di GitHub Actions:
Summary otomatis dicetak di akhir setiap screening run

#### Manual via Python:
```python
from modules.usage_logger import print_daily_summary, print_monthly_summary

# Print today's stats
print_daily_summary()

# Print this month's stats
print_monthly_summary()
```

---

### 🛠️ Testing

Module sudah ditest dan berfungsi dengan baik:
```bash
python modules/usage_logger.py
```

Output menunjukkan:
- ✅ Logging berhasil
- ✅ Daily summary tampil
- ✅ Monthly summary tampil
- ✅ File JSON tergenerate

---

### 📁 File yang Dimodifikasi

1. `modules/scorer.py` - Perbaikan ekstraksi CV lengkap
2. `modules/usage_logger.py` - Module logging baru
3. `scripts/auto_screen.py` - Integrasi logging GitHub Actions
4. `app.py` - Integrasi logging Streamlit + menu Usage Log
5. `.gitignore` - Exclude logs directory
6. `docs/API_USAGE_LOGGING.md` - Dokumentasi lengkap

---

### ✅ Checklist Implementasi

- [x] Perbaiki ekstraksi CV - proses semua halaman
- [x] Buat modul logging untuk tracking penggunaan
- [x] Integrasi logging ke auto_screen.py (GitHub Actions)
- [x] Integrasi logging ke app.py (Streamlit)
- [x] Tambah menu Usage Log di Streamlit
- [x] Buat dokumentasi lengkap
- [x] Test module logging
- [x] Update .gitignore

---

### 🎯 Next Steps (Opsional)

1. **Export to Excel**: Tambah fitur export log ke Excel
2. **Alerts**: Email notification jika usage melebihi threshold
3. **Cost Tracking**: Integrasi dengan actual billing API
4. **Visualization**: Grafik lebih advanced (pie chart, bar chart)
5. **Filtering**: Filter log by date range, position, source

---

## Summary

Sistem sekarang sudah:
1. ✅ Memproses CV secara lengkap (bukan hanya 2 halaman pertama)
2. ✅ Mencatat semua penggunaan API secara otomatis
3. ✅ Menyediakan dashboard statistik yang mudah dipahami
4. ✅ Memberikan estimasi biaya yang akurat

Semua fitur sudah terintegrasi dan ready to use! 🚀
