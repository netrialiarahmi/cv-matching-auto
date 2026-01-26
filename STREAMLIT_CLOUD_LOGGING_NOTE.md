# Important: API Usage Log in Streamlit Cloud

## ⚠️ Critical Information

### The Situation
When running **Streamlit Cloud** (not local), the API usage log **will NOT automatically appear in GitHub** after processing candidates.

### Why?
**Streamlit Cloud is read-only** - it cannot commit files back to GitHub repository automatically.

### What Happens Now?
✅ **Logging DOES work** - the file `logs/api_usage_log.json` is created and updated  
✅ **You can VIEW logs** in the Streamlit app via "Usage Log" menu  
❌ **File is NOT committed to GitHub** from Streamlit Cloud  
✅ **GitHub Actions WILL commit logs** when auto-screening runs

---

## How It Works

### 1. Local Development (Your Computer)
When you run Streamlit locally:
```bash
streamlit run app.py
```
- ✅ Logs are written to `logs/api_usage_log.json`
- ✅ You can manually commit and push to GitHub
- ✅ File appears in repository

### 2. Streamlit Cloud (Public Deployment)
When users access your Streamlit app online:
- ✅ Logs are written to **temporary container storage**
- ✅ Visible in app's "Usage Log" menu during session
- ❌ **File is lost when container restarts**
- ❌ **NOT committed to GitHub automatically**

### 3. GitHub Actions (Auto-Screening)
When auto-screening workflow runs:
- ✅ Logs are written to `logs/api_usage_log.json`
- ✅ **Automatically committed and pushed to GitHub**
- ✅ File persists in repository
- ✅ Visible in GitHub

---

## Solutions

### Option 1: GitHub Actions (Recommended)
**Use GitHub Actions for all production screening**
- Logs are automatically committed
- No manual intervention needed
- Full tracking persists in repository

**How to use:**
1. Candidates added to Google Sheets
2. GitHub Actions runs daily (or manually)
3. Processing happens
4. Logs automatically committed to repo

### Option 2: Manual Commit (Local Streamlit)
**Run Streamlit locally and commit manually**

```bash
# Run Streamlit locally
streamlit run app.py

# After processing candidates, commit logs
git add logs/api_usage_log.json
git commit -m "chore: update API usage logs"
git push origin main
```

### Option 3: View in App Only (Streamlit Cloud)
**Accept that logs are temporary in Streamlit Cloud**
- View current session logs in "Usage Log" menu
- Use for immediate feedback only
- Rely on GitHub Actions for permanent logging

### Option 4: External Database (Future Enhancement)
**Store logs in external database instead of file**
- Use PostgreSQL, MongoDB, or cloud storage
- Accessible from both Streamlit Cloud and GitHub Actions
- Requires additional setup

---

## Current Setup Status

✅ **Logging Function**: Working correctly  
✅ **Absolute Path**: Fixed to work from any directory  
✅ **Debug Output**: Prints confirmation when logging  
✅ **GitHub Actions**: Will auto-commit logs  
✅ **Streamlit UI**: "Usage Log" menu shows current data  
⚠️ **Streamlit Cloud**: Logs temporary, not committed  

---

## Verification

### Check if logging works:
```python
from modules.usage_logger import log_cv_processing, load_usage_log
import json

# Test
log_cv_processing(
    source="streamlit",
    candidate_name="Test",
    position="Test Position",
    success=True
)

# Verify
log = load_usage_log()
print(json.dumps(log, indent=2))
```

### Check file location:
```python
from modules.usage_logger import LOG_FILE
print(f"Log file: {LOG_FILE}")
# Output: /workspaces/cv-matching-auto/logs/api_usage_log.json
```

### View logs in Streamlit:
Navigate to **Usage Log** menu in the app

---

## Recommendation

**For Production:**
Use **GitHub Actions** for all candidate screening to ensure:
- ✅ Complete API usage tracking
- ✅ Logs persisted in repository
- ✅ Automatic cost calculation
- ✅ Historical data preserved

**For Testing:**
Use **local Streamlit** with manual commits

**For Demo:**
Accept that **Streamlit Cloud logs are temporary**

---

## Summary

| Environment | Logging Works? | Visible in App? | Committed to GitHub? |
|-------------|----------------|-----------------|---------------------|
| **Local Streamlit** | ✅ Yes | ✅ Yes | 🔧 Manual commit needed |
| **Streamlit Cloud** | ✅ Yes | ✅ Yes | ❌ No (read-only) |
| **GitHub Actions** | ✅ Yes | ❌ No (no UI) | ✅ Yes (automatic) |

## Files Updated
- `modules/usage_logger.py`: Changed to absolute path
- `.gitignore`: Added `!logs/*.json` to allow tracking
- `logs/api_usage_log.json`: Now tracked in repository

## Next Steps
After each Streamlit processing session (if running locally):
```bash
git add logs/api_usage_log.json
git commit -m "chore: update API usage logs"
git push
```

Or simply rely on **GitHub Actions** for automatic logging! 🎉
