import streamlit as st
from streamlit_option_menu import option_menu
import pandas as pd
from modules.extractor import extract_text_from_pdf
from modules.scorer import score_with_openrouter, get_openrouter_client, extract_candidate_name_from_cv, extract_candidate_info_from_cv, score_table_data, _get_model_name, call_api_with_retry
from modules.github_utils import (
    save_results_to_github,
    load_results_from_github,
    load_results_for_position,
    clear_results_cache,
    save_job_positions_to_github,
    load_job_positions_from_github,
    delete_job_position_from_github,
    update_job_position_in_github,
    update_results_in_github,
    get_results_filename
)
from modules.candidate_processor import (
    parse_candidate_csv,
    extract_resume_from_url,
    build_candidate_context,
    get_candidate_identifier,
    _get_column_value,
    fetch_candidates_from_google_sheets
)
from modules.usage_logger import log_cv_processing, print_daily_summary, get_daily_summary
from PIL import Image
from datetime import datetime
import io
import re
import time

# Constants for candidate status
REJECTION_REASONS = [
    "Diterima ditempat lain",
    "Mengundurkan diri",
    "Overbudget",
    "Karena status",
    "Kompetensi"
]
REJECTION_REASON_CV_SCREENING = "Tidak lolos CV screening"

# --- Page Config ---
logo = Image.open("logo.webp")
st.set_page_config(
    page_title="Kompas.com CV Matching System",
    page_icon=logo,
    layout="wide"
)

# --- Custom Styling ---
st.markdown("""
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    
    <style>
    /* Modern Design System Variables */
    :root {
        --primary-50: #eff6ff;
        --primary-100: #dbeafe;
        --primary-500: #3b82f6;
        --primary-600: #2563eb;
        --primary-700: #1d4ed8;
        --success-50: #ecfdf5;
        --success-500: #10b981;
        --success-600: #059669;
        --error-50: #fef2f2;
        --error-500: #ef4444;
        --error-600: #dc2626;
        --warning-50: #fffbeb;
        --warning-500: #f59e0b;
        --neutral-50: #f9fafb;
        --neutral-100: #f3f4f6;
        --neutral-200: #e5e7eb;
        --neutral-300: #d1d5db;
        --neutral-400: #9ca3af;
        --neutral-500: #6b7280;
        --neutral-600: #4b5563;
        --neutral-700: #374151;
        --neutral-800: #1f2937;
        --neutral-900: #111827;
        --shadow-sm: 0 1px 2px 0 rgba(0, 0, 0, 0.05);
        --shadow-md: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
        --shadow-lg: 0 10px 15px -3px rgba(0, 0, 0, 0.1);
        --radius-md: 8px;
        --radius-lg: 12px;
        --radius-xl: 16px;
    }
    
    /* Global Typography */
    * {
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
        -webkit-font-smoothing: antialiased;
        -moz-osx-font-smoothing: grayscale;
    }
    
    body {
        background-color: var(--neutral-50);
        color: var(--neutral-800);
    }
    
    .block-container {
        padding-top: 2rem;
        max-width: 1400px;
    }
    
    /* Step Headers */
    .step-header {
        display: flex;
        align-items: center;
        gap: 12px;
        font-size: 1.3rem;
        font-weight: 600;
        color: var(--text-primary);
        margin: 1.5rem 0 1rem 0;
        padding-bottom: 0.5rem;
        border-bottom: 2px solid var(--border-color);
    }
    
    .step-number {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        width: 32px;
        height: 32px;
        background: linear-gradient(135deg, var(--primary-color), var(--primary-hover));
        color: white;
        border-radius: 50%;
        font-size: 1rem;
        font-weight: 700;
        box-shadow: 0 2px 8px rgba(37, 99, 235, 0.3);
    }

    /* Animations */
    @keyframes fadeIn {
        from { opacity: 0; transform: translateY(10px); }
        to { opacity: 1; transform: translateY(0); }
    }
    
    @keyframes slideIn {
        from { transform: translateX(-20px); opacity: 0; }
        to { transform: translateX(0); opacity: 1; }
    }
    
    @keyframes scaleIn {
        from { transform: scale(0.95); opacity: 0; }
        to { transform: scale(1); opacity: 1; }
    }
    
    @keyframes shimmer {
        0% { background-position: -1000px 0; }
        100% { background-position: 1000px 0; }
    }
    
    /* Headers */
    h1, h2, h3, h4, h5, h6 {
        font-weight: 600;
        color: var(--neutral-900);
        animation: fadeIn 0.5s ease-out;
        letter-spacing: -0.025em;
    }
    
    h1 { font-size: 2rem; line-height: 2.5rem; }
    h2 { font-size: 1.5rem; line-height: 2rem; }
    h3 { font-size: 1.25rem; line-height: 1.75rem; }
    
    /* Step Headers */
    .step-header {
        display: flex;
        align-items: center;
        gap: 12px;
        font-size: 1.3rem;
        font-weight: 600;
        color: var(--text-primary);
        margin: 1.5rem 0 1rem 0;
        padding-bottom: 0.5rem;
        border-bottom: 2px solid var(--border-color);
    }
    
    .step-number {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        width: 32px;
        height: 32px;
        background: linear-gradient(135deg, var(--primary-color), var(--primary-hover));
        color: white;
        border-radius: 50%;
        font-size: 1rem;
        font-weight: 700;
        box-shadow: 0 2px 8px rgba(37, 99, 235, 0.3);
    }
    
    /* Progress Stepper */
    .progress-stepper {
        display: flex;
        align-items: center;
        justify-content: center;
        margin: 2rem 0 3rem 0;
        padding: 1.5rem;
        background: white;
        border-radius: var(--radius-lg);
        box-shadow: var(--shadow-sm);
    }
    
    .step-indicator {
        display: flex;
        align-items: center;
        gap: 0.75rem;
        flex: 1;
        max-width: 200px;
    }
    
    .step-indicator-circle {
        display: flex;
        align-items: center;
        justify-content: center;
        width: 44px;
        height: 44px;
        border-radius: 50%;
        font-weight: 700;
        font-size: 1.1rem;
        transition: all 0.3s ease;
        flex-shrink: 0;
    }
    
    .step-indicator-circle.completed {
        background: var(--primary-600);
        color: white;
        box-shadow: 0 2px 8px rgba(37, 99, 235, 0.3);
    }
    
    .step-indicator-circle.active {
        background: linear-gradient(135deg, var(--primary-500), var(--primary-600));
        color: white;
        box-shadow: 0 4px 12px rgba(37, 99, 235, 0.4);
        animation: pulse 2s infinite;
    }
    
    .step-indicator-circle.upcoming {
        background: var(--neutral-200);
        color: var(--neutral-500);
    }
    
    .step-indicator-label {
        display: flex;
        flex-direction: column;
        gap: 0.25rem;
    }
    
    .step-indicator-title {
        font-weight: 600;
        font-size: 0.95rem;
        color: var(--neutral-700);
        transition: all 0.3s ease;
    }
    
    .step-indicator-subtitle {
        font-size: 0.75rem;
        color: var(--neutral-500);
    }
    
    .step-indicator.active .step-indicator-title {
        color: var(--primary-600);
        font-weight: 700;
    }
    
    .step-indicator.completed .step-indicator-title {
        color: var(--neutral-600);
    }
    
    .step-connector {
        flex: 1;
        height: 3px;
        background: var(--neutral-200);
        position: relative;
        margin: 0 1rem;
        max-width: 80px;
    }
    
    .step-connector.completed {
        background: var(--primary-600);
    }
    
    @keyframes pulse {
        0%, 100% { transform: scale(1); }
        50% { transform: scale(1.05); }
    }
    
    /* Step Cards */
    .step-card {
        background: white;
        border-radius: var(--radius-xl);
        padding: 2rem;
        margin-bottom: 1.5rem;
        box-shadow: var(--shadow-md);
        border: 2px solid var(--neutral-200);
        animation: slideIn 0.3s ease-out;
    }
    
    .step-card-active {
        border-color: var(--primary-500);
        box-shadow: 0 4px 16px rgba(37, 99, 235, 0.15);
    }
    
    .step-card-completed {
        background: var(--neutral-50);
        border: 1px solid var(--neutral-300);
        padding: 1.25rem 2rem;
        cursor: pointer;
        transition: all 0.2s ease;
    }
    
    .step-card-completed:hover {
        border-color: var(--primary-400);
        box-shadow: var(--shadow-sm);
    }
    
    .step-summary {
        display: flex;
        align-items: center;
        justify-content: space-between;
    }
    
    .step-summary-content {
        display: flex;
        align-items: center;
        gap: 1rem;
    }
    
    .step-summary-icon {
        width: 32px;
        height: 32px;
        border-radius: 50%;
        background: var(--primary-600);
        color: white;
        display: flex;
        align-items: center;
        justify-content: center;
        font-weight: 700;
    }
    
    .step-summary-text {
        display: flex;
        flex-direction: column;
        gap: 0.25rem;
    }
    
    .step-summary-label {
        font-size: 0.85rem;
        color: var(--neutral-600);
        font-weight: 500;
    }
    
    .step-summary-value {
        font-size: 1rem;
        color: var(--neutral-900);
        font-weight: 600;
    }
    
    .step-card-header {
        margin-bottom: 1.5rem;
        padding-bottom: 1rem;
        border-bottom: 2px solid var(--neutral-200);
    }
    
    .step-card-title {
        font-size: 1.4rem;
        font-weight: 700;
        color: var(--neutral-900);
        margin-bottom: 0.5rem;
    }
    
    .step-card-subtitle {
        font-size: 0.95rem;
        color: var(--neutral-600);
    }
    
    /* Step Actions */
    .step-actions {
        display: flex;
        gap: 1rem;
        margin-top: 2rem;
        padding-top: 1.5rem;
        border-top: 1px solid var(--neutral-200);
    }
    
    /* Metric Cards */
    [data-testid="stMetricValue"] {
        font-size: 2rem;
        font-weight: 700;
        color: var(--primary-600);
    }
    
    [data-testid="stMetric"] {
        background: white;
        padding: 1.25rem;
        border-radius: var(--radius-lg);
        border: 1px solid var(--neutral-200);
        box-shadow: var(--shadow-sm);
        transition: all 0.3s ease;
        animation: scaleIn 0.4s ease-out;
    }
    
    [data-testid="stMetric"]:hover {
        box-shadow: var(--shadow-md);
        transform: translateY(-2px);
        border-color: var(--primary-300);
    }
    
    /* Buttons */
    .stButton > button {
        border-radius: var(--radius-md);
        font-weight: 500;
        padding: 0.5rem 1.5rem;
        transition: all 0.2s ease;
        box-shadow: var(--shadow-sm);
        font-size: 0.875rem;
    }
    
    .stButton > button:hover {
        transform: translateY(-1px);
        box-shadow: var(--shadow-md);
    }
    
    .stButton > button:active {
        transform: translateY(0);
    }
    
    .stButton > button[kind="primary"] {
        background: linear-gradient(135deg, var(--primary-600) 0%, var(--primary-700) 100%);
        color: white;
        border: none;
    }
    
    .stButton > button[kind="secondary"] {
        background: white;
        color: var(--neutral-700);
        border: 1px solid var(--neutral-300);
    }
    
    /* Input Fields */
    .stTextInput > div > div > input,
    .stTextArea > div > div > textarea,
    .stSelectbox > div > div > select {
        border-radius: var(--radius-md);
        border: 1px solid var(--neutral-300);
        transition: all 0.2s ease;
        font-size: 0.875rem;
    }
    
    .stTextInput > div > div > input:focus,
    .stTextArea > div > div > textarea:focus,
    .stSelectbox > div > div > select:focus {
        border-color: var(--primary-500);
        box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1);
        outline: none;
    }
    
    /* Expanders (Candidate Cards) */
    .streamlit-expanderHeader {
        background: white;
        border: 1px solid var(--neutral-200);
        border-radius: var(--radius-lg);
        padding: 1rem 1.5rem;
        font-weight: 500;
        transition: all 0.3s ease;
        animation: fadeIn 0.3s ease-out;
        color: var(--neutral-800);
    }
    
    .streamlit-expanderHeader:hover {
        background: var(--neutral-50);
        border-color: var(--primary-300);
        box-shadow: var(--shadow-sm);
    }
    
    .streamlit-expanderContent {
        border: 1px solid var(--neutral-200);
        border-top: none;
        border-radius: 0 0 var(--radius-lg) var(--radius-lg);
        padding: 1.5rem;
        background: white;
        animation: fadeIn 0.4s ease-out;
    }
    
    /* Status Badges */
    .status-badge {
        display: inline-flex;
        align-items: center;
        gap: 0.375rem;
        padding: 0.375rem 0.875rem;
        border-radius: 9999px;
        font-size: 0.875rem;
        font-weight: 500;
        animation: scaleIn 0.3s ease-out;
    }
    
    .status-ok {
        background: var(--success-50);
        color: var(--success-600);
    }
    
    .status-rejected {
        background: var(--error-50);
        color: var(--error-600);
    }
    
    .status-pending {
        background: var(--warning-50);
        color: #92400e;
    }
    
    .status-pooled {
        background: var(--primary-50);
        color: var(--primary-600);
    }
    
    /* DataFrames */
    .dataframe {
        border: 1px solid var(--neutral-200) !important;
        border-radius: var(--radius-lg) !important;
        overflow: hidden;
        animation: fadeIn 0.5s ease-out;
        font-size: 0.875rem;
    }
    
    .dataframe th {
        background: var(--neutral-100) !important;
        color: var(--neutral-700) !important;
        font-weight: 600 !important;
        padding: 0.75rem !important;
        border-bottom: 2px solid var(--neutral-300) !important;
        text-align: left !important;
    }
    
    .dataframe td {
        padding: 0.75rem !important;
        border-bottom: 1px solid var(--neutral-200) !important;
    }
    
    .dataframe tr:hover {
        background: var(--neutral-50) !important;
        transition: background 0.15s ease;
    }
    
    /* File Uploader */
    [data-testid="stFileUploader"] {
        border: 2px dashed var(--neutral-300);
        border-radius: var(--radius-lg);
        padding: 2rem;
        text-align: center;
        transition: all 0.3s ease;
        background: white;
    }
    
    [data-testid="stFileUploader"]:hover {
        border-color: var(--primary-500);
        background: var(--primary-50);
    }
    
    /* Divider */
    hr {
        border: none;
        border-top: 1px solid var(--neutral-200);
        margin: 2rem 0;
    }
    
    /* Alerts */
    .stAlert {
        border-radius: var(--radius-md);
        border-left-width: 4px;
        animation: slideIn 0.3s ease-out;
    }
    
    /* Progress Bar */
    .stProgress > div > div {
        background: linear-gradient(90deg, var(--primary-500) 0%, var(--primary-600) 100%);
        border-radius: 9999px;
    }
    
    /* Tabs */
    .stTabs [data-baseweb="tab-list"] {
        gap: 0.5rem;
        border-bottom: 1px solid var(--neutral-200);
    }
    
    .stTabs [data-baseweb="tab"] {
        border-radius: var(--radius-md) var(--radius-md) 0 0;
        padding: 0.625rem 1.25rem;
        font-weight: 500;
        transition: all 0.2s ease;
        color: var(--neutral-600);
        border: none;
    }
    
    .stTabs [data-baseweb="tab"]:hover {
        background: var(--neutral-100);
        color: var(--neutral-900);
    }
    
    .stTabs [aria-selected="true"] {
        background: var(--primary-600);
        color: white;
    }
    
    /* Spinner */
    .stSpinner > div {
        border-color: var(--primary-500) !important;
        border-right-color: transparent !important;
    }
    
    /* Download Button */
    .stDownloadButton > button {
        background: white;
        border: 1px solid var(--neutral-300);
        color: var(--neutral-700);
    }
    
    .stDownloadButton > button:hover {
        border-color: var(--primary-500);
        color: var(--primary-600);
    }
    
    /* Remove emoji from labels */
    label { font-weight: 500; color: var(--neutral-700); }
    
    /* Smooth page transitions */
    .main { animation: fadeIn 0.4s ease-out; }
    
    /* Modern Navbar Styles */
    .navbar-container {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 0;
        margin: -5rem -5rem 2rem -5rem;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
        position: sticky;
        top: 0;
        z-index: 1000;
    }
    
    .navbar-header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 1.25rem 2.5rem;
        background: rgba(255, 255, 255, 0.95);
        backdrop-filter: blur(10px);
        border-bottom: 1px solid rgba(255, 255, 255, 0.2);
    }
    
    .navbar-brand {
        display: flex;
        align-items: center;
        gap: 1rem;
    }
    
    .navbar-logo {
        font-size: 1.75rem;
        font-weight: 700;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
    }
    
    .navbar-subtitle {
        font-size: 0.875rem;
        color: var(--neutral-500);
        font-weight: 500;
    }
    
    /* Override streamlit-option-menu default styles */
    div[data-testid="stHorizontalBlock"] > div:has(nav) {
        background: white !important;
        padding: 0 !important;
        margin: 0 !important;
    }
    
    nav[data-testid="stHorizontalBlock"] {
        background: white !important;
        box-shadow: none !important;
        border-bottom: 1px solid var(--neutral-200) !important;
    }
    </style>
""", unsafe_allow_html=True)

# --- Navigation Bar ---
selected = option_menu(
    menu_title=None,
    options=["Job Management", "Screening", "Dashboard", "Pooling", "Usage Log"],
    icons=["briefcase-fill", "search", "bar-chart-fill", "archive-fill", "clock-history"],
    orientation="horizontal",
    default_index=0,
    styles={
        "container": {
            "padding": "0 2rem",
            "background-color": "white",
            "margin": "0 -4rem 2.5rem -4rem",
            "border-bottom": "1px solid #e5e7eb",
            "box-shadow": "0 1px 3px rgba(0,0,0,0.05)"
        },
        "icon": {
            "font-size": "1.1rem",
            "margin-right": "0.5rem",
        },
        "nav-link": {
            "color": "#6b7280",
            "font-size": "0.95rem",
            "font-weight": "500",
            "text-align": "center",
            "margin": "0",
            "padding": "1rem 2rem",
            "border-radius": "0",
            "transition": "all 0.2s ease",
            "border": "none",
            "border-bottom": "3px solid transparent",
            "background-color": "transparent"
        },
        "nav-link-selected": {
            "background": "linear-gradient(135deg, rgba(102, 126, 234, 0.08) 0%, rgba(118, 75, 162, 0.08) 100%)",
            "color": "#667eea",
            "font-weight": "600",
            "border-bottom": "3px solid #667eea",
        },
    },
)

# --- Helper: AI evaluates recruiter feedback ---
def evaluate_recruiter_feedback(feedback_text):
    """AI evaluates recruiter feedback sentiment and returns score 0–100."""
    if not feedback_text.strip():
        return 0

    client = get_openrouter_client()
    prompt = f"""
You are an HR evaluator AI.
Rate the recruiter feedback below from 0–100 based on its positivity and hiring confidence.

Guidelines:
- 90–100: Excellent candidate, very positive feedback
- 70–89: Positive, likely fit
- 50–69: Neutral feedback
- 30–49: Concerns present
- 0–29: Negative, poor fit

Return only:
Score: <number>

Recruiter Feedback:
{feedback_text}
"""

    try:
        response = call_api_with_retry(
            client,
            model=_get_model_name(),
            messages=[
                {"role": "system", "content": "You are an HR evaluator AI."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.2,
        )
        output = response.choices[0].message.content.strip()
        match = re.search(r"Score\s*:\s*(\d{1,3})", output)
        score = int(match.group(1)) if match else 50
    except Exception as e:
        st.warning(f"AI Evaluation failed: {e}")
        score = 50

    return min(max(score, 0), 100)


# ========================================
# SECTION 1: JOB MANAGEMENT
# ========================================
if selected == "Job Management":
    st.markdown("<h2 style='text-align:center;color:#111827;font-weight:600;'>Job Position Management</h2>", unsafe_allow_html=True)

    st.markdown("### Add or Update Job Position")

    col1, col2, col3 = st.columns([1, 1, 2])

    with col1:
        job_position = st.text_input("Job Position", placeholder="e.g., Business Analyst")
    
    with col2:
        job_id = st.text_input("Job ID (Kalibrr)", placeholder="e.g., 261105")

    with col3:
        job_description = st.text_area("Job Description", height=200, placeholder="Paste job description here...")

    if st.button("Save Job Position", type="primary"):
        if not job_position.strip() or not job_description.strip():
            st.warning("Please provide both Job Position and Job Description.")
        elif not job_id.strip():
            st.warning("Please provide Job ID from Kalibrr.")
        else:
            # Check if job position already exists
            existing_jobs = load_job_positions_from_github()
            if existing_jobs is not None and not existing_jobs.empty:
                existing_positions = existing_jobs[existing_jobs['Job Position'].str.lower() == job_position.strip().lower()]
                
                # Check if exists and is NOT pooled
                active_duplicates = existing_positions[existing_positions.get('Pooling Status', '') != 'Pooled']
                
                if not active_duplicates.empty:
                    # Duplicate exists and is active (not pooled)
                    st.error(f"⚠️ Job position '{job_position}' already exists and is active! Created on: {active_duplicates.iloc[0]['Date Created']}")
                    st.info("Please use a different name or edit the existing position.")
                elif not existing_positions.empty:
                    # Duplicate exists but is pooled - allow merging with confirmation
                    st.warning(f"ℹ️ Job position '{job_position}' exists in pooling (created on: {existing_positions.iloc[0]['Date Created']})")
                    st.info("✅ New position will be added. Old pooled position will remain in pooling for reference.")
                    
                    new_job = pd.DataFrame([{
                        "Job ID": job_id.strip(),
                        "Job Position": job_position.strip(),
                        "Job Description": job_description.strip(),
                        "Date Created": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    }])

                    if save_job_positions_to_github(new_job):
                        st.success(f"Job position '{job_position}' saved successfully! Old pooled version preserved.")
                        time.sleep(1)
                        st.rerun()
                else:
                    # No duplicate found
                    new_job = pd.DataFrame([{
                        "Job ID": job_id.strip(),
                        "Job Position": job_position.strip(),
                        "Job Description": job_description.strip(),
                        "Date Created": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    }])

                    if save_job_positions_to_github(new_job):
                        st.success(f"Job position '{job_position}' saved successfully!")
                        time.sleep(1)
                        st.rerun()
            else:
                new_job = pd.DataFrame([{
                    "Job ID": job_id.strip(),
                    "Job Position": job_position.strip(),
                    "Job Description": job_description.strip(),
                    "Date Created": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }])

                if save_job_positions_to_github(new_job):
                    st.success(f"Job position '{job_position}' saved successfully!")
                    time.sleep(1)
                    st.rerun()

    st.markdown("---")
    st.markdown("### All Job Positions")

    # Load and display all job positions
    jobs_df = load_job_positions_from_github()

    if jobs_df is not None and not jobs_df.empty:
        # Ensure Pooling Status column exists
        if "Pooling Status" not in jobs_df.columns:
            jobs_df["Pooling Status"] = ""
        
        # Display each job position with edit, delete, and pooling buttons
        for idx, row in jobs_df.iterrows():
            pooling_status = row.get('Pooling Status', '')
            is_pooled = pooling_status == "Pooled"
            job_id = row.get('Job ID', 'N/A')
            
            # Show pooling indicator in expander title
            title_prefix = "[Pooled] " if is_pooled else ""
            with st.expander(f"{title_prefix}{row['Job Position']}", expanded=False):
                col_info1, col_info2 = st.columns(2)
                with col_info1:
                    st.markdown(f"**Date Created:** {row['Date Created']}")
                    last_modified = row.get('Last Modified', '')
                    if last_modified and last_modified != '':
                        st.markdown(f"**Last Modified:** {last_modified}")
                with col_info2:
                    st.markdown(f"**Job ID:** `{job_id}`")
                if is_pooled:
                    st.markdown("**Status:** **In Pooling** (Not visible in Dashboard)")
                st.markdown("**Job Description:**")
                st.text_area("Job Description", value=row['Job Description'], height=150, disabled=True, key=f"view_desc_{idx}", label_visibility="collapsed")

                col1, col2, col3 = st.columns([1, 1, 1])

                with col1:
                    if st.button(f"Edit", key=f"edit_{idx}", type="secondary", use_container_width=True):
                        st.session_state[f"editing_{idx}"] = True
                        st.rerun()

                with col2:
                    if st.button(f"Delete", key=f"delete_{idx}", type="secondary", use_container_width=True):
                        if delete_job_position_from_github(row['Job Position']):
                            st.success(f"Job position '{row['Job Position']}' deleted successfully!")
                            time.sleep(1)
                            st.rerun()
                        else:
                            st.error("Failed to delete job position")
                
                with col3:
                    # Pooling toggle button
                    if is_pooled:
                        if st.button(f"Unpool", key=f"unpool_{idx}", type="primary", use_container_width=True):
                            from modules.github_utils import toggle_job_pooling_status
                            if toggle_job_pooling_status(row['Job Position'], ""):
                                st.success(f"Position '{row['Job Position']}' removed from pooling!")
                                time.sleep(1)
                                st.rerun()
                            else:
                                st.error("Failed to update pooling status")
                    else:
                        if st.button(f"Pool", key=f"pool_{idx}", use_container_width=True):
                            from modules.github_utils import toggle_job_pooling_status
                            if toggle_job_pooling_status(row['Job Position'], "Pooled"):
                                st.success(f"Position '{row['Job Position']}' moved to pooling!")
                                time.sleep(1)
                                st.rerun()
                            else:
                                st.error("Failed to update pooling status")

                # Edit form (shown when edit button is clicked)
                if st.session_state.get(f"editing_{idx}", False):
                    st.markdown("---")
                    st.markdown("#### Edit Job Position")

                    edit_col1, edit_col2 = st.columns([1, 1])
                    
                    with edit_col1:
                        edit_job_position = st.text_input(
                            "Job Position",
                            value=row['Job Position'],
                            key=f"edit_pos_{idx}"
                        )
                    
                    with edit_col2:
                        edit_job_id = st.text_input(
                            "Job ID (Kalibrr)",
                            value=row.get('Job ID', ''),
                            key=f"edit_id_{idx}"
                        )
                    
                    edit_job_description = st.text_area(
                        "Job Description",
                        value=row['Job Description'],
                        height=200,
                        key=f"edit_desc_{idx}"
                    )

                    col_save, col_cancel = st.columns([1, 1])

                    with col_save:
                        if st.button("Save Changes", key=f"save_{idx}", type="primary"):
                            if not edit_job_position.strip() or not edit_job_description.strip():
                                st.warning("Please provide both Job Position and Job Description.")
                            elif not edit_job_id.strip():
                                st.warning("Please provide Job ID from Kalibrr.")
                            else:
                                if update_job_position_in_github(
                                    row['Job Position'],
                                    edit_job_position.strip(),
                                    edit_job_description.strip(),
                                    edit_job_id.strip()
                                ):
                                    st.success(f"Job position updated successfully!")
                                    st.session_state[f"editing_{idx}"] = False
                                    time.sleep(1)
                                    st.rerun()
                                else:
                                    st.error("Failed to update job position")

                    with col_cancel:
                        if st.button("Cancel", key=f"cancel_{idx}"):
                            st.session_state[f"editing_{idx}"] = False
                            st.rerun()
    else:
        st.info("ℹ️ No job positions saved yet. Add your first job position above!")


# ========================================
# SECTION 2: SCREENING
# ========================================
elif selected == "Screening":
    st.markdown("<h2 style='text-align:center;color:#0b3d91;'>Candidate Screening</h2>", unsafe_allow_html=True)

    # Initialize session state for screening steps
    if 'screening_step' not in st.session_state:
        st.session_state.screening_step = 1
    if 'screening_selected_job' not in st.session_state:
        st.session_state.screening_selected_job = None
    if 'screening_data_source' not in st.session_state:
        st.session_state.screening_data_source = None
    if 'screening_data' not in st.session_state:
        st.session_state.screening_data = None

    # Load job positions
    jobs_df = load_job_positions_from_github()

    if jobs_df is None or jobs_df.empty:
        st.warning("No job positions found. Please add job positions in the Job Management section first.")
    else:
        # Ensure Pooling Status column exists
        if 'Pooling Status' not in jobs_df.columns:
            jobs_df['Pooling Status'] = ''
        
        # Filter only active (non-pooled) positions
        # Case-insensitive filter, handle null/empty values
        active_jobs_df = jobs_df[
            (jobs_df['Pooling Status'].fillna('').astype(str).str.strip().str.lower() != 'pooled')
        ].copy()
        
        pooled_count = len(jobs_df) - len(active_jobs_df)
        
        if active_jobs_df.empty:
            st.info(f"ℹ️ No active job positions available. All {len(jobs_df)} position(s) are in pooling.")
            st.info("💡 Tip: Go to Job Management to unpool positions you want to screen.")
        else:
            if pooled_count > 0:
                st.info(f"ℹ️ Showing {len(active_jobs_df)} active positions ({pooled_count} position(s) in pooling are excluded)")
            # === PROGRESS STEPPER ===
            st.markdown("""
            <div class='progress-stepper'>
                <div class='step-indicator {step1_status}'>
                    <div class='step-indicator-circle {step1_status}'>
                        {step1_icon}
                    </div>
                    <div class='step-indicator-label'>
                        <div class='step-indicator-title'>Select Position</div>
                        <div class='step-indicator-subtitle'>Choose job role</div>
                    </div>
                </div>
                <div class='step-connector {connector1_status}'></div>
                <div class='step-indicator {step2_status}'>
                    <div class='step-indicator-circle {step2_status}'>
                        {step2_icon}
                    </div>
                    <div class='step-indicator-label'>
                        <div class='step-indicator-title'>Load Data</div>
                        <div class='step-indicator-subtitle'>Import candidates</div>
                    </div>
                </div>
                <div class='step-connector {connector2_status}'></div>
                <div class='step-indicator {step3_status}'>
                    <div class='step-indicator-circle {step3_status}'>
                        {step3_icon}
                    </div>
                    <div class='step-indicator-label'>
                        <div class='step-indicator-title'>Screen & Process</div>
                        <div class='step-indicator-subtitle'>Run AI screening</div>
                    </div>
                </div>
            </div>
            """.format(
                step1_status="completed" if st.session_state.screening_step > 1 else "active" if st.session_state.screening_step == 1 else "upcoming",
                step1_icon="✓" if st.session_state.screening_step > 1 else "1",
                connector1_status="completed" if st.session_state.screening_step > 1 else "",
                step2_status="completed" if st.session_state.screening_step > 2 else "active" if st.session_state.screening_step == 2 else "upcoming",
                step2_icon="✓" if st.session_state.screening_step > 2 else "2",
                connector2_status="completed" if st.session_state.screening_step > 2 else "",
                step3_status="active" if st.session_state.screening_step == 3 else "upcoming",
                step3_icon="3"
            ), unsafe_allow_html=True)

            # === STEP 1: SELECT POSITION ===
            if st.session_state.screening_step == 1:
                st.markdown("<div class='step-card step-card-active'>", unsafe_allow_html=True)
                st.markdown("<div class='step-card-header'><div class='step-card-title'>Step 1: Select Job Position</div><div class='step-card-subtitle'>Choose the position you want to screen candidates for</div></div>", unsafe_allow_html=True)
                
                job_positions = active_jobs_df["Job Position"].tolist()
                
                # Initialize or get current selection
                if 'step1_current_job' not in st.session_state:
                    st.session_state.step1_current_job = st.session_state.screening_selected_job if st.session_state.screening_selected_job else job_positions[0]
                
                selected_job = st.selectbox(
                    "Job Position",
                    job_positions,
                    key="step1_job_select",
                    index=job_positions.index(st.session_state.step1_current_job) if st.session_state.step1_current_job in job_positions else 0
                )
                
                # Update current job when selection changes
                if selected_job != st.session_state.step1_current_job:
                    st.session_state.step1_current_job = selected_job

                if selected_job:
                    job_info = active_jobs_df[active_jobs_df["Job Position"] == selected_job].iloc[0]
                    
                    # Full job description
                    st.markdown("---")
                    st.markdown("**Job Description:**")
                    job_desc = job_info['Job Description']
                    st.text_area("Job Description", value=job_desc, height=300, disabled=True, label_visibility="collapsed", key=f"step1_full_desc_{selected_job}")

                st.markdown("<div class='step-actions'>", unsafe_allow_html=True)
                col1, col2 = st.columns([1, 5])
                with col2:
                    if st.button("Continue to Load Data →", type="primary", disabled=not selected_job, use_container_width=True):
                        st.session_state.screening_selected_job = selected_job
                        st.session_state.screening_step = 2
                        st.rerun()
                st.markdown("</div></div>", unsafe_allow_html=True)

            # === STEP 1 COMPLETED SUMMARY ===
            elif st.session_state.screening_step > 1:
                st.markdown("<div class='step-card step-card-completed'>", unsafe_allow_html=True)
                st.markdown(f"""
                <div class='step-summary'>
                    <div class='step-summary-content'>
                        <div class='step-summary-icon'>✓</div>
                        <div class='step-summary-text'>
                            <div class='step-summary-label'>Selected Position</div>
                            <div class='step-summary-value'>{st.session_state.screening_selected_job}</div>
                        </div>
                    </div>
                </div>
                """, unsafe_allow_html=True)
                st.markdown("</div>", unsafe_allow_html=True)

            # === STEP 2: LOAD DATA ===
            if st.session_state.screening_step == 2:
                st.markdown("<div class='step-card step-card-active'>", unsafe_allow_html=True)
                st.markdown("<div class='step-card-header'><div class='step-card-title'>Step 2: Load Candidate Data</div><div class='step-card-subtitle'>Import candidates from Google Sheets or upload files</div></div>", unsafe_allow_html=True)
                
                selected_job = st.session_state.screening_selected_job
                
                # Try to fetch from Google Sheets first
                candidates_df = fetch_candidates_from_google_sheets(selected_job)
                
                data_loaded = False
                data_source = None
                loaded_data = None
                
                if candidates_df is not None and not candidates_df.empty:
                    # Primary option: Google Sheets
                    st.success(f"✓ Found {len(candidates_df)} candidates in Google Sheets for '{selected_job}'")
                    
                    with st.expander("Preview Candidate Data", expanded=False):
                        st.dataframe(candidates_df.head(10), use_container_width=True)
                    
                    col1, col2 = st.columns([3, 1])
                    with col1:
                        st.info("Candidates loaded from Google Sheets. Click Continue to proceed with screening.")
                    with col2:
                        if st.button("Use This Data", type="primary", use_container_width=True):
                            st.session_state.screening_data_source = "Google Sheets"
                            st.session_state.screening_data = candidates_df
                            st.session_state.screening_step = 3
                            st.rerun()
                else:
                    st.info("No Google Sheets data found for this position. Please upload candidate files below.")
                
                # Alternative options (collapsed by default)
                with st.expander("📁 Or Upload Files"):
                    st.markdown("**Upload CV Files (PDF)**")
                    uploaded_cvs = st.file_uploader(
                        "Select one or more PDF files",
                        type=["pdf"],
                        accept_multiple_files=True,
                        key="step2_cv_upload",
                        help="Upload CV files in PDF format for screening"
                    )
                    
                    if uploaded_cvs:
                        st.success(f"✓ {len(uploaded_cvs)} CV file(s) selected")
                        if st.button("Use CV Files", type="primary", key="use_cv_files"):
                            st.session_state.screening_data_source = "PDF Upload"
                            st.session_state.screening_data = uploaded_cvs
                            st.session_state.screening_step = 3
                            st.rerun()
                    
                    st.markdown("---")
                    st.markdown("**Upload Candidate CSV**")
                    uploaded_csv = st.file_uploader(
                        "Select CSV file with candidate information",
                        type=["csv"],
                        key="step2_csv_upload",
                        help="CSV file with candidate data including resume links"
                    )
                    
                    if uploaded_csv:
                        csv_df = parse_candidate_csv(uploaded_csv)
                        if csv_df is not None and not csv_df.empty:
                            st.success(f"✓ {len(csv_df)} candidates loaded from CSV")
                            with st.expander("Preview CSV Data"):
                                st.dataframe(csv_df.head(10), use_container_width=True)
                            if st.button("Use CSV Data", type="primary", key="use_csv_data"):
                                st.session_state.screening_data_source = "CSV Upload"
                                st.session_state.screening_data = csv_df
                                st.session_state.screening_step = 3
                                st.rerun()

                st.markdown("<div class='step-actions'>", unsafe_allow_html=True)
                col1, col2 = st.columns([1, 5])
                with col1:
                    if st.button("← Back", use_container_width=True):
                        st.session_state.screening_step = 1
                        st.rerun()
                st.markdown("</div></div>", unsafe_allow_html=True)

            # === STEP 2 COMPLETED SUMMARY ===
            elif st.session_state.screening_step > 2:
                st.markdown("<div class='step-card step-card-completed'>", unsafe_allow_html=True)
                
                # Calculate actual new candidates after duplicate check
                data_count = 0
                if isinstance(st.session_state.screening_data, pd.DataFrame):
                    candidates_df = st.session_state.screening_data
                    selected_job = st.session_state.screening_selected_job
                    
                    # Load existing results to check for duplicates
                    position_results_file = get_results_filename(selected_job)
                    existing_results = load_results_from_github(path=position_results_file)
                    
                    existing_emails = set()
                    existing_name_phone = set()
                    existing_names = set()  # Add name-only tracking
                    
                    if existing_results is not None and not existing_results.empty:
                        # Convert to string first before using .str accessor
                        existing_emails = set(
                            existing_results[existing_results["Candidate Email"].notna()]["Candidate Email"].astype(str).str.lower()
                        )
                        for _, row in existing_results.iterrows():
                            name = row.get("Candidate Name", "")
                            phone = row.get("Phone", "")
                            # Track by name+phone
                            if pd.notna(name) and pd.notna(phone) and str(name).strip() and str(phone).strip():
                                key = f"{str(name).strip().lower()}_{str(phone).strip()}"
                                existing_name_phone.add(key)
                            # Track by name-only as fallback
                            if pd.notna(name) and str(name).strip():
                                existing_names.add(str(name).strip().lower())
                    for idx, row in candidates_df.iterrows():
                        first_name = row.get("Nama Depan") or row.get("First Name") or ""
                        last_name = row.get("Nama Belakang") or row.get("Last Name") or ""
                        candidate_name = f"{first_name} {last_name}".strip()
                        if not candidate_name:
                            candidate_name = row.get("Nama") or row.get("Candidate Name") or row.get("Name", "")
                        
                        candidate_email = row.get("Alamat Email") or row.get("Email Pelamar") or row.get("Candidate Email") or row.get("Email", "")
                        candidate_phone = row.get("Nomor Handphone") or row.get("Telp") or row.get("Phone") or row.get("Telepon", "")
                        
                        is_duplicate = False
                        if pd.notna(candidate_email) and str(candidate_email).strip():
                            if str(candidate_email).strip().lower() in existing_emails:
                                is_duplicate = True
                        elif pd.notna(candidate_name) and pd.notna(candidate_phone) and str(candidate_phone).strip():
                            # Check by name+phone
                            name_phone_key = f"{str(candidate_name).strip().lower()}_{str(candidate_phone).strip()}"
                            if name_phone_key in existing_name_phone:
                                is_duplicate = True
                        elif pd.notna(candidate_name) and str(candidate_name).strip():
                            # Fallback: check by name-only if no email and no phone
                            if str(candidate_name).strip().lower() in existing_names:
                                is_duplicate = True
                        
                        if not is_duplicate:
                            data_count += 1
                
                st.markdown(f"""
                <div class='step-summary'>
                    <div class='step-summary-content'>
                        <div class='step-summary-icon'>✓</div>
                        <div class='step-summary-text'>
                            <div class='step-summary-label'>Data Loaded ({st.session_state.screening_data_source})</div>
                            <div class='step-summary-value'>{data_count} new candidate(s)</div>
                        </div>
                    </div>
                </div>
                """, unsafe_allow_html=True)
                st.markdown("</div>", unsafe_allow_html=True)

            # === STEP 3: PROCESS & SCREEN ===
            if st.session_state.screening_step == 3:
                st.markdown("<div class='step-card step-card-active'>", unsafe_allow_html=True)
                st.markdown("<div class='step-card-header'><div class='step-card-title'>Step 3: Process & Screen Candidates</div><div class='step-card-subtitle'>Run AI screening on loaded candidates</div></div>", unsafe_allow_html=True)
                
                selected_job = st.session_state.screening_selected_job
                job_info = active_jobs_df[active_jobs_df["Job Position"] == selected_job].iloc[0]
                data_source = st.session_state.screening_data_source
                
                # Check for existing candidates to prevent duplicates
                position_results_file = get_results_filename(selected_job)
                existing_results = load_results_from_github(path=position_results_file)
                
                # Build sets for duplicate detection (by email OR by name+phone OR by name-only)
                existing_emails = set()
                existing_name_phone = set()
                existing_names = set()  # Add name-only tracking
                
                if existing_results is not None and not existing_results.empty:
                    # Track by email - convert to string first before using .str accessor
                    existing_emails = set(
                        existing_results[existing_results["Candidate Email"].notna()]["Candidate Email"].astype(str).str.lower()
                    )
                    
                    # Track by name+phone for candidates without email
                    for _, row in existing_results.iterrows():
                        name = row.get("Candidate Name", "")
                        phone = row.get("Phone", "")
                        # Track by name+phone
                        if pd.notna(name) and pd.notna(phone) and str(name).strip() and str(phone).strip():
                            key = f"{str(name).strip().lower()}_{str(phone).strip()}"
                            existing_name_phone.add(key)
                        # Track by name-only as fallback
                        if pd.notna(name) and str(name).strip():
                            existing_names.add(str(name).strip().lower())

                # Handle different data sources
                if data_source == "PDF Upload":
                    uploaded_cvs = st.session_state.screening_data
                    total_files = len(uploaded_cvs)
                    
                    st.info(f"Ready to process {total_files} CV file(s)")
                    
                    if st.button("🚀 Start Screening", type="primary", use_container_width=True):
                        progress = st.progress(0)
                        status_text = st.empty()
                        save_status = st.empty()
                        
                        successfully_saved = 0
                        failed_saves = 0
                        
                        for i, uploaded_cv in enumerate(uploaded_cvs):
                            filename = uploaded_cv.name
                            status_text.text(f"Processing {i+1}/{total_files}: {filename}")
                            
                            cv_text = extract_text_from_pdf(uploaded_cv)
                            candidate_name = ""
                            if cv_text:
                                candidate_name = extract_candidate_name_from_cv(cv_text)
                            if not candidate_name:
                                candidate_name = filename.rsplit('.', 1)[0]
                            
                            status_text.text(f"Processing {i+1}/{total_files}: {candidate_name}")
                            
                            cv_score = 0
                            summary = "No resume or information available"
                            strengths = []
                            weaknesses = []
                            gaps = []
                            
                            if cv_text.strip():
                                cv_score, summary, strengths, weaknesses, gaps = score_with_openrouter(
                                    cv_text, selected_job, job_info['Job Description']
                                )
                            
                            candidate_result = {
                                "Candidate Name": candidate_name,
                                "Candidate Email": "",
                                "Phone": "",
                                "Job Position": selected_job,
                                "Match Score": cv_score,
                                "AI Summary": summary,
                                "Strengths": ", ".join(strengths) if strengths else "",
                                "Weaknesses": ", ".join(weaknesses) if weaknesses else "",
                                "Gaps": ", ".join(gaps) if gaps else "",
                                "Latest Job Title": "",
                                "Latest Company": "",
                                "Education": "",
                                "University": "",
                                "Major": "",
                                "Kalibrr Profile": "",
                                "Application Link": "",
                                "Resume Link": f"Uploaded: {filename}",
                                "Recruiter Feedback": "",
                                "Shortlisted": False,
                                "Candidate Status": "",
                                "Interview Status": "",
                                "Rejection Reason": "",
                                "Date Processed": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                            }
                            
                            try:
                                result_df = pd.DataFrame([candidate_result])
                                if save_results_to_github(result_df, job_position=selected_job):
                                    successfully_saved += 1
                                    save_status.success(f"Saved {candidate_name} ({successfully_saved}/{i+1})")
                                    # Log successful CV processing
                                    log_cv_processing(
                                        source="streamlit",
                                        candidate_name=candidate_name,
                                        position=selected_job,
                                        success=True
                                    )
                                else:
                                    failed_saves += 1
                                    # Log failed CV processing
                                    log_cv_processing(
                                        source="streamlit",
                                        candidate_name=candidate_name,
                                        position=selected_job,
                                        success=False
                                    )
                            except Exception as e:
                                failed_saves += 1
                                # Log failed CV processing
                                log_cv_processing(
                                    source="streamlit",
                                    candidate_name=candidate_name,
                                    position=selected_job,
                                    success=False
                                )
                            
                            progress.progress((i + 1) / total_files)
                        
                        status_text.text("CV Screening completed!")
                        if successfully_saved > 0:
                            clear_results_cache()
                            st.success(f"🎉 Successfully processed {successfully_saved} CV(s)!")
                            # Reset to step 1 for next screening
                            st.session_state.screening_step = 1
                            st.session_state.screening_data = None
                        else:
                            st.error("Failed to save results. Please try again.")
                
                elif data_source in ["Google Sheets", "CSV Upload"]:
                    candidates_df = st.session_state.screening_data
                    
                    # Check for duplicates (by email OR by name+phone)
                    new_candidates = []
                    skipped_candidates = []
                    
                    for idx, row in candidates_df.iterrows():
                        # Get candidate info with proper Kalibrr column mapping
                        # Kalibrr uses "Nama Depan" and "Nama Belakang"
                        first_name = row.get("Nama Depan") or row.get("First Name") or ""
                        last_name = row.get("Nama Belakang") or row.get("Last Name") or ""
                        candidate_name = f"{first_name} {last_name}".strip()
                        if not candidate_name:
                            candidate_name = row.get("Nama") or row.get("Candidate Name") or row.get("Name", "")
                        
                        candidate_email = row.get("Alamat Email") or row.get("Email Pelamar") or row.get("Candidate Email") or row.get("Email", "")
                        candidate_phone = row.get("Nomor Handphone") or row.get("Telp") or row.get("Phone") or row.get("Telepon", "")
                        
                        # Check by email first
                        is_duplicate = False
                        if pd.notna(candidate_email) and str(candidate_email).strip():
                            if str(candidate_email).strip().lower() in existing_emails:
                                skipped_candidates.append(f"{candidate_name} ({candidate_email})")
                                is_duplicate = True
                        elif pd.notna(candidate_name) and pd.notna(candidate_phone) and str(candidate_phone).strip():
                            # Check by name+phone
                            name_phone_key = f"{str(candidate_name).strip().lower()}_{str(candidate_phone).strip()}"
                            if name_phone_key in existing_name_phone:
                                skipped_candidates.append(f"{candidate_name} ({candidate_phone})")
                                is_duplicate = True
                        elif pd.notna(candidate_name) and str(candidate_name).strip():
                            # Fallback: check by name-only if no email and no phone
                            if str(candidate_name).strip().lower() in existing_names:
                                skipped_candidates.append(f"{candidate_name} (name match)")
                                is_duplicate = True
                        
                        if not is_duplicate:
                            new_candidates.append(row)
                    
                    if skipped_candidates:
                        st.warning(f"⏩ Skipping {len(skipped_candidates)} already-analyzed candidate(s):")
                        with st.expander("View skipped candidates"):
                            for name in skipped_candidates[:20]:  # Show max 20
                                st.text(f"  • {name}")
                            if len(skipped_candidates) > 20:
                                st.text(f"  ... and {len(skipped_candidates) - 20} more")
                    
                    if new_candidates:
                        st.info(f"Ready to process {len(new_candidates)} new candidate(s)")
                        
                        if st.button("🚀 Start Screening", type="primary", use_container_width=True):
                            progress = st.progress(0)
                            status_text = st.empty()
                            save_status = st.empty()
                            
                            successfully_saved = 0
                            failed_saves = 0
                            
                            for i, row in enumerate(new_candidates):
                                # Get candidate name with proper Kalibrr column mapping
                                first_name = row.get("Nama Depan") or row.get("First Name") or ""
                                last_name = row.get("Nama Belakang") or row.get("Last Name") or ""
                                candidate_name = f"{first_name} {last_name}".strip()
                                if not candidate_name:
                                    candidate_name = row.get("Nama") or row.get("Candidate Name") or row.get("Name", "Unknown")
                                
                                status_text.text(f"Processing {i+1}/{len(new_candidates)}: {candidate_name}")
                                
                                # Get resume link
                                resume_link = row.get("Link Resume") or row.get("Tautan Resume") or row.get("Resume Link") or row.get("Resume", "")
                                cv_text = ""
                                if pd.notna(resume_link) and str(resume_link).strip():
                                    cv_text = extract_resume_from_url(resume_link)
                                
                                cv_score = 0
                                summary = "No resume available"
                                strengths = []
                                weaknesses = []
                                gaps = []
                                candidate_info = {
                                    "latest_job_title": "",
                                    "latest_company": "",
                                    "education": "",
                                    "university": "",
                                    "major": ""
                                }
                                
                                if cv_text.strip():
                                    # Extract score and evaluation
                                    cv_score, summary, strengths, weaknesses, gaps = score_with_openrouter(
                                        cv_text, selected_job, job_info['Job Description']
                                    )
                                    # Extract candidate info from CV
                                    candidate_info = extract_candidate_info_from_cv(cv_text)
                                
                                candidate_result = {
                                    "Candidate Name": candidate_name,
                                    "Candidate Email": row.get("Alamat Email") or row.get("Candidate Email") or row.get("Email", ""),
                                    "Phone": row.get("Nomor Handphone") or row.get("Phone") or row.get("Telepon", ""),
                                    "Job Position": selected_job,
                                    "Match Score": cv_score,
                                    "AI Summary": summary,
                                    "Strengths": ", ".join(strengths) if strengths else "",
                                    "Weaknesses": ", ".join(weaknesses) if weaknesses else "",
                                    "Gaps": ", ".join(gaps) if gaps else "",
                                    "Latest Job Title": candidate_info.get("latest_job_title") or row.get("Jabatan Terakhir") or row.get("Latest Job Title") or "",
                                    "Latest Company": candidate_info.get("latest_company") or row.get("Perusahaan Terakhir") or row.get("Latest Company") or "",
                                    "Education": candidate_info.get("education") or row.get("Tingkat Pendidikan") or row.get("Education") or "",
                                    "University": candidate_info.get("university") or row.get("Universitas") or row.get("University") or "",
                                    "Major": candidate_info.get("major") or row.get("Jurusan") or row.get("Major") or "",
                                    "Kalibrr Profile": row.get("Link Profil Kalibrr") or row.get("Kalibrr Profile") or row.get("Profile", ""),
                                    "Application Link": row.get("Link Aplikasi Pekerjaan") or row.get("Application Link") or row.get("Application", ""),
                                    "Resume Link": resume_link,
                                    "Recruiter Feedback": "",
                                    "Shortlisted": False,
                                    "Candidate Status": "",
                                    "Interview Status": "",
                                    "Rejection Reason": "",
                                    "Date Processed": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                                }
                                
                                try:
                                    result_df = pd.DataFrame([candidate_result])
                                    if save_results_to_github(result_df, job_position=selected_job):
                                        successfully_saved += 1
                                        save_status.success(f"Saved {candidate_name} ({successfully_saved}/{i+1})")
                                        # Log successful CV processing
                                        log_cv_processing(
                                            source="streamlit",
                                            candidate_name=candidate_name,
                                            position=selected_job,
                                            success=True
                                        )
                                    else:
                                        failed_saves += 1
                                        # Log failed CV processing
                                        log_cv_processing(
                                            source="streamlit",
                                            candidate_name=candidate_name,
                                            position=selected_job,
                                            success=False
                                        )
                                except Exception as e:
                                    failed_saves += 1
                                    # Log failed CV processing
                                    log_cv_processing(
                                        source="streamlit",
                                        candidate_name=candidate_name,
                                        position=selected_job,
                                        success=False
                                    )
                                
                                progress.progress((i + 1) / len(new_candidates))
                            
                            status_text.text("Screening completed!")
                            if successfully_saved > 0:
                                clear_results_cache()
                                st.success(f"🎉 Successfully processed {successfully_saved} candidate(s)!")
                                st.session_state.screening_step = 1
                                st.session_state.screening_data = None
                            else:
                                st.error("Failed to save results. Please try again.")
                    else:
                        st.info("ℹ️ All candidates have already been processed for this position.")

                st.markdown("<div class='step-actions'>", unsafe_allow_html=True)
                col1, col2 = st.columns([1, 5])
                with col1:
                    if st.button("← Back to Data Loading", use_container_width=True):
                        st.session_state.screening_step = 2
                        st.rerun()
                st.markdown("</div></div>", unsafe_allow_html=True)

# ========================================
# SECTION 3: DASHBOARD
# ========================================
elif selected == "Dashboard":
    st.markdown("<h2 style='text-align:center;color:#0b3d91;'>Screening Dashboard</h2>", unsafe_allow_html=True)

    # Load job positions for the dropdown (lightweight - only loads job_positions.csv)
    jobs_df = load_job_positions_from_github()

    # Check if we have any job positions
    if jobs_df is None or jobs_df.empty or "Job Position" not in jobs_df.columns:
        st.info("ℹ️ No job positions available. Please add job positions in the Job Management section first.")
        st.stop()
    
    # Ensure Pooling Status column exists
    if "Pooling Status" not in jobs_df.columns:
        jobs_df["Pooling Status"] = ""
    
    # Filter out pooled positions (they should only appear in Pooling tab)
    jobs_df_active = jobs_df[jobs_df["Pooling Status"] != "Pooled"]

    # Get list of active (non-pooled) job positions
    job_positions = jobs_df_active["Job Position"].tolist()
    
    if not job_positions:
        st.info("ℹ️ No active job positions available. All positions are in pooling. Check the Pooling tab or add new positions in Job Management.")
        st.stop()
    
    selected_job = st.selectbox("Pilih posisi untuk melihat hasil screening", job_positions)
    
    # Load results only for the selected position (efficient - loads single file)
    df = load_results_for_position(selected_job)
    
    # Check for errors (None means authentication/connection error)
    if df is None:
        st.error("Failed to load results from GitHub. Please check your GitHub token, repository access, and network connection.")
        st.stop()

    # Check if we have any data for this position
    if df.empty:
        st.info(f"ℹ️ No screening results yet for '{selected_job}'. Please run a screening first from the 'Screening' section.")
        st.stop()

    # Data loaded successfully
    st.session_state["results"] = df

    # Ensure columns exist
    for col in ["Recruiter Feedback", "Strengths", "Weaknesses", "Gaps", "AI Summary", "Shortlisted", "Candidate Status", "Interview Status", "Rejection Reason"]:
        if col not in df.columns:
            if col == "Shortlisted":
                df[col] = False
            elif col in ["Candidate Status", "Interview Status", "Rejection Reason"]:
                df[col] = ""
            else:
                df[col] = ""
    
    # Clean up Shortlisted column - ensure it only contains boolean values
    if "Shortlisted" in df.columns:
        df["Shortlisted"] = df["Shortlisted"].astype(str).str.strip().str.lower().isin(['true', '1'])
    
    # Clean up Candidate Status column - ensure valid values only
    if "Candidate Status" in df.columns:
        df["Candidate Status"] = df["Candidate Status"].fillna("").astype(str)
        df.loc[~df["Candidate Status"].isin(["", "OK", "Rejected"]), "Candidate Status"] = ""
    
    # Clean up Interview Status column - ensure valid values only
    if "Interview Status" in df.columns:
        df["Interview Status"] = df["Interview Status"].fillna("").astype(str)
        df.loc[~df["Interview Status"].isin(["", "Lanjut", "Rejected"]), "Interview Status"] = ""

    # Convert numeric columns
    numeric_cols = ["Match Score"]
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    # Store the full dataframe for statistics
    df_full = df.copy()
    
    # --- Overview Statistics (at top) ---
    st.markdown("### Overview Statistics")
    avg_score = int(df_full["Match Score"].mean())
    top_score = int(df_full["Match Score"].max())
    total_candidates = len(df_full)
    pending_count = len(df_full[df_full["Candidate Status"] == ""])
    ok_count = len(df_full[(df_full["Candidate Status"] == "OK") & (df_full["Interview Status"] == "")])
    ok_passed_count = len(df_full[(df_full["Candidate Status"] == "OK") & (df_full["Interview Status"] == "Lanjut")])
    rejected_count = len(df_full[df_full["Candidate Status"] == "Rejected"])
    ok_rejected_count = len(df_full[(df_full["Candidate Status"] == "OK") & (df_full["Interview Status"] == "Rejected")])

    metric_col1, metric_col2, metric_col3 = st.columns(3)
    metric_col1.metric("Average Score", avg_score)
    metric_col2.metric("Top Score", top_score)
    metric_col3.metric("Total Candidates", total_candidates)
    
    st.markdown("### Status Breakdown")
    breakdown_col1, breakdown_col2, breakdown_col3, breakdown_col4, breakdown_col5 = st.columns(5)
    breakdown_col1.metric("Pending", pending_count)
    breakdown_col2.metric("OK", ok_count)
    breakdown_col3.metric("OK-Passed", ok_passed_count)
    breakdown_col4.metric("Rejected", rejected_count)
    breakdown_col5.metric("OK-Rejected", ok_rejected_count)

    st.divider()
    
    # --- Filter & Search Section ---
    st.markdown("### Filter & Search")
    
    filter_col1, filter_col2, filter_col3 = st.columns(3)
    
    with filter_col1:
        # Status filter
        status_options = ["All Status", "Pending", "OK", "OK-Passed", "Rejected", "OK-Rejected"]
        selected_status_filter = st.selectbox("Filter by Status", status_options, key="dashboard_status_filter")
    
    with filter_col2:
        # Score filter
        score_options = ["All Scores", "High (>80)", "Medium (50-80)", "Low (<50)"]
        selected_score_filter = st.selectbox("Filter by Score", score_options, key="dashboard_score_filter")
    
    with filter_col3:
        # Sort options
        sort_options = ["Score (High to Low)", "Score (Low to High)", "Name (A-Z)", "Name (Z-A)"]
        selected_sort = st.selectbox("Sort by", sort_options, key="dashboard_sort")
    
    # Search box
    search_query = st.text_input("Search by Name or Email", placeholder="Type to search...", key="dashboard_search")
    
    st.divider()
    
    # Apply filters
    df_filtered = df_full.copy()
    
    # Status filter
    if selected_status_filter != "All Status":
        if selected_status_filter == "Pending":
            df_filtered = df_filtered[df_filtered["Candidate Status"] == ""]
        elif selected_status_filter == "OK":
            df_filtered = df_filtered[
                (df_filtered["Candidate Status"] == "OK") & 
                (df_filtered["Interview Status"] == "")
            ]
        elif selected_status_filter == "OK-Passed":
            df_filtered = df_filtered[
                (df_filtered["Candidate Status"] == "OK") & 
                (df_filtered["Interview Status"] == "Lanjut")
            ]
        elif selected_status_filter == "Rejected":
            df_filtered = df_filtered[df_filtered["Candidate Status"] == "Rejected"]
        elif selected_status_filter == "OK-Rejected":
            df_filtered = df_filtered[
                (df_filtered["Candidate Status"] == "OK") & 
                (df_filtered["Interview Status"] == "Rejected")
            ]
    
    # Score filter
    if selected_score_filter != "All Scores":
        if selected_score_filter == "High (>80)":
            df_filtered = df_filtered[df_filtered["Match Score"] > 80]
        elif selected_score_filter == "Medium (50-80)":
            df_filtered = df_filtered[(df_filtered["Match Score"] >= 50) & (df_filtered["Match Score"] <= 80)]
        elif selected_score_filter == "Low (<50)":
            df_filtered = df_filtered[df_filtered["Match Score"] < 50]
    
    # Search filter
    if search_query:
        df_filtered = df_filtered[
            df_filtered["Candidate Name"].fillna("").str.contains(search_query, case=False, na=False) |
            df_filtered["Candidate Email"].fillna("").str.contains(search_query, case=False, na=False)
        ]
    
    # Apply sorting
    if selected_sort == "Score (High to Low)":
        df_filtered = df_filtered.sort_values(by="Match Score", ascending=False)
    elif selected_sort == "Score (Low to High)":
        df_filtered = df_filtered.sort_values(by="Match Score", ascending=True)
    elif selected_sort == "Name (A-Z)":
        df_filtered = df_filtered.sort_values(by="Candidate Name", ascending=True)
    elif selected_sort == "Name (Z-A)":
        df_filtered = df_filtered.sort_values(by="Candidate Name", ascending=False)
    
    df_filtered = df_filtered.reset_index(drop=True)
    df_sorted = df_filtered

    # Show message if no candidates match filter
    if df_filtered.empty:
        st.info(f"No candidates found matching the selected filters.")
        st.stop()

    # Helper function to sanitize keys for Streamlit widgets
    def sanitize_key(text):
        """Remove special characters from text to create safe widget keys."""
        import re
        if not text:
            return ""
        return re.sub(r'[^a-zA-Z0-9_]', '_', str(text))
    
    # Helper function to get candidate status display information
    def get_status_display_info(candidate_status, interview_status, rejection_reason, candidate_name, score):
        """Generate status display information for a candidate.
        
        Returns:
            tuple: (status_color, display_html) where status_color is the hex color or None,
                   and display_html is the HTML string to display.
        """
        if candidate_status == "OK" and interview_status == "Rejected":
            # Red font color for rejected in interview
            status_color = "#dc3545"
            reason_text = f" - {rejection_reason}" if rejection_reason else ""
            display_html = f'<p style="color: {status_color}; font-weight: bold; margin-bottom: 0;">{candidate_name} - Score: {score} - OK-Rejected{reason_text}</p>'
        elif candidate_status == "OK":
            # Green font color for OK status (no interview rejection)
            status_color = "#28a745"
            display_html = f'<p style="color: {status_color}; font-weight: bold; margin-bottom: 0;">{candidate_name} - Score: {score} - OK</p>'
        elif candidate_status == "Rejected":
            # Red font color for Rejected status
            status_color = "#dc3545"
            reason_text = f" - {rejection_reason}" if rejection_reason else ""
            display_html = f'<p style="color: {status_color}; font-weight: bold; margin-bottom: 0;">{candidate_name} - Score: {score} - Rejected{reason_text}</p>'
        else:
            # Default for pending review (no color change)
            status_color = None
            display_html = f'{candidate_name} - Score: {score}'
        
        return status_color, display_html
    
    # Helper function to update candidate status in the full dataframe
    def update_candidate_status_in_df(df_to_update, candidate_email_val, candidate_name_val, new_status, new_shortlisted, job_position, rejection_reason="", interview_status=""):
        """Update candidate status in dataframe and save to GitHub.
        
        Uses email + job position as primary identifier, falls back to name + job position.
        """
        mask = None
        if pd.notna(candidate_email_val) and str(candidate_email_val).strip():
            # Use email + job position for precise matching
            mask = (df_to_update["Candidate Email"] == candidate_email_val) & (df_to_update["Job Position"] == job_position)
        else:
            # Fall back to name + job position
            mask = (df_to_update["Candidate Name"] == candidate_name_val) & (df_to_update["Job Position"] == job_position)
        
        if mask is not None and mask.any():
            df_to_update.loc[mask, "Candidate Status"] = new_status
            df_to_update.loc[mask, "Shortlisted"] = new_shortlisted
            df_to_update.loc[mask, "Rejection Reason"] = rejection_reason
            df_to_update.loc[mask, "Interview Status"] = interview_status
            return update_results_in_github(df_to_update, job_position=job_position)
        return False

    # --- Display candidates with expanders ---
    st.markdown(f"**Showing {len(df_filtered)} candidate(s)**")

    for idx, row in df_sorted.iterrows():
        # Handle NaN values properly for candidate name
        candidate_name = row.get("Candidate Name")
        if pd.isna(candidate_name) or not str(candidate_name).strip() or str(candidate_name).strip() == "nan":
            # Try to use email as identifier
            email = row.get("Candidate Email")
            if pd.notna(email) and str(email).strip() and str(email).strip() != "nan":
                candidate_name = str(email).split("@")[0]
            else:
                # Check if there's a Filename column as fallback
                candidate_name = row.get("Filename")
                if pd.isna(candidate_name) or not str(candidate_name).strip():
                    candidate_name = f"Candidate {idx + 1}"

        score = row.get("Match Score", 0)
        
        # Get candidate status for display in expander title
        candidate_status = row.get("Candidate Status", "") if pd.notna(row.get("Candidate Status")) else ""
        interview_status = row.get("Interview Status", "") if pd.notna(row.get("Interview Status")) else ""
        rejection_reason = row.get("Rejection Reason", "") if pd.notna(row.get("Rejection Reason")) else ""
        
        # Get status display information using helper function
        status_color, display_html = get_status_display_info(
            candidate_status, interview_status, rejection_reason, candidate_name, score
        )

        # Display colored text label using markdown, then expander
        if status_color:
            st.markdown(display_html, unsafe_allow_html=True)
        else:
            st.markdown(display_html)
        
        # Display candidate details in expander (no checkbox)
        with st.expander("View Details", expanded=False):
            # Helper function to get non-NaN value
            def get_value(key, default='N/A'):
                val = row.get(key, default)
                return val if pd.notna(val) and str(val).strip() else default

            # --- Score Badge + Info (Card Style) ---
            score_val = int(row.get('Match Score', 0))

            # Score badge using st.columns (no raw HTML)
            badge_col, info_col = st.columns([1, 5])
            with badge_col:
                if score_val >= 70:
                    st.success(f"Score: **{score_val}**")
                elif score_val >= 50:
                    st.warning(f"Score: **{score_val}**")
                else:
                    st.error(f"Score: **{score_val}**")

            with info_col:
                # Row 1: Contact
                contact_parts = []
                if "Candidate Email" in row:
                    email_val = get_value('Candidate Email')
                    phone_val = get_value('Phone')
                    if email_val != 'N/A':
                        contact_parts.append(f"**Email:** {email_val}")
                    if phone_val != 'N/A':
                        contact_parts.append(f"**Phone:** {phone_val}")
                if contact_parts:
                    st.markdown(" · ".join(contact_parts))

                # Row 2: Job + Company
                st.markdown(f"**Job:** {get_value('Latest Job Title')} · **Company:** {get_value('Latest Company')}")

                # Row 3: Education
                st.markdown(f"**Education:** {get_value('Education')} · **University:** {get_value('University')}")

            # --- Evaluation: Strengths | Weaknesses | Gaps (3 columns) ---
            st.markdown("---")
            eval_col1, eval_col2, eval_col3 = st.columns(3)

            with eval_col1:
                st.markdown("**Strengths**")
                strengths = str(row.get("Strengths", "")) if pd.notna(row.get("Strengths")) else ""
                if strengths and strengths.strip():
                    for s in re.split(r'\.[;,]\s+', strengths.strip()):
                        if s.strip():
                            st.markdown(f"- {s.strip().rstrip('.')}")
                else:
                    st.caption("—")

            with eval_col2:
                st.markdown("**Weaknesses**")
                weaknesses = str(row.get("Weaknesses", "")) if pd.notna(row.get("Weaknesses")) else ""
                if weaknesses and weaknesses.strip():
                    for w in re.split(r'\.[;,]\s+', weaknesses.strip()):
                        if w.strip():
                            st.markdown(f"- {w.strip().rstrip('.')}")
                else:
                    st.caption("—")

            with eval_col3:
                st.markdown("**Gaps**")
                gaps = str(row.get("Gaps", "")) if pd.notna(row.get("Gaps")) else ""
                if gaps and gaps.strip():
                    for g in re.split(r'\.[;,]\s+', gaps.strip()):
                        if g.strip():
                            st.markdown(f"- {g.strip().rstrip('.')}")
                else:
                    st.caption("—")

            # --- Summary ---
            ai_summary = row.get("AI Summary")
            if pd.notna(ai_summary) and str(ai_summary).strip():
                st.markdown("---")
                st.markdown(f"**Summary:** {ai_summary}")

            # --- Links ---
            kalibrr_profile = row.get("Kalibrr Profile")
            application_link = row.get("Application Link")
            resume_link = row.get("Resume Link")

            has_links = (
                (pd.notna(kalibrr_profile) and str(kalibrr_profile).strip()) or
                (pd.notna(application_link) and str(application_link).strip()) or
                (pd.notna(resume_link) and str(resume_link).strip())
            )

            if has_links:
                st.markdown("---")
                links_parts = []
                if pd.notna(kalibrr_profile) and str(kalibrr_profile).strip():
                    links_parts.append(f"[Kalibrr Profile]({kalibrr_profile})")
                if pd.notna(application_link) and str(application_link).strip():
                    links_parts.append(f"[Application]({application_link})")
                if pd.notna(resume_link) and str(resume_link).strip():
                    links_parts.append(f"[Resume/CV]({resume_link})")
                st.markdown(" · ".join(links_parts))

            # --- Candidate Status Section ---
            st.markdown("---")
            current_status = row.get("Candidate Status", "")
            if pd.isna(current_status):
                current_status = ""
            
            # Get current interview status
            current_interview_status = row.get("Interview Status", "")
            if pd.isna(current_interview_status):
                current_interview_status = ""
            
            # Get current rejection reason
            current_rejection_reason = row.get("Rejection Reason", "")
            if pd.isna(current_rejection_reason):
                current_rejection_reason = ""
            
            # Create unique key using sanitized candidate email or name + index
            candidate_email = row.get("Candidate Email", "")
            email_key = sanitize_key(candidate_email) if pd.notna(candidate_email) and str(candidate_email).strip() else ""
            name_key = sanitize_key(candidate_name)
            unique_key = f"{email_key}_{idx}" if email_key else f"{name_key}_{idx}"
            
            # Stage 1: Initial CV Screening (OK / Reject)
            if current_status == "":
                st.info("Status: Pending Review")
                
                btn_col1, btn_col2, btn_col3 = st.columns(3)
                
                with btn_col1:
                    # OK button - for initial CV screening approval
                    if st.button("OK", key=f"ok_{unique_key}", type="primary", use_container_width=True):
                        with st.spinner("Saving status..."):
                            if update_candidate_status_in_df(df_full, candidate_email, candidate_name, "OK", True, selected_job, "", ""):
                                clear_results_cache()
                                st.success(f"{candidate_name} passed CV screening!")
                                time.sleep(0.5)
                                st.rerun()
                            else:
                                st.error("Failed to save status")
                
                with btn_col2:
                    # Initial Reject button
                    if st.button("Reject", key=f"reject_initial_{unique_key}", type="secondary", use_container_width=True):
                        with st.spinner("Saving status..."):
                            if update_candidate_status_in_df(df_full, candidate_email, candidate_name, "Rejected", False, selected_job, REJECTION_REASON_CV_SCREENING, ""):
                                clear_results_cache()
                                st.success(f"{candidate_name} did not pass CV screening")
                                time.sleep(0.5)
                                st.rerun()
                            else:
                                st.error("Failed to save status")
            
            # Stage 2: Show OK status and interview options
            elif current_status == "OK" and current_interview_status == "":
                st.success("Status: OK (Passed CV Screening)")
                
                st.markdown("**Interview Result:**")
                
                # Pass Interview button
                if st.button("Pass Interview", key=f"lanjut_{unique_key}", type="primary", use_container_width=True):
                    with st.spinner("Saving status..."):
                        if update_candidate_status_in_df(df_full, candidate_email, candidate_name, "OK", True, selected_job, "", "Lanjut"):
                            clear_results_cache()
                            st.success(f"{candidate_name} passed interview!")
                            time.sleep(0.5)
                            st.rerun()
                        else:
                            st.error("Failed to save status")
                
                st.markdown("---")
                st.markdown("**Or Reject with Reason:**")
                
                # Rejection reason form - always visible
                selected_rejection_reason = st.selectbox(
                    "Select rejection reason",
                    options=["-- Select reason --"] + REJECTION_REASONS,
                    key=f"reason_{unique_key}",
                    index=0
                )
                
                if st.button("Submit Rejection", key=f"submit_reject_{unique_key}", type="secondary", disabled=(selected_rejection_reason == "-- Select reason --"), use_container_width=True):
                    with st.spinner("Saving status..."):
                        if update_candidate_status_in_df(df_full, candidate_email, candidate_name, "OK", False, selected_job, selected_rejection_reason, "Rejected"):
                            clear_results_cache()
                            st.success(f"{candidate_name} did not pass interview! Reason: {selected_rejection_reason}")
                            time.sleep(0.5)
                            st.rerun()
                        else:
                            st.error("Failed to save status")
            
            # Stage 3: Show final status for completed candidates
            elif current_status == "Rejected":
                rejection_display = f" - Reason: {current_rejection_reason}" if current_rejection_reason else ""
                st.error(f"Status: Rejected{rejection_display}")
            
            elif current_status == "OK" and current_interview_status == "Lanjut":
                st.success("Status: OK - Passed Interview")
            
            elif current_status == "OK" and current_interview_status == "Rejected":
                rejection_display = f" - Reason: {current_rejection_reason}" if current_rejection_reason else ""
                st.error(f"Status: OK - Rejected at Interview{rejection_display}")
            
            # Reset button - available after any status is set
            if current_status:
                st.markdown("---")
                if st.button("Reset Status", key=f"reset_{unique_key}", use_container_width=False):
                    with st.spinner("Mereset status..."):
                        if update_candidate_status_in_df(df_full, candidate_email, candidate_name, "", False, selected_job, "", ""):
                            clear_results_cache()
                            st.info(f"{candidate_name} status direset")
                            time.sleep(0.5)
                            st.rerun()
                        else:
                            st.error("Gagal mereset status")

    st.divider()

    # --- Summary Table ---
    st.subheader("Summary Table")

    # Create a display dataframe with cleaned values
    df_display = df_sorted.copy()

    # Replace NaN values with appropriate defaults for display
    if "Candidate Name" in df_display.columns:
        def get_display_name(row):
            name = row.get("Candidate Name")
            if pd.isna(name) or not str(name).strip() or str(name).strip() == "nan":
                # Try email as fallback
                email = row.get("Candidate Email")
                if pd.notna(email) and str(email).strip() and str(email).strip() != "nan":
                    return str(email).split("@")[0]
                # Final fallback to index
                return f"Candidate {row.name + 1}"
            return str(name)

        df_display["Candidate Name"] = df_display.apply(get_display_name, axis=1)

    # Select key columns for display
    display_cols = ["Candidate Name" if "Candidate Name" in df_display.columns else "Filename",
                   "Job Position", "Match Score", "Candidate Status", "Interview Status", "Rejection Reason"]

    # Add optional columns if they exist
    optional_cols = ["Latest Job Title", "Education"]
    for col in optional_cols:
        if col in df_display.columns:
            display_cols.append(col)

    st.dataframe(
        df_display[display_cols],
        use_container_width=True
    )

# ============================================
# POOLING TAB - ARCHIVED CANDIDATES
# ============================================
elif selected == "Pooling":
    st.markdown("<h2 style='text-align:center;color:#0b3d91;'>Position Pooling</h2>", unsafe_allow_html=True)
    
    # Load job positions
    jobs_df = load_job_positions_from_github()

    if jobs_df is None or jobs_df.empty or "Job Position" not in jobs_df.columns:
        st.info("No job positions available.")
        st.stop()
    
    # Ensure Pooling Status column exists
    if "Pooling Status" not in jobs_df.columns:
        jobs_df["Pooling Status"] = ""
    
    # Filter only pooled positions
    jobs_df_pooled = jobs_df[jobs_df["Pooling Status"] == "Pooled"]

    # Get list of pooled job positions
    job_positions = jobs_df_pooled["Job Position"].tolist()
    
    if not job_positions:
        st.info("No positions in pooling yet. Move positions to pooling from the Job Management section.")
        st.stop()
    
    st.markdown("**Select Position:**")
    selected_job = st.selectbox("Select Position", job_positions, label_visibility="collapsed")
    
    # Load results for the selected position
    df_pooled = load_results_for_position(selected_job)
    
    # Check for errors
    if df_pooled is None:
        st.error("Failed to load results from GitHub.")
        st.stop()
    
    if df_pooled.empty:
        st.info(f"ℹ️ Belum ada kandidat untuk posisi '{selected_job}'.")
        st.stop()
    
    st.session_state["pooling_results"] = df_pooled
    
    # Ensure required columns exist
    for col in ["Strengths", "Weaknesses", "Gaps", "AI Summary", "Candidate Status", "Interview Status", "Rejection Reason"]:
        if col not in df_pooled.columns:
            df_pooled[col] = ""
    
    # Convert numeric columns
    if "Match Score" in df_pooled.columns:
        df_pooled["Match Score"] = pd.to_numeric(df_pooled["Match Score"], errors="coerce").fillna(0)
    
    df_pooled_sorted = df_pooled.sort_values(by="Match Score", ascending=False).reset_index(drop=True)
    
    # --- KPI metrics ---
    st.markdown("### Pooling Statistics")
    avg_score = int(df_pooled["Match Score"].mean())
    top_score = int(df_pooled["Match Score"].max())
    total_pooled = len(df_pooled)
    
    c1, c2, c3 = st.columns(3)
    c1.metric("Average Score", avg_score)
    c2.metric("Top Score", top_score)
    c3.metric("Total Pooled", total_pooled)
    
    # Status breakdown
    st.markdown("### Status Breakdown")
    total_candidates = len(df_pooled_sorted)
    pending_count = len(df_pooled_sorted[df_pooled_sorted["Candidate Status"] == ""])
    ok_count = len(df_pooled_sorted[(df_pooled_sorted["Candidate Status"] == "OK") & (df_pooled_sorted["Interview Status"] == "")])
    ok_passed_count = len(df_pooled_sorted[(df_pooled_sorted["Candidate Status"] == "OK") & (df_pooled_sorted["Interview Status"] == "Lanjut")])
    rejected_count = len(df_pooled_sorted[df_pooled_sorted["Candidate Status"] == "Rejected"])
    ok_rejected_count = len(df_pooled_sorted[(df_pooled_sorted["Candidate Status"] == "OK") & (df_pooled_sorted["Interview Status"] == "Rejected")])
    
    breakdown_col1, breakdown_col2, breakdown_col3, breakdown_col4, breakdown_col5 = st.columns(5)
    breakdown_col1.metric("Pending", pending_count)
    breakdown_col2.metric("OK", ok_count)
    breakdown_col3.metric("OK-Passed", ok_passed_count)
    breakdown_col4.metric("Rejected", rejected_count)
    breakdown_col5.metric("OK-Rejected", ok_rejected_count)
    
    st.divider()
    
    # --- Filters Section ---
    st.markdown("### Filter & Search")
    
    filter_col1, filter_col2, filter_col3 = st.columns(3)
    
    with filter_col1:
        # Status filter
        status_options = ["All Status", "Pending", "OK", "OK-Passed", "Rejected", "OK-Rejected"]
        selected_status_filter = st.selectbox("Filter by Status", status_options, key="pooling_status_filter")
    
    with filter_col2:
        # Score filter
        score_options = ["All Scores", "High (>80)", "Medium (50-80)", "Low (<50)"]
        selected_score_filter = st.selectbox("Filter by Score", score_options, key="pooling_score_filter")
    
    with filter_col3:
        # Sort options
        sort_options = ["Score (High to Low)", "Score (Low to High)", "Name (A-Z)", "Name (Z-A)"]
        selected_sort = st.selectbox("Sort by", sort_options, key="pooling_sort")
    
    # Search box
    search_query = st.text_input("Search by Name or Email", placeholder="Type to search...", key="pooling_search")
    
    # Apply filters
    df_filtered = df_pooled_sorted.copy()
    
    # Status filter
    if selected_status_filter != "All Status":
        if selected_status_filter == "Pending":
            df_filtered = df_filtered[df_filtered["Candidate Status"] == ""]
        elif selected_status_filter == "OK":
            df_filtered = df_filtered[
                (df_filtered["Candidate Status"] == "OK") & 
                (df_filtered["Interview Status"] == "")
            ]
        elif selected_status_filter == "OK-Passed":
            df_filtered = df_filtered[
                (df_filtered["Candidate Status"] == "OK") & 
                (df_filtered["Interview Status"] == "Lanjut")
            ]
        elif selected_status_filter == "Rejected":
            df_filtered = df_filtered[df_filtered["Candidate Status"] == "Rejected"]
        elif selected_status_filter == "OK-Rejected":
            df_filtered = df_filtered[
                (df_filtered["Candidate Status"] == "OK") & 
                (df_filtered["Interview Status"] == "Rejected")
            ]
    
    # Score filter
    if selected_score_filter != "All Scores":
        if selected_score_filter == "High (>80)":
            df_filtered = df_filtered[df_filtered["Match Score"] > 80]
        elif selected_score_filter == "Medium (50-80)":
            df_filtered = df_filtered[(df_filtered["Match Score"] >= 50) & (df_filtered["Match Score"] <= 80)]
        elif selected_score_filter == "Low (<50)":
            df_filtered = df_filtered[df_filtered["Match Score"] < 50]
    
    # Search filter
    if search_query:
        df_filtered = df_filtered[
            df_filtered["Candidate Name"].fillna("").str.contains(search_query, case=False, na=False) |
            df_filtered["Candidate Email"].fillna("").str.contains(search_query, case=False, na=False)
        ]
    
    # Apply sorting
    if selected_sort == "Score (High to Low)":
        df_filtered = df_filtered.sort_values(by="Match Score", ascending=False)
    elif selected_sort == "Score (Low to High)":
        df_filtered = df_filtered.sort_values(by="Match Score", ascending=True)
    elif selected_sort == "Name (A-Z)":
        df_filtered = df_filtered.sort_values(by="Candidate Name", ascending=True)
    elif selected_sort == "Name (Z-A)":
        df_filtered = df_filtered.sort_values(by="Candidate Name", ascending=False)
    
    df_filtered = df_filtered.reset_index(drop=True)
    
    st.divider()
    
    # --- Pagination ---
    if df_filtered.empty:
        st.info("No candidates found matching the selected filters.")
    else:
        items_per_page = 10
        total_pages = max(1, (len(df_filtered) + items_per_page - 1) // items_per_page)
        
        # Initialize page number in session state
        if "pooling_page" not in st.session_state:
            st.session_state.pooling_page = 1
        
        # Ensure page is within valid range
        if st.session_state.pooling_page > total_pages:
            st.session_state.pooling_page = total_pages
        
        st.markdown(f"### Candidate Details (Showing {len(df_filtered)} of {total_candidates})")
        
        # Pagination controls
        page_col1, page_col2, page_col3 = st.columns([1, 2, 1])
        with page_col1:
            if st.button("← Previous", disabled=(st.session_state.pooling_page == 1), key="prev_page"):
                st.session_state.pooling_page -= 1
                st.rerun()
        with page_col2:
            st.markdown(f"<p style='text-align:center'>Page {st.session_state.pooling_page} of {total_pages}</p>", unsafe_allow_html=True)
        with page_col3:
            if st.button("Next →", disabled=(st.session_state.pooling_page == total_pages), key="next_page"):
                st.session_state.pooling_page += 1
                st.rerun()
        
        # Get current page data
        start_idx = (st.session_state.pooling_page - 1) * items_per_page
        end_idx = start_idx + items_per_page
        df_to_display = df_filtered.iloc[start_idx:end_idx]
    
    # Helper function to sanitize keys
    def sanitize_key(text):
        """Remove special characters from text to create safe widget keys."""
        if pd.isna(text) or not str(text).strip():
            return "unknown"
        return re.sub(r'[^a-zA-Z0-9_]', '_', str(text))
    
    for idx, row in df_to_display.iterrows():
        candidate_name = row.get("Candidate Name")
        if pd.isna(candidate_name) or not str(candidate_name).strip() or str(candidate_name).strip() == "nan":
            candidate_email = row.get("Candidate Email")
            if pd.notna(candidate_email) and str(candidate_email).strip():
                candidate_name = str(candidate_email).split("@")[0]
            else:
                candidate_name = row.get("Filename")
                if pd.isna(candidate_name) or not str(candidate_name).strip():
                    candidate_name = f"Candidate {idx + 1}"
        
        score = row.get("Match Score", 0)
        candidate_status = row.get("Candidate Status", "") if pd.notna(row.get("Candidate Status")) else ""
        interview_status = row.get("Interview Status", "") if pd.notna(row.get("Interview Status")) else ""
        rejection_reason = row.get("Rejection Reason", "") if pd.notna(row.get("Rejection Reason")) else ""
        
        # Format status display
        if candidate_status == "OK" and interview_status == "Rejected":
            status_display = f"OK-Rejected - {rejection_reason}" if rejection_reason else "OK-Rejected"
            status_color = "#dc3545"
        elif candidate_status == "OK" and interview_status == "Lanjut":
            status_display = "OK-Passed"
            status_color = "#28a745"
        elif candidate_status == "OK":
            status_display = "OK"
            status_color = "#28a745"
        elif candidate_status == "Rejected":
            status_display = f"Rejected - {rejection_reason}" if rejection_reason else "Rejected"
            status_color = "#dc3545"
        else:
            status_display = "Pending"
            status_color = "#6c757d"
        
        # Display candidate card
        st.markdown(f"""
        <div style='padding: 15px; background-color: #f8f9fa; border-left: 5px solid {status_color}; border-radius: 8px; margin-bottom: 10px;'>
            <h4 style='margin: 0; color: #212529;'>{candidate_name} - Score: {score}</h4>
            <p style='margin: 5px 0; color: {status_color}; font-weight: 600;'>Status: {status_display}</p>
        </div>
        """, unsafe_allow_html=True)
        
        # Details in expander
        with st.expander("View Details", expanded=False):
            col1, col2 = st.columns([1, 1])
            
            with col1:
                st.markdown("### Basic Info")
                def get_value(key, default='N/A'):
                    val = row.get(key, default)
                    return val if pd.notna(val) and str(val).strip() else default
                
                if "Candidate Email" in row:
                    st.text(f"Email: {get_value('Candidate Email')}")
                    st.text(f"Phone: {get_value('Phone')}")
                st.text(f"Job: {get_value('Latest Job Title')}")
                st.text(f"Company: {get_value('Latest Company')}")
                st.text(f"Education: {get_value('Education')}")
                st.text(f"University: {get_value('University')}")
            
            with col2:
                st.markdown("### Strengths")
                strengths = str(row.get("Strengths", "")) if pd.notna(row.get("Strengths")) else ""
                if strengths and strengths.strip():
                    for strength in strengths.split(", "):
                        if strength.strip():
                            st.markdown(f"- {strength.strip()}")
                else:
                    st.text("No strengths listed")
                
                st.markdown("### Weaknesses")
                weaknesses = str(row.get("Weaknesses", "")) if pd.notna(row.get("Weaknesses")) else ""
                if weaknesses and weaknesses.strip():
                    for weakness in weaknesses.split(", "):
                        if weakness.strip():
                            st.markdown(f"- {weakness.strip()}")
                else:
                    st.text("No weaknesses listed")
            
            st.markdown("### AI Summary")
            ai_summary = row.get("AI Summary")
            if pd.notna(ai_summary) and str(ai_summary).strip():
                st.info(ai_summary)
            else:
                st.info("No summary available")
            
            # Links section
            kalibrr_profile = row.get("Kalibrr Profile")
            application_link = row.get("Application Link")
            resume_link = row.get("Resume Link")
            
            has_links = (
                (pd.notna(kalibrr_profile) and str(kalibrr_profile).strip()) or
                (pd.notna(application_link) and str(application_link).strip()) or
                (pd.notna(resume_link) and str(resume_link).strip())
            )
            
            if has_links:
                st.markdown("### Links")
                link_cols = st.columns(3)
                if pd.notna(kalibrr_profile) and str(kalibrr_profile).strip():
                    link_cols[0].markdown(f"[Kalibrr Profile]({kalibrr_profile})")
                if pd.notna(application_link) and str(application_link).strip():
                    link_cols[1].markdown(f"[Application]({application_link})")
                if pd.notna(resume_link) and str(resume_link).strip():
                    link_cols[2].markdown(f"[Resume]({resume_link})")


# ============================================
# USAGE LOG TAB - API USAGE TRACKING
# ============================================
elif selected == "Usage Log":
    st.markdown("<h2 style='text-align:center;color:#0b3d91;'>API Usage Log</h2>", unsafe_allow_html=True)
    
    # Get today's summary
    from modules.usage_logger import load_usage_log, get_monthly_summary
    
    today = datetime.now().strftime("%Y-%m-%d")
    today_summary = get_daily_summary(today)
    
    # Today's statistics
    st.markdown("### Today's Usage")
    if today_summary:
        col1, col2, col3, col4, col5 = st.columns(5)
        col1.metric("Total CVs", today_summary.get('total', 0))
        col2.metric("Streamlit", today_summary.get('streamlit', 0))
        col3.metric("GitHub Actions", today_summary.get('github_action', 0))
        col4.metric("Successful", today_summary.get('successful', 0))
        col5.metric("Failed", today_summary.get('failed', 0))
        
        # By position
        if today_summary.get('positions'):
            st.markdown("### Today's Usage by Position")
            positions_df = pd.DataFrame([
                {"Position": pos, "Count": count} 
                for pos, count in sorted(today_summary['positions'].items(), key=lambda x: x[1], reverse=True)
            ])
            st.dataframe(positions_df, use_container_width=True, hide_index=True)
    else:
        st.info("No usage recorded today yet.")
    
    st.divider()
    
    # Monthly summary
    st.markdown("### This Month's Usage")
    current_year = datetime.now().year
    current_month = datetime.now().month
    monthly_summary = get_monthly_summary(current_year, current_month)
    
    if monthly_summary and monthly_summary.get('total', 0) > 0:
        col1, col2, col3, col4, col5 = st.columns(5)
        col1.metric("Total CVs", monthly_summary.get('total', 0))
        col2.metric("Streamlit", monthly_summary.get('streamlit', 0))
        col3.metric("GitHub Actions", monthly_summary.get('github_action', 0))
        col4.metric("Successful", monthly_summary.get('successful', 0))
        col5.metric("Failed", monthly_summary.get('failed', 0))
        
        # By position
        if monthly_summary.get('positions'):
            st.markdown("### Monthly Usage by Position")
            monthly_positions_df = pd.DataFrame([
                {"Position": pos, "Count": count} 
                for pos, count in sorted(monthly_summary['positions'].items(), key=lambda x: x[1], reverse=True)
            ])
            st.dataframe(monthly_positions_df, use_container_width=True, hide_index=True)
        
        # Daily breakdown chart
        if monthly_summary.get('daily_breakdown'):
            st.markdown("### Daily Usage Chart")
            daily_data = []
            for date_key, day_data in sorted(monthly_summary['daily_breakdown'].items()):
                daily_data.append({
                    "Date": date_key,
                    "Total": day_data.get('total', 0),
                    "Streamlit": day_data.get('streamlit', 0),
                    "GitHub Actions": day_data.get('github_action', 0)
                })
            
            daily_df = pd.DataFrame(daily_data)
            st.line_chart(daily_df.set_index('Date'))
    else:
        st.info("No usage recorded this month yet.")
    
    st.divider()
    
    # Historical view
    st.markdown("### Historical Data")
    all_logs = load_usage_log()
    
    if all_logs:
        # Create summary table
        historical_data = []
        for date_key in sorted(all_logs.keys(), reverse=True):
            day_data = all_logs[date_key]
            historical_data.append({
                "Date": date_key,
                "Total": day_data.get('total', 0),
                "Streamlit": day_data.get('streamlit', 0),
                "GitHub Actions": day_data.get('github_action', 0),
                "Successful": day_data.get('successful', 0),
                "Failed": day_data.get('failed', 0)
            })
        
        historical_df = pd.DataFrame(historical_data)
        st.dataframe(historical_df, use_container_width=True, hide_index=True)
        
        # Calculate estimated costs (example - adjust based on your API pricing)
        st.markdown("### Estimated API Costs")
        st.info("""
        **Cost Estimation Guide:**
        - Gemini 2.5 Pro (via OpenRouter): ~$0.001 - $0.003 per CV processed
        - Monthly total estimation based on usage patterns
        
        *Note: Actual costs may vary based on CV length and API response complexity.*
        """)
        
        total_monthly = monthly_summary.get('total', 0)
        estimated_cost_low = total_monthly * 0.001
        estimated_cost_high = total_monthly * 0.003
        
        cost_col1, cost_col2, cost_col3 = st.columns(3)
        cost_col1.metric("CVs This Month", total_monthly)
        cost_col2.metric("Est. Cost (Low)", f"${estimated_cost_low:.2f}")
        cost_col3.metric("Est. Cost (High)", f"${estimated_cost_high:.2f}")
    else:
        st.info("No historical data available yet.")
