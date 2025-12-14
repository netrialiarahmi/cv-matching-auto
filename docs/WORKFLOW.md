# CV Matching System Workflow

## Section 1: Job Management

```
User Action: Add Job Position
    ↓
Input: Job Position Name + Job Description
    ↓
Save to GitHub: job_positions.csv
    ↓
Display: Table of all job positions
```

## Section 2: Screening

```
User Action: Upload Candidate CSV
    ↓
Select: Job Position from dropdown
    ↓
Preview: Job Description + Candidate Data (first 10 rows)
    ↓
Process: For each candidate
    │
    ├─→ Check if already in dashboard (by email)
    │   └─→ Skip if exists
    │
    ├─→ Extract resume from "Link Resume" URL
    │
    ├─→ Build context from CSV columns:
    │   - Work history (3 positions)
    │   - Education (3 levels)
    │   - Personal info
    │
    ├─→ Combine: Resume text + Structured data
    │
    └─→ AI Matching: OpenRouter (Gemini 2.5 Pro)
        ├─→ Match Score (0-100)
        ├─→ Strengths (list)
        ├─→ Weaknesses (list)
        ├─→ Gaps (list)
        └─→ AI Summary (2-3 sentences)
    ↓
Save to GitHub: results.csv
    ↓
Display: Preview of results
```

## Section 3: Dashboard

```
Load: results.csv from GitHub
    ↓
Filter: By Job Position (optional)
    ↓
Sort: By Final Score (descending)
    ↓
Display: For each candidate
    │
    ├─→ KPI Metrics:
    │   - Average Final Score
    │   - Top Final Score
    │   - Total Candidates
    │
    ├─→ Expandable Cards:
    │   - Scores (Match, AI Recruiter, Final)
    │   - Basic Info (Email, Phone, Job, Education)
    │   - ✅ Strengths
    │   - ⚠️ Weaknesses
    │   - 🔴 Gaps
    │   - 🤖 AI Summary
    │   - 🔗 Links (Resume, Profile, Application)
    │
    ├─→ Summary Table:
    │   - All candidates ranked
    │
    └─→ Visualizations:
        - Bar chart of scores
    ↓
Download Options:
    - CSV
    - Excel
```

## Data Storage

All data persisted in GitHub repository:

```
repository/
├── job_positions.csv
│   - Job Position
│   - Job Description
│   - Date Created
│
└── results.csv
    - Candidate Name
    - Candidate Email
    - Phone
    - Job Position
    - Match Score
    - AI Summary
    - Strengths
    - Weaknesses
    - Gaps
    - Latest Job Title
    - Latest Company
    - Education
    - University
    - Major
    - Kalibrr Profile
    - Application Link
    - Resume Link
    - Recruiter Feedback
    - AI Recruiter Score
    - Final Score
    - Date Processed
```

## Key Features

### Duplicate Prevention
- Checks existing results by email before processing
- Skips candidates already in dashboard
- Shows count of new vs skipped candidates

### AI-Powered Matching
- Uses OpenRouter API with Gemini 2.5 Pro
- Analyzes both resume PDF and structured CSV data
- Provides detailed evaluation:
  - Numeric score (0-100)
  - Specific strengths
  - Clear weaknesses
  - Skill/experience gaps
  - Contextual summary

### Data Persistence
- All data saved to GitHub
- Version control for changes
- No local storage dependency
- Accessible from any deployment

### User Experience
- Preview data before processing
- Progress indicators during screening
- Filter and sort results
- Expandable detail views
- Multiple export formats
