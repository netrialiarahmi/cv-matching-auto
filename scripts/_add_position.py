"""Add Data Analyst KG Media position to config files."""
import csv

JOB_DESC = """Job Description
Collect, process, and analyze large datasets from various sources to generate actionable business insights.
Build and maintain interactive dashboards and reports using BI tools (e.g., Looker Studio, Tableau, Metabase, or Google Data Studio).
Write and optimize SQL queries for data extraction, transformation, and analysis.
Perform data cleaning, validation, and quality assurance to ensure data accuracy and reliability.
Collaborate with cross-functional teams (Product, Marketing, Editorial, Business Development) to define KPIs and reporting needs.
Conduct ad-hoc analysis to support strategic decision-making and identify growth opportunities.
Develop and automate recurring reports and data pipelines using Python or similar tools.
Present data findings and recommendations clearly to both technical and non-technical stakeholders.
Monitor key business metrics and proactively flag anomalies or trends.

Minimum Qualifications
Bachelor's degree in Statistics, Mathematics, Computer Science, Information Systems, or a related quantitative field.
Minimum 1-2 years of experience as a Data Analyst, Business Intelligence Analyst, or similar role.
Strong proficiency in SQL for querying and data manipulation.
Experience with BI/visualization tools such as Looker Studio, Tableau, Metabase, or Power BI.
Proficiency in Python or R for data analysis and automation.
Strong analytical thinking and problem-solving skills.
Excellent communication skills with the ability to translate data into clear insights.
Experience with data warehousing concepts and ETL processes is a plus.
Familiarity with Google BigQuery, cloud data platforms, or dbt is a plus.
Experience in media, publishing, or digital content industry is preferred."""

# 1. Add to job_positions.csv
row = [
    'Data Analyst KG Media',
    JOB_DESC,
    '2026-03-27',
    '',       # Pooling Status (empty = active)
    '265246.0',
    ''        # Last Modified
]

with open('job_positions.csv', 'a', newline='') as f:
    writer = csv.writer(f)
    writer.writerow(row)

print("Added Data Analyst KG Media to job_positions.csv")

# 2. Add to sheet_positions.csv
sheet_row = [
    'Data Analyst KG Media',
    '265246',
    '',
    'kalibrr_exports/Data_Analyst_KG_Media.csv'
]

with open('sheet_positions.csv', 'a', newline='') as f:
    writer = csv.writer(f)
    writer.writerow(sheet_row)

print("Added Data Analyst KG Media to sheet_positions.csv")

# Verify
import pandas as pd
jobs = pd.read_csv('job_positions.csv')
match = jobs[jobs['Job Position'] == 'Data Analyst KG Media']
print(f"\nVerification - job_positions.csv: {len(match)} match(es)")
if not match.empty:
    print(f"  Pooling Status: '{match.iloc[0].get('Pooling Status', '')}'")
    print(f"  Job ID: {match.iloc[0].get('Job ID', '')}")

sheet = pd.read_csv('sheet_positions.csv')
smatch = sheet[sheet['Nama Posisi'] == 'Data Analyst KG Media']
print(f"Verification - sheet_positions.csv: {len(smatch)} match(es)")
if not smatch.empty:
    print(f"  File Storage: {smatch.iloc[0].get('File Storage', '')}")
