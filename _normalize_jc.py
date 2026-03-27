"""Normalize the Account_Executive_Japanese_Client.csv and check columns."""
import pandas as pd
from modules.kalibrr_core import _normalize_export_df

csv_path = 'kalibrr_exports/Account_Executive_Japanese_Client.csv'
df = pd.read_csv(csv_path)
print(f'Before: {df.shape}')
print(f'Columns (first 20): {list(df.columns[:20])}')

# Check if already has normalized columns
has_first_name = 'First Name' in df.columns
has_link_resume = 'Link Resume' in df.columns
print(f'Has "First Name": {has_first_name}')
print(f'Has "Link Resume": {has_link_resume}')

if not has_first_name or not has_link_resume:
    # Need to find the job_id for this position
    jobs = pd.read_csv('job_positions.csv')
    match = jobs[jobs['Job Position'] == 'Account Executive Japanese Client']
    if not match.empty:
        job_id = int(match.iloc[0]['Job ID'])
        print(f'Job ID: {job_id}')
        df_norm = _normalize_export_df(df, job_id)
        df_norm.to_csv(csv_path, index=False)
        print(f'After normalization: {df_norm.shape}')
        if 'Link Resume' in df_norm.columns:
            print(f'Link Resume samples: {df_norm["Link Resume"].dropna().head(3).tolist()}')
    else:
        print('Position not found in job_positions.csv')
else:
    # Already normalized, just fix resume URLs if needed
    if has_link_resume:
        samples = df['Link Resume'].dropna().head(3).tolist()
        print(f'Link Resume samples: {samples}')
        needs_fix = any(str(s).startswith('/api/') for s in samples)
        if needs_fix:
            df['Link Resume'] = df['Link Resume'].apply(
                lambda r: f'https://www.kalibrr.com{r}' if isinstance(r, str) and r.startswith('/api/') else r
            )
            df.to_csv(csv_path, index=False)
            print('Fixed resume URLs')
            print(f'New samples: {df["Link Resume"].dropna().head(3).tolist()}')
        else:
            print('Resume URLs already OK')
