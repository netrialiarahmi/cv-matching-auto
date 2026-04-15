"""
Centralized path constants for the project.

All data, log, and output paths are defined here so they can be imported
consistently across src/, scripts/, and tests/.
"""
from pathlib import Path

# Project root: src/config/paths.py → src/config/ → src/ → project root
ROOT = Path(__file__).resolve().parent.parent.parent

# ── Data ────────────────────────────────────────────────────────────────────
DATA_DIR = ROOT / "data"
DATA_RAW_DIR = DATA_DIR / "raw"          # Kalibrr CSV exports
DATA_PROCESSED_DIR = DATA_DIR / "processed"  # Screening results

# Config / seed data at data root
JOB_POSITIONS_FILE = DATA_DIR / "job_positions.csv"
SHEET_POSITIONS_FILE = DATA_DIR / "sheet_positions.csv"

# ── Outputs ──────────────────────────────────────────────────────────────────
OUTPUTS_DIR = ROOT / "outputs"
CV_DOWNLOAD_DIR = OUTPUTS_DIR / "cv"

# ── Logs ─────────────────────────────────────────────────────────────────────
LOGS_DIR = ROOT / "logs"
API_USAGE_LOG = LOGS_DIR / "api_usage_log.json"

# ── String versions (for GitHub API paths — must be repo-relative) ───────────
RESULTS_DIR = "data/processed"          # used in github_utils as GitHub path prefix
EXPORT_DIR_NAME = "data/raw"            # used in kalibrr_core / update_cv_links
