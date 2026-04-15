import pandas as pd
import os

for pos_name in ['Account_Executive_Japanese_Client', 'Account_Executive_Pasangiklancom']:
    csv_path = f'data/raw/{pos_name}.csv'
    results_path = f'data/processed/results_{pos_name}.csv'

    if not os.path.isfile(csv_path):
        continue

    cands = pd.read_csv(csv_path)
    emails_in_csv = set()
    for _, r in cands.iterrows():
        e = r.get('Email Address') or r.get('Alamat Email') or r.get('email') or ''
        if pd.notna(e) and str(e).strip():
            emails_in_csv.add(str(e).strip().lower())

    already = set()
    if os.path.isfile(results_path):
        res = pd.read_csv(results_path)
        for _, r in res.iterrows():
            e = r.get('Candidate Email', '')
            if pd.notna(e) and str(e).strip():
                already.add(str(e).strip().lower())

    new = emails_in_csv - already
    print(f'{pos_name}:')
    print(f'  Export: {len(cands)} candidates ({len(emails_in_csv)} unique emails)')
    print(f'  Already processed: {len(already)} results')
    print(f'  New to process: {len(new)}')
