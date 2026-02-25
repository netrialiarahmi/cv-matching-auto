# Daily Resume Link Maintenance - Technical Documentation

## Overview

The `scripts/update_cv_links.py` script executes daily maintenance operations to refresh resume links in position-specific screening result files without re-executing candidate analysis workflows.

## Update Scope

The script modifies exclusively the "Resume Link" column (column 17) within position-specific result files, including:
- `results/results_Account_Executive_Kompasiana.csv`
- `results/results_Product_Designer.csv`
- `results/results_Content_Creator.csv`
- Additional position-specific result files

## Result File Schema

Each position-specific result file adheres to a standardized 20-column schema:

| Column | Field Name | Description |
|--------|------------|-------------|
| 1 | Candidate Name | Full name of candidate |
| 2 | Candidate Email | Email address (primary matching key) |
| 3 | Phone | Contact telephone number |
| 4 | Job Position | Applied position title |
| 5 | Match Score | Quantitative match score (0-100 scale) |
| 6 | AI Summary | Generated candidate evaluation summary |
| 7 | Strengths | Identified candidate strengths |
| 8 | Weaknesses | Identified candidate weaknesses |
| 9 | Gaps | Skill or experience gaps |
| 10 | Latest Job Title | Most recent position title |
| 11 | Latest Company | Most recent employer |
| 12 | Education | Highest education level attained |
| 13 | University | Educational institution name |
| 14 | Major | Field of study |
| 15 | Kalibrr Profile | Kalibrr profile URL |
| 16 | Application Link | Application submission URL |
| **17** | **Resume Link** | **Resume document URL (update target)** |
| 18 | Recruiter Feedback | Recruiter evaluation notes |
| 19 | Shortlisted | Shortlist status indicator |
| 20 | Date Processed | Initial processing timestamp |

## Implementation Details

### 1. Position Data Retrieval
```python
# Load updated position data from sheet_positions.csv
# (maintained by kalibrr_export_pooling.py / kalibrr_export_dashboard.py)
df = pd.read_csv("sheet_positions.csv")
```

The `sheet_positions.csv` file contains:
- Position Name
- JOB_ID
- UPLOAD_ID
- **File Storage** (URL endpoint for current candidate CSV data from Kalibrr)

Source of truth for positions: `job_positions.csv` (includes Pooling Status).
No Google Sheets dependency — all data is local/GitHub.

### 2. Existing Result Retrieval
```python
# Load position-specific result file
df = pd.read_csv("results/results_Position_Name.csv")
```

### 3. Current Candidate Data Acquisition
```python
# Retrieve current candidate CSV from File Storage URL
response = requests.get(file_storage_url)
fresh_candidates = pd.read_csv(BytesIO(response.content))
```

### 4. Candidate Matching Logic
```python
# Construct email-to-resume-link mapping from current data
for _, row in fresh_candidates.iterrows():
    email = row["Email Address"]
    resume_link = row["Resume Link"]
    email_to_resume_link[email] = resume_link
```

### 5. Resume Link Update Execution
```python
# Update Resume Link for matching candidates in existing results
for idx, row in existing_results.iterrows():
    candidate_email = row["Candidate Email"]
    
    # Match against current data by email
    if candidate_email in email_to_resume_link:
        new_resume_link = email_to_resume_link[candidate_email]
        
        # Update only Resume Link column
        existing_results.at[idx, "Resume Link"] = new_resume_link
```

### 6. Result Persistence
```python
# Persist updated results to original file
existing_results.to_csv(results_file, index=False)
```

## Preserved Data

The script maintains all other column data without modification:
- Match Score (tetap sama)
- AI Summary (tetap sama)
- Strengths, Weaknesses, Gaps (tetap sama)
- Semua informasi kandidat lainnya (tetap sama)

## Rationale for Daily Updates

1. **URL Expiration Management**: Kalibrr resume URLs from Google Cloud Storage include time-limited `Expires=` parameters that invalidate after a specific duration
2. **Cost Optimization**: Eliminates redundant AI/LLM API calls for candidate re-analysis
3. **Performance Efficiency**: Avoids unnecessary PDF download and text extraction operations
4. **Data Accuracy**: Maintains current resume links while preserving existing analysis results

## Daily Workflow Sequence

```
00:00 UTC (07:00 WIB) - GitHub Actions workflows initiation

=== Workflow 1: Pooling CV Link Update ===
  |
  v
Step 1: scripts/kalibrr_export_pooling.py execution
  - Read pooled positions from job_positions.csv (Pooling Status == "Pooled")
  - Skip positions without Job ID
  - Export candidate data from Kalibrr (FORCE_EXPORT=true)
  - Update sheet_positions.csv with current File Storage URLs
  |
  v
Step 2: scripts/update_cv_links.py --mode pooling
  - Load sheet_positions.csv (filtered to pooled positions via job_positions.csv)
  - For each pooled position:
    * Load results/results_Position_Name.csv
    * Fetch current candidate data from File Storage URL
    * Match candidates by email address
    * Update Resume Link column exclusively
    * Persist results/results_Position_Name.csv
  |
  v
Step 3: Version control commit
  - Commit sheet_positions.csv + results/*.csv → push to GitHub

=== Workflow 2: Dashboard Export and CV Link Update ===
  |
  v
Step 1: scripts/kalibrr_export_dashboard.py execution
  - Read active (non-pooled) positions from job_positions.csv
  - Skip positions without Job ID
  - Export candidate data from Kalibrr (FORCE_EXPORT=true)
  - Update sheet_positions.csv with current File Storage URLs
  |
  v
Step 2: scripts/update_cv_links.py --mode dashboard
  - Load sheet_positions.csv (filtered to active positions via job_positions.csv)
  - For each active position:
    * Load results/results_Position_Name.csv
    * Fetch current candidate data from File Storage URL
    * Match candidates by email address
    * Update Resume Link column exclusively
    * Persist results/results_Position_Name.csv
  |
  v
Step 3: Version control commit
  - Commit sheet_positions.csv + results/*.csv → push to GitHub

=== Workflow 3: Automated CV Screening (triggers after Workflow 2) ===
  |
  v
Step 1: scripts/auto_screen.py execution
  - Load active positions from job_positions.csv (skip pooled)
  - For each position with File Storage URL in sheet_positions.csv:
    * Download candidate CSV
    * Skip already-processed candidates
    * For each NEW candidate: download CV, AI score, save results
  |
  v
Step 2: Version control commit
  - Commit results/*.csv → push to GitHub
```

## Example Execution Output

```
============================================================
Processing: Content Creator
============================================================
Loaded 54 existing results from results/results_Content_Creator.csv
Fetching fresh candidate data from File Storage...
Fetched 68 candidates from File Storage
Found 68 candidates with resume links in fresh data

  Updated resume link for: John Doe
    Old: https://storage.googleapis.com/.../old-link.pdf?Expires=1234567890...
    New: https://storage.googleapis.com/.../new-link.pdf?Expires=9876543210...

Saved 1 updated resume link(s) to results/results_Content_Creator.csv
   Updated column: Resume Link (column 17 in standard format)
```

## Troubleshooting

### Expired URL Handling
Script displays warning for expired URLs:
```
HTTP 403 - URL may have expired
Could not fetch fresh candidate data for Position Name
   This may be due to expired URLs or network issues
   CV links will not be updated for this position
```

**Resolution**: Automatic retry on next scheduled execution (following day).

### Missing Resume Link Column
```
Warni