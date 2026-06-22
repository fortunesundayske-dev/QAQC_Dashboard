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
    render_navigation,
    render_top_nav
)
from auth import login

DATA_FILE = Path(__file__).parents[1] / "data" / "QAQC_Master.xlsx"
BASE_DIR = Path(__file__).resolve().parent.parent
st.set_page_config(page_title="Daily Reports", layout="wide")
inject_global_ui()
if not login():
    st.stop()
render_navigation()
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

st.title("Daily Reports")
st.markdown("Track daily site reports and progress summaries across all projects.")

filters = global_filter_sidebar(load_master_data(DATA_FILE))
data = load_master_data(DATA_FILE)
reports = apply_filters(data.get("Daily Reports", pd.DataFrame()), filters, date_column="Report_Date")

if reports.empty:
    st.warning("No daily report records available.")
    st.stop()

c1, c2, c3 = st.columns(3)
c1.metric("Total Reports", len(reports))
project_counts = reports["Project"].value_counts().reset_index()
project_counts.columns = ["Project", "Count"]
c2.metric("Projects Covered", project_counts.shape[0])
avg_reports = int(len(reports) / max(1, project_counts.shape[0]))
c3.metric("Avg Reports per Project", avg_reports)

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
table_cols = [col for col in ["Report_ID", "Project", "Discipline", "Report_Date", "Summary", "Status"] if col in reports.columns]
id_col = "Report_ID" if "Report_ID" in reports.columns else None
selected = render_table_with_details(reports, id_col=id_col, table_columns=table_cols, detail_label="Daily Report")

st.markdown("---")
if "Report_Date" in reports.columns:
    trend = reports.copy()
    trend["Month"] = trend["Report_Date"].dt.to_period("M").dt.to_timestamp()
    trend = trend.groupby("Month").size().reset_index(name="Reports")
    st.plotly_chart(px.line(trend, x="Month", y="Reports", title="Daily Report Submission Trend", markers=True), use_container_width=True)

if "Project" in reports.columns:
    st.plotly_chart(px.bar(project_counts, x="Project", y="Count", title="Daily Reports by Project"), use_container_width=True)
