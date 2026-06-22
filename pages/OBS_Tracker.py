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

st.set_page_config(page_title="OBS Tracker", layout="wide")
inject_global_ui()

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
if not login():
    st.stop()
DATA_FILE = Path(__file__).parents[1] / "data" / "QAQC_Master.xlsx"
BASE_DIR = Path(__file__).resolve().parent.parent

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
render_top_nav()

st.title("OBS Tracker")
st.markdown("Track observation reports and monitor closing performance.")

filters = global_filter_sidebar(load_master_data(DATA_FILE))
data = load_master_data(DATA_FILE)
obs = apply_filters(data.get("OBS Log", pd.DataFrame()), filters, date_column="Date_Raised")

if obs.empty:
    st.warning("No OBS records found for the selected filters.")
    st.stop()

c1, c2, c3, c4 = st.columns(4)
c1.metric("Total OBS", len(obs))
c2.metric("Open OBS", int((obs["Status"].str.lower() == "open").sum()))
c3.metric("Closed OBS", int((obs["Status"].str.lower() == "closed").sum()))
c4.metric("Closeout %", f"{int((obs["Status"].str.lower() == "closed").sum() / max(1, len(obs)) * 100)}%")

st.markdown("---")
st.subheader("OBS Records")
table_cols = [col for col in ["OBS_ID", "Project", "Status", "Responsible_Person", "Due_Date"] if col in obs.columns]
id_col = "OBS_ID" if "OBS_ID" in obs.columns else None
selected = render_table_with_details(obs, id_col=id_col, table_columns=table_cols, detail_label="OBS")

st.markdown("---")
status_counts = obs["Status"].str.title().value_counts().reset_index()
status_counts.columns = ["Status", "Count"]
sub1, sub2 = st.columns(2)
sub1.plotly_chart(px.pie(status_counts, values="Count", names="Status", title="OBS Status"), use_container_width=True)

if "Due_Date" in obs.columns:
    obs["Aging Days"] = (pd.to_datetime("today") - obs["Due_Date"]).dt.days
    aging = obs.groupby("Project")["Aging Days"].mean().reset_index()
    sub2.plotly_chart(px.bar(aging, x="Project", y="Aging Days", title="OBS Aging Analysis"), use_container_width=True)

trend = obs.copy()
if "Date_Raised" in trend.columns:
    trend["Month"] = trend["Date_Raised"].dt.to_period("M").dt.to_timestamp()
    trend = trend.groupby(["Month", "Status"]).size().reset_index(name="Count")
    st.plotly_chart(px.line(trend, x="Month", y="Count", color="Status", title="OBS Trend"), use_container_width=True)
