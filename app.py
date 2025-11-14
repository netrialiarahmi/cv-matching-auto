import streamlit as st
from streamlit_option_menu import option_menu
import pandas as pd
from modules.extractor import extract_text_from_pdf
from modules.scorer import score_with_openrouter, get_openrouter_client
from modules.github_utils import (
    save_results_to_github, 
    load_results_from_github,
    save_job_positions_to_github,
    load_job_positions_from_github
)
from modules.candidate_processor import (
    parse_candidate_csv,
    extract_resume_from_url,
    build_candidate_context,
    get_candidate_identifier
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
        response = client.chat.completions.create(
            model="google/gemini-2.5-pro",
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
        st.dataframe(
            jobs_df,
            use_container_width=True,
            hide_index=True
        )
        
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
                st.text_area("", value=job_info['Job Description'], height=150, disabled=True, key="jd_preview")
        
        st.markdown("---")
        st.markdown("### 2️⃣ Upload Candidate Data")
        
        uploaded_csv = st.file_uploader(
            "📤 Upload Candidate CSV File",
            type=["csv"],
            help="Upload CSV file with candidate information including resume links"
        )
        
        if uploaded_csv:
            candidates_df = parse_candidate_csv(uploaded_csv)
            
            if candidates_df is not None:
                st.success(f"✅ CSV loaded successfully! Found {len(candidates_df)} candidates.")
                
                with st.expander("👀 Preview Candidate Data", expanded=True):
                    st.dataframe(candidates_df.head(10), use_container_width=True)
                
                st.markdown("---")
                
                # Load existing results to check for duplicates
                existing_results = load_results_from_github()
                existing_candidates = set()
                
                if existing_results is not None and not existing_results.empty:
                    for _, row in existing_results.iterrows():
                        if "Candidate Email" in row and pd.notna(row["Candidate Email"]):
                            existing_candidates.add(row["Candidate Email"])
                
                # Check which candidates are new
                new_candidates = []
                skipped_candidates = []
                
                for idx, row in candidates_df.iterrows():
                    candidate_email = str(row.get("Alamat Email", "")).strip()
                    if candidate_email in existing_candidates:
                        skipped_candidates.append(f"{row.get('Nama Depan', '')} {row.get('Nama Belakang', '')}")
                    else:
                        new_candidates.append(idx)
                
                if skipped_candidates:
                    st.info(f"ℹ️ {len(skipped_candidates)} candidate(s) already processed and will be skipped.")
                
                st.markdown(f"### 3️⃣ Process Candidates ({len(new_candidates)} new)")
                
                if st.button("🚀 Start Screening", type="primary", disabled=len(new_candidates) == 0):
                    results = []
                    progress = st.progress(0)
                    status_text = st.empty()
                    
                    for i, idx in enumerate(new_candidates):
                        row = candidates_df.iloc[idx]
                        candidate_name = f"{row.get('Nama Depan', '')} {row.get('Nama Belakang', '')}".strip()
                        
                        status_text.text(f"Processing {i+1}/{len(new_candidates)}: {candidate_name}")
                        progress.progress((i + 1) / len(new_candidates))
                        
                        # Extract resume from URL
                        resume_url = row.get("Link Resume", "")
                        cv_text = ""
                        
                        if pd.notna(resume_url) and resume_url.strip():
                            with st.spinner(f"📥 Downloading resume for {candidate_name}..."):
                                cv_text = extract_resume_from_url(resume_url)
                        
                        # Build additional context from CSV data
                        additional_context = build_candidate_context(row)
                        
                        # Combine CV text with additional context
                        full_context = f"{cv_text}\n\n--- Additional Information ---\n{additional_context}"
                        
                        # Score the candidate
                        if full_context.strip():
                            score, summary, strengths, weaknesses, gaps = score_with_openrouter(
                                full_context, 
                                selected_job, 
                                job_info['Job Description']
                            )
                        else:
                            score = 0
                            summary = "No resume or information available"
                            strengths = []
                            weaknesses = []
                            gaps = []
                        
                        results.append({
                            "Candidate Name": candidate_name,
                            "Candidate Email": str(row.get("Alamat Email", "")),
                            "Phone": str(row.get("Nomor Handphone", "")),
                            "Job Position": selected_job,
                            "Match Score": score,
                            "AI Summary": summary,
                            "Strengths": ", ".join(strengths) if strengths else "",
                            "Weaknesses": ", ".join(weaknesses) if weaknesses else "",
                            "Gaps": ", ".join(gaps) if gaps else "",
                            "Latest Job Title": str(row.get("Jabatan Pekerjaan Terakhir", "")),
                            "Latest Company": str(row.get("Perusahaan Terakhir", "")),
                            "Education": str(row.get("Tingkat Pendidikan Tertinggi", "")),
                            "University": str(row.get("Sekolah/Universitas", "")),
                            "Major": str(row.get("Jurusan/Program Studi", "")),
                            "Kalibrr Profile": str(row.get("Link Profil Kalibrr", "")),
                            "Application Link": str(row.get("Link Aplikasi Pekerjaan", "")),
                            "Resume Link": resume_url,
                            "Recruiter Feedback": "",
                            "AI Recruiter Score": "",
                            "Final Score": score,
                            "Date Processed": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        })
                    
                    status_text.text("✅ Screening completed!")
                    
                    if results:
                        df = pd.DataFrame(results)
                        st.session_state["screening_results"] = df
                        
                        st.success(f"🎉 Successfully screened {len(results)} candidates!")
                        
                        # Preview results
                        st.markdown("### 📊 Screening Results Preview")
                        st.dataframe(
                            df[["Candidate Name", "Job Position", "Match Score", "AI Summary"]],
                            use_container_width=True
                        )
                        
                        # Save to GitHub
                        if st.button("💾 Save Results to GitHub"):
                            if save_results_to_github(df):
                                st.success("✅ Results saved to GitHub successfully!")
                            else:
                                st.error("❌ Failed to save results to GitHub")


# ========================================
# SECTION 3: DASHBOARD
# ========================================
elif selected == "Dashboard":
    st.markdown("<h2 style='text-align:center;color:#0b3d91;'>📊 Screening Dashboard</h2>", unsafe_allow_html=True)

    df = load_results_from_github()
    if df is None or df.empty:
        st.warning("⚠️ No results found on GitHub. Please run a screening first.")
    else:
        st.session_state["results"] = df

        # Ensure columns exist
        for col in ["Recruiter Feedback", "AI Recruiter Score", "Final Score", "Strengths", "Weaknesses", "Gaps", "AI Summary"]:
            if col not in df.columns:
                df[col] = ""

        # Filter by position
        job_positions = df["Job Position"].unique().tolist()
        selected_job = st.selectbox("🎯 Filter by Job Position", ["All"] + job_positions)
        if selected_job != "All":
            df = df[df["Job Position"] == selected_job]

        # Convert numeric columns
        numeric_cols = ["Match Score", "AI Recruiter Score", "Final Score"]
        for col in numeric_cols:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

        df_sorted = df.sort_values(by="Final Score", ascending=False).reset_index(drop=True)

        # --- KPI metrics ---
        avg_score = int(df_sorted["Final Score"].mean())
        top_score = int(df_sorted["Final Score"].max())
        total_candidates = len(df_sorted)

        c1, c2, c3 = st.columns(3)
        c1.metric("📈 Avg Final Score", avg_score)
        c2.metric("🏆 Top Final Score", top_score)
        c3.metric("👥 Candidates", total_candidates)

        st.divider()
        
        # --- Display candidates with expanders ---
        st.subheader("📋 Candidate Details (Ranked by Score)")
        
        for idx, row in df_sorted.iterrows():
            candidate_name = row.get("Candidate Name", row.get("Filename", f"Candidate {idx}"))
            score = row.get("Final Score", row.get("Match Score", 0))
            
            with st.expander(f"🔍 {candidate_name} - Score: {score}", expanded=False):
                col1, col2 = st.columns([1, 1])
                
                with col1:
                    st.markdown("### 📊 Scores")
                    st.metric("Match Score", f"{row.get('Match Score', 0)}")
                    if row.get("AI Recruiter Score"):
                        st.metric("AI Recruiter Score", f"{row.get('AI Recruiter Score', 0)}")
                    st.metric("Final Score", f"{row.get('Final Score', 0)}")
                    
                    st.markdown("### 👤 Basic Info")
                    if "Candidate Email" in row:
                        st.text(f"📧 Email: {row.get('Candidate Email', 'N/A')}")
                        st.text(f"📱 Phone: {row.get('Phone', 'N/A')}")
                    st.text(f"💼 Job: {row.get('Latest Job Title', 'N/A')}")
                    st.text(f"🏢 Company: {row.get('Latest Company', 'N/A')}")
                    st.text(f"🎓 Education: {row.get('Education', 'N/A')}")
                    st.text(f"🏫 University: {row.get('University', 'N/A')}")
                
                with col2:
                    st.markdown("### ✅ Strengths")
                    strengths = row.get("Strengths", "")
                    if strengths and strengths.strip():
                        for strength in strengths.split(", "):
                            if strength.strip():
                                st.markdown(f"- {strength.strip()}")
                    else:
                        st.text("No strengths listed")
                    
                    st.markdown("### ⚠️ Weaknesses")
                    weaknesses = row.get("Weaknesses", "")
                    if weaknesses and weaknesses.strip():
                        for weakness in weaknesses.split(", "):
                            if weakness.strip():
                                st.markdown(f"- {weakness.strip()}")
                    else:
                        st.text("No weaknesses listed")
                    
                    st.markdown("### 🔴 Gaps")
                    gaps = row.get("Gaps", "")
                    if gaps and gaps.strip():
                        for gap in gaps.split(", "):
                            if gap.strip():
                                st.markdown(f"- {gap.strip()}")
                    else:
                        st.text("No gaps identified")
                
                st.markdown("### 🤖 AI Summary")
                st.info(row.get("AI Summary", "No summary available"))
                
                # Links section
                if "Resume Link" in row or "Kalibrr Profile" in row:
                    st.markdown("### 🔗 Links")
                    link_cols = st.columns(3)
                    if row.get("Resume Link"):
                        link_cols[0].markdown(f"[📄 Resume]({row['Resume Link']})")
                    if row.get("Kalibrr Profile"):
                        link_cols[1].markdown(f"[👤 Kalibrr Profile]({row['Kalibrr Profile']})")
                    if row.get("Application Link"):
                        link_cols[2].markdown(f"[📝 Application]({row['Application Link']})")

        st.divider()
        
        # --- Summary Table ---
        st.subheader("📊 Summary Table (All Candidates)")
        
        # Select key columns for display
        display_cols = ["Candidate Name" if "Candidate Name" in df_sorted.columns else "Filename", 
                       "Job Position", "Match Score", "Final Score"]
        
        # Add optional columns if they exist
        optional_cols = ["AI Recruiter Score", "Latest Job Title", "Education"]
        for col in optional_cols:
            if col in df_sorted.columns:
                display_cols.append(col)
        
        st.dataframe(
            df_sorted[display_cols],
            use_container_width=True
        )
        
        # --- Visualizations ---
        st.subheader("📈 Score Distribution")
        st.bar_chart(df_sorted.set_index(df_sorted["Candidate Name"] if "Candidate Name" in df_sorted.columns else df_sorted["Filename"])["Final Score"])

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
