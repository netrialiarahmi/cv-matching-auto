# Quick Reference - Perubahan Sistem

## 🔍 Ringkasan Perubahan

### 1. CV Processing - Optimal 3-4 Halaman ✅
**Sebelum:** Hanya 2 halaman pertama (~4000 karakter)  
**Sekarang:** 3-4 halaman profesional (~1000 tokens / 5000 karakter)

**Alasan:**
- CV profesional biasanya 3-4 halaman
- Lebih dari itu umumnya tidak relevan
- Optimal untuk akurasi dan efisiensi cost

### 2. Usage Logging - Tracking Otomatis ✅
**Fitur Baru:** Sistem logging untuk track berapa CV diproses per hari

---

## 📊 Cara Cek Usage Log

### Via Streamlit (Paling Mudah)
1. Buka aplikasi Streamlit
2. Klik menu **"Usage Log"** (menu baru di navigation bar)
3. Lihat semua statistik penggunaan

### Via File Log Langsung
```bash
# Lihat log file
cat logs/api_usage_log.json

# atau dengan pretty print
python -c "
import json
with open('logs/api_usage_log.json', 'r') as f:
    print(json.dumps(json.load(f), indent=2))
"
```

### Via Python Script
```python
from modules.usage_logger import print_daily_summary, print_monthly_summary

# Print today's usage
print_daily_summary()

# Print this month's usage
print_monthly_summary()
```

---

## � Format Log JSON

Log disimpan dalam format JSON yang mudah dibaca dan diparse:

```json
{
  "2026-01-26": {
    "total": 25,                    // Total CVs hari ini
    "streamlit": 10,                // Via Streamlit
    "github_action": 15,            // Via GitHub Actions
    "successful": 23,               // Berhasil
    "failed": 2,                    // Gagal
    "positions": {                  // Per posisi
      "Software Engineer": 12,
      "Data Analyst": 8
    },
    "entries": [                    // Detail (max 100)
      {
        "timestamp": "2026-01-26 10:30:45",
        "source": "streamlit",
        "candidate": "John Doe",
        "position": "Software Engineer",
        "success": true
      }
    ]
  }
}
```

### Parse JSON dengan Python:

```python
import json

with open('logs/api_usage_log.json', 'r') as f:
    data = json.load(f)

# Get today's stats
today = "2026-01-26"
print(f"Total: {data[today]['total']}")
print(f"Positions: {data[today]['positions']}")
```

---

## 🎯 Limit Token CV: 1000 Tokens

**Kenapa 1000 tokens?**
- CV profesional = 3-4 halaman
- 1000 tokens ≈ 5000 karakter ≈ 3-4 halaman
- Lebih dari itu biasanya tidak relevan

**Konversi:**
- 1 token ≈ 4-5 karakter (bahasa campur)
- 1000 tokens = ~5000 karakter
- ~5000 karakter = 3-4 halaman CV standar

---

## �💰 Estimasi Biaya

| Jumlah CV/Bulan | Estimasi Biaya (Low) | Estimasi Biaya (High) |
|----------------|---------------------|---------------------|
| 100 CVs        | $0.10               | $0.30               |
| 500 CVs        | $0.50               | $1.50               |
| 1000 CVs       | $1.00               | $3.00               |
| 2000 CVs       | $2.00               | $6.00               |

*Berdasarkan Gemini 2.5 Pro pricing via OpenRouter*

---

## 📝 Yang Dicatat di Log

Setiap CV yang diproses mencatat:
- ✅ Timestamp (kapan diproses)
- ✅ Source (Streamlit atau GitHub Actions)
- ✅ Nama kandidat
- ✅ Posisi pekerjaan
- ✅ Status (berhasil/gagal)

**Tidak dicatat** (untuk privacy):
- ❌ Email
- ❌ Phone number
- ❌ CV content
- ❌ Personal data lainnya

---

## 🎯 Menu Usage Log di Streamlit

Menampilkan:
1. **Today's Usage** - Statistik hari ini
   - Total CVs processed
   - Breakdown: Streamlit vs GitHub Actions
   - Successful vs Failed
   - Breakdown per posisi

2. **This Month's Usage** - Statistik bulan ini
   - Total CVs processed
   - Grafik penggunaan harian (line chart)
   - Breakdown per posisi
   - Estimasi biaya

3. **Historical Data** - Semua data
   - Table lengkap semua hari
   - Export ready (bisa dicopy)

---

## 🚀 Test Logging

```bash
# Test module
python modules/usage_logger.py

# Output akan menunjukkan:
# - Sample log entries
# - Daily summary
# - Monthly summary
```

---

## 📂 File Locations

```
cv-matching-auto/
├── modules/
│   └── usage_logger.py          # Module logging (NEW)
├── logs/
│   └── api_usage_log.json       # Log file (auto-generated)
├── docs/
│   └── API_USAGE_LOGGING.md     # Dokumentasi lengkap (NEW)
└── CHANGELOG.md                  # Changelog detail (NEW)
```

---

## ⚡ Quick Commands

```bash
# View today's stats
python -c "from modules.usage_logger import print_daily_summary; print_daily_summary()"

# View monthly stats
python -c "from modules.usage_logger import print_monthly_summary; print_monthly_summary()"

# Check log file size
ls -lh logs/api_usage_log.json

# Backup log file
cp logs/api_usage_log.json logs/backup_$(date +%Y%m%d).json
```

---

## 🛠️ Troubleshooting

### Log tidak muncul?
1. Cek folder `logs/` sudah ada
2. Cek file `logs/api_usage_log.json` ada
3. Pastikan sudah ada CV yang diproses setelah update

### Cara reset log?
```bash
# Hapus log file (akan di-recreate otomatis)
rm logs/api_usage_log.json
```

### Cara export ke CSV?
```python
from modules.usage_logger import load_usage_log
import pandas as pd

data = load_usage_log()
rows = []
for date, info in data.items():
    rows.append({
        'Date': date,
        'Total': info['total'],
        'Streamlit': info['streamlit'],
        'GitHub Actions': info['github_action'],
        'Successful': info['successful'],
        'Failed': info['failed']
    })

df = pd.DataFrame(rows)
df.to_csv('usage_export.csv', index=False)
print("Exported to usage_export.csv")
```

---

## ✅ Verification Checklist

- [x] Module `usage_logger.py` created
- [x] Streamlit menu "Usage Log" added
- [x] GitHub Actions integration done
- [x] CV processing now full (no 4000 char limit)
- [x] Log file excluded from git (`.gitignore`)
- [x] Documentation complete
- [x] No errors in code
- [x] Module tested successfully

---

## 📞 Support

Jika ada masalah:
1. Cek CHANGELOG.md untuk detail lengkap
2. Baca docs/API_USAGE_LOGGING.md
3. Review module: modules/usage_logger.py
4. Check logs: logs/api_usage_log.json

---

**Update Date:** 26 Januari 2026  
**Status:** ✅ Ready to Use
