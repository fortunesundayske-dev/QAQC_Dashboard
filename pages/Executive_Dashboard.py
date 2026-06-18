import streamlit as st
import pandas as pd
import plotly.express as px
from pathlib import Path
from utils import load_master_data, global_filter_sidebar, apply_filters, load_company_logo, inject_global_ui
from auth import login

if not login():
    st.stop()
DATA_FILE = Path(__file__).parents[1] / "data" / "QAQC_Master.xlsx"
LOGO_PATH = Path(__file__).parents[1] / "assets" / "company_logo.png"
BASE_DIR = Path(__file__).resolve().parent.parent
st.set_page_config(page_title="Executive Dashboard", layout="wide")
inject_global_ui()
st.subheader("ITR Debug")

st.title("Executive Dashboard")
st.markdown("A management-level summary of quality performance across all construction projects.")

filters = global_filter_sidebar(load_master_data(DATA_FILE))
data = load_master_data(DATA_FILE)

ncr = apply_filters(data.get("NCR Log", pd.DataFrame()), filters, date_column="Date Raised")
obs = apply_filters(data.get("OBS Log", pd.DataFrame()), filters, date_column="Date Raised")
itr = apply_filters(data.get("ITR Log", pd.DataFrame()), filters, date_column="Date")
st.write("ITR Rows:", len(itr))
st.write("ITR Columns:", itr.columns.tolist())
st.write(itr.head())
concrete = apply_filters(data.get("Concrete Tracker", pd.DataFrame()), filters, date_column="Date")
audit = apply_filters(data.get("Audit Register", pd.DataFrame()), filters, date_column="Planned Date")
surveillance = apply_filters(data.get("Surveillance Register", pd.DataFrame()), filters, date_column="Planned Date")
docs = apply_filters(data.get("Document Register", pd.DataFrame()), filters, date_column="Issue_Date")
lessons = apply_filters(data.get("Lessons Learned", pd.DataFrame()), filters, date_column="Date_Logged")

projects = sorted(
    set(
        str(p)
        for df in data.values()
        if "Project" in df.columns
        for p in df["Project"].dropna().unique()
    )
)
def status_counts(df, status):
    if "Status" not in df.columns:
        return 0

    s = (
        df["Status"]
        .astype(str)
        .str.strip()
        .str.lower()
    )

    return int((s == status.lower()).sum())
def build_metrics():
    return [
        {"label": "Total Projects", "value": len(projects), "color": "#0D9488"},
        {"label": "Daily Reports", "value": len(data.get("Daily Reports", [])), "color": "#2563EB"},
        {"label": "Open NCR", "value": status_counts(ncr, "Open"), "color": "#DC2626"},
        {"label": "Closed NCR", "value": status_counts(ncr, "Closed"), "color": "#22C55E"},
        {"label": "Open OBS", "value": status_counts(obs, "Open"), "color": "#FBBF24"},
        {"label": "Closed OBS", "value": status_counts(obs, "Closed"), "color": "#10B981"},
        {"label": "Open ITR", "value": status_counts(itr, "Open"), "color": "#F97316"},
        {"label": "Closed ITR", "value": status_counts(itr, "Closed"), "color": "#8B5CF6"},
        {"label": "Concrete Pours", "value": len(concrete), "color": "#0EA5E9"},
        {"label": "Audits Planned", "value": len(audit), "color": "#A855F7"},
        {"label": "Surveillance Planned", "value": len(surveillance), "color": "#9333EA"},
        {"label": "Lessons Learned", "value": len(lessons), "color": "#22D3EE"},
    ]

if st.button("Refresh Dashboard"):
    st.rerun()

cols = st.columns(4)
for index, metric in enumerate(build_metrics()):
    cols[index % 4].metric(metric["label"], metric["value"])

st.markdown("---")

ncr_status = pd.DataFrame({"Status": ["Open", "Closed"], "Count": [status_counts(ncr, "Open"), status_counts(ncr, "Closed")]})
obs_status = pd.DataFrame({"Status": ["Open", "Closed"], "Count": [status_counts(obs, "Open"), status_counts(obs, "Closed")]})
itr_status = pd.DataFrame({"Status": ["Open", "Closed"], "Count": [status_counts(itr, "Open"), status_counts(itr, "Closed")]})

col1, col2, col3 = st.columns(3)
col1.plotly_chart(px.pie(ncr_status, values="Count", names="Status", title="NCR Status"), use_container_width=True)
col2.plotly_chart(px.pie(obs_status, values="Count", names="Status", title="OBS Status"), use_container_width=True)
col3.plotly_chart(px.pie(itr_status, values="Count", names="Status", title="ITR Closeout Status"), use_container_width=True)

st.markdown("---")

if not audit.empty:
    audit_summary = audit["Status"].value_counts().reindex(["Planned", "Completed"], fill_value=0).rename_axis("Status").reset_index(name="Count")
else:
    audit_summary = pd.DataFrame({"Status": ["Planned", "Completed"], "Count": [0, 0]})
if not surveillance.empty:
    surveillance_summary = surveillance["Status"].value_counts().reindex(["Planned", "Completed"], fill_value=0).rename_axis("Status").reset_index(name="Count")
else:
    surveillance_summary = pd.DataFrame({"Status": ["Planned", "Completed"], "Count": [0, 0]})

col1, col2 = st.columns(2)
col1.plotly_chart(px.bar(audit_summary, x="Status", y="Count", title="Audit Planned vs Actual"), use_container_width=True)
col2.plotly_chart(px.bar(surveillance_summary, x="Status", y="Count", title="Surveillance Planned vs Actual"), use_container_width=True)

st.markdown("---")

def build_trend(df, date_col, value_label, title):
    if df.empty or date_col not in df.columns:
        return None
    trend = df.copy()
    trend["Month"] = trend[date_col].dt.to_period("M").dt.to_timestamp()
    trend = trend.groupby("Month").size().reset_index(name=value_label)
    return px.line(trend, x="Month", y=value_label, title=title, markers=True)

reports_trend = build_trend(data.get("Daily Reports", pd.DataFrame()), "Report_Date", "Reports", "Daily Report Submission Trend")
concrete_trend = build_trend(concrete, "Date", "Pours", "Concrete Placement Trend")

col1, col2 = st.columns(2)
if reports_trend is not None:
    col1.plotly_chart(reports_trend, use_container_width=True)
if concrete_trend is not None:
    col2.plotly_chart(concrete_trend, use_container_width=True)

st.markdown("---")

project_heat = ncr.groupby("Project").size().reset_index(name="NCR Count") if not ncr.empty else pd.DataFrame(columns=["Project", "NCR Count"])
quality_rank = project_heat.sort_values("NCR Count", ascending=False).head(10)

col1, col2 = st.columns(2)
col1.plotly_chart(px.bar(quality_rank, x="NCR Count", y="Project", orientation="h", title="Project Quality Performance Ranking"), use_container_width=True)

discipline_metrics = pd.concat([ncr.assign(Type="NCR"), itr.assign(Type="ITR")], ignore_index=True) if not ncr.empty or not itr.empty else pd.DataFrame()
if not discipline_metrics.empty and "Discipline" in discipline_metrics.columns:
    disc = discipline_metrics.groupby("Discipline").size().reset_index(name="Count")
    col2.plotly_chart(px.bar(disc, x="Discipline", y="Count", title="Discipline Performance Comparison"), use_container_width=True)
else:
    col2.info("No discipline data available.")

st.markdown("---")
if not project_heat.empty:
    heatmap = px.density_heatmap(project_heat, x="Project", y="NCR Count", title="Quality Heat Map: Project vs NCR Count")
    st.plotly_chart(heatmap, use_container_width=True)
else:
    st.info("Quality heat map requires NCR project data.")
