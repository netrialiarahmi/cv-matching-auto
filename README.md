# CV Matching Auto

An automated CV matching system with 3 main sections for managing job positions, screening candidates, and viewing results.

## Features

### 1. Job Management
- Upload and manage job positions with descriptions
- Store job positions in GitHub repository
- View all saved job positions in a table
- Download job positions as CSV

### 2. Screening
- Upload candidate data via CSV file (50 columns including work history, education, and resume links)
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

The candidate CSV file must include the following 50 columns:

1. Nama Depan
2. Nama Belakang
3. Jenis Kelamin
4. Tanggal Lahir (mm/dd/yy)
5. Alamat Email
6. Nomor Handphone
7. Alamat Domisili
8. Jabatan Pekerjaan Terakhir
9. Perusahaan Terakhir
10. Periode Mulai Kerja
11. Periode Akhir Kerja
12. Spesialisasi
13. Tingkat Posisi
14. Deskripsi Pekerjaan
15. Jabatan Pekerjaan Sebelumnya (1)
16. Perusahaan Sebelumnya (1)
17. Periode Mulai Kerja (1)
18. Periode Akhir Kerja (1)
19. Spesialisasi (1)
20. Tingkat Posisi (1)
21. Deskripsi Pekerjaan (1)
22. Jabatan Pekerjaan Sebelumnya (2)
23. Perusahaan Sebelumnya (2)
24. Periode Mulai Kerja (2)
25. Periode Akhir Kerja (2)
26. Spesialisasi (2)
27. Tingkat Posisi (2)
28. Deskripsi Pekerjaan (2)
29. Tingkat Pendidikan Tertinggi
30. Sekolah/Universitas
31. Jurusan/Program Studi
32. Periode Mulai Studi
33. Periode Akhir Studi
34. Tingkat Pendidikan Sebelumnya (1)
35. Sekolah/Universitas (1)
36. Jurusan/Program Studi (1)
37. Periode Mulai Studi (1)
38. Periode Akhir Studi (1)
39. Tingkat Pendidikan Sebelumnya (2)
40. Sekolah/Universitas (2)
41. Jurusan/Program Studi (2)
42. Periode Mulai Studi (2)
43. Periode Akhir Studi (2)
44. Tanggal Aplikasi Dimulai (mm/dd/yy hr:mn)
45. Tanggal Assessment Selesai (mm/dd/yy hr:mn)
46. Nama Pekerjaan
47. Status Aplikasi
48. Link Profil Kalibrr
49. Link Aplikasi Pekerjaan
50. Link Resume

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

3. Run the application:
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

2. **Screening**: HR uploads a CSV file with candidate data. The system:
   - Downloads resumes from provided URLs
   - Combines resume content with structured data from the CSV
   - Uses AI to match candidates against the selected job position
   - Saves results to `results.csv` in GitHub

3. **Dashboard**: Results are loaded from GitHub and displayed in an organized view with filtering, ranking, and detailed analysis for each candidate.

## Data Storage

All data is stored in the GitHub repository:
- `job_positions.csv` - Job positions and descriptions
- `results.csv` - Screening results with scores and analysis

This ensures data persistence and version control.