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
st.set_page_config(page_title="Document Status", layout="wide")
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

st.title("Document Status")
st.markdown("Monitor AFC, IFR, IFA, IFC and superseded document compliance.")

filters = global_filter_sidebar(load_master_data(DATA_FILE))
data = load_master_data(DATA_FILE)
docs = apply_filters(data.get("Document Register", pd.DataFrame()), filters, date_column="Issue_Date")

if docs.empty:
    st.warning("No document register records available.")
    st.stop()

c1, c2, c3, c4 = st.columns(4)
c1.metric("Total Documents", len(docs))

afc = int(docs[docs["Document_Type"].str.upper() == "AFC"].shape[0]) if "Document_Type" in docs.columns else 0
c2.metric("AFC Documents", afc)
non_afc = len(docs) - afc
c3.metric("Non-AFC Documents", non_afc)
compliance_pct = int(afc / max(1, len(docs)) * 100)
c4.metric("AFC Compliance", f"{compliance_pct}%")

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
table_cols = [col for col in ["Document_ID", "Project", "Document_Type", "Status", "Revision", "Issue_Date", "Due_Date"] if col in docs.columns]
id_col = "Document_ID" if "Document_ID" in docs.columns else None
selected = render_table_with_details(docs, id_col=id_col, table_columns=table_cols, detail_label="Document")

st.markdown("---")
pie_data = docs["Document_Type"].value_counts().reset_index()
pie_data.columns = ["Document_Type", "Count"]
st.plotly_chart(px.pie(pie_data, values="Count", names="Document_Type", title="Document Status Breakdown"), use_container_width=True)

if "Project" in docs.columns:
    project_docs = docs["Project"].value_counts().reset_index()
    project_docs.columns = ["Project", "Count"]
    st.plotly_chart(px.bar(project_docs, x="Project", y="Count", title="Documents by Project"), use_container_width=True)
