# CV Matching System - Technical Workflow

## Module 1: Job Position Management

```
User Interaction: Create Job Position
    |
    v
Input Capture: Position Title + Role Description
    |
    v
Data Persistence: Commit to GitHub (job_positions.csv)
    |
    v
Interface Update: Display position roster in tabular format
```

## Module 2: Candidate Screening

```
User Interaction: Upload Candidate Dataset
    |
    v
Position Selection: Choose target position from dropdown menu
    |
    v
Data Preview: Display job requirements + candidate data (first 10 records)
    |
    v
Processing Pipeline: For each candidate record
    |
    +-- Duplicate Detection: Verify candidate email against existing results
    |   |
    |   +-- Skip if previously processed
    |
    +-- Resume Acquisition: Extract document from "Resume Link" URL
    |
    +-- Context Assembly: Aggregate structured data from CSV columns:
    |   - Employment history (3 most recent positions)
    |   - Educational background (3 highest qualifications)
    |   - Personal information
    |
    +-- Data Integration: Combine extracted resume text with structured data
    |
    +-- AI Analysis: Execute evaluation using OpenRouter (Gemini 2.5 Pro)
        |
        +-- Match Score: Quantitative assessment (0-100 scale)
        +-- Strengths: Array of identified positive attributes
        +-- Weaknesses: Array of identified limitations
        +-- Gaps: Array of missing qualifications or experience
        +-- Summary: Generated 2-3 sentence candidate evaluation
    |
    v
Data Persistence: Commit results to GitHub (results.csv)
    |
    v
Interface Update: Display screening results preview
```

## Module 3: Results Dashboard

```
Data Retrieval: Load results.csv from GitHub repository
    |
    v
Filter Application: Apply position filter (optional)
    |
    v
Sort Application: Order by Final Score (descending)
    |
    v
Display Generation: For each candidate
    |
    +-- Key Performance Indicators:
    |   - Average Final Score
    |   - Maximum Final Score
    |   - Total Candidate Count
    |
    +-- Candidate Cards (expandable):
    |   - Quantitative Scores (Match, AI Recruiter, Final)
    |   - Basic Information (Email, Phone, Position, Education)
    |   - Strengths Analysis
    |   - Weaknesses Analysis
    |   - Gap Analysis
    |   - AI-Generated Summary
    |   - Resource Links (Resume, Profile, Application)
    |
    +-- Summary Table:
    |   - Complete candidate ranking
    |
    +-- Data Visualizations:
        - Score distribution bar chart
    |
    v
Export Options:
    - CSV format export
    - Excel format export
```

## Data Persistence Architecture

All system data is persisted to GitHub repository:

```
repository/
├── job_positions.csv          ← Source of truth for positions
│   - Job Position
│   - Job Description
│   - Date Created
│   - Pooling Status           ← "Pooled" or empty
│   - Job ID                   ← Kalibrr Job ID
│   - Last Modified
│
├── sheet_positions.csv        ← File Storage URL cache
│   - Nama Posisi
│   - JOB_ID
│   - UPLOAD_ID
│   - File Storage             ← Kalibrr CSV download URL
│
├── results/
│   └── results_<Position>.csv ← Per-position screening results
│
├── scripts/
│   ├── kalibrr_export_pooling.py    ← Export pooled positions
│   ├── kalibrr_export_dashboard.py  ← Export active positions
│   ├── update_cv_links.py           ← Refresh resume URLs (--mode pooling/dashboard)
│   └── auto_screen.py               ← AI CV screening (active positions only)
│
├── modules/
│   ├── kalibrr_core.py       ← Shared Kalibrr export logic
│   └── ...                    ← Other modules
│
└── .github/workflows/
    ├── pooling-link-update.yml      ← Workflow 1: Pooling link refresh
    ├── dashboard-export.yml         ← Workflow 2: Dashboard export + links
    └── auto-screening.yml           ← Workflow 3: AI screening (after Workflow 2)
```

### GitHub Actions Flow

```
Daily 00:00 UTC (07:00 WIB)
  │
  ├── Workflow 1: Pooling CV Link Update
  │   ├── kalibrr_export_pooling.py  (pooled positions only)
  │   ├── update_cv_links.py --mode pooling
  │   └── git commit + push
  │
  ├── Workflow 2: Dashboard Export and CV Link Update
  │   ├── kalibrr_export_dashboard.py  (active positions only)
  │   ├── update_cv_links.py --mode dashboard
  │   └── git commit + push
  │
  └── Workflow 3: Automated CV Screening  (triggers after Workflow 2)
      ├── auto_screen.py  (screen new candidates for active positions)
      └── git commit + push
```