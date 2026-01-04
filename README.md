# CV Matching Automation System

An automated candidate screening and matching system designed to streamline recruitment workflows. The system provides comprehensive tools for managing job positions, evaluating candidates against role requirements, and tracking recruitment progress through an integrated dashboard.

## System Overview

This application automates the candidate screening process by integrating multiple data sources, performing AI-powered resume analysis, and providing actionable insights for recruitment teams. The system supports both manual and automated workflows to accommodate different operational requirements.

## Recent Updates

### Version 2.0 (January 2026)
- Implemented automated daily screening via GitHub Actions workflow (executes at 07:30 WIB)
- Added intelligent duplicate detection to prevent redundant candidate processing
- Introduced position-level error handling for improved system resilience
- Enabled background processing for continuous candidate evaluation

### Version 1.x (2024)
- Added local filesystem fallback for improved availability when GitHub API is unavailable
- Resolved API authentication issues for Gemini API integration
- Integrated Google Sheets File Storage column for dynamic candidate data retrieval
- Implemented flexible API key management supporting both OpenRouter and Gemini APIs
- Streamlined scoring methodology to use single Match Score metric
- Removed manual processing triggers in favor of automatic background processing

## Core Features

### 1. Job Position Management
The system provides comprehensive tools for managing recruitment positions:
- Create and configure job positions with detailed role descriptions
- Edit existing position information (title and requirements)
- Remove obsolete positions from the active roster
- Persist all position data to GitHub repository for version control
- View positions in an organized, expandable card interface
- Export position data to CSV format for external analysis
- Archive filled positions using the "Pooled" status designation

### 2. Candidate Screening
The screening module supports both manual and automated evaluation workflows:

#### Manual Screening Interface
- Guided multi-step wizard for streamlined data input
- Automatic candidate data retrieval from Google Sheets File Storage URLs
- CSV file upload fallback when Google Sheets integration is unavailable
- Position selection from saved job roster
- Preview interface for job description and candidate data verification
- Automatic background processing without user intervention
- Intelligent duplicate detection to skip previously evaluated candidates

#### Automated Daily Screening
- Scheduled execution daily at 07:30 WIB (00:30 UTC)
- Processes all active (non-pooled) positions automatically
- Retrieves current candidate data from Google Sheets
- Applies duplicate detection to process only new candidates
- Downloads and extracts text from candidate resumes
- Performs AI-powered analysis using Gemini language model
- Commits screening results directly to GitHub repository
- Implements graceful error handling to ensure partial failures do not halt processing
- Supports manual workflow trigger via GitHub Actions interface

### 3. Results Dashboard
The dashboard provides comprehensive access to screening outcomes:
- Centralized view of all screening results stored in GitHub
- Multi-criteria filtering by position, candidate status, and score range
- Full-text search capability across candidate names and email addresses
- Flexible sorting options (score, name, date)
- Detailed candidate cards displaying:
  - Quantitative Match Score derived from CV analysis
  - Identified candidate strengths, weaknesses, and skill gaps
  - AI-generated candidate summary
  - Comprehensive candidate profile information
  - Direct links to resume documents, applicant profiles, and applications
- Status management tools for marking candidates as approved or rejected
- Interview status tracking functionality
- Recruiter feedback and rejection reason documentation
- Aggregate statistics including average score, top score, and candidate count
- Status distribution metrics across evaluation stages

### 4. Position Pooling
The pooling feature provides archival capabilities for completed recruitment cycles:
- Archive filled positions to maintain focused active screening view
- Consolidated view of all pooled candidates across positions
- Status and score-based filtering options
- Full-text search across candidate information
- Multiple sorting criteria for flexible data organization
- Paginated interface for efficient navigation of large candidate pools
- Complete candidate management capabilities consistent with Dashboard module

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
   Navigate to repository Settings > Secrets and variables > Actions and configure the following secrets:
   - `GEMINI_API_KEY` - API key for Gemini language model integration
   - `KAID` - Kalibrr authentication cookie for candidate export functionality
   - `KB` - Kalibrr authentication cookie for candidate export functionality
     - `GSHEET_URL` - Google Sheets edit URL for File Storage column updates
     - `GSHEET_CSV_URL` - Published Google Sheets CSV endpoint for position data retrieval
   
   Note: The `GITHUB_TOKEN` secret is automatically provisioned by GitHub Actions and does not require manual configuration.→ Actions
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

The system implements two GitHub Actions workflows for autonomous operation:

### 1. Daily Candidate Export and Resume Link Maintenance
**Workflow File:** `.github/workflows/weekly-export.yml`  
**Execution Schedule:** Daily at 07:00 WIB (00:00 UTC)  
**Primary Function:** Synchronize candidate data from Kalibrr and maintain current resume links

**Workflow Operations:**
1. Retrieves candidate data from Kalibrr for all active positions
2. Updates `sheet_positions.csv` with current UPLOAD_ID and File Storage URLs
3. Refreshes Resume Link column in existing result files without re-executing analysis
4. Commits updated data to GitHub repository

### 2. Automated Candidate Screening
**Workflow File:** `.github/workflows/auto-screening.yml`  
**Execution Schedule:** Daily at 07:30 WIB (00:30 UTC), offset 30 minutes after export workflow  
**Primary Function:** Execute AI-powered screening for new candidates

**Workflow Operations:**
1. Retrieves all active (non-pooled) job positions from repository
2. Fetches current candidate data from Google Sheets File Storage endpoints
3. Compares against existing results to identify unprocessed candidates
4. Processes only new candidates, implementing duplicate prevention logic
5. Downloads candidate resumes and performs text extraction
6. Executes AI analysis using Gemini language model
7. Persists screening results to position-specific CSV files
8. Commits all results to GitHub repository

**Manual Execution:**
Both workflows support manual triggering through the GitHub Actions interface:
- Navigate to repository Actions tab
- Select target workflow
- Click "Run workflow" button

**Error Handling Implementation:**
- Position-level error isolation prevents cascading failures
- Network operation retry logic with exponential backoff
- API rate limiting compliance (6.5 second delay between AI requests)
- Comprehensive execution logs uploaded as workflow artifacts

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
└──System Architecture

### 1. Job Position Management
Recruitment personnel configure job positions with comprehensive role descriptions. Position data is persisted to `job_positions.csv` in the GitHub repository, providing version-controlled storage accessible across all system components.

### 2. Candidate Screening Pipeline
Upon position selection, the system executes the following workflow:
   - Attempts to retrieve candidate data from configured Google Sheets endpoint
   - Identifies the row corresponding to the selected position
   - Extracts the File Storage URL from the designated column
   - Downloads candidate CSV from the specified URL (typically cloud storage endpoints)
   - Falls back to manual CSV upload if Google Sheets retrieval fails
   - Performs duplicate detection against existing screening results
   - Processes new candidates automatically in background thread
   - Downloads resume documents from provided URLs
   - Executes AI-powered analysis using Gemini language model
   - Evaluates candidates against position requirements
   - Persists screening results to `results.csv` in GitHub repository
 Architecture

The system implements a hybrid storage strategy with GitHub as the primary data store:
- `job_positions.csv` - Position definitions and role requirements
- `results.csv` - Candidate screening results with quantitative scores and qualitative analysis

### Storage Implementation

The application employs a dual-layer storage approach for maximum reliability:

1. **Primary Layer: GitHub API**
   - Data is retrieved from configured repository and branch
   - Provides cloud-based storage with full version control capabilities
   - Requires configuration of `GITHUB_TOKEN`, `GITHUB_REPO`, and `GITHUB_BRANCH` credentials

2. **Fallback Layer: Local Filesystem**
   - Activates when GitHub API is unavailable or returns errors
   - Automatically loads from local `results.csv` and `job_positions.csv` files
   - Ensures system availability during network disruptions or development scenarios

This architecture ensures data persistence and version control while maintaining high system availets

2. **Fallback**: Local filesystem
   - If GitHub API is unavailable, returns an error, or file doesn't exist in the branch
   - Automatically loads from local `results.csv` and `job_positions.csv`
   - Ensures the app works even without network connectivity or during development

This ensures data persistence and version control while maintaining reliability.