import streamlit as st
from streamlit_option_menu import option_menu
import pandas as pd
from modules.extractor import extract_text_from_pdf
from modules.scorer import score_with_openrouter, get_openrouter_client, extract_candidate_name_from_cv, score_table_data, _get_model_name, call_api_with_retry
from modules.github_utils import (
    save_results_to_github,
    load_results_from_github,
    load_all_results_from_github,
    save_job_positions_to_github,
    load_job_positions_from_github,
    delete_job_position_from_github,
    update_job_position_in_github,
    update_results_in_github
)
from modules.candidate_processor import (
    parse_candidate_csv,
    extract_resume_from_url,
    build_candidate_context,
    get_candidate_identifier,
    _get_column_value,
    fetch_candidates_from_google_sheets
)
from PIL import Image
from datetime import datetime
import io
import re
import time

# --- Page Config ---
logo = Image.open("cqdybkxstovyrla2dje3.webp")
st.set_page_config(
    page_title="Kompas.com CV Matching System",
    page_icon=logo,
    layout="wide"
)

# --- Custom Styling ---
st.markdown("""
    <style>
    body { background-color: #f8fbff; }
    .main-title {
        text-align:center;
        font-size:30px;
        font-weight:700;
        color:#0b3d91;
        margin-bottom:10px;
    }
    .metric-card {
        background-color: #f7faff;
        padding: 15px;
        border-radius: 12px;
        text-align: center;
        border: 1px solid #d8e3f0;
    }
    .score-highlight {
        font-size: 36px;
        font-weight: 700;
        color: #004aad;
    }
    </style>
""", unsafe_allow_html=True)

# --- Navigation Bar ---
selected = option_menu(
    menu_title=None,
    options=["Job Management", "Screening", "Dashboard"],
    icons=["briefcase-fill", "cloud-upload-fill", "bar-chart-line-fill"],
    orientation="horizontal",
    default_index=0,
    styles={
        "container": {
            "padding": "5px 0",
            "background-color": "#0d6efd",
            "border-radius": "8px",
            "width": "100%",
            "display": "flex",
            "justify-content": "center",
            "margin-bottom": "2rem",
        },
        "icon": {"color": "#f9fafb", "font-size": "18px"},
        "nav-link": {
            "color": "#f9fafb",
            "font-size": "15px",
            "text-align": "center",
            "margin": "0 10px",
            "--hover-color": "#0761e97e",
            "padding": "10px 10px",
            "border-radius": "16px",
        },
        "nav-link-selected": {
            "background-color": "#ffd700",
            "color": "#0d6efd",
            "font-weight": "bold",
            "border-radius": "8px",
            "padding": "10px 15px",
            "box-shadow": "0px 4px 10px rgba(0, 0, 0, 0.15)",
            "transition": "background-color 0.3s ease",
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
        st.warning(f"⚠️ AI Evaluation failed: {e}")
        score = 50

    return min(max(score, 0), 100)


# ========================================
# SECTION 1: JOB MANAGEMENT
# ========================================
if selected == "Job Management":
    st.markdown("<h2 style='text-align:center;color:#0b3d91;'>💼 Job Position Management</h2>", unsafe_allow_html=True)

    st.markdown("### 📝 Add/Update Job Position")

    col1, col2 = st.columns([1, 2])

    with col1:
        job_position = st.text_input("🧑‍💼 Job Position", placeholder="e.g., Business Analyst")

    with col2:
        job_description = st.text_area("📝 Job Description", height=200, placeholder="Paste job description here...")

    if st.button("💾 Save Job Position", type="primary"):
        if not job_position.strip() or not job_description.strip():
            st.warning("⚠️ Please provide both Job Position and Job Description.")
        else:
            new_job = pd.DataFrame([{
                "Job Position": job_position.strip(),
                "Job Description": job_description.strip(),
                "Date Created": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }])

            if save_job_positions_to_github(new_job):
                st.success(f"✅ Job position '{job_position}' saved successfully!")
                st.rerun()

    st.markdown("---")
    st.markdown("### 📋 All Job Positions")

    # Load and display all job positions
    jobs_df = load_job_positions_from_github()

    if jobs_df is not None and not jobs_df.empty:
        # Display each job position with edit and delete buttons
        for idx, row in jobs_df.iterrows():
            with st.expander(f"💼 {row['Job Position']}", expanded=False):
                st.markdown(f"**Date Created:** {row['Date Created']}")
                st.markdown("**Job Description:**")
                st.text_area("", value=row['Job Description'], height=150, disabled=True, key=f"view_desc_{idx}")

                col1, col2, col3 = st.columns([1, 1, 3])

                with col1:
                    if st.button(f"✏️ Edit", key=f"edit_{idx}", type="secondary"):
                        st.session_state[f"editing_{idx}"] = True
                        st.rerun()

                with col2:
                    if st.button(f"🗑️ Delete", key=f"delete_{idx}", type="secondary"):
                        if delete_job_position_from_github(row['Job Position']):
                            st.success(f"✅ Job position '{row['Job Position']}' deleted successfully!")
                            time.sleep(1)
                            st.rerun()
                        else:
                            st.error("❌ Failed to delete job position")

                # Edit form (shown when edit button is clicked)
                if st.session_state.get(f"editing_{idx}", False):
                    st.markdown("---")
                    st.markdown("#### Edit Job Position")

                    edit_job_position = st.text_input(
                        "Job Position",
                        value=row['Job Position'],
                        key=f"edit_pos_{idx}"
                    )
                    edit_job_description = st.text_area(
                        "Job Description",
                        value=row['Job Description'],
                        height=200,
                        key=f"edit_desc_{idx}"
                    )

                    col_save, col_cancel = st.columns([1, 1])

                    with col_save:
                        if st.button("💾 Save Changes", key=f"save_{idx}", type="primary"):
                            if not edit_job_position.strip() or not edit_job_description.strip():
                                st.warning("⚠️ Please provide both Job Position and Job Description.")
                            else:
                                if update_job_position_in_github(
                                    row['Job Position'],
                                    edit_job_position.strip(),
                                    edit_job_description.strip()
                                ):
                                    st.success(f"✅ Job position updated successfully!")
                                    st.session_state[f"editing_{idx}"] = False
                                    time.sleep(1)
                                    st.rerun()
                                else:
                                    st.error("❌ Failed to update job position")

                    with col_cancel:
                        if st.button("❌ Cancel", key=f"cancel_{idx}"):
                            st.session_state[f"editing_{idx}"] = False
                            st.rerun()

        st.markdown("---")

        # Download option
        csv = jobs_df.to_csv(index=False).encode("utf-8")
        st.download_button(
            "💾 Download Job Positions (CSV)",
            data=csv,
            file_name="job_positions.csv",
            mime="text/csv"
        )
    else:
        st.info("ℹ️ No job positions saved yet. Add your first job position above!")


# ========================================
# SECTION 2: SCREENING
# ========================================
elif selected == "Screening":
    st.markdown("<h2 style='text-align:center;color:#0b3d91;'>🔍 Candidate Screening</h2>", unsafe_allow_html=True)

    # Load job positions
    jobs_df = load_job_positions_from_github()

    if jobs_df is None or jobs_df.empty:
        st.warning("⚠️ No job positions found. Please add job positions in the Job Management section first.")
    else:
        # Job position selection
        st.markdown("### 1️⃣ Select Job Position")
        job_positions = jobs_df["Job Position"].tolist()
        selected_job = st.selectbox("🎯 Choose Job Position", job_positions)

        # Display selected job details
        if selected_job:
            job_info = jobs_df[jobs_df["Job Position"] == selected_job].iloc[0]

            with st.expander("📄 View Job Position Details", expanded=True):
                st.markdown(f"**Job Position:** {job_info['Job Position']}")
                st.markdown(f"**Job Description:**")
                # Use dynamic key based on job position and date to ensure fresh data display
                jd_key = f"jd_preview_{selected_job}_{job_info.get('Date Created', 'default')}"
                st.text_area("", value=job_info['Job Description'], height=150, disabled=True, key=jd_key)

        st.markdown("---")
        st.markdown("### 2️⃣ Load Candidate Data")

        # Try to fetch candidates from Google Sheets first
        candidates_df = None
        data_source = None

        with st.spinner("🔍 Checking Google Sheets for candidate data..."):
            candidates_df = fetch_candidates_from_google_sheets(selected_job)

        if candidates_df is not None and not candidates_df.empty:
            # Data found in Google Sheets
            data_source = "Google Sheets"
            st.success(f"✅ Found {len(candidates_df)} candidate(s) from Google Sheets for '{selected_job}'")

            with st.expander("👀 Preview Candidate Data from Google Sheets", expanded=True):
                st.dataframe(candidates_df.head(10), use_container_width=True)
        else:
            # No data in Google Sheets, show upload option
            st.info("ℹ️ No candidate data found in Google Sheets for this position. Please upload a CSV file.")

            uploaded_csv = st.file_uploader(
                "📤 Upload Candidate CSV File",
                type=["csv"],
                help="Upload CSV file with candidate information including resume links"
            )

            if uploaded_csv:
                candidates_df = parse_candidate_csv(uploaded_csv)
                data_source = "Uploaded CSV"

                if candidates_df is not None:
                    st.success(f"✅ CSV loaded successfully! Found {len(candidates_df)} candidates.")

                    with st.expander("👀 Preview Candidate Data", expanded=True):
                        st.dataframe(candidates_df.head(10), use_container_width=True)

        # Process candidates if data is available from any source
        if candidates_df is not None and not candidates_df.empty:
            st.markdown("---")

            # Load existing results to check for duplicates
            existing_results = load_results_from_github()
            existing_candidate_job_pairs = set()

            if existing_results is not None and not existing_results.empty:
                for _, row in existing_results.iterrows():
                    if "Candidate Email" in row and pd.notna(row["Candidate Email"]) and "Job Position" in row and pd.notna(row["Job Position"]):
                        # Store combination of email + job position
                        existing_candidate_job_pairs.add((row["Candidate Email"], row["Job Position"]))

            # Check which candidates are new for this specific job position
            new_candidates = []
            skipped_candidates = []

            for idx, row in candidates_df.iterrows():
                # Support both English and Indonesian column names
                candidate_email = _get_column_value(row, "Email Address", "Alamat Email", "").strip()
                # Check if this candidate has already been processed for this specific job position
                if (candidate_email, selected_job) in existing_candidate_job_pairs:
                    first_name = _get_column_value(row, "First Name", "Nama Depan")
                    last_name = _get_column_value(row, "Last Name", "Nama Belakang")
                    skipped_candidates.append(f"{first_name} {last_name}")
                else:
                    new_candidates.append(idx)

            if skipped_candidates:
                st.info(f"ℹ️ {len(skipped_candidates)} candidate(s) already processed for '{selected_job}' position and will be skipped.")
                with st.expander("👀 View skipped candidates", expanded=False):
                    for name in skipped_candidates:
                        st.text(f"  • {name}")

            st.markdown(f"### 3️⃣ Process Candidates ({len(new_candidates)} new)")

            # Automatically process new candidates without requiring button click
            if len(new_candidates) > 0:
                st.info("🔄 Automatically processing new candidates in the background...")
                progress = st.progress(0)
                status_text = st.empty()
                save_status = st.empty()

                # Track successful saves
                successfully_saved = 0
                failed_saves = 0

                for i, idx in enumerate(new_candidates):
                    row = candidates_df.iloc[idx]
                    # Get candidate name supporting both English and Indonesian columns
                    first_name = _get_column_value(row, "First Name", "Nama Depan")
                    last_name = _get_column_value(row, "Last Name", "Nama Belakang")
                    candidate_name = f"{first_name} {last_name}".strip()

                    # Extract resume from URL
                    resume_url = _get_column_value(row, "Resume Link", "Link Resume")
                    cv_text = ""

                    if resume_url and str(resume_url).strip():
                        # Use a temporary name for status display
                        temp_name = candidate_name if candidate_name else f"Candidate {i+1}"
                        status_text.text(f"Processing {i+1}/{len(new_candidates)}: {temp_name}")
                        with st.spinner(f"📥 Downloading resume for {temp_name}..."):
                            cv_text = extract_resume_from_url(resume_url)

                    # If candidate name is missing from CSV, try to extract it from CV
                    if not candidate_name and cv_text:
                        with st.spinner(f"🔍 Extracting name from resume..."):
                            candidate_name = extract_candidate_name_from_cv(cv_text)

                    # Final fallback: use email or generate identifier
                    if not candidate_name:
                        email = _get_column_value(row, "Email Address", "Alamat Email", "").strip()
                        if email and email != "nan":
                            candidate_name = email.split("@")[0]
                        else:
                            candidate_name = f"Candidate {i+1}"

                    status_text.text(f"Processing {i+1}/{len(new_candidates)}: {candidate_name}")

                    # Build additional context from CSV data
                    additional_context = build_candidate_context(row)

                    # Combine CV text with additional context for CV scoring
                    full_context = f"{cv_text}\n\n--- Additional Information ---\n{additional_context}"

                    # Score: CV Match Score (from resume analysis only)
                    cv_score = 0
                    summary = "No resume or information available"
                    strengths = []
                    weaknesses = []
                    gaps = []

                    if cv_text.strip():
                        cv_score, summary, strengths, weaknesses, gaps = score_with_openrouter(
                            cv_text,
                            selected_job,
                            job_info['Job Description']
                        )

                    # Use CV score as the final match score
                    final_score = cv_score

                    # Create result for this candidate
                    candidate_result = {
                        "Candidate Name": candidate_name,
                        "Candidate Email": _get_column_value(row, "Email Address", "Alamat Email"),
                        "Phone": _get_column_value(row, "Mobile Number", "Nomor Handphone"),
                        "Job Position": selected_job,
                        "Match Score": final_score,
                        "AI Summary": summary,
                        "Strengths": ", ".join(strengths) if strengths else "",
                        "Weaknesses": ", ".join(weaknesses) if weaknesses else "",
                        "Gaps": ", ".join(gaps) if gaps else "",
                        "Latest Job Title": _get_column_value(row, "Latest Job Title", "Jabatan Pekerjaan Terakhir"),
                        "Latest Company": _get_column_value(row, "Latest Company", "Perusahaan Terakhir"),
                        "Education": _get_column_value(row, "Latest Educational Attainment", "Tingkat Pendidikan Tertinggi"),
                        "University": _get_column_value(row, "Latest School/University", "Sekolah/Universitas"),
                        "Major": _get_column_value(row, "Latest Major/Course", "Jurusan/Program Studi"),
                        "Kalibrr Profile": _get_column_value(row, "Kalibrr Profile Link", "Link Profil Kalibrr"),
                        "Application Link": _get_column_value(row, "Job Application Link", "Link Aplikasi Pekerjaan"),
                        "Resume Link": resume_url,
                        "Recruiter Feedback": "",
                        "Shortlisted": False,
                        "Date Processed": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    }

                    # Save immediately after processing each candidate
                    try:
                        result_df = pd.DataFrame([candidate_result])
                        # Save to position-specific file
                        if save_results_to_github(result_df, job_position=selected_job):
                            successfully_saved += 1
                            save_status.success(f"💾 Saved {candidate_name} ({successfully_saved}/{i+1})")
                        else:
                            failed_saves += 1
                            save_status.warning(f"⚠️ Failed to save {candidate_name}. Will retry at the end.")
                    except Exception as e:
                        failed_saves += 1
                        save_status.warning(f"⚠️ Error saving {candidate_name}: {str(e)}")

                    # Update progress
                    progress.progress((i + 1) / len(new_candidates))

                status_text.text("✅ Screening completed!")

                # Show final save summary
                if successfully_saved > 0:
                    st.success(f"🎉 Successfully processed and saved {successfully_saved} candidate(s)!")
                    if len(skipped_candidates) > 0:
                        st.info(f"ℹ️ Skipped {len(skipped_candidates)} candidate(s) already processed for this position (no duplicates).")
                    if failed_saves > 0:
                        st.warning(f"⚠️ {failed_saves} candidate(s) failed to save. Please check the Dashboard and re-run if needed.")
                    st.info("💡 You can now view the results in the Dashboard section.")
                else:
                    st.error("❌ Failed to save any results to GitHub. Please check your connection and try again.")
            else:
                st.info("ℹ️ All candidates have already been processed for this position. Check the Dashboard to view results.")


# ========================================
# SECTION 3: DASHBOARD
# ========================================
elif selected == "Dashboard":
    st.markdown("<h2 style='text-align:center;color:#0b3d91;'>📊 Screening Dashboard</h2>", unsafe_allow_html=True)

    # Load all results from all position-specific files
    df = load_all_results_from_github()

    # Check for errors (None means authentication/connection error)
    if df is None:
        st.error("❌ Failed to load results from GitHub. Please check your GitHub token, repository access, and network connection.")
        st.stop()

    # Check if we have any data
    if df.empty:
        st.info("ℹ️ No screening results yet. Please run a screening first from the 'Screening' section.")
        st.stop()

    # Data loaded successfully
    st.session_state["results"] = df

    # Ensure columns exist
    for col in ["Recruiter Feedback", "Strengths", "Weaknesses", "Gaps", "AI Summary", "Shortlisted"]:
        if col not in df.columns:
            if col == "Shortlisted":
                df[col] = False
            else:
                df[col] = ""
    
    # Clean up Shortlisted column - ensure it only contains boolean values
    # This handles any corrupted data (e.g., timestamps) that may exist
    if "Shortlisted" in df.columns:
        df["Shortlisted"] = df["Shortlisted"].apply(
            lambda x: True if str(x).strip() == "True" or x is True else False
        )

    # Filter by position
    job_positions = df["Job Position"].unique().tolist()
    selected_job = st.selectbox("🎯 Filter by Job Position", ["All"] + job_positions)
    
    if selected_job != "All":
        df = df[df["Job Position"] == selected_job].copy()

    # Convert numeric columns
    numeric_cols = ["Match Score"]
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    df_sorted = df.sort_values(by="Match Score", ascending=False).reset_index(drop=True)

    # --- KPI metrics ---
    avg_score = int(df_sorted["Match Score"].mean())
    top_score = int(df_sorted["Match Score"].max())
    total_candidates = len(df_sorted)

    c1, c2, c3 = st.columns(3)
    c1.metric("📈 Avg Match Score", avg_score)
    c2.metric("🏆 Top Match Score", top_score)
    c3.metric("👥 Candidates", total_candidates)

    st.divider()

    # --- Display candidates with expanders ---
    st.subheader("📋 Candidate Details (Ranked by Score)")

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

        # Get shortlist status
        is_shortlisted = row.get("Shortlisted", False)
        if pd.isna(is_shortlisted) or is_shortlisted == "" or is_shortlisted == "False":
            is_shortlisted = False
        elif is_shortlisted == "True" or is_shortlisted == True:
            is_shortlisted = True
        else:
            is_shortlisted = bool(is_shortlisted)

        # Create unique key for checkbox
        checkbox_key = f"shortlist_{idx}_{candidate_name.replace(' ', '_')}"

        # Create layout with checkbox and expander
        col_checkbox, col_expander = st.columns([0.05, 0.95])

        with col_checkbox:
            # Checkbox for shortlisting
            new_shortlist_status = st.checkbox("Shortlist", value=is_shortlisted, key=checkbox_key, label_visibility="collapsed")

            # If checkbox status changed, update the dataframe and save
            if new_shortlist_status != is_shortlisted:
                # Update the dataframe
                # Find the original row index in the full dataframe
                original_df = st.session_state["results"]

                # Try to identify the row by email + job position, or just candidate name
                candidate_email = row.get("Candidate Email")
                job_position = row.get("Job Position")

                if pd.notna(candidate_email) and candidate_email:
                    mask = (original_df["Candidate Email"] == candidate_email) & (original_df["Job Position"] == job_position)
                else:
                    mask = (original_df["Candidate Name"] == candidate_name) & (original_df["Job Position"] == job_position)

                original_df.loc[mask, "Shortlisted"] = new_shortlist_status

                # Save only the records for this specific position to its position-specific file
                position_df = original_df[original_df["Job Position"] == job_position].copy()
                if update_results_in_github(position_df, job_position=job_position):
                    st.session_state["results"] = original_df
                    st.rerun()

        with col_expander:
            # Show checkmark in title if shortlisted
            shortlist_mark = " ✅" if new_shortlist_status else ""
            with st.expander(f"🔍 {candidate_name} - Score: {score}{shortlist_mark}", expanded=False):
                col1, col2 = st.columns([1, 1])

                with col1:
                    st.markdown("### 📊 Score")
                    st.metric("Match Score", f"{row.get('Match Score', 0)}")

                    st.markdown("### 👤 Basic Info")
                    # Helper function to get non-NaN value
                    def get_value(key, default='N/A'):
                        val = row.get(key, default)
                        return val if pd.notna(val) and str(val).strip() else default

                    if "Candidate Email" in row:
                        st.text(f"📧 Email: {get_value('Candidate Email')}")
                        st.text(f"📱 Phone: {get_value('Phone')}")
                    st.text(f"💼 Job: {get_value('Latest Job Title')}")
                    st.text(f"🏢 Company: {get_value('Latest Company')}")
                    st.text(f"🎓 Education: {get_value('Education')}")
                    st.text(f"🏫 University: {get_value('University')}")

                with col2:
                    st.markdown("### ✅ Strengths")
                    strengths = str(row.get("Strengths", "")) if pd.notna(row.get("Strengths")) else ""
                    if strengths and strengths.strip():
                        for strength in strengths.split(", "):
                            if strength.strip():
                                st.markdown(f"- {strength.strip()}")
                    else:
                        st.text("No strengths listed")

                    st.markdown("### ⚠️ Weaknesses")
                    weaknesses = str(row.get("Weaknesses", "")) if pd.notna(row.get("Weaknesses")) else ""
                    if weaknesses and weaknesses.strip():
                        for weakness in weaknesses.split(", "):
                            if weakness.strip():
                                st.markdown(f"- {weakness.strip()}")
                    else:
                        st.text("No weaknesses listed")

                    st.markdown("### 🔴 Gaps")
                    gaps = str(row.get("Gaps", "")) if pd.notna(row.get("Gaps")) else ""
                    if gaps and gaps.strip():
                        for gap in gaps.split(", "):
                            if gap.strip():
                                st.markdown(f"- {gap.strip()}")
                    else:
                        st.text("No gaps identified")

                st.markdown("### 🤖 AI Summary")
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
                    st.markdown("### 🔗 Links")
                    link_cols = st.columns(3)
                    if pd.notna(kalibrr_profile) and str(kalibrr_profile).strip():
                        link_cols[0].markdown(f"[👤 Kalibrr Profile]({kalibrr_profile})")
                    if pd.notna(application_link) and str(application_link).strip():
                        link_cols[1].markdown(f"[📝 Application]({application_link})")
                    if pd.notna(resume_link) and str(resume_link).strip():
                        link_cols[2].markdown(f"[📄 Resume]({resume_link})")

    st.divider()

    # --- Summary Table ---
    st.subheader("📊 Summary Table (All Candidates)")

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
                   "Job Position", "Match Score"]

    # Add optional columns if they exist
    optional_cols = ["Latest Job Title", "Education"]
    for col in optional_cols:
        if col in df_display.columns:
            display_cols.append(col)

    st.dataframe(
        df_display[display_cols],
        use_container_width=True
    )

    # --- Visualizations ---
    st.subheader("📈 Score Distribution")

    # Create chart data with cleaned candidate names
    chart_data = df_display.copy()
    chart_index = chart_data["Candidate Name"] if "Candidate Name" in chart_data.columns else chart_data.index
    st.bar_chart(chart_data.set_index(chart_index)["Match Score"])

    # --- Download buttons ---
    csv = df_sorted.to_csv(index=False).encode("utf-8")
    st.download_button(
        "💾 Download Results (CSV)",
        data=csv,
        file_name="cv_screening_results.csv",
        mime="text/csv"
    )

    # Excel download
    excel_buffer = io.BytesIO()
    with pd.ExcelWriter(excel_buffer, engine="xlsxwriter") as writer:
        df_sorted.to_excel(writer, index=False, sheet_name="Results")

    st.download_button(
        "📘 Download Results (Excel)",
        data=excel_buffer.getvalue(),
        file_name="cv_screening_results.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
