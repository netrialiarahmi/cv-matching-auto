"""Run screening for AE VCBL, AE Pasangiklan.com, and Business Development Analyst."""
import sys, os
sys.path.insert(0, '.')
from dotenv import load_dotenv
load_dotenv()

import pandas as pd
from scripts.auto_screen import screen_position

jobs_df = pd.read_csv('data/job_positions.csv')

positions_to_run = [
    ('Account Executive VCBL', 'data/raw/Account_Executive_KG_Media.csv'),
    ('Account Executive Pasangiklan.com', 'data/raw/Account_Executive_KG_Media.csv'),
    ('Business Development Analyst', 'data/raw/Business_Development_Analyst.csv'),
]

for pos_name, csv_path in positions_to_run:
    match = jobs_df[jobs_df['Job Position'] == pos_name]
    if match.empty:
        print(f"❌ {pos_name} not found in job_positions.csv")
        continue
    
    row = match.iloc[0]
    job_description = row['Job Description']
    job_id = row.get('Job ID', '')
    
    print(f"\n{'='*70}")
    print(f"Position: {pos_name}")
    print(f"Job ID: {job_id}")
    print(f"CSV: {csv_path}")
    print(f"{'='*70}\n")
    
    screen_position(pos_name, job_description, job_id, csv_path)
