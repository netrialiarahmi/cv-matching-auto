"""Run screening for Data Analyst (Business Intelligence) position only."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))) if '__file__' in dir() else '.')
from dotenv import load_dotenv
load_dotenv()

import pandas as pd
from scripts.auto_screen import screen_position

# Load job_positions.csv to get job description
jobs_df = pd.read_csv('job_positions.csv')
match = jobs_df[jobs_df['Job Position'] == 'Data Analyst (Business Intelligence)']

if match.empty:
    print("❌ Data Analyst (Business Intelligence) not found in job_positions.csv")
    sys.exit(1)

row = match.iloc[0]
position_name = row['Job Position']
job_description = row['Job Description']
job_id = row.get('Job ID', '265246')
csv_url = 'kalibrr_exports/Data_Analyst_KG_Media.csv'

print(f"Position: {position_name}")
print(f"Job ID: {job_id}")
print(f"CSV: {csv_url}")
print(f"Job Description: {job_description[:100]}...")
print()

screened = screen_position(position_name, job_description, job_id, csv_url)
print(f"\n{'='*50}")
print(f"Total screened: {screened}")
