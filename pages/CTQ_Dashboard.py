import streamlit as st
import pandas as pd
import plotly.express as px
import utils
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


render_top_nav()

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
st.set_page_config(page_title="CTQ Dashboard", layout="wide")
inject_global_ui()

st.title("CTQ Management")
st.markdown("Track CTQ compliance and identify failure categories across projects.")

filters = global_filter_sidebar(load_master_data(DATA_FILE))
data = load_master_data(DATA_FILE)
ctq = apply_filters(data.get("CTQ Log", pd.DataFrame()), filters, date_column="Date")

if ctq.empty:
    st.warning("No CTQ records available.")
else:
    table_cols = [col for col in ["CTQ_ID", "Project", "Discipline", "Activity", "CTQ Description", "Acceptance Criteria", "Target Value", "Actual Value", "Status", "Date", "Responsible Inspector"] if col in ctq.columns]
    id_col = "CTQ_ID" if "CTQ_ID" in ctq.columns else None
    render_table_with_details(ctq, id_col=id_col, table_columns=table_cols, detail_label="CTQ")

status_counts = ctq["Status"].str.title().value_counts().reset_index()
status_counts.columns = ["Status", "Count"]
col1, col2 = st.columns(2)
col1.plotly_chart(px.pie(status_counts, values="Count", names="Status", title="CTQ Pass vs Fail"), use_container_width=True)

if "Project" in ctq.columns:
    project_compliance = ctq.groupby("Project").apply(lambda x: int((x["Status"].str.lower() == "passed").sum() / max(1, len(x)) * 100)).reset_index(name="Compliance %")
    col2.plotly_chart(px.bar(project_compliance, x="Project", y="Compliance %", title="CTQ Compliance by Project"), use_container_width=True)

if "Discipline" in ctq.columns:
    discipline_compliance = ctq.groupby("Discipline").apply(lambda x: int((x["Status"].str.lower() == "passed").sum() / max(1, len(x)) * 100)).reset_index(name="Compliance %")
    st.plotly_chart(px.bar(discipline_compliance, x="Discipline", y="Compliance %", title="CTQ Compliance by Discipline"), use_container_width=True)

failure_pareto = ctq[ctq["Status"].str.lower() == "failed"]["CTQ Description"].value_counts().reset_index().head(10)
failure_pareto.columns = ["Category", "Count"]
st.plotly_chart(px.bar(failure_pareto, x="Category", y="Count", title="CTQ Failure Pareto Chart"), use_container_width=True)
