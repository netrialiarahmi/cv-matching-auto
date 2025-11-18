# CV Matching Auto

An automated CV matching system with 3 main sections for managing job positions, screening candidates, and viewing results.

## Features

### 1. Job Management
- Upload and manage job positions with descriptions
- Edit existing job positions (name and description)
- Delete job positions
- Store job positions in GitHub repository
- View all saved job positions in expandable cards
- Download job positions as CSV

### 2. Screening
- **Automatic data fetching from Google Sheets** - Automatically loads candidate data from a configured Google Sheets URL when you select a job position
- **Fallback to CSV upload** - If no data is found for the position in Google Sheets, you can upload a CSV file manually
- Select job position from saved positions
- Preview job description and candidate data before screening
- Automatically extract and analyze resumes from URLs
- Combine resume content with structured candidate data
- Skip candidates already in the dashboard
- AI-powered matching using OpenRouter (Gemini 2.5 Pro)
- Save results to GitHub

### 3. Dashboard
- View all screening results from GitHub
- Filter by job position
- Expandable cards for each candidate showing:
  - Match scores
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
OPENROUTER_API_KEY = "your-openrouter-api-key"
GITHUB_TOKEN = "your-github-token"
GITHUB_REPO = "username/repo-name"
GITHUB_BRANCH = "main"
```

3. (Optional) Configure Google Sheets URL:
   - The Google Sheets URL is configured in `modules/candidate_processor.py`
   - By default, it uses: `https://docs.google.com/spreadsheets/d/e/2PACX-1vRKC_5lHg9yJgGoBlkH0A-fjpjpiYu4MzO4ieEdSId5wAKS7bsLDdplXWx8944xFlHf2f9lVcUYzVcr/pub?output=csv`
   - Your Google Sheet should contain a column named "Job Name" or "Nama Pekerjaan" to match against job positions
   - The sheet should follow the same CSV format as described in the "Required CSV Format" section

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
   - Filters candidates by matching the job position name with the "Job Name" or "Nama Pekerjaan" column
   - If no data is found in Google Sheets, prompts for CSV file upload
   - Downloads resumes from provided URLs
   - Combines resume content with structured data from the CSV/Google Sheets
   - Uses AI to match candidates against the selected job position
   - Saves results to `results.csv` in GitHub

3. **Dashboard**: Results are loaded from GitHub and displayed in an organized view with filtering, ranking, and detailed analysis for each candidate.

## Data Storage

All data is stored in the GitHub repository:
- `job_positions.csv` - Job positions and descriptions
- `results.csv` - Screening results with scores and analysis

This ensures data persistence and version control.