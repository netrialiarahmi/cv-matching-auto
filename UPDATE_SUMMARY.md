# Update Summary - Token Limit & JSON Log

**Update Date:** 26 Januari 2026

---

## ✅ Perubahan yang Telah Dilakukan

### 1. **Token Limit: 1000 Tokens** ⚡

**Implementasi:**
- CV processing dibatasi **1000 tokens** (~5000 karakter)
- Setara dengan **3-4 halaman CV profesional**

**Alasan:**
- CV profesional standar = 3-4 halaman
- Lebih dari itu biasanya tidak relevan untuk screening
- Optimal untuk akurasi dan efisiensi biaya

**Detail Limit:**
| Function | Limit | Tujuan |
|----------|-------|---------|
| `score_with_openrouter()` | 5000 char | Scoring AI (1000 tokens) |
| `extract_candidate_info_from_cv()` | 5000 char | Ekstraksi info kandidat |
| `extract_candidate_name_from_cv()` | 1000 char | Ekstraksi nama (bagian awal) |

**Konversi Token:**
```
1 token ≈ 4-5 karakter (mixed content)
1000 tokens = ~5000 karakter
~5000 karakter = 3-4 halaman CV standar
```

---

### 2. **Log Format: JSON** 📋

**Format yang Digunakan:**
```json
{
  "2026-01-26": {
    "total": 25,
    "streamlit": 10,
    "github_action": 15,
    "successful": 23,
    "failed": 2,
    "positions": {
      "Software Engineer": 12,
      "Data Analyst": 8
    },
    "entries": [
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

**Keuntungan Format JSON:**
- ✅ Mudah dibaca (human-readable)
- ✅ Mudah di-parse dengan Python
- ✅ Support nested structure
- ✅ Standard format untuk data exchange
- ✅ Bisa di-import ke berbagai tools (Excel, databases, etc.)

---

## 📁 File yang Dimodifikasi

1. **modules/scorer.py**
   - Update limit ke 1000 tokens (5000 karakter)
   - 3 functions updated: scoring, info extraction, name extraction

2. **CHANGELOG.md**
   - Update dokumentasi dengan limit 1000 tokens
   - Penjelasan alasan limit

3. **QUICK_REFERENCE.md**
   - Tambah section format JSON
   - Tambah penjelasan token limit
   - Contoh parsing JSON

4. **docs/API_USAGE_LOGGING.md**
   - Detail struktur JSON
   - Field descriptions
   - Contoh parsing dan export

---

## 📂 File Baru

### **scripts/parse_usage_log.py** - JSON Parser Script

Script Python lengkap dengan 7 contoh:
1. **Basic Reading** - Baca stats hari ini
2. **Last 7 Days** - Analisis 7 hari terakhir
3. **Position Analysis** - Posisi paling banyak diproses
4. **Success Rate** - Hitung success rate
5. **Export to CSV** - Export JSON ke CSV
6. **Busiest Day** - Cari hari tersibuk
7. **Cost Estimation** - Estimasi biaya

**Cara Pakai:**
```bash
python scripts/parse_usage_log.py
```

---

## 🎯 Cara Menggunakan

### Lihat Format JSON Log:
```bash
cat logs/api_usage_log.json
```

### Parse JSON dengan Python:
```python
import json

with open('logs/api_usage_log.json', 'r') as f:
    data = json.load(f)

# Get today's stats
today = "2026-01-26"
stats = data[today]
print(f"Total CVs: {stats['total']}")
print(f"By Position: {stats['positions']}")
```

### Export ke CSV:
```bash
python scripts/parse_usage_log.py
# Output: usage_export_summary.csv, usage_export_detailed.csv
```

### Lihat di Streamlit:
```
1. Buka Streamlit app
2. Klik menu "Usage Log"
3. Semua stats tersedia dalam format visual
```

---

## 💰 Estimasi Biaya (Updated)

Dengan limit 1000 tokens per CV:

| CVs/Bulan | Cost Low | Cost High | Average |
|-----------|----------|-----------|---------|
| 100 CVs   | $0.10    | $0.30     | $0.20   |
| 500 CVs   | $0.50    | $1.50     | $1.00   |
| 1000 CVs  | $1.00    | $3.00     | $2.00   |
| 2000 CVs  | $2.00    | $6.00     | $4.00   |

*Based on Gemini 2.5 Pro pricing via OpenRouter*

---

## 🧪 Testing

Script parse_usage_log.py sudah ditest:
```
✅ Basic reading works
✅ 7-day analysis works
✅ Position analysis works
✅ Success rate calculation works
✅ CSV export works
✅ Busiest day detection works
✅ Cost estimation works
```

---

## 📚 Dokumentasi

1. **CHANGELOG.md** - Semua perubahan detail
2. **QUICK_REFERENCE.md** - Quick reference guide
3. **docs/API_USAGE_LOGGING.md** - Full documentation
4. **UPDATE_SUMMARY.md** - This file

---

## ✅ Checklist

- [x] Token limit set ke 1000 tokens (5000 char)
- [x] Log format JSON verified
- [x] Documentation updated
- [x] Parser script created & tested
- [x] No errors in code
- [x] All functions working correctly

---

## 🎉 Kesimpulan

Sistem sekarang:
1. ✅ CV diproses **optimal 3-4 halaman** (1000 tokens)
2. ✅ Log dalam **format JSON** yang mudah diparse
3. ✅ **Script parser** tersedia untuk analisis
4. ✅ **Estimasi biaya** lebih akurat
5. ✅ **Documentation** lengkap

**Status: READY TO USE! 🚀**

---

**Questions?**
- Check QUICK_REFERENCE.md
- Read docs/API_USAGE_LOGGING.md
- Run scripts/parse_usage_log.py
- Review CHANGELOG.md
