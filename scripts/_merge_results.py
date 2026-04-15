"""Merge local + remote results for Data Analyst position, then prepare for git operations."""
import os, sys, subprocess
sys.path.insert(0, '.')
import pandas as pd

WORKDIR = "/Users/netrialiarahmi/Library/Mobile Documents/com~apple~CloudDocs/career/kg/cv-matching-auto"
os.chdir(WORKDIR)

# 1. Read the remote results from GitHub
print("=== Step 1: Read remote results ===")
remote_csv = subprocess.run(
    ["git", "show", "origin/main:results/results_Data_Analyst_Business_Intelligence.csv"],
    capture_output=True, text=True
).stdout

from io import StringIO
remote_df = pd.read_csv(StringIO(remote_csv))
print(f"Remote (Streamlit) candidates: {len(remote_df)}")
print(f"Remote emails: {remote_df['Candidate Email'].tolist()}")

# 2. Read local results
print("\n=== Step 2: Read local results ===")
local_df = pd.read_csv("results/results_Data_Analyst_KG_Media.csv")
print(f"Local candidates: {len(local_df)}")
print(f"Local emails (first 5): {local_df['Candidate Email'].head().tolist()}")

# 3. Normalize position name to match GitHub's "Data Analyst (Business Intelligence)"
local_df["Job Position"] = "Data Analyst (Business Intelligence)"

# 4. Merge: combine both, dedup by email (keep first = remote/Streamlit wins)
print("\n=== Step 3: Merge ===")
merged = pd.concat([remote_df, local_df], ignore_index=True)
before_dedup = len(merged)
merged = merged.drop_duplicates(subset=["Candidate Email"], keep="first")
print(f"Combined: {before_dedup} → {len(merged)} after dedup")
dupes = before_dedup - len(merged)
if dupes > 0:
    print(f"  ({dupes} duplicates removed)")

# Sort by Date Applied (latest first)
if "Date Applied" in merged.columns:
    merged = merged.sort_values(by=["Date Applied"], ascending=[False], na_position="last").reset_index(drop=True)

# 5. Save to the correct filename
output_path = "results/results_Data_Analyst_Business_Intelligence.csv"
merged.to_csv(output_path, index=False)
print(f"\n=== Step 4: Saved merged results to {output_path} ===")
print(f"Total candidates: {len(merged)}")

# 6. Remove the old local-only results file
if os.path.exists("results/results_Data_Analyst_KG_Media.csv"):
    os.remove("results/results_Data_Analyst_KG_Media.csv")
    print("Removed results/results_Data_Analyst_KG_Media.csv (merged into correct file)")

# 7. How many candidates still need processing?
export_df = pd.read_csv("kalibrr_exports/Data_Analyst_KG_Media.csv")
all_emails = set(export_df["Email Address"].dropna().str.lower())
processed_emails = set(merged["Candidate Email"].dropna().str.lower())
remaining = all_emails - processed_emails
print(f"\n=== Summary ===")
print(f"Total applicants in CSV: {len(export_df)}")
print(f"Already processed: {len(processed_emails)}")
print(f"Remaining to process: {len(remaining)}")
