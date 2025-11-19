import pandas as pd
import requests
from io import BytesIO
import streamlit as st
from modules.extractor import extract_text_from_pdf

# Google Sheets CSV URL
GOOGLE_SHEETS_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRKC_5lHg9yJgGoBlkH0A-fjpjpiYu4MzO4ieEdSId5wAKS7bsLDdplXWx8944xFlHf2f9lVcUYzVcr/pub?output=csv"


def fetch_candidates_from_google_sheets(job_position_name, max_retries=3):
    """
    Fetch candidate data from Google Sheets by:
    1. Loading the sheet to get the File Storage URL for the job position
    2. Downloading the CSV from the File Storage URL
    3. Returning the candidate data from that CSV
    
    Args:
        job_position_name: The job position name to filter candidates by.
        max_retries: Maximum number of retry attempts on failure.
        
    Returns:
        DataFrame with candidates from the File Storage CSV, or None if fetch fails.
    """
    import time
    
    for attempt in range(max_retries):
        try:
            # Step 1: Fetch the main sheet to get File Storage URLs
            response = requests.get(GOOGLE_SHEETS_URL, timeout=30)
            
            if response.status_code != 200:
                if attempt < max_retries - 1:
                    time.sleep(2)
                    continue
                st.warning(f"⚠️ Failed to fetch Google Sheets (status {response.status_code})")
                return None
                
            # Parse the sheet content
            sheet_df = pd.read_csv(BytesIO(response.content))
            
            if sheet_df.empty:
                st.info("ℹ️ Google Sheets is empty")
                return None
            
            # Step 2: Find the row matching the job position name
            # Look for columns that might contain position name
            # Expected format: Nama Posisi, JOB_ID, UPLOAD_ID, File Storage
            position_column = None
            if "Nama Posisi" in sheet_df.columns:
                position_column = "Nama Posisi"
            elif "Job Position" in sheet_df.columns:
                position_column = "Job Position"
            elif "Position" in sheet_df.columns:
                position_column = "Position"
            
            if position_column is None:
                # If no position column, can't match
                available_columns = ", ".join(sheet_df.columns)
                st.warning(f"⚠️ No position column found in Google Sheets. Available columns: {available_columns}")
                return None
            
            # Find matching row (case-insensitive)
            # Filter out NaN values first before string operations
            valid_positions = sheet_df[position_column].notna()
            matching_rows = sheet_df[valid_positions & (sheet_df[position_column].str.strip().str.lower() == job_position_name.strip().lower())]
            
            if matching_rows.empty:
                available_positions = sheet_df[valid_positions][position_column].str.strip().unique().tolist()
                st.info(f"ℹ️ No match found for '{job_position_name}' in Google Sheets. Available positions: {', '.join(available_positions[:5])}")
                return None
            
            # Step 3: Get the File Storage URL from the matching row
            file_storage_column = None
            if "File Storage" in sheet_df.columns:
                file_storage_column = "File Storage"
            elif "file_storage" in sheet_df.columns:
                file_storage_column = "file_storage"
            
            if file_storage_column is None:
                # No File Storage column found
                st.warning(f"⚠️ No 'File Storage' column found in Google Sheets")
                return None
            
            # Get the first matching row's File Storage URL
            file_storage_url = matching_rows.iloc[0][file_storage_column]
            
            if pd.isna(file_storage_url) or not str(file_storage_url).strip():
                st.warning(f"⚠️ No File Storage URL found for position '{job_position_name}'")
                return None
            
            # Step 4: Download the CSV from the File Storage URL (with retry)
            st.info(f"📥 Downloading candidate data from File Storage...")
            csv_response = requests.get(str(file_storage_url).strip(), timeout=60)
            
            if csv_response.status_code != 200:
                if attempt < max_retries - 1:
                    time.sleep(2)
                    continue
                st.warning(f"⚠️ Failed to download CSV from File Storage (status {csv_response.status_code})")
                return None
            
            # Parse the candidate CSV data
            candidates_df = pd.read_csv(BytesIO(csv_response.content))
            
            if candidates_df.empty:
                st.info("ℹ️ Downloaded CSV is empty")
                return None
            
            st.success(f"✅ Successfully fetched {len(candidates_df)} candidate(s) from File Storage")
            return candidates_df
            
        except requests.exceptions.Timeout:
            if attempt < max_retries - 1:
                time.sleep(3)
                continue
            return None
        except requests.exceptions.RequestException:
            if attempt < max_retries - 1:
                time.sleep(2)
                continue
            return None
        except Exception as e:
            # For other errors (parsing, etc.), don't retry
            return None
    
    return None


def parse_candidate_csv(uploaded_file):
    """Parse uploaded candidate CSV file and return DataFrame."""
    try:
        df = pd.read_csv(uploaded_file)
        return df
    except Exception as e:
        st.error(f"❌ Failed to parse CSV: {e}")
        return None


def extract_resume_from_url(url, max_retries=3):
    """Download and extract text from resume URL (PDF) with retry logic.
    
    Args:
        url: URL to the resume PDF
        max_retries: Maximum number of retry attempts on failure
    
    Returns:
        str: Extracted text from the PDF, or empty string on failure
    """
    if pd.isna(url) or not url.strip():
        return ""
    
    import time
    
    for attempt in range(max_retries):
        try:
            response = requests.get(url, timeout=60)
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
            elif response.status_code == 429:  # Too many requests
                if attempt < max_retries - 1:
                    time.sleep(5)  # Wait 5 seconds before retrying
                    continue
                else:
                    st.warning(f"⚠️ Too many requests. Failed to download resume.")
                    return ""
            else:
                if attempt < max_retries - 1:
                    time.sleep(2)  # Wait before retrying
                    continue
                else:
                    st.warning(f"⚠️ Failed to download resume. Status {response.status_code}")
                    return ""
        except requests.exceptions.Timeout:
            if attempt < max_retries - 1:
                time.sleep(3)  # Wait before retrying
                continue
            else:
                st.warning(f"⚠️ Timeout downloading resume.")
                return ""
        except requests.exceptions.RequestException as e:
            if attempt < max_retries - 1:
                time.sleep(2)  # Wait before retrying
                continue
            else:
                st.warning(f"⚠️ Network error extracting resume.")
                return ""
        except Exception as e:
            # Non-network errors (like PDF parsing errors) should not retry
            st.warning(f"⚠️ Error extracting resume: {e}")
            return ""
    
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
