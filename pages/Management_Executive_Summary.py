import streamlit as st
import pandas as pd
from pathlib import Path
import plotly.express as px
from utils import load_master_data, global_filter_sidebar, apply_filters, inject_global_ui
from auth import login

if not login():
    st.stop()
DATA_FILE = Path(__file__).parents[1] / "data" / "QAQC_Master.xlsx"
BASE_DIR = Path(__file__).resolve().parent.parent
st.set_page_config(page_title="Management Executive Summary", layout="wide")
inject_global_ui()
ASSETS = BASE_DIR / "assets"
EVOMEC_LOGO = ASSETS / "evomec_logo.png"
NLNG_LOGO = ASSETS / "nlng_logo.png"


def safe_path(path):
    return str(path) if path.exists() else None

EVOMEC_LOGO = safe_path(EVOMEC_LOGO)
NLNG_LOGO = safe_path(NLNG_LOGO)

col1, col2 = st.columns(2)

with col1:
    if EVOMEC_LOGO:
        st.image(EVOMEC_LOGO, width=150)

with col2:
    if NLNG_LOGO:
        st.image(NLNG_LOGO, width=140)
        
st.title("Management Executive Summary")
st.markdown("Automated executive insights, risk summary, and management recommendations.")

filters = global_filter_sidebar(load_master_data(DATA_FILE))
data = load_master_data(DATA_FILE)

ncr = apply_filters(data.get("NCR Log", pd.DataFrame()), filters, date_column="Date Raised")
obs = apply_filters(data.get("OBS Log", pd.DataFrame()), filters, date_column="Date_Raised")
itr = apply_filters(data.get("ITR Log", pd.DataFrame()), filters, date_column="Date")
audit = apply_filters(data.get("Audit Register", pd.DataFrame()), filters, date_column="Planned_Date")
surv = apply_filters(data.get("Surveillance Register", pd.DataFrame()), filters, date_column="Planned_Date")
docs = apply_filters(data.get("Document Register", pd.DataFrame()), filters, date_column="Issue_Date")
ctq = apply_filters(data.get("CTQ Log", pd.DataFrame()), filters, date_column="Date")
defects = apply_filters(data.get("Defect/Rework Log", pd.DataFrame()), filters, date_column="Date Identified")

quality_index = 0
log_count = len(ncr) + len(itr) + len(audit) + len(surv) + len(ctq) + len(defects)
quality_index = int((
    (int((ncr["Status"].str.lower() == "closed").sum()) / max(1, len(ncr))) * 30 if not ncr.empty else 0 +
    (int((itr["Status"].str.lower() == "closed").sum()) / max(1, len(itr))) * 20 if not itr.empty else 0 +
    (int((audit["Status"].str.lower() == "completed").sum()) / max(1, len(audit))) * 15 if not audit.empty else 0 +
    (int((surv["Status"].str.lower() == "completed").sum()) / max(1, len(surv))) * 15 if not surv.empty else 0 +
    (int((ctq["Status"].str.lower() == "passed").sum()) / max(1, len(ctq))) * 10 if not ctq.empty else 0 +
    (1 - len(defects) / max(1, len(itr))) * 10 if not itr.empty else 0
) * 100)

recommendations = []
if quality_index < 70:
    recommendations.append("Immediate corrective action required: focus on overdue NCRs and OBS closeouts.")
if len(ncr[ncr["Status"].str.lower() == "open"]) > 5:
    recommendations.append("Assign dedicated resources to close open NCRs within the next 7 days.")
if len(obs[obs["Status"].str.lower() == "open"]) > 5:
    recommendations.append("Review OBS closure processes and improve contractor accountability.")
if quality_index < 85 and not ctq.empty:
    recommendations.append("Increase CTQ inspection rigor and close non-compliant CTQs immediately.")
if not defects.empty and defects["Status"].str.lower().eq("open").any():
    recommendations.append("Analyze recurring defects and implement preventive actions for root causes.")

top_project = "N/A"
lowest_project = "N/A"
if "Project" in ncr.columns:
    project_scores = ncr.groupby("Project").apply(lambda x: int((x["Status"].str.lower() == "closed").sum() / max(1, len(x)) * 100)).reset_index(name="Closeout %")
    if not project_scores.empty:
        top_project = project_scores.sort_values("Closeout %", ascending=False).iloc[0]["Project"]
        lowest_project = project_scores.sort_values("Closeout %").iloc[0]["Project"]

c1, c2, c3, c4 = st.columns(4)
c1.metric("Quality Index", f"{quality_index}%")
c2.metric("Top Performing Project", top_project)
c3.metric("Lowest Performing Project", lowest_project)
c4.metric("Open Quality Issues", len(ncr[ncr["Status"].str.lower() == "open"]))

st.markdown("---")
st.subheader("Management Summary")
st.write("### Critical Risks")
for rec in recommendations:
    st.write(f"- {rec}")

st.write("### Overdue Items")
st.write(f"- Overdue NCRs: {len(ncr[(ncr["Status"].str.lower() == "open") & (pd.to_datetime(ncr["Due_Date"], errors='coerce') < pd.Timestamp('today'))])}")
st.write(f"- Overdue OBS: {len(obs[(obs["Status"].str.lower() == "open") & (pd.to_datetime(obs["Due_Date"], errors='coerce') < pd.Timestamp('today'))])}")
st.write(f"- Overdue CTQ Actions: {len(ctq[(ctq["Status"].str.lower() == "open") & (pd.to_datetime(ctq["Date"], errors='coerce') < pd.Timestamp('today'))])}")

st.markdown("---")
if not ncr.empty and "Project" in ncr.columns:
    issue_counts = ncr["Project"].value_counts().rename_axis("Project").reset_index(name="Count")
    st.plotly_chart(px.bar(issue_counts, x="Project", y="Count", title="Open Quality Issues by Project"), use_container_width=True)
