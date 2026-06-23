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
st.set_page_config(page_title="ITR Tracker", layout="wide")
inject_global_ui()
if not login():
    st.stop()
render_navigation()
render_top_nav()

st.title("ITR Tracker")
st.markdown("Inspection and Test Records with completion status and trend analytics.")

filters = global_filter_sidebar(load_master_data(DATA_FILE))
data = load_master_data(DATA_FILE)
itr = apply_filters(data.get("ITR Log", pd.DataFrame()), filters, date_column="Date")

# Load ITR data
itr_df = data.get("ITR Log", pd.DataFrame())

# Filters
col1, col2, col3 = st.columns(3)

with col1:
    project_filter = st.selectbox(
        "Project",
        ["All"] + sorted(itr_df["Project"].dropna().unique().tolist())
    )

with col2:
    discipline_filter = st.selectbox(
        "Discipline",
        ["All"] + sorted(itr_df["Discipline"].dropna().unique().tolist())
    )

with col3:
    status_filter = st.selectbox(
        "Status",
        ["All"] + sorted(itr_df["Status"].dropna().unique().tolist())
    )

# Apply filters
filtered_df = itr_df.copy()

if project_filter != "All":
    filtered_df = filtered_df[filtered_df["Project"] == project_filter]

if discipline_filter != "All":
    filtered_df = filtered_df[filtered_df["Discipline"] == discipline_filter]

if status_filter != "All":
    filtered_df = filtered_df[filtered_df["Status"] == status_filter]

# Display filtered data
st.dataframe(filtered_df, use_container_width=True)

if itr.empty:
    st.warning("No ITR records found.")
    st.stop()

c1, c2, c3, c4 = st.columns(4)
c1.metric("Total ITRs", len(itr))
c2.metric("Open ITRs", int((itr["Status"].str.lower() == "open").sum()))
c3.metric("Closed ITRs", int((itr["Status"].str.lower() == "closed").sum()))
c4.metric("Completion %", f"{int((itr["Status"].str.lower() == "closed").sum() / max(1, len(itr)) * 100)}%")

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
st.subheader("ITR Records")
table_cols = [col for col in ["ITR_ID", "Project", "Discipline", "Activity", "Status"] if col in itr.columns]
id_col = "ITR_ID" if "ITR_ID" in itr.columns else None
selected = render_table_with_details(itr, id_col=id_col, table_columns=table_cols, detail_label="ITR")

st.markdown("---")
status_counts = itr["Status"].str.title().value_counts().reset_index()
status_counts.columns = ["Status", "Count"]
col1, col2 = st.columns(2)
col1.plotly_chart(px.pie(status_counts, values="Count", names="Status", title="ITR Pass vs Fail / Completion"), use_container_width=True)

trend = itr.copy()
if "Date" in trend.columns:
    trend["Month"] = trend["Date"].dt.to_period("M").dt.to_timestamp()
    trend = trend.groupby(["Month", "Status"]).size().reset_index(name="Count")
    col2.plotly_chart(px.line(trend, x="Month", y="Count", color="Status", title="ITR Monthly Trend"), use_container_width=True)
