# Candidate Name Extraction - Implementation Summary

## Problem
The Dashboard was displaying "Candidate 1", "Candidate 2", etc. instead of actual candidate names from the uploaded CSV or their CV documents.

## Root Cause
When the uploaded CSV file had missing or empty values in the "Nama Depan" (First Name) and "Nama Belakang" (Last Name) columns, the system would save an empty string as the candidate name in results.csv. This led to generic labels being displayed in the Dashboard.

## Solution
Implemented a multi-tier fallback strategy that attempts to extract candidate names from multiple sources, prioritizing accuracy while ensuring a graceful fallback.

### Extraction Strategy (Priority Order)

1. **PRIMARY: CSV Columns** (Existing)
   - Extracts from "Nama Depan" + "Nama Belakang" columns
   - Most reliable when data is properly filled

2. **SECONDARY: CV Text via AI** (NEW ✨)
   - Downloads CV from "Link Resume" URL
   - Uses AI (Gemini 2.5 Pro) to extract candidate name from CV text
   - Handles various CV formats and layouts
   - Returns "Unknown Candidate" if extraction fails

3. **TERTIARY: Email Address** (NEW ✨)
   - Uses the prefix of "Alamat Email" (before @) as identifier
   - Example: "john.doe@example.com" → "john.doe"

4. **FALLBACK: Generic Label** (Existing)
   - Uses "Candidate {number}" as last resort
   - Ensures every candidate has an identifier

## Implementation Details

### Changes Made

#### 1. modules/scorer.py
Added new function `extract_candidate_name_from_cv()`:
```python
def extract_candidate_name_from_cv(cv_text):
    """Extract candidate name from CV text using AI."""
    # Uses Gemini 2.5 Pro to intelligently extract names
    # Handles edge cases and malformed responses
    # Returns clean name or "Unknown Candidate"
```

#### 2. app.py - Screening Section (Lines 334-370)
Updated the screening loop to:
- Try CSV columns first
- If empty, download CV and extract name using AI
- If CV unavailable, use email prefix
- Final fallback to generic label
- Show progress with proper candidate identification

#### 3. app.py - Dashboard Section (Lines 478-495)
Enhanced display logic for expandable cards:
- Checks for valid candidate name
- Falls back to email prefix
- Uses generic label only as last resort
- Handles NaN and empty string values properly

#### 4. app.py - Dashboard Section (Lines 583-595)
Enhanced summary table display:
- Applies same fallback strategy
- Ensures consistent naming across all dashboard views
- Creates readable display DataFrame

## Usage

### For New Screenings
When uploading a new CSV file with candidates:
1. System tries to get names from CSV columns
2. If missing, downloads each CV and extracts name using AI
3. If no CV available, uses email as identifier
4. Shows progress with proper candidate names

### For Existing Results
The Dashboard automatically applies the improved display logic:
- Shows actual names when available in results.csv
- Falls back to email prefix if name is empty
- Uses "Candidate {number}" only when no identifying info exists

## Benefits

1. **Better User Experience**: Shows meaningful candidate identifiers instead of generic labels
2. **AI-Powered**: Leverages AI to extract names from unstructured CV text
3. **Flexible**: Handles various data quality scenarios gracefully
4. **Consistent**: Same fallback logic applied across all views
5. **Non-Breaking**: Existing data continues to work without reprocessing

## Testing

All test scenarios pass:
- ✅ CSV name extraction
- ✅ Email fallback
- ✅ Generic fallback
- ✅ NaN value handling
- ✅ AI extraction flow

## Future Improvements

Possible enhancements:
1. Add a manual name editing feature in the Dashboard
2. Cache extracted names to avoid re-downloading CVs
3. Support extracting names from other document formats (DOCX, TXT)
4. Add batch reprocessing tool for existing results

## Technical Notes

- AI extraction uses OpenRouter API with Gemini 2.5 Pro model
- Temperature set to 0.1 for consistent name extraction
- Maximum name length: 100 characters (prevents errors)
- Newlines and special characters are cleaned from extracted names
- Email extraction uses simple split on '@' character
