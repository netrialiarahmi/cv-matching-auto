# Contoh Praktis - Parsing JSON Log

## Quick Examples

### 1. Lihat Isi Log JSON
```bash
# Pretty print JSON
cat logs/api_usage_log.json | python -m json.tool

# Atau dengan jq (jika installed)
cat logs/api_usage_log.json | jq .
```

### 2. Cek Berapa CV Diproses Hari Ini
```python
import json
from datetime import datetime

with open('logs/api_usage_log.json', 'r') as f:
    data = json.load(f)

today = datetime.now().strftime("%Y-%m-%d")
if today in data:
    print(f"Hari ini: {data[today]['total']} CVs")
else:
    print("Belum ada CV diproses hari ini")
```

### 3. Lihat Posisi Paling Banyak
```python
import json
from collections import defaultdict

with open('logs/api_usage_log.json', 'r') as f:
    data = json.load(f)

# Aggregate semua posisi
positions = defaultdict(int)
for date, info in data.items():
    for pos, count in info.get('positions', {}).items():
        positions[pos] += count

# Top 5 posisi
top_5 = sorted(positions.items(), key=lambda x: x[1], reverse=True)[:5]
print("Top 5 Posisi:")
for pos, count in top_5:
    print(f"  {count} CVs - {pos}")
```

### 4. Hitung Total Bulan Ini
```python
import json
from datetime import datetime

with open('logs/api_usage_log.json', 'r') as f:
    data = json.load(f)

current_month = datetime.now().strftime("%Y-%m")
monthly_total = sum(
    info['total'] 
    for date, info in data.items() 
    if date.startswith(current_month)
)

print(f"Bulan ini: {monthly_total} CVs")

# Estimasi biaya
low = monthly_total * 0.001
high = monthly_total * 0.003
print(f"Estimasi: ${low:.2f} - ${high:.2f}")
```

### 5. Export ke Excel
```python
import json
import pandas as pd

with open('logs/api_usage_log.json', 'r') as f:
    data = json.load(f)

# Buat DataFrame
rows = []
for date, info in sorted(data.items()):
    rows.append({
        'Date': date,
        'Total': info['total'],
        'Streamlit': info['streamlit'],
        'GitHub Actions': info['github_action'],
        'Successful': info['successful'],
        'Failed': info['failed']
    })

df = pd.DataFrame(rows)

# Export ke Excel
df.to_excel('usage_log.xlsx', index=False)
print("✅ Exported to usage_log.xlsx")
```

### 6. Cari Kandidat Tertentu
```python
import json

with open('logs/api_usage_log.json', 'r') as f:
    data = json.load(f)

search_name = "John Doe"
found = []

for date, info in data.items():
    for entry in info.get('entries', []):
        if search_name.lower() in entry['candidate'].lower():
            found.append({
                'date': date,
                'timestamp': entry['timestamp'],
                'position': entry['position'],
                'source': entry['source']
            })

if found:
    print(f"Found {len(found)} entries for '{search_name}':")
    for item in found:
        print(f"  {item['timestamp']} - {item['position']}")
else:
    print(f"Not found: '{search_name}'")
```

### 7. Monitor Success Rate
```python
import json

with open('logs/api_usage_log.json', 'r') as f:
    data = json.load(f)

total = sum(info['total'] for info in data.values())
successful = sum(info['successful'] for info in data.values())
failed = sum(info['failed'] for info in data.values())

if total > 0:
    success_rate = (successful / total) * 100
    print(f"Success Rate: {success_rate:.1f}%")
    print(f"Total: {total}, Success: {successful}, Failed: {failed}")
    
    # Alert jika success rate rendah
    if success_rate < 90:
        print("⚠️  WARNING: Success rate below 90%")
```

### 8. Backup & Compress Log
```bash
# Backup dengan timestamp
cp logs/api_usage_log.json logs/backup_$(date +%Y%m%d_%H%M%S).json

# Compress old backups
gzip logs/backup_*.json

# Keep only last 7 backups
cd logs && ls -t backup_*.json.gz | tail -n +8 | xargs rm -f
```

### 9. Visualisasi dengan matplotlib
```python
import json
import matplotlib.pyplot as plt
from datetime import datetime

with open('logs/api_usage_log.json', 'r') as f:
    data = json.load(f)

# Prepare data
dates = sorted(data.keys())
totals = [data[d]['total'] for d in dates]

# Plot
plt.figure(figsize=(10, 6))
plt.plot(dates, totals, marker='o')
plt.title('Daily CV Processing')
plt.xlabel('Date')
plt.ylabel('CVs Processed')
plt.xticks(rotation=45)
plt.tight_layout()
plt.savefig('usage_chart.png')
print("✅ Chart saved to usage_chart.png")
```

### 10. One-liner Commands
```bash
# Total CVs all time
python -c "import json; data=json.load(open('logs/api_usage_log.json')); print(sum(d['total'] for d in data.values()))"

# Today's total
python -c "import json; from datetime import datetime; data=json.load(open('logs/api_usage_log.json')); today=datetime.now().strftime('%Y-%m-%d'); print(data.get(today, {}).get('total', 0))"

# Success rate
python -c "import json; data=json.load(open('logs/api_usage_log.json')); total=sum(d['total'] for d in data.values()); success=sum(d['successful'] for d in data.values()); print(f'{success/total*100:.1f}%' if total>0 else '0%')"
```

## Running the Full Parser

Untuk analisis lengkap:
```bash
python scripts/parse_usage_log.py
```

Output akan mencakup:
- Today's stats
- Last 7 days analysis
- Position analysis
- Success rate
- CSV exports
- Busiest day
- Cost estimation

## Tips

1. **Regular Backups**: Backup log file setiap minggu
2. **Monitor Success Rate**: Jika <90%, ada masalah
3. **Check Costs**: Review monthly costs
4. **Archive Old Data**: Compress logs >3 bulan
5. **Use Parser Script**: Lebih mudah dari manual parsing

## Troubleshooting

**File not found:**
```bash
# Create logs directory
mkdir -p logs
# Log akan dibuat otomatis saat CV pertama diproses
```

**JSON parse error:**
```bash
# Validate JSON
python -c "import json; json.load(open('logs/api_usage_log.json'))"
```

**Empty data:**
- Log dibuat setelah CV pertama diproses
- Check apakah sudah ada screening yang jalan

---

**Pro Tip:** Gunakan `scripts/parse_usage_log.py` untuk analisis cepat! 🚀
