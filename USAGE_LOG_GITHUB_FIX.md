# API Usage Log - GitHub Visibility Fix

## Problem
`api_usage_log.json` was not visible in GitHub repository even though GitHub Actions tried to commit it.

## Root Cause
The `.gitignore` file had:
```
logs/
```

This completely ignored the entire `logs/` directory, preventing ANY files inside it from being tracked by git, including `logs/*.json`.

## Solution
Updated `.gitignore` with negation pattern:
```
# Logs (but allow JSON usage logs for tracking)
logs/
!logs/*.json
*.log
```

**How it works:**
1. `logs/` - Ignore the entire logs directory
2. `!logs/*.json` - **BUT** allow JSON files (negation pattern)
3. `*.log` - Still ignore .log files

## Result
✅ `logs/api_usage_log.json` is now tracked and visible in GitHub  
✅ GitHub Actions can commit updates to the log file  
✅ Other log files (*.log) are still ignored  

## Verification
```bash
# Check if file is tracked
git ls-files logs/
# Output: logs/api_usage_log.json

# View current log
cat logs/api_usage_log.json
```

## How Logging Works

### Automatic Logging
Every CV processing is automatically logged:
- **Streamlit**: When you screen candidates via web UI
- **GitHub Actions**: When auto-screening runs via workflow

### Log Structure
```json
{
  "2026-01-26": {
    "total": 3,
    "streamlit": 2,
    "github_action": 1,
    "successful": 3,
    "failed": 0,
    "positions": {
      "Accounting Staff": 2,
      "Software Engineer": 1
    },
    "entries": [
      {
        "timestamp": "2026-01-26 10:30:15",
        "source": "streamlit",
        "candidate": "John Doe",
        "position": "Accounting Staff",
        "success": true
      }
    ]
  }
}
```

### Viewing Logs

#### In Streamlit
Navigate to: **Usage Log** menu
- Daily summary with charts
- Monthly aggregation
- Position breakdown

#### In Terminal
```bash
# Print today's summary
python -c "from modules.usage_logger import print_daily_summary; print_daily_summary()"

# Parse with examples
python scripts/parse_usage_log.py
```

#### In GitHub
View file directly: `logs/api_usage_log.json`

## Important Notes

1. **File Location**: `logs/api_usage_log.json`
2. **Git Tracking**: Now tracked by git (was ignored before)
3. **Auto-commit**: GitHub Actions automatically commits updates
4. **Cost Tracking**: Use this log to calculate monthly API costs
5. **Estimation**: ~$0.001-$0.003 per CV processed

## Next Steps

When processing candidates:
1. ✅ Logging happens automatically
2. ✅ File gets updated in repository
3. ✅ View statistics in Streamlit "Usage Log" menu
4. ✅ Calculate costs using `scripts/parse_usage_log.py`

## References
- Full logging docs: `docs/API_USAGE_LOGGING.md`
- Parsing examples: `docs/JSON_PARSING_EXAMPLES.md`
- Logger module: `modules/usage_logger.py`
