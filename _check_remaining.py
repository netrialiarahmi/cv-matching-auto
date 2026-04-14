"""Check remaining candidates for each position."""
import pandas as pd

positions = [
    ('Account Executive VCBL', 'results/results_Account_Executive_VCBL.csv', 'kalibrr_exports/Account_Executive_KG_Media.csv'),
    ('Account Executive Pasangiklan.com', 'results/results_Account_Executive_Pasangiklancom.csv', 'kalibrr_exports/Account_Executive_KG_Media.csv'),
    ('Business Development Analyst', 'results/results_Business_Development_Analyst.csv', 'kalibrr_exports/Business_Development_Analyst.csv'),
]

for pos_name, results_path, csv_path in positions:
    try:
        results = pd.read_csv(results_path)
        processed_emails = set(results[results['Candidate Email'].notna()]['Candidate Email'].str.lower())
    except Exception:
        processed_emails = set()
    
    csv_df = pd.read_csv(csv_path)
    email_col = 'Email Address' if 'Email Address' in csv_df.columns else 'Alamat Email'
    all_emails = set(csv_df[email_col].dropna().str.lower())
    
    remaining = all_emails - processed_emails
    print(f'{pos_name}: {len(all_emails)} total, {len(processed_emails)} processed, {len(remaining)} remaining')
