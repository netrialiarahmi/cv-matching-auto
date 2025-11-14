# Column Mapping Update Documentation

## Overview
This document describes the changes made to support English column names in the CV matching system, while maintaining backward compatibility with the Indonesian column format.

## Problem Statement
The system originally used Indonesian column names (e.g., "Nama Depan", "Nama Belakang"). The new requirement is to support English column names from Kalibrr exports (e.g., "First Name", "Last Name") while displaying candidate names as "First Name + Last Name" instead of "Candidate 1", "Candidate 2", etc.

## Solution
Implemented a dual-format column mapping system that supports both English and Indonesian column names through a helper function.

## Changes Made

### 1. modules/candidate_processor.py
- **Added** `_get_column_value(row, english_name, indonesian_name, default='')` helper function
  - Tries English column name first (new format)
  - Falls back to Indonesian column name (legacy format)
  - Returns default value if neither exists

- **Updated** `build_candidate_context(row)` function
  - Now uses `_get_column_value()` for all field extractions
  - Supports both English and Indonesian column formats
  - Changed output labels from Indonesian to English (e.g., "Pengalaman Kerja" → "Work Experience")

- **Updated** `get_candidate_identifier(row)` function
  - Uses `_get_column_value()` for email and name extraction
  - Maintains same identifier format for consistency

### 2. app.py
- **Added** import of `_get_column_value` from candidate_processor module

- **Updated** screening section (lines 308-410)
  - Replaced direct `row.get()` calls with `_get_column_value()` calls
  - Updated all candidate data extraction to support both formats
  - Candidate name now properly extracted as "First Name + Last Name"

### 3. README.md
- **Updated** CSV format documentation
  - Listed all 50 English column names (recommended format)
  - Added note about legacy Indonesian format still being supported
  - Provided mapping examples between formats

## Column Mapping Table

| English Column Name | Indonesian Column Name | Description |
|---------------------|------------------------|-------------|
| First Name | Nama Depan | Candidate's first name |
| Last Name | Nama Belakang | Candidate's last name |
| Email Address | Alamat Email | Email address |
| Mobile Number | Nomor Handphone | Phone number |
| Latest Job Title | Jabatan Pekerjaan Terakhir | Most recent job title |
| Latest Company | Perusahaan Terakhir | Most recent company |
| Latest Educational Attainment | Tingkat Pendidikan Tertinggi | Highest education level |
| Latest School/University | Sekolah/Universitas | University name |
| Latest Major/Course | Jurusan/Program Studi | Major/program |
| Resume Link | Link Resume | URL to resume PDF |
| Kalibrr Profile Link | Link Profil Kalibrr | Kalibrr profile URL |
| Job Application Link | Link Aplikasi Pekerjaan | Application link |

(And many more - see README.md for complete list)

## Testing
All changes have been tested with:
1. Unit tests for helper functions
2. End-to-end tests with English column CSV
3. Backward compatibility tests with Indonesian column CSV
4. Syntax validation for all Python files

## Backward Compatibility
✅ **Fully backward compatible** - existing CSV files with Indonesian column names will continue to work without any changes.

## Usage
Users can now upload CSV files in either format:
- **New format**: English column names (recommended for Kalibrr exports)
- **Legacy format**: Indonesian column names (still supported)

The system automatically detects which format is being used and processes accordingly.

## Benefits
1. **Proper Name Display**: Candidates now show as "Fazlur Rahman", "Eko Prastyo" instead of "Candidate 1", "Candidate 2"
2. **Kalibrr Compatibility**: Direct support for Kalibrr CSV exports with English column names
3. **Backward Compatible**: Existing Indonesian format CSVs still work
4. **Future-Proof**: Easy to add support for additional column name variations if needed
