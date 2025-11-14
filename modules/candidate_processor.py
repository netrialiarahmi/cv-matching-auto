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


def build_candidate_context(row):
    """Build additional context from candidate CSV data for re-ranking."""
    context_parts = []
    
    # Basic info
    if pd.notna(row.get("Nama Depan")):
        context_parts.append(f"Nama: {row.get('Nama Depan', '')} {row.get('Nama Belakang', '')}")
    
    # Work experience
    work_exp = []
    if pd.notna(row.get("Jabatan Pekerjaan Terakhir")):
        work_exp.append(f"- {row.get('Jabatan Pekerjaan Terakhir')} at {row.get('Perusahaan Terakhir', 'N/A')} ({row.get('Periode Mulai Kerja', 'N/A')} - {row.get('Periode Akhir Kerja', 'N/A')})")
        if pd.notna(row.get("Deskripsi Pekerjaan")):
            work_exp.append(f"  Description: {row.get('Deskripsi Pekerjaan')}")
    
    if pd.notna(row.get("Jabatan Pekerjaan Sebelumnya (1)")):
        work_exp.append(f"- {row.get('Jabatan Pekerjaan Sebelumnya (1)')} at {row.get('Perusahaan Sebelumnya (1)', 'N/A')} ({row.get('Periode Mulai Kerja (1)', 'N/A')} - {row.get('Periode Akhir Kerja (1)', 'N/A')})")
    
    if pd.notna(row.get("Jabatan Pekerjaan Sebelumnya (2)")):
        work_exp.append(f"- {row.get('Jabatan Pekerjaan Sebelumnya (2)')} at {row.get('Perusahaan Sebelumnya (2)', 'N/A')} ({row.get('Periode Mulai Kerja (2)', 'N/A')} - {row.get('Periode Akhir Kerja (2)', 'N/A')})")
    
    if work_exp:
        context_parts.append("Pengalaman Kerja:")
        context_parts.extend(work_exp)
    
    # Education
    education = []
    if pd.notna(row.get("Tingkat Pendidikan Tertinggi")):
        education.append(f"- {row.get('Tingkat Pendidikan Tertinggi')} - {row.get('Jurusan/Program Studi', 'N/A')} at {row.get('Sekolah/Universitas', 'N/A')} ({row.get('Periode Mulai Studi', 'N/A')} - {row.get('Periode Akhir Studi', 'N/A')})")
    
    if pd.notna(row.get("Tingkat Pendidikan Sebelumnya (1)")):
        education.append(f"- {row.get('Tingkat Pendidikan Sebelumnya (1)')} - {row.get('Jurusan/Program Studi (1)', 'N/A')} at {row.get('Sekolah/Universitas (1)', 'N/A')}")
    
    if education:
        context_parts.append("Pendidikan:")
        context_parts.extend(education)
    
    return "\n".join(context_parts)


def get_candidate_identifier(row):
    """Generate unique identifier for candidate to avoid duplicates."""
    email = str(row.get("Alamat Email", "")).strip()
    name = f"{row.get('Nama Depan', '')} {row.get('Nama Belakang', '')}".strip()
    return f"{email}_{name}" if email else name
