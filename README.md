# CV Matching Auto

An automated CV matching system with 3 main sections for managing job positions, screening candidates, and viewing results.

## Recent Updates

### ✨ Latest Changes (2024)
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

### 2. Screening
- **Automatic data fetching from Google Sheets** - Fetches CSV URLs from "File Storage" column and downloads candidate data from cloud storage
- **Fallback to CSV upload** - If no data is found for the position in Google Sheets, you can upload a CSV file manually
- Select job position from saved positions
- Preview job description and candidate data before screening
- **Automatic background processing** - New candidates are automatically processed without button clicks
- Automatically skip candidates already processed for the same position
- Automatically extract and analyze resumes from URLs
- AI-powered matching using Gemini 2.5 Pro (supports both OpenRouter and direct Gemini API)
- Automatically save results to GitHub

### 3. Dashboard
- View all screening results from GitHub
- Filter by job position
- Expandable cards for each candidate showing:
  - Match Score (based on CV analysis)
  - Strengths, Weaknesses, and Gaps
  - AI Summary
  - Basic candidate information
  - Direct links to resume, profile, and application
- Ranked table sorted by match score
- Visual score distribution chart
- Download results as CSV or Excel

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

4. Run the application:
```bash
streamlit run app.py
```

## Repository Structure

```
cv-matching-auto/
├── app.py                          # Main Streamlit application
├── modules/
│   ├── __init__.py
│   ├── extractor.py               # PDF text extraction
│   ├── scorer.py                  # AI scoring with OpenRouter
│   ├── github_utils.py            # GitHub integration for storage
│   ├── candidate_processor.py     # CSV parsing and candidate data processing
│   └── utils.py                   # Utility functions
├── requirements.txt               # Python dependencies
├── .gitignore
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