import streamlit as st
import pandas as pd
import utils
import plotly.express as px
from pathlib import Path
from utils import (
    load_master_data,
    global_filter_sidebar,
    apply_filters,
    render_table,
    inject_global_ui,
    render_table_with_details,
    render_top_nav
)
from auth import login

DATA_FILE = Path(__file__).parents[1] / "data" / "QAQC_Master.xlsx"
BASE_DIR = Path(__file__).resolve().parent.parent
st.set_page_config(page_title="Defect & Rework Tracker", layout="wide")
inject_global_ui()
if not login():
    st.stop()
render_top_nav()
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

st.title("Defect & Rework Tracker")
st.markdown("Monitor defects, rework costs, aging, and performance trends.")

filters = global_filter_sidebar(load_master_data(DATA_FILE))
data = load_master_data(DATA_FILE)
defects = apply_filters(data.get("Defect/Rework Log", pd.DataFrame()), filters, date_column="Date Identified")

if defects.empty:
    st.warning("No defect/rework records available.")
    st.stop()

defects["Date Identified"] = pd.to_datetime(defects["Date Identified"], errors="coerce")
defects["Date Closed"] = pd.to_datetime(defects["Date Closed"], errors="coerce")
defects["Aging Days"] = (defects["Date Closed"].fillna(pd.Timestamp("today")) - defects["Date Identified"]).dt.days

c1, c2, c3, c4 = st.columns(4)
c1.metric("Total Defects", len(defects))
c2.metric("Open Defects", int((defects["Status"].str.lower() == "open").sum()))
c3.metric("Closed Defects", int((defects["Status"].str.lower() == "closed").sum()))
closure_rate = int((defects["Status"].str.lower() == "closed").sum() / max(1, len(defects)) * 100)
c4.metric("Defect Closure Rate", f"{closure_rate}%")

c5, c6, c7 = st.columns(3)
rework_cost = defects["Rework Cost"].sum() if "Rework Cost" in defects.columns else 0
rework_hours = defects["Rework Manhours"].sum() if "Rework Manhours" in defects.columns else 0
c5.metric("Total Rework Cost", f"${rework_cost:,.2f}")
c6.metric("Total Rework Manhours", f"{rework_hours:,.1f}")
defect_density = int(len(defects) / max(1, len(defects)) * 100)
c7.metric("Defect Density", f"{defect_density}%")

st.markdown("---")
table_cols = [col for col in ["Defect_ID", "Project", "Discipline", "Area/Location", "Description", "Root Cause", "Responsible Contractor", "Date Identified", "Date Closed", "Status", "Rework Cost", "Rework Manhours", "Impact Category", "Preventive Action"] if col in defects.columns]
id_col = "Defect_ID" if "Defect_ID" in defects.columns else None
selected = render_table_with_details(defects, id_col=id_col, table_columns=table_cols, detail_label="Defect")

st.markdown("""
<style>
div[data-testid="stHorizontalBlock"] {
    position: sticky;
    top: 0;
    background-color: white;
    z-index: 999;
    padding-top: 5px;
}
</style>
""", unsafe_allow_html=True)

st.markdown("---")
trend = defects.copy()
if "Date Identified" in trend.columns:
    trend["Month"] = trend["Date Identified"].dt.to_period("M").dt.to_timestamp()
    monthly = trend.groupby("Month").size().reset_index(name="Count")
    st.plotly_chart(px.line(monthly, x="Month", y="Count", title="Monthly Defect Trend", markers=True), use_container_width=True)

project_counts = defects["Project"].value_counts().reset_index()
project_counts.columns = ["Project", "Count"]
st.plotly_chart(px.bar(project_counts, x="Project", y="Count", title="Defects by Project"), use_container_width=True)

discipline_counts = defects["Discipline"].value_counts().reset_index()
discipline_counts.columns = ["Discipline", "Count"]
st.plotly_chart(px.bar(discipline_counts, x="Discipline", y="Count", title="Defects by Discipline"), use_container_width=True)

root_causes = defects["Root Cause"].value_counts().reset_index().head(10)
root_causes.columns = ["Root Cause", "Count"]
st.plotly_chart(px.bar(root_causes, x="Root Cause", y="Count", title="Defects by Root Cause"), use_container_width=True)

aging = defects.groupby("Project")["Aging Days"].mean().reset_index()
st.plotly_chart(px.bar(aging, x="Project", y="Aging Days", title="Defect Aging Analysis"), use_container_width=True)

defects["Date Identified"] = pd.to_datetime(defects["Date Identified"], errors="coerce")

defects["Month"] = defects["Date Identified"].dt.to_period("M").dt.to_timestamp()

cost_trend = (
    defects.groupby("Month")["Rework Cost"]
    .sum()
    .reset_index()
)
cost_trend.columns = ["Month", "Rework Cost"]
st.plotly_chart(px.line(cost_trend, x="Month", y="Rework Cost", title="Rework Cost Trend", markers=True), use_container_width=True)

repeat_defects = defects["Description"].value_counts().reset_index().head(10)
repeat_defects.columns = ["Description", "Count"]
st.plotly_chart(px.bar(repeat_defects, x="Description", y="Count", title="Top 10 Recurring Defects"), use_container_width=True)
