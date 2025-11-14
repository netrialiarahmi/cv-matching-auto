import streamlit as st
from streamlit_option_menu import option_menu
import pandas as pd
from modules.extractor import extract_text_from_pdf
from modules.scorer import score_with_openrouter, get_openrouter_client
from modules.github_utils import save_results_to_github, load_results_from_github
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
    options=["Upload & Screening", "Dashboard"],
    icons=["cloud-upload-fill", "bar-chart-line-fill"],
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

# --- UPLOAD & SCREENING PAGE ---
if selected == "Upload & Screening":
    st.markdown("<h2 style='text-align:center;color:#0b3d91;'>📤 Upload CVs & Job Info</h2>", unsafe_allow_html=True)

    uploaded_files = st.file_uploader(
        "Upload multiple CVs (PDF)",
        type=["pdf"],
        accept_multiple_files=True
    )

    job_position = st.text_input("🧑‍💼 Job Position", placeholder="e.g., Business Analyst")
    job_description = st.text_area("📝 Job Description", height=200, placeholder="Paste job description here...")

    if st.button("🚀 Run Screening", type="primary"):
        if not uploaded_files:
            st.warning("Please upload at least one CV.")
        elif not job_position.strip() or not job_description.strip():
            st.warning("Please provide both Job Position and Job Description.")
        else:
            results = []
            progress = st.progress(0)
            for i, f in enumerate(uploaded_files):
                progress.progress((i + 1) / len(uploaded_files))
                text = extract_text_from_pdf(f)
                score, summary, strengths, weaknesses, gaps = score_with_openrouter(text, job_position, job_description)
                results.append({
                    "Filename": f.name,
                    "Job Position": job_position,
                    "Match Score": score,
                    "AI Summary": summary,
                    "Strengths": ", ".join(strengths) if strengths else "",
                    "Weaknesses": ", ".join(weaknesses) if weaknesses else "",
                    "Gaps": ", ".join(gaps) if gaps else "",
                    "Recruiter Feedback": "",
                    "AI Recruiter Score": "",
                    "Final Score": score,
                    "Date Processed": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                })

            df = pd.DataFrame(results)
            st.session_state["results"] = df
            
            # Save to GitHub and check if successful
            if save_results_to_github(df):
                # Success message already shown by save_results_to_github
                pass
            else:
                st.warning("⚠️ Results processed but not saved to GitHub. Check your credentials.")

# --- DASHBOARD PAGE ---
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

        st.subheader("🧠 Recruiter Feedback Evaluation (AI-Enhanced)")
        st.info("Enter recruiter feedback — AI will interpret sentiment and adjust scores automatically.")

        for idx, row in df.iterrows():
            with st.expander(f"📄 {row['Filename']} — Current Score: {row['Match Score']}"):
                feedback = st.text_area(
                    f"💬 Recruiter Feedback for {row['Filename']}",
                    value=row.get("Recruiter Feedback", ""),
                    key=f"fb_{idx}"
                )
                df.at[idx, "Recruiter Feedback"] = feedback

                if st.button(f"⚡ Analyze Feedback with AI for {row['Filename']}", key=f"analyze_{idx}"):
                    with st.spinner("🤖 AI evaluating feedback..."):
                        time.sleep(1)
                        ai_score = evaluate_recruiter_feedback(feedback)
                        df.at[idx, "AI Recruiter Score"] = ai_score
                        df.at[idx, "Final Score"] = round((0.6 * float(df.at[idx, "Match Score"])) + (0.4 * ai_score), 1)
                        st.success(f"🤖 AI Recruiter Score: {ai_score}")

        if st.button("💾 Save AI Feedback & Re-Rank"):
            numeric_cols = ["Match Score", "AI Recruiter Score", "Final Score"]
            for col in numeric_cols:
                df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

            df_sorted = df.sort_values(by="Final Score", ascending=False).reset_index(drop=True)
            
            # Save to GitHub and check if successful
            if save_results_to_github(df_sorted):
                st.session_state["results"] = df_sorted
                # Success message already shown by save_results_to_github
            else:
                st.warning("⚠️ AI feedback processed locally but not saved to GitHub. Check your credentials.")

        # --- KPI metrics ---
        numeric_cols = ["Match Score", "AI Recruiter Score", "Final Score"]
        for col in numeric_cols:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

        df_sorted = df.sort_values(by="Final Score", ascending=False)
        avg_score = int(df_sorted["Final Score"].mean())
        top_score = int(df_sorted["Final Score"].max())
        total_candidates = len(df_sorted)

        c1, c2, c3 = st.columns(3)
        c1.metric("📈 Avg Final Score", avg_score)
        c2.metric("🏆 Top Final Score", top_score)
        c3.metric("👥 Candidates", total_candidates)

        st.divider()
        st.subheader("📋 Final Candidate Ranking")
        st.dataframe(
            df_sorted[
                ["Filename", "Job Position", "Match Score", "AI Recruiter Score", "Final Score",
                 "Strengths", "Weaknesses", "Gaps", "Recruiter Feedback", "AI Summary"]
            ],
            use_container_width=True
        )
        st.bar_chart(df_sorted.set_index("Filename")["Final Score"])

        # --- Download buttons ---
        csv = df_sorted.to_csv(index=False).encode("utf-8")
        st.download_button(
            "💾 Download Final Results (CSV)",
            data=csv,
            file_name="cv_screening_ai_final_results.csv",
            mime="text/csv"
        )

        # Excel download
        excel_buffer = io.BytesIO()
        with pd.ExcelWriter(excel_buffer, engine="xlsxwriter") as writer:
            df_sorted.to_excel(writer, index=False, sheet_name="Results")

        st.download_button(
            "📘 Download Final Results (Excel)",
            data=excel_buffer.getvalue(),
            file_name="cv_screening_ai_final_results.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
