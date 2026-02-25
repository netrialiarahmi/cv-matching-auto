# API Usage Logging

## Overview

Sistem ini sekarang dilengkapi dengan logging otomatis untuk tracking penggunaan API. Setiap CV yang diproses akan dicatat untuk membantu menghitung biaya API.

## Fitur

### 1. Logging Otomatis
- Setiap CV yang diproses akan dicatat secara otomatis
- Mencatat sumber (Streamlit atau GitHub Actions)
- Mencatat status (berhasil/gagal)
- Mencatat posisi pekerjaan
- Timestamp lengkap

### 2. Statistik Harian
- Total CV diproses hari ini
- Breakdown per sumber (Streamlit vs GitHub Actions)
- Breakdown per posisi
- Status keberhasilan

### 3. Statistik Bulanan
- Total CV diproses bulan ini
- Grafik penggunaan harian
- Estimasi biaya API
- Breakdown detail per hari

### 4. Riwayat Lengkap
- Data historis semua pemrosesan CV
- Tersimpan dalam format JSON
- Mudah untuk analisis lebih lanjut

## Cara Menggunakan

## Cara Menggunakan

### Membaca Log JSON Langsung

```python
import json

# Load log file
with open('logs/api_usage_log.json', 'r') as f:
    log_data = json.load(f)

# Get today's data
today = "2026-01-26"
if today in log_data:
    today_stats = log_data[today]
    print(f"Total CVs today: {today_stats['total']}")
    print(f"Streamlit: {today_stats['streamlit']}")
    print(f"GitHub Actions: {today_stats['github_action']}")
    
    # Position breakdown
    for position, count in today_stats['positions'].items():
        print(f"  {position}: {count}")

# Get all entries for specific position
for date, data in log_data.items():
    for entry in data['entries']:
        if entry['position'] == 'Software Engineer':
            print(f"{entry['timestamp']} - {entry['candidate']}")
```

### Export JSON to CSV

```python
import json
import csv

# Load JSON
with open('logs/api_usage_log.json', 'r') as f:
    log_data = json.load(f)

# Export daily summary
with open('daily_summary.csv', 'w', newline='') as f:
    writer = csv.writer(f)
    writer.writerow(['Date', 'Total', 'Streamlit', 'GitHub Actions', 'Successful', 'Failed'])
    
    for date, data in sorted(log_data.items()):
        writer.writerow([
            date,
            data['total'],
            data['streamlit'],
            data['github_action'],
            data['successful'],
            data['failed']
        ])

print("Exported to daily_summary.csv")

# Export detailed entries
all_entries = []
for date, data in log_data.items():
    for entry in data['entries']:
        entry['date'] = date
        all_entries.append(entry)

with open('detailed_entries.csv', 'w', newline='') as f:
    if all_entries:
        writer = csv.DictWriter(f, fieldnames=['date', 'timestamp', 'source', 'candidate', 'position', 'success'])
        writer.writeheader()
        writer.writerows(all_entries)

print("Exported to detailed_entries.csv")
```

### Query Specific Data

```python
import json
from datetime import datetime, timedelta

# Load log
with open('logs/api_usage_log.json', 'r') as f:
    log_data = json.load(f)

# Get last 7 days
today = datetime.now()
last_7_days = [(today - timedelta(days=i)).strftime("%Y-%m-%d") for i in range(7)]

total_week = 0
for date in last_7_days:
    if date in log_data:
        total_week += log_data[date]['total']

print(f"Total CVs processed in last 7 days: {total_week}")

# Find busiest day
busiest_date = max(log_data.items(), key=lambda x: x[1]['total'])
print(f"Busiest day: {busiest_date[0]} with {busiest_date[1]['total']} CVs")

# Calculate success rate
total_all = sum(data['total'] for data in log_data.values())
successful_all = sum(data['successful'] for data in log_data.values())
success_rate = (successful_all / total_all * 100) if total_all > 0 else 0
print(f"Overall success rate: {success_rate:.1f}%")
```

### Di Streamlit (Web Interface)

1. Buka aplikasi Streamlit
2. Klik menu **"Usage Log"** di navigation bar
3. Lihat statistik penggunaan:
   - **Today's Usage**: Penggunaan hari ini
   - **This Month's Usage**: Penggunaan bulan ini
   - **Historical Data**: Semua data historis
   - **Estimated API Costs**: Perkiraan biaya

### Di GitHub Actions (Automated Screening)

Log otomatis dicetak di akhir setiap run GitHub Actions:

```
============================================================
API Usage Summary - 2026-01-26
============================================================
Total CVs Processed: 25
  • Streamlit: 10
  • GitHub Actions: 15
  • Successful: 23
  • Failed: 2

By Position:
  • Software Engineer: 12
  • Data Analyst: 8
  • Product Manager: 5
============================================================
```

### Via Python Script

Anda juga bisa menggunakan module `usage_logger` secara langsung:

```python
from modules.usage_logger import (
    log_cv_processing,
    print_daily_summary,
    print_monthly_summary,
    get_daily_summary,
    get_monthly_summary
)

# Log CV processing
log_cv_processing(
    source="streamlit",           # or "github_action"
    candidate_name="John Doe",
    position="Software Engineer",
    success=True                   # or False
)

# Print today's summary
print_daily_summary()

# Print this month's summary
print_monthly_summary()

# Get data programmatically
today_data = get_daily_summary()  # Returns dict
monthly_data = get_monthly_summary()  # Returns dict
```

## File Log

Log disimpan di: `logs/api_usage_log.json`

**Format JSON Structure:**
```json
{
  "2026-01-26": {                      // Date key (YYYY-MM-DD)
    "total": 25,                       // Total CVs processed on this date
    "streamlit": 10,                   // CVs processed via Streamlit
    "github_action": 15,               // CVs processed via GitHub Actions
    "successful": 23,                  // Successfully processed CVs
    "failed": 2,                       // Failed CVs
    "positions": {                     // Breakdown by job position
      "Software Engineer": 12,
      "Data Analyst": 8,
      "Product Manager": 5
    },
    "entries": [                       // Detailed log entries (last 100)
      {
        "timestamp": "2026-01-26 10:30:45",
        "source": "streamlit",         // "streamlit" or "github_action"
        "candidate": "John Doe",       // Candidate name
        "position": "Software Engineer", // Job position
        "success": true                // true or false
      }
    ]
  }
}
```

**Field Descriptions:**

| Field | Type | Description |
|-------|------|-------------|
| `total` | int | Total number of CVs processed on this date |
| `streamlit` | int | CVs processed through Streamlit web interface |
| `github_action` | int | CVs processed through automated GitHub Actions |
| `successful` | int | Number of successfully processed CVs |
| `failed` | int | Number of failed CV processing attempts |
| `positions` | object | Breakdown count by job position name |
| `entries` | array | Detailed log entries (kept last 100 to prevent file bloat) |

**Entry Object:**

| Field | Type | Description |
|-------|------|-------------|
| `timestamp` | string | ISO format: "YYYY-MM-DD HH:MM:SS" |
| `source` | string | Either "streamlit" or "github_action" |
| `candidate` | string | Candidate name (for reference only) |
| `position` | string | Job position name |
| `success` | boolean | `true` if processing succeeded, `false` if failed |

## Estimasi Biaya

### Gemini 2.5 Pro (via OpenRouter)

Berdasarkan dokumentasi OpenRouter:
- Input: ~$0.0001 per 1K tokens
- Output: ~$0.0003 per 1K tokens

**Estimasi per CV:**
- CV rata-rata: ~3000 tokens input
- Response rata-rata: ~1000 tokens output
- **Total per CV: ~$0.001 - $0.003**

**Contoh Perhitungan Bulanan:**
- 100 CVs/bulan: $0.10 - $0.30
- 500 CVs/bulan: $0.50 - $1.50
- 1000 CVs/bulan: $1.00 - $3.00

*Note: Biaya aktual dapat bervariasi tergantung panjang CV dan kompleksitas analisis.*

## Privacy & Data

- Log file disimpan lokal (tidak di-commit ke GitHub)
- Hanya menyimpan nama kandidat untuk referensi
- Tidak menyimpan data sensitif (email, phone, dll)
- File log dapat dihapus kapan saja jika diperlukan

## Maintenance

### Membersihkan Log Lama

Untuk menghapus log lama (opsional):

```python
import os
log_file = "logs/api_usage_log.json"
if os.path.exists(log_file):
    os.remove(log_file)
```

### Backup Log

Log file JSON dapat di-backup secara manual atau otomatis:

```bash
# Backup manual
cp logs/api_usage_log.json logs/backup_api_usage_log_2026-01.json

# Atau export ke CSV untuk analisis di Excel
python -c "
from modules.usage_logger import load_usage_log
import json
import csv

data = load_usage_log()
with open('usage_export.csv', 'w') as f:
    writer = csv.writer(f)
    writer.writerow(['Date', 'Total', 'Streamlit', 'GitHub Actions', 'Successful', 'Failed'])
    for date, info in sorted(data.items()):
        writer.writerow([date, info['total'], info['streamlit'], info['github_action'], info['successful'], info['failed']])
"
```

## Troubleshooting

### Log tidak muncul di Streamlit

1. Pastikan sudah ada CV yang diproses
2. Refresh halaman Streamlit
3. Cek file `logs/api_usage_log.json` sudah ada

### Log tidak tercatat di GitHub Actions

1. Cek GitHub Actions logs
2. Pastikan tidak ada error di script `auto_screen.py`
3. Verifikasi permissions untuk membuat folder `logs/`

## Support

Jika ada pertanyaan atau masalah terkait logging:
1. Cek file `modules/usage_logger.py` untuk detail implementasi
2. Review file log di `logs/api_usage_log.json`
3. Konsultasikan dengan tim development
