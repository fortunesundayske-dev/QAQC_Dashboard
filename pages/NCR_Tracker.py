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

st.set_page_config(page_title="NCR Tracker", layout="wide")
inject_global_ui()

if not login():
    st.stop()
DATA_FILE = Path(__file__).parents[1] / "data" / "QAQC_Master.xlsx"
BASE_DIR = Path(__file__).resolve().parent.parent

render_navigation()
render_top_nav()

st.title("NCR Tracker")
st.markdown("Monitor non-conformance records, aging, and closeout performance across projects.")

filters = global_filter_sidebar(load_master_data(DATA_FILE))
data = load_master_data("data/QAQC_Master.xlsx")
ncr = apply_filters(data.get("NCR Log", pd.DataFrame()), filters, date_column="Date Raised")

if ncr.empty:
    st.warning("No NCR records found for the selected filter criteria.")
    st.stop()

ncr["Aging"] = (pd.to_datetime("today") - ncr["Date Raised"]).dt.days

c1, c2, c3, c4 = st.columns(4)
c1.metric("Total NCRs", len(ncr))
c2.metric("Open NCRs", int((ncr["Status"].str.lower() == "open").sum()))
c3.metric("Closed NCRs", int((ncr["Status"].str.lower() == "closed").sum()))
closed_pct = int((ncr["Status"].str.lower() == "closed").sum() / max(1, len(ncr)) * 100)
c4.metric("Closeout %", f"{closed_pct}%")

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
st.subheader("NCR Table")
table_cols = [col for col in ["NCR_ID", "Project", "Discipline", "Description", "Date Raised", "Due_Date", "Status", "Responsible_Person", "Aging"] if col in ncr.columns]
id_col = "NCR_ID" if "NCR_ID" in ncr.columns else None
selected = render_table_with_details(ncr, id_col=id_col, table_columns=table_cols, detail_label="NCR")

st.markdown("---")
status_counts = ncr["Status"].str.title().value_counts().reset_index()
status_counts.columns = ["Status", "Count"]
sub1, sub2 = st.columns(2)
sub1.plotly_chart(px.pie(status_counts, values="Count", names="Status", title="NCR Open vs Closed"), use_container_width=True)

aging = ncr.groupby("Project")["Aging"].mean().reset_index()
sub2.plotly_chart(px.bar(aging, x="Project", y="Aging", title="NCR Aging Analysis"), use_container_width=True)

st.markdown("---")
trend = ncr.copy()
if "Date Raised" in trend.columns:
    trend["Month"] = trend["Date Raised"].dt.to_period("M").dt.to_timestamp()
    trend = trend.groupby(["Month", "Status"]).size().reset_index(name="Count")
    st.plotly_chart(px.line(trend, x="Month", y="Count", color="Status", title="NCR Trend"), use_container_width=True)

open_by_project = ncr[ncr["Status"].str.lower() == "open"].groupby("Project").size().reset_index(name="Open NCRs")
if not open_by_project.empty:
    st.plotly_chart(px.bar(open_by_project, x="Project", y="Open NCRs", title="Open NCRs by Project"), use_container_width=True)

closeout_percentage = ncr.groupby("Project").apply(lambda x: int((x["Status"].str.lower() == "closed").sum() / max(1, len(x)) * 100)).reset_index(name="Closeout %")
st.plotly_chart(px.bar(closeout_percentage, x="Project", y="Closeout %", title="NCR Closeout Percentage"), use_container_width=True)
