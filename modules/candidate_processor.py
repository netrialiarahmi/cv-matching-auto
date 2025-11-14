import pandas as pd
import requests
from io import BytesIO
import streamlit as st
from modules.extractor import extract_text_from_pdf


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
