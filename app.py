import streamlit as st
# =========================
# CONFIG (MUST BE FIRST)
# =========================
st.set_page_config(
    page_title="Evomec QA/QC Executive Dashboard",
    page_icon="🏗️",
    layout="wide",
    initial_sidebar_state="expanded",
)
from pathlib import Path
from utils import (
    load_master_data,
    global_filter_sidebar,
    inject_enterprise_theme,
    render_header,
    render_top_nav,
    extract_projects,
    render_line_chart,
    render_bar_chart,
    render_table,
    render_kpi_cards,
    build_kpis,
)
from auth import login
import pandas as pd
# =========================
# PATHS
# =========================
BASE_DIR = Path(__file__).resolve().parent

EXCEL_FILE = BASE_DIR / "data" / "QAQC_Master.xlsx"
ASSETS = BASE_DIR / "assets"

EVOMEC_LOGO = ASSETS / "evomec_logo.png"
NLNG_LOGO = ASSETS / "nlng_logo.png"



if not login():
    st.stop()

# =========================
# INIT STATE (FIRST THING)
# =========================



# =========================
# THEME
# =========================
inject_enterprise_theme()
render_header()
render_top_nav()

# =========================
# DATA PREVIEW
# =========================
#for name, df in data.items():
#    st.markdown(f"### {name}")
#    render_table(df, height=250)

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

st.markdown(
    """
<div class="dashboard-hero">
    <div class="hero-eyebrow">Executive quality oversight</div>
    <h1>Evomec QA/QC Executive Dashboard</h1>
    <p>A consolidated quality management console for construction projects, live registers, performance indicators, and executive review.</p>
</div>
""",
    unsafe_allow_html=True
)

st.sidebar.title("Evomec QA/QC Executive")

try:
    data = load_master_data(EXCEL_FILE)
except FileNotFoundError as err:
    st.error(err)
    st.stop()

filtered_data = global_filter_sidebar(data)
projects = extract_projects(filtered_data)
project_count = len(projects)

kpis = build_kpis(filtered_data)
st.markdown('<div class="section-heading">Quality Performance Snapshot</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="section-caption">Key project, compliance, observation, inspection, and delivery indicators.</div>',
    unsafe_allow_html=True
)
render_kpi_cards(kpis)


st.markdown('<div class="section-heading">Data Source Overview</div>', unsafe_allow_html=True)
cols = st.columns(3)
cols[0].metric("Data Sheets", len(data))
cols[1].metric("Last Refresh", st.session_state.get("last_refresh", "On load"))
cols[2].metric(
    "Records Loaded",
    sum(len(df) for df in data.values() if isinstance(df, pd.DataFrame))
)


if "Daily Reports" in filtered_data:
    st.markdown('<div class="section-heading">Daily Reports Preview</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="section-caption">Recent daily report records from the active project filter.</div>',
        unsafe_allow_html=True
    )
    render_table(filtered_data["Daily Reports"].head(10), height=300)
else:
    st.info("Daily Reports sheet is not available in the data source.")


# render_workspace()

sheet_names = list(filtered_data.keys())

if len(sheet_names) > 0:
    first_df = filtered_data[sheet_names[0]]

    st.markdown('<div class="section-heading">Trend & Distribution</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="section-caption">A quick visual readout from the first available filtered data sheet.</div>',
        unsafe_allow_html=True
    )

    col1, col2 = st.columns(2)

    with col1:
        if "Date" in first_df.columns and len(first_df.columns) > 1:
            num_col = first_df.select_dtypes(include="number").columns
            if len(num_col) > 0:
                render_line_chart(first_df, "Date", num_col[0], "Trend Analysis")

    with col2:
        if len(first_df.select_dtypes(include="number").columns) > 0:
            num_col = first_df.select_dtypes(include="number").columns[0]
            render_bar_chart(first_df, first_df.columns[0], num_col, "Distribution")



# =========================
# PROJECT LIST
# =========================

st.sidebar.caption(f"Total Projects: {project_count}")
