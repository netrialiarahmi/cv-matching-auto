"""Quick validation of all code changes."""
import sys
sys.path.insert(0, '.')

# 1. Test imports
from modules.kalibrr_core import export_position, _normalize_export_df, _iso_to_kalibrr_date, COLUMN_RENAME
print('kalibrr_core: OK')

# 2. Test ISO date conversion
assert _iso_to_kalibrr_date('2025-09-29T05:26:25.017968+00:00') == '09/29/25 05:26'
assert _iso_to_kalibrr_date('2024-01-15T10:30:00.000000+00:00') == '01/15/24 10:30'
assert _iso_to_kalibrr_date('') == ''
assert _iso_to_kalibrr_date(None) == ''
print('ISO date conversion: OK')

# 3. Test parse_kalibrr_date with all formats
from modules.github_utils import parse_kalibrr_date
assert parse_kalibrr_date('01/11/26 09:43') == '2026-01-11 09:43'
assert parse_kalibrr_date('2025-09-29T05:26:25.017968+00:00') == '2025-09-29 05:26'
assert parse_kalibrr_date('2024-01-15T10:30:00.123456+00:00') == '2024-01-15 10:30'
assert parse_kalibrr_date('2026-01-11 09:43') == '2026-01-11 09:43'
assert parse_kalibrr_date('') == ''
assert parse_kalibrr_date(None) == ''
print('parse_kalibrr_date: OK (all formats)')

# 4. Test column normalization
import pandas as pd
df = pd.DataFrame([{
    'first_name': 'John',
    'last_name': 'Doe',
    'email': 'john@test.com',
    'mobile_number': '08123',
    'resume': '/api/candidate_uploads/123',
    'application.created_at': '2025-09-29T05:26:25.017968+00:00',
    'id': 12345,
    'relevant_work.job_title': 'Sales Manager',
    'relevant_work.company_name': 'ACME Inc',
    'education_school': 'UI',
    'education_fields': 'Marketing',
    'education_level': '550',
}])
df = _normalize_export_df(df, 256571)

assert 'First Name' in df.columns, f"Missing 'First Name', have: {list(df.columns)}"
assert 'Email Address' in df.columns
assert 'Link Resume' in df.columns
assert 'Latest Job Title' in df.columns
assert 'Date Application Started (mm/dd/yy hr:mn)' in df.columns
assert df.iloc[0]['Date Application Started (mm/dd/yy hr:mn)'] == '09/29/25 05:26'
assert 'Link Profil Kalibrr' in df.columns
assert 'Link Aplikasi Pekerjaan' in df.columns
assert 'Nama' in df.columns
assert df.iloc[0]['Nama'] == 'John Doe'
print('Column normalization: OK')

# 5. Test auto_screen imports compile
from scripts.auto_screen import fetch_candidates_from_sheet_csv
print('auto_screen import: OK')

# 6. Test local file reading in fetch_candidates_from_sheet_csv
import os
csv_path = 'kalibrr_exports/Account_Executive_Pasangiklancom.csv'
if os.path.isfile(csv_path):
    df = fetch_candidates_from_sheet_csv(csv_path)
    assert df is not None, "Failed to load local CSV"
    assert len(df) > 0, "Empty DataFrame"
    # Check that normalized columns exist
    has_first = 'First Name' in df.columns or 'first_name' in df.columns
    has_email = 'Email Address' in df.columns or 'email' in df.columns
    print(f'Local CSV: {len(df)} rows, First Name col: {has_first}, Email col: {has_email}')
else:
    print(f'Skipping local CSV test (file not found: {csv_path})')

# 7. Test callers import
from scripts.kalibrr_export_dashboard import main as dash_main
from scripts.kalibrr_export_pooling import main as pool_main
print('Caller imports: OK')

print('\n=== ALL TESTS PASSED ===')
