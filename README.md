# CV Matching Auto

An automated CV matching system with 3 main sections for managing job positions, screening candidates, and viewing results.

## Recent Updates

### ✨ Latest Changes (January 2026)
- **Automated Daily Screening**: GitHub Actions workflow automatically screens new candidates every day at 7:30 AM WIB
- **Background Processing**: CVs are analyzed in the background without manual intervention
- **Smart Duplicate Prevention**: Only new candidates are processed; already-screened candidates are automatically skipped
- **Error Resilience**: Position-level error handling ensures one failure doesn't block processing of other positions

### Previous Updates (2024)
- **Local File Fallback**: Dashboard and Job Management now load from local files when GitHub API is unavailable or files don't exist in the configured branch
- **API Authentication Fix**: Fixed OpenRouter 401 error when using GEMINI_API_KEY - system now properly routes to Gemini API endpoint
- **File Storage Integration**: System now fetches candidate CSVs from URLs in Google Sheets "File Storage" column
- **API Key Flexibility**: Added fallback support for GEMINI_API_KEY when OPENROUTER_API_KEY is not available
- **Simplified Scoring**: Removed AI Recruiter Score, now using only Match Score based on CV analysis
- **Automatic Processing**: Candidates are now processed automatically without manual button clicks

## Features

### 1. Job Management
- Upload and manage job positions with descriptions
- Edit existing job positions (name and description)
- Delete job positions
- Store job positions in GitHub repository
- View all saved job positions in expandable cards
- Download job positions as CSV
- Mark positions as "Pooled" to archive filled positions

### 2. Screening (Manual & Automated)
- **Manual Screening (via Streamlit UI)**:
  - Multi-step wizard for easy data loading
  - **Automatic data fetching from Google Sheets** - Fetches CSV URLs from "File Storage" column and downloads candidate data from cloud storage
  - **Fallback to CSV upload** - If no data is found for the position in Google Sheets, you can upload a CSV file manually
  - Select job position from saved positions
  - Preview job description and candidate data before screening
  - **Automatic background processing** - New candidates are automatically processed without button clicks
  - Automatically skip candidates already processed for the same position
  
- **Automated Daily Screening (via GitHub Actions)**:
  - Runs every day at **7:30 AM WIB (00:30 UTC)**
  - Automatically processes all active (non-pooled) positions
  - Fetches latest candidate data from Google Sheets
  - Only screens new candidates (skips already-processed candidates)
  - Downloads CVs, extracts text, and analyzes with Gemini AI
  - Saves results directly to GitHub repository
  - Continues processing even if one position fails (error resilience)
  - Can be manually triggered via GitHub Actions tab

### 3. Dashboard
- View all screening results from GitHub
- Filter by job position, candidate status, and score range
- Search candidates by name or email
- Sort by score, name, or date
- Expandable cards for each candidate showing:
  - Match Score (based on CV analysis)
  - Strengths, Weaknesses, and Gaps
  - AI Summary
  - Basic candidate information
  - Direct links to resume, profile, and application
- Update candidate status (OK, Rejected) and interview status
- Add recruiter feedback and rejection reasons
- Overview statistics: Average Score, Top Score, Total Candidates
- Status breakdown: Pending, OK, OK-Passed, Rejected, OK-Rejected

### 4. Pooling
- Archive filled positions to keep screening dashboard clean
- View all pooled candidates across positions
- Filter by status and score range
- Search by name or email
- Sort by various criteria
- Pagination for easy browsing
- Same candidate management features as Dashboard

## Required CSV Format for Candidate Upload

The candidate CSV file supports both English and Indonesian column names. Use the English format (recommended) or the legacy Indonesian format:

### English Format (Recommended)
1. First Name
2. Last Name
3. Gender
4. Birthdate (mm/dd/yy)
5. Email Address
6. Mobile Number
7. Physical Address
8. Latest Job Title
9. Latest Company
10. Latest Job Starting Period
11. Latest Job Ending Period
12. Latest Job Function
13. Latest Job Level
14. Latest Job Description
15. Previous Job Title (1)
16. Previous Company (1)
17. Previous Job Starting Period (1)
18. Previous Job Ending Period (1)
19. Previous Job Function (1)
20. Previous Job Level (1)
21. Previous Job Description (1)
22. Previous Job Title (2)
23. Previous Company (2)
24. Previous Job Starting Period (2)
25. Previous Job Ending Period (2)
26. Previous Job Function (2)
27. Previous Job Level (2)
28. Previous Job Description (2)
29. Latest Educational Attainment
30. Latest School/University
31. Latest Major/Course
32. Latest Education Starting Period
33. Latest Education Ending Period
34. Previous Educational Attainment (1)
35. Previous School/University (1)
36. Previous Major/Course (1)
37. Previous Education Starting Period (1)
38. Previous Education Ending Period (1)
39. Previous Educational Attainment (2)
40. Previous School/University (2)
41. Previous Major/Course (2)
42. Previous Education Starting Period (2)
43. Previous Education Ending Period (2)
44. Date Application Started (mm/dd/yy hr:mn)
45. Date Assessment Completed (mm/dd/yy hr:mn)
46. Job Name
47. Application Status
48. Kalibrr Profile Link
49. Job Application Link
50. Resume Link

### Indonesian Format (Legacy - Still Supported)
The system also supports the legacy Indonesian column names for backward compatibility:
- Nama Depan / Nama Belakang → First Name / Last Name
- Alamat Email → Email Address
- Nomor Handphone → Mobile Number
- Jabatan Pekerjaan Terakhir → Latest Job Title
- Perusahaan Terakhir → Latest Company
- Tingkat Pendidikan Tertinggi → Latest Educational Attainment
- And so on...

## Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Configure Streamlit secrets (`.streamlit/secrets.toml`):
```toml
# API Key (use one of these)
OPENROUTER_API_KEY = "your-openrouter-api-key"  # Uses OpenRouter API (google/gemini-2.5-pro)
# OR
GEMINI_API_KEY = "your-gemini-api-key"  # Uses Gemini API directly (gemini-2.0-flash-exp)

# GitHub configuration
GITHUB_TOKEN = "your-github-token"
GITHUB_REPO = "username/repo-name"
GITHUB_BRANCH = "main"
```

**Note:** The system automatically detects which API key is available and uses the appropriate endpoint:
- `OPENROUTER_API_KEY` → OpenRouter API at `https://openrouter.ai/api/v1`
- `GEMINI_API_KEY` → Gemini API at `https://generativelanguage.googleapis.com/v1beta`

3. (Optional) Configure Google Sheets URL:
   - The Google Sheets URL is configured in `modules/candidate_processor.py`
   - By default, it uses: `https://docs.google.com/spreadsheets/d/e/2PACX-1vRKC_5lHg9yJgGoBlkH0A-fjpjpiYu4MzO4ieEdSId5wAKS7bsLDdplXWx8944xFlHf2f9lVcUYzVcr/pub?output=csv`
   - Your Google Sheet should contain these columns:
     - **Nama Posisi** - Job position name (primary column name)
     - **File Storage** - URL to the candidate CSV file (e.g., storage.googleapis.com URLs)
     - JOB_ID, UPLOAD_ID (optional, for reference)
   - Example format:
     ```
     Nama Posisi                         JOB_ID    UPLOAD_ID   File Storage
     Account Executive Kompasiana        260796    18964456    https://storage.googleapis.com/.../candidates.csv
     Account Executive Pasangiklan.com   256571    18964460    https://storage.googleapis.com/.../candidates2.csv
     ```
   - The system will:
     1. Find the row matching the job position in "Nama Posisi" column
     2. Extract the File Storage URL from that row
     3. Download and parse the candidate CSV from that URL

4. **Configure GitHub Actions Secrets** (for automated screening):
   - Go to your GitHub repository → Settings → Secrets and variables → Actions
   - Add the following secrets:
     - `GEMINI_API_KEY` - Your Gemini API key for AI scoring
     - `KAID` - Kalibrr authentication cookie (for candidate export)
     - `KB` - Kalibrr authentication cookie (for candidate export)
     - `GSHEET_URL` - Google Sheets edit URL (for updating File Storage URLs)
     - `GSHEET_CSV_URL` - Published Google Sheets CSV URL (for reading positions)
   - Note: `GITHUB_TOKEN` is automatically provided by GitHub Actions

5. Run the application:
```bash
streamlit run app.py
```

## Automation Workflows

The system includes two GitHub Actions workflows for automated processing:

### 1. Daily Kalibrr Export and CV Link Update
**File:** `.github/workflows/weekly-export.yml`  
**Schedule:** Every day at 7:00 AM WIB (00:00 UTC)  
**Purpose:** Export candidates from Kalibrr and update CV links in existing results

**What it does:**
1. Exports candidate data from Kalibrr for all active positions
2. Updates `sheet_positions.csv` with UPLOAD_ID and File Storage URLs
3. Updates Resume Link column in existing result files (no re-analysis)
4. Commits changes back to GitHub

### 2. Automated CV Screening
**File:** `.github/workflows/auto-screening.yml`  
**Schedule:** Every day at 7:30 AM WIB (00:30 UTC) - runs 30 minutes after export  
**Purpose:** Automatically screen new candidates with AI

**What it does:**
1. Loads all active (non-pooled) job positions
2. Fetches candidate data from Google Sheets File Storage URLs
3. Checks existing results to identify new candidates
4. **Only processes candidates not yet screened** (skips duplicates)
5. Downloads CVs, extracts text, and analyzes with Gemini AI
6. Saves new screening results to position-specific CSV files
7. Commits results back to GitHub

**Manual Trigger:**
- Both workflows can be manually triggered via GitHub Actions tab
- Go to Actions → Select workflow → Run workflow

**Error Handling:**
- Position-level error handling: If one position fails, others continue processing
- Network retries with exponential backoff
- Rate limiting compliance (6.5s delay between AI calls)
- Detailed logging uploaded as artifacts

## Kalibrr Export Tool

The `scripts/kalibrr_export.py` script automates exporting candidate data from Kalibrr and updating the Google Sheets with File Storage URLs.

### Setup

1. Install additional dependencies:
```bash
pip install playwright python-dotenv pandas requests gspread google-auth
playwright install chromium
```

2. Create a `.env` file with your Kalibrr credentials:
```
KAID=your_kaid_cookie_value
KB=your_kb_cookie_value
GSHEET_URL=https://docs.google.com/spreadsheets/d/YOUR_SHEET_ID/edit
GSHEET_CSV_URL=https://docs.google.com/spreadsheets/d/e/YOUR_PUBLISHED_SHEET_ID/pub?output=csv
```

Note: 
- `GSHEET_URL` is optional. If not provided, it defaults to the preconfigured sheet.
- `GSHEET_CSV_URL` is the published CSV URL for reading position data. The sheet must be published to web (File > Share > Publish to web).

### Usage

```bash
python scripts/kalibrr_export.py
```

The script will:
1. **Automatically fetch job positions from Google Sheets** (no manual configuration needed!)
2. Export candidates from each position on Kalibrr
3. Save CSV files locally to `kalibrr_exports/` directory
4. Open Google Sheets and update the UPLOAD_ID and File Storage columns

### Daily Automated Updates

The script supports **automated daily updates** via GitHub Actions. Every day at 00:00 UTC (07:00 WIB), the workflow will:
1. Fetch all positions (Nama Posisi + JOB_ID) from Google Sheets
2. Export fresh candidate data from Kalibrr (gets UPLOAD_ID and File Storage URLs)
3. **Save all data to `sheet_positions.csv` in GitHub** (UPLOAD_ID and File Storage are auto-filled!)
4. **Update CV links in existing results** - Updates Resume Link field for existing candidates without re-analyzing
5. Also update Google Sheets with the export results

#### Automatic CV Link Updates (No Re-Analysis)

The daily workflow includes an automatic CV link update feature:
- Updates **only the Resume Link** field in existing screening results
- **Does not re-score or re-analyze** candidates
- Matches candidates by email address
- Useful when candidate CV links are refreshed in Kalibrr

This ensures that all resume links stay current without the overhead of re-processing candidates who have already been screened.

#### Data Storage in GitHub (`sheet_positions.csv`)

The daily workflow automatically commits `sheet_positions.csv` to the GitHub repository. This file contains:
- **Nama Posisi** - Position names (from Google Sheets)
- **JOB_ID** - Kalibrr job IDs (from Google Sheets)
- **UPLOAD_ID** - Auto-filled by daily export workflow
- **File Storage** - Auto-filled by daily export workflow (URLs to candidate CSVs)

**Benefits:**
- The application works even when Google Sheets is unavailable
- UPLOAD_ID and File Storage are automatically updated daily
- CV links are kept current without re-analysis
- All data is version-controlled in GitHub

#### Setting up Daily Automation

To enable daily automated updates, configure these GitHub Secrets:

| Secret Name | Description |
|-------------|-------------|
| `KAID` | Kalibrr cookie value |
| `KB` | Kalibrr cookie value |
| `GSHEET_URL` | Google Sheets edit URL |
| `GSHEET_CSV_URL` | Published CSV URL for reading positions |

You can also manually trigger the workflow from the Actions tab.

### Dynamic Position Loading

The script **automatically reads positions from Google Sheets**, so you only need to add new positions directly to the sheet. No code changes required!

Simply add a new row to your Google Sheet with:
- **Nama Posisi**: The position name
- **JOB_ID**: The Kalibrr job ID

The daily workflow will automatically:
1. Pick up new positions
2. Export candidate data from Kalibrr
3. Fill in UPLOAD_ID and File Storage
4. Update CV links in existing results (without re-analysis)
5. Save everything to GitHub

### Google Sheets Format

The script reads from and updates a Google Sheet with the following structure:

| Nama Posisi | JOB_ID | UPLOAD_ID | File Storage |
|-------------|--------|-----------|--------------|
| Position name | Job ID | Auto-filled | Auto-filled URL |

## Repository Structure

```
cv-matching-auto/
├── app.py                          # Main Streamlit application
├── requirements.txt               # Python dependencies
├── scripts/
│   ├── kalibrr_export.py          # Kalibrr export automation script
│   └── update_cv_links.py         # Daily CV link updater script
├── modules/
│   ├── __init__.py
│   ├── extractor.py               # PDF text extraction
│   ├── scorer.py                  # AI scoring with OpenRouter
│   ├── github_utils.py            # GitHub integration for storage
│   ├── candidate_processor.py     # CSV parsing and candidate data processing
│   └── utils.py                   # Utility functions
├── results/                        # Screening results (position-specific CSV files)
│   ├── results_Position_Name.csv
│   └── ...
├── docs/                           # Documentation files
│   ├── DAILY_CV_UPDATE.md         # Daily CV update documentation
│   └── WORKFLOW.md                # Workflow documentation
├── .gitignore
└── README.md
```
└── README.md
```

## How It Works

1. **Job Management**: HR adds job positions with detailed descriptions. These are saved to `job_positions.csv` in GitHub.

2. **Screening**: When a job position is selected, the system:
   - First attempts to fetch candidate data from the configured Google Sheets URL
   - Finds the row matching the job position name
   - Extracts the File Storage URL from the "File Storage" column
   - Downloads the candidate CSV from that URL (e.g., from storage.googleapis.com)
   - If no data is found in Google Sheets, prompts for CSV file upload
   - Automatically checks for candidates already processed for this position
   - **Automatically processes new candidates in the background** (no button click needed)
   - Downloads resumes from provided URLs
   - Uses AI (Gemini 2.5 Pro) to analyze CVs and match against the job position
   - Automatically saves results to `results.csv` in GitHub

3. **Dashboard**: Results are loaded from GitHub and displayed in an organized view with filtering, ranking, and detailed analysis for each candidate.

## Data Storage

All data is stored in the GitHub repository with local file fallback:
- `job_positions.csv` - Job positions and descriptions
- `results.csv` - Screening results with scores and analysis

### How It Works

The application uses a **hybrid storage approach**:

1. **Primary**: GitHub API (when credentials are configured)
   - Data is loaded from the configured GitHub repository and branch
   - Provides cloud storage and version control
   - Requires `GITHUB_TOKEN`, `GITHUB_REPO`, and `GITHUB_BRANCH` in secrets

2. **Fallback**: Local filesystem
   - If GitHub API is unavailable, returns an error, or file doesn't exist in the branch
   - Automatically loads from local `results.csv` and `job_positions.csv`
   - Ensures the app works even without network connectivity or during development

This ensures data persistence and version control while maintaining reliability.