import pandas as pd
import requests
from io import BytesIO
import streamlit as st
from modules.extractor import extract_text_from_pdf

# Google Sheets CSV URL
GOOGLE_SHEETS_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRKC_5lHg9yJgGoBlkH0A-fjpjpiYu4MzO4ieEdSId5wAKS7bsLDdplXWx8944xFlHf2f9lVcUYzVcr/pub?output=csv"


def fetch_candidates_from_google_sheets(job_position_name):
    """
    Fetch candidate data from Google Sheets by:
    1. Loading the sheet to get the File Storage URL for the job position
    2. Downloading the CSV from the File Storage URL
    3. Returning the candidate data from that CSV
    
    Args:
        job_position_name: The job position name to filter candidates by.
        
    Returns:
        DataFrame with candidates from the File Storage CSV, or None if fetch fails.
    """
    try:
        # Step 1: Fetch the main sheet to get File Storage URLs
        response = requests.get(GOOGLE_SHEETS_URL, timeout=30)
        
        if response.status_code != 200:
            return None
            
        # Parse the sheet content
        sheet_df = pd.read_csv(BytesIO(response.content))
        
        if sheet_df.empty:
            return None
        
        # Step 2: Find the row matching the job position name
        # Look for columns that might contain position name
        position_column = None
        if "Nama Posisi" in sheet_df.columns:
            position_column = "Nama Posisi"
        elif "Job Position" in sheet_df.columns:
            position_column = "Job Position"
        elif "Position" in sheet_df.columns:
            position_column = "Position"
        
        if position_column is None:
            # If no position column, can't match
            return None
        
        # Find matching row (case-insensitive)
        matching_rows = sheet_df[sheet_df[position_column].str.strip().str.lower() == job_position_name.strip().lower()]
        
        if matching_rows.empty:
            return None
        
        # Step 3: Get the File Storage URL from the matching row
        file_storage_column = None
        if "File Storage" in sheet_df.columns:
            file_storage_column = "File Storage"
        elif "file_storage" in sheet_df.columns:
            file_storage_column = "file_storage"
        
        if file_storage_column is None:
            # No File Storage column found
            return None
        
        # Get the first matching row's File Storage URL
        file_storage_url = matching_rows.iloc[0][file_storage_column]
        
        if pd.isna(file_storage_url) or not str(file_storage_url).strip():
            return None
        
        # Step 4: Download the CSV from the File Storage URL
        csv_response = requests.get(str(file_storage_url).strip(), timeout=60)
        
        if csv_response.status_code != 200:
            return None
        
        # Parse the candidate CSV data
        candidates_df = pd.read_csv(BytesIO(csv_response.content))
        
        if candidates_df.empty:
            return None
        
        return candidates_df
        
    except Exception as e:
        # Silently fail and return None to allow fallback to CSV upload
        return None


def parse_candidate_csv(uploaded_file):
    """Parse uploaded candidate CSV file and return DataFrame."""
    try:
        df = pd.read_csv(uploaded_file)
        return df
    except Exception as e:
        st.error(f"❌ Failed to parse CSV: {e}")
        return None


def extract_resume_from_url(url):
    """Download and extract text from resume URL (PDF)."""
    if pd.isna(url) or not url.strip():
        return ""
    
    try:
        response = requests.get(url, timeout=30)
        if response.status_code == 200:
            pdf_file = BytesIO(response.content)
            # Create a file-like object that mimics uploaded_file
            class PDFFile:
                def __init__(self, content):
                    self.content = content
                def read(self):
                    return self.content
            
            pdf_obj = PDFFile(response.content)
            text = extract_text_from_pdf(pdf_obj)
            return text
        else:
            st.warning(f"⚠️ Failed to download resume from {url}: Status {response.status_code}")
            return ""
    except Exception as e:
        st.warning(f"⚠️ Error extracting resume from {url}: {e}")
        return ""


def _get_column_value(row, english_name, indonesian_name, default=''):
    """Get column value supporting both English and Indonesian column names."""
    # Try English name first (new format)
    if english_name in row and pd.notna(row.get(english_name)):
        return row.get(english_name, default)
    # Fallback to Indonesian name (old format)
    return row.get(indonesian_name, default)


def build_candidate_context(row):
    """Build additional context from candidate CSV data for re-ranking."""
    context_parts = []
    
    # Basic info - support both English and Indonesian column names
    first_name = _get_column_value(row, "First Name", "Nama Depan")
    last_name = _get_column_value(row, "Last Name", "Nama Belakang")
    
    if first_name:
        context_parts.append(f"Name: {first_name} {last_name}")
    
    # Work experience
    work_exp = []
    latest_job = _get_column_value(row, "Latest Job Title", "Jabatan Pekerjaan Terakhir")
    if latest_job:
        latest_company = _get_column_value(row, "Latest Company", "Perusahaan Terakhir", 'N/A')
        start_period = _get_column_value(row, "Latest Job Starting Period", "Periode Mulai Kerja", 'N/A')
        end_period = _get_column_value(row, "Latest Job Ending Period", "Periode Akhir Kerja", 'N/A')
        work_exp.append(f"- {latest_job} at {latest_company} ({start_period} - {end_period})")
        
        job_desc = _get_column_value(row, "Latest Job Description", "Deskripsi Pekerjaan")
        if job_desc:
            work_exp.append(f"  Description: {job_desc}")
    
    prev_job_1 = _get_column_value(row, "Previous Job Title (1)", "Jabatan Pekerjaan Sebelumnya (1)")
    if prev_job_1:
        prev_company_1 = _get_column_value(row, "Previous Company (1)", "Perusahaan Sebelumnya (1)", 'N/A')
        prev_start_1 = _get_column_value(row, "Previous Job Starting Period (1)", "Periode Mulai Kerja (1)", 'N/A')
        prev_end_1 = _get_column_value(row, "Previous Job Ending Period (1)", "Periode Akhir Kerja (1)", 'N/A')
        work_exp.append(f"- {prev_job_1} at {prev_company_1} ({prev_start_1} - {prev_end_1})")
    
    prev_job_2 = _get_column_value(row, "Previous Job Title (2)", "Jabatan Pekerjaan Sebelumnya (2)")
    if prev_job_2:
        prev_company_2 = _get_column_value(row, "Previous Company (2)", "Perusahaan Sebelumnya (2)", 'N/A')
        prev_start_2 = _get_column_value(row, "Previous Job Starting Period (2)", "Periode Mulai Kerja (2)", 'N/A')
        prev_end_2 = _get_column_value(row, "Previous Job Ending Period (2)", "Periode Akhir Kerja (2)", 'N/A')
        work_exp.append(f"- {prev_job_2} at {prev_company_2} ({prev_start_2} - {prev_end_2})")
    
    if work_exp:
        context_parts.append("Work Experience:")
        context_parts.extend(work_exp)
    
    # Education
    education = []
    latest_edu = _get_column_value(row, "Latest Educational Attainment", "Tingkat Pendidikan Tertinggi")
    if latest_edu:
        latest_school = _get_column_value(row, "Latest School/University", "Sekolah/Universitas", 'N/A')
        latest_major = _get_column_value(row, "Latest Major/Course", "Jurusan/Program Studi", 'N/A')
        edu_start = _get_column_value(row, "Latest Education Starting Period", "Periode Mulai Studi", 'N/A')
        edu_end = _get_column_value(row, "Latest Education Ending Period", "Periode Akhir Studi", 'N/A')
        education.append(f"- {latest_edu} - {latest_major} at {latest_school} ({edu_start} - {edu_end})")
    
    prev_edu_1 = _get_column_value(row, "Previous Educational Attainment (1)", "Tingkat Pendidikan Sebelumnya (1)")
    if prev_edu_1:
        prev_school_1 = _get_column_value(row, "Previous School/University (1)", "Sekolah/Universitas (1)", 'N/A')
        prev_major_1 = _get_column_value(row, "Previous Major/Course (1)", "Jurusan/Program Studi (1)", 'N/A')
        education.append(f"- {prev_edu_1} - {prev_major_1} at {prev_school_1}")
    
    if education:
        context_parts.append("Education:")
        context_parts.extend(education)
    
    return "\n".join(context_parts)


def get_candidate_identifier(row):
    """Generate unique identifier for candidate to avoid duplicates."""
    email = _get_column_value(row, "Email Address", "Alamat Email", "").strip()
    first_name = _get_column_value(row, "First Name", "Nama Depan")
    last_name = _get_column_value(row, "Last Name", "Nama Belakang")
    name = f"{first_name} {last_name}".strip()
    return f"{email}_{name}" if email else name
