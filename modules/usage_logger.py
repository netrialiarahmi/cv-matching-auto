"""
Usage Logger Module
Tracks daily API usage for CV processing (both Streamlit and GitHub Actions)
"""

import os
import json
import base64
from datetime import datetime
from pathlib import Path
import requests

# Log file path - use absolute path relative to this file
CURRENT_DIR = Path(__file__).parent.parent
LOG_FILE = CURRENT_DIR / "logs" / "api_usage_log.json"

def ensure_log_directory():
    """Ensure logs directory exists"""
    log_dir = LOG_FILE.parent
    log_dir.mkdir(parents=True, exist_ok=True)


def _commit_log_to_github(log_data):
    """Commit usage log to GitHub repository using GitHub API
    
    Args:
        log_data (dict): Log data to commit
        
    Returns:
        bool: True if commit successful, False otherwise
    """
    try:
        # Get GitHub credentials from environment
        token = os.environ.get("GITHUB_TOKEN")
        repo = os.environ.get("GITHUB_REPO", "netrialiarahmi/cv-matching-auto")
        
        if not token:
            # If no token, just save locally
            return False
        
        headers = {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github+json"
        }
        
        # File path in repo
        file_path = "logs/api_usage_log.json"
        
        # Get current file SHA (needed for update)
        url = f"https://api.github.com/repos/{repo}/contents/{file_path}"
        response = requests.get(url, headers=headers, timeout=10)
        
        sha = None
        if response.status_code == 200:
            sha = response.json().get("sha")
        
        # Prepare content
        content = json.dumps(log_data, indent=2, ensure_ascii=False)
        encoded_content = base64.b64encode(content.encode()).decode()
        
        # Commit message
        message = f"chore: update API usage log - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        
        # Prepare payload
        payload = {
            "message": message,
            "content": encoded_content,
            "branch": "main"
        }
        
        if sha:
            payload["sha"] = sha
        
        # Push to GitHub
        response = requests.put(url, headers=headers, json=payload, timeout=10)
        
        if response.status_code in [200, 201]:
            print(f"✓ Log committed to GitHub: {file_path}")
            return True
        else:
            print(f"⚠ GitHub commit failed: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"⚠ Could not commit to GitHub: {e}")
        return False


def load_usage_log():
    """Load existing usage log from file
    
    Returns:
        dict: Usage log data, or empty dict if file doesn't exist
    """
    ensure_log_directory()
    
    if not LOG_FILE.exists():
        return {}
    
    try:
        with open(LOG_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"Warning: Could not load usage log: {e}")
        return {}


def save_usage_log(log_data):
    """Save usage log to file and optionally commit to GitHub
    
    Args:
        log_data (dict): Usage log data to save
    """
    ensure_log_directory()
    
    try:
        # Always save to local file first
        with open(LOG_FILE, 'w', encoding='utf-8') as f:
            json.dump(log_data, f, indent=2, ensure_ascii=False)
        
        # Try to commit to GitHub (will only work if GITHUB_TOKEN is available)
        _commit_log_to_github(log_data)
        
    except Exception as e:
        print(f"Warning: Could not save usage log: {e}")


def log_cv_processing(source="unknown", candidate_name="", position="", success=True):
    """Log a single CV processing event
    
    Args:
        source (str): Source of processing - "streamlit" or "github_action"
        candidate_name (str): Name of candidate processed
        position (str): Job position
        success (bool): Whether processing was successful
    """
    # Get current date (YYYY-MM-DD)
    today = datetime.now().strftime("%Y-%m-%d")
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Load existing log
    log_data = load_usage_log()
    
    # Initialize date entry if it doesn't exist
    if today not in log_data:
        log_data[today] = {
            "total": 0,
            "streamlit": 0,
            "github_action": 0,
            "successful": 0,
            "failed": 0,
            "positions": {},
            "entries": []
        }
    
    # Update counters
    log_data[today]["total"] += 1
    
    # Update source counter
    if source in ["streamlit", "github_action"]:
        log_data[today][source] += 1
    
    # Update success counter
    if success:
        log_data[today]["successful"] += 1
    else:
        log_data[today]["failed"] += 1
    
    # Update position counter
    if position:
        if position not in log_data[today]["positions"]:
            log_data[today]["positions"][position] = 0
        log_data[today]["positions"][position] += 1
    
    # Add detailed entry (optional - can be disabled to reduce file size)
    log_data[today]["entries"].append({
        "timestamp": timestamp,
        "source": source,
        "candidate": candidate_name,
        "position": position,
        "success": success
    })
    
    # Keep only last 100 entries per day to prevent log from growing too large
    if len(log_data[today]["entries"]) > 100:
        log_data[today]["entries"] = log_data[today]["entries"][-100:]
    
    # Save updated log
    save_usage_log(log_data)
    
    # Print confirmation (useful for debugging)
    print(f"✓ Logged: {candidate_name} ({position}) - {'Success' if success else 'Failed'} - Source: {source}")
    
    return log_data[today]


def get_daily_summary(date=None):
    """Get usage summary for a specific date
    
    Args:
        date (str): Date in YYYY-MM-DD format, or None for today
        
    Returns:
        dict: Summary for the specified date, or None if no data
    """
    if date is None:
        date = datetime.now().strftime("%Y-%m-%d")
    
    log_data = load_usage_log()
    return log_data.get(date)


def get_monthly_summary(year=None, month=None):
    """Get usage summary for a specific month
    
    Args:
        year (int): Year, or None for current year
        month (int): Month (1-12), or None for current month
        
    Returns:
        dict: Monthly summary with totals and daily breakdown
    """
    if year is None:
        year = datetime.now().year
    if month is None:
        month = datetime.now().month
    
    # Format month as YYYY-MM
    month_prefix = f"{year:04d}-{month:02d}"
    
    log_data = load_usage_log()
    
    # Filter entries for the specified month
    monthly_data = {
        "month": month_prefix,
        "total": 0,
        "streamlit": 0,
        "github_action": 0,
        "successful": 0,
        "failed": 0,
        "positions": {},
        "daily_breakdown": {}
    }
    
    for date_key, day_data in log_data.items():
        if date_key.startswith(month_prefix):
            monthly_data["total"] += day_data.get("total", 0)
            monthly_data["streamlit"] += day_data.get("streamlit", 0)
            monthly_data["github_action"] += day_data.get("github_action", 0)
            monthly_data["successful"] += day_data.get("successful", 0)
            monthly_data["failed"] += day_data.get("failed", 0)
            
            # Merge position counts
            for pos, count in day_data.get("positions", {}).items():
                if pos not in monthly_data["positions"]:
                    monthly_data["positions"][pos] = 0
                monthly_data["positions"][pos] += count
            
            # Store daily summary (without detailed entries to reduce size)
            monthly_data["daily_breakdown"][date_key] = {
                "total": day_data.get("total", 0),
                "streamlit": day_data.get("streamlit", 0),
                "github_action": day_data.get("github_action", 0)
            }
    
    return monthly_data


def print_daily_summary(date=None):
    """Print formatted daily summary
    
    Args:
        date (str): Date in YYYY-MM-DD format, or None for today
    """
    if date is None:
        date = datetime.now().strftime("%Y-%m-%d")
    
    summary = get_daily_summary(date)
    
    if summary is None:
        print(f"No usage data for {date}")
        return
    
    print(f"\n{'='*60}")
    print(f"API Usage Summary - {date}")
    print(f"{'='*60}")
    print(f"Total CVs Processed: {summary['total']}")
    print(f"  • Streamlit: {summary['streamlit']}")
    print(f"  • GitHub Actions: {summary['github_action']}")
    print(f"  • Successful: {summary['successful']}")
    print(f"  • Failed: {summary['failed']}")
    
    if summary.get('positions'):
        print(f"\nBy Position:")
        for pos, count in sorted(summary['positions'].items(), key=lambda x: x[1], reverse=True):
            print(f"  • {pos}: {count}")
    
    print(f"{'='*60}\n")


def print_monthly_summary(year=None, month=None):
    """Print formatted monthly summary
    
    Args:
        year (int): Year, or None for current year
        month (int): Month (1-12), or None for current month
    """
    summary = get_monthly_summary(year, month)
    
    print(f"\n{'='*60}")
    print(f"API Usage Summary - {summary['month']}")
    print(f"{'='*60}")
    print(f"Total CVs Processed: {summary['total']}")
    print(f"  • Streamlit: {summary['streamlit']}")
    print(f"  • GitHub Actions: {summary['github_action']}")
    print(f"  • Successful: {summary['successful']}")
    print(f"  • Failed: {summary['failed']}")
    
    if summary.get('positions'):
        print(f"\nBy Position:")
        for pos, count in sorted(summary['positions'].items(), key=lambda x: x[1], reverse=True):
            print(f"  • {pos}: {count}")
    
    if summary.get('daily_breakdown'):
        print(f"\nDaily Breakdown:")
        for date_key, day_data in sorted(summary['daily_breakdown'].items()):
            print(f"  • {date_key}: {day_data['total']} CVs")
    
    print(f"{'='*60}\n")


# Example usage for testing
if __name__ == "__main__":
    # Test logging
    print("Testing usage logger...")
    
    # Log some sample entries
    log_cv_processing("streamlit", "John Doe", "Software Engineer", success=True)
    log_cv_processing("github_action", "Jane Smith", "Data Analyst", success=True)
    log_cv_processing("streamlit", "Bob Johnson", "Product Manager", success=False)
    
    # Print today's summary
    print_daily_summary()
    
    # Print this month's summary
    print_monthly_summary()
