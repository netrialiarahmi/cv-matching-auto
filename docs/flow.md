# CV Matching Pipeline — Flow & Bug Analysis

## Overall Architecture

```mermaid
flowchart TB
    subgraph TRIGGER["⏰ Daily Schedule"]
        T1["00:07 UTC<br>Pooling Export"]
        T2["00:37 UTC<br>Dashboard Export"]
        T3["After ② completes<br>CV Screening"]
    end

    T1 --> W1
    T2 --> W2
    W2 -->|workflow_run| W3
    T3 -.-> W3

    subgraph W1["① Pooling Link Update"]
        P1["kalibrr_export_pooling.py"]
        P2["update_cv_links.py --mode pooling"]
        P3["git commit & push"]
        P1 --> P2 --> P3
    end

    subgraph W2["② Dashboard Export"]
        D1["kalibrr_export_dashboard.py"]
        D2["update_cv_links.py --mode dashboard"]
        D3["git commit & push"]
        D4["Upload artifact<br>dashboard-exports-*"]
        D1 --> D2 --> D3 --> D4
    end

    subgraph W3["③ CV Screening"]
        S0["Download artifact<br>dashboard-exports-*"]
        S1["auto_screen.py"]
        S2["git commit & push"]
        S0 --> S1 --> S2
    end
```

## Detailed Data Flow

```mermaid
flowchart LR
    subgraph INPUT["📄 Input Files"]
        JP[("job_positions.csv<br>29 positions<br>Job ID, Pooling Status")]
        SP[("sheet_positions.csv<br>17 positions<br>File Storage paths")]
    end

    subgraph KALIBRR["🌐 Kalibrr ATS"]
        API["POST /api/ats/candidates<br>Paginated API<br>(kb-csrf + auth cookies)"]
    end

    subgraph EXPORT["📤 Export Scripts"]
        EXP_P["kalibrr_export_pooling.py<br>Filter: Pooled only"]
        EXP_D["kalibrr_export_dashboard.py<br>Filter: Active only"]
    end

    subgraph LOCAL["💾 kalibrr_exports/"]
        CSV["*.csv files<br>(candidate data per position)"]
    end

    subgraph RESULTS["📊 results/"]
        RES["results_*.csv<br>(screening results per position)"]
    end

    JP --> EXP_P & EXP_D
    EXP_P & EXP_D -->|Playwright + API| API
    API -->|JSON → normalized CSV| CSV
    EXP_P & EXP_D -->|upsert local paths| SP

    CSV -->|update_cv_links.py<br>refresh Resume Link only| RES
    CSV -->|auto_screen.py<br>new candidates| SCREEN

    subgraph SCREEN["🤖 AI Scoring"]
        direction TB
        PDF["Download PDF<br>from Resume Link"]
        EXTRACT["Extract text<br>(PyMuPDF)"]
        STEP1["Step 1: Extract & Classify<br>(Gemini 2.5 Flash)"]
        STEP2["Step 2: Evaluate & Score<br>(Gemini 2.5 Pro)"]
        STEP3["Step 3: Score Ceiling<br>(Python rules)"]
        PDF --> EXTRACT --> STEP1 --> STEP2 --> STEP3
    end

    SCREEN --> RES
```

## Per-Workflow Breakdown

### ① Pooling Link Update (00:07 UTC)
```
job_positions.csv (Pooled only)
        │
        ▼
kalibrr_export_pooling.py
        │
        ├── Playwright → Kalibrr API (paginated)
        │       ↓
        │   kalibrr_exports/{position}.csv  ←── candidate data
        │       ↓
        └── sheet_positions.csv  ←── upsert File Storage = "kalibrr_exports/..."
                │
                ▼
update_cv_links.py --mode pooling
        │
        ├── Read sheet_positions.csv (pooled positions only)
        ├── Read kalibrr_exports/{position}.csv (fresh data)
        ├── Read results/results_{position}.csv (existing)
        └── Update ONLY "Resume Link" column → save back
                │
                ▼
        git add & commit & push:
          - sheet_positions.csv
          - results/*.csv
          - kalibrr_exports/*.csv  (⚠️ ignored by .gitignore!)
        upload artifact: kalibrr_exports/
```

### ② Dashboard Export (00:37 UTC)
```
Same as ① but:
  - Filter: Active positions (NOT Pooled)
  - Script: kalibrr_export_dashboard.py
  - update_cv_links.py --mode dashboard
  - Artifact: dashboard-exports-{run_number}
```

### ③ CV Screening (triggered by ② success)
```
Download artifact: dashboard-exports-* → kalibrr_exports/
Checkout: latest commit on main
        │
        ▼
auto_screen.py
        │
        ├── job_positions.csv → active positions only (10)
        ├── sheet_positions.csv → File Storage path per position
        │
        │   For each position:
        │   ├── Load candidates: sheet_positions.csv File Storage path
        │   │     └── Fallback: kalibrr_exports/{safe_name}.csv
        │   ├── Load existing results → skip already-processed (by email)
        │   │
        │   │   For each NEW candidate:
        │   │   ├── Download PDF (resume link from CSV)
        │   │   ├── Extract text (PyMuPDF)
        │   │   ├── AI Score (Flash → Pro → Ceiling)
        │   │   └── Save result (GitHub API + local)
        │   └── ───────────────────────────────
        │
        ▼
git add results/*.csv logs/*.json
git commit & push
```

---

## 🐛 Known Bugs & Issues

### BUG 1: `kalibrr_exports/` in `.gitignore` — FILES NEVER ACTUALLY COMMITTED
**Status:** 🔴 ACTIVE — root cause of all "File not found" errors

`.gitignore` contains:
```
kalibrr_exports/
```

This means `git add kalibrr_exports/*.csv` **silently does nothing** (unless `-f` flag is used). Even though workflows ① and ② try to commit these files, git ignores them.

**Impact:**
- Workflow ③ checks out repo → `kalibrr_exports/` is empty → all positions fail with "File not found"
- `update_cv_links.py` in ② works fine because it runs on the SAME runner where files were just exported

**Fix options:**
| Option | Approach | Pros | Cons |
|--------|----------|------|------|
| A | Remove `kalibrr_exports/` from `.gitignore` | Simple, files always available | Bloats repo history with large CSVs |
| **B** ✅ | Artifacts only (current approach) | Clean, no repo bloat | Need artifact download in ③ |
| C | `git add -f kalibrr_exports/*.csv` | Overrides `.gitignore` | Confusing — tracked files in ignored dir |

**Current fix:** Option B is partially implemented — ③ downloads artifacts, BUT the `git add` in ① and ② still silently fails. Those lines should be removed to avoid confusion.

### BUG 2: Artifact Download Only Covers Dashboard Exports
**Status:** 🟡 Minor

Workflow ③ only downloads `dashboard-exports-*` artifacts. If a position was exported by pooling (①) but NOT by dashboard (②), the CSV won't be available in ③.

**This is currently OK** because ③ only screens active (non-pooled) positions, so pooling CSVs are not needed.

### BUG 3: `sheet_positions.csv` Contains Stale Local Paths
**Status:** 🟡 Cosmetic

`File Storage` column has values like `kalibrr_exports/Software_Engineer.csv`. This works within a single runner but is misleading — it's not a URL, it's a relative path that only works if the file exists locally.

**Impact:** If someone tries to use `sheet_positions.csv` outside of the GitHub Actions context (e.g., local dev, Streamlit app), the paths won't resolve unless files are present.

### BUG 4: Dead Code in `auto_screen.py`
**Status:** ⚪ Cleanup

`fetch_candidates_from_kalibrr()` function (~100 lines) duplicates `kalibrr_core.py`'s `export_position()` and is never called.

### BUG 5: Double-Write Results (API + git commit)
**Status:** ⚪ By Design

`auto_screen.py` writes each result via GitHub Contents API immediately (resilience), then the workflow does `git add results/*.csv && git commit && git push` at the end. This is intentional for crash recovery but can cause merge conflicts if timing is unlucky.

---

## ✅ Action Items

| # | Priority | Action | Bug |
|---|----------|--------|-----|
| 1 | 🔴 HIGH | Remove useless `git add kalibrr_exports/*.csv` from workflow ① and ② (they're in `.gitignore`, so it's a no-op) | BUG 1 |
| 2 | 🔴 HIGH | Verify artifact download in ③ works correctly (test with `workflow_dispatch`) | BUG 1 |
| 3 | 🟡 MED | Also download `pooling-exports-*` in ③ if pooled positions ever need screening | BUG 2 |
| 4 | 🟡 MED | Consider storing File Storage as artifact names instead of local paths | BUG 3 |
| 5 | ⚪ LOW | Remove dead `fetch_candidates_from_kalibrr()` from `auto_screen.py` | BUG 4 |
