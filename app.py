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
    inject_global_ui,
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
st.divider()

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

st.sidebar.title("Evomec QA/QC Executive")
st.title("Evomec QA/QC Executive Dashboard")
st.markdown("A consolidated quality management console for construction projects with automated analytics and executive insights.")

try:
    data = load_master_data(EXCEL_FILE)
except FileNotFoundError as err:
    st.error(err)
    st.stop()



import pandas as pd

projects = set()

for df in data.values():

    # 🔥 STRICT TYPE CHECK (prevents crash)
    if not isinstance(df, pd.DataFrame):
        continue

    # 🔥 COLUMN CHECK SAFELY
    if "Project" not in df.columns:
        continue

    # 🔥 CLEAN EXTRA SAFETY
    if df.empty:
        continue

    projects.update(
        df["Project"].dropna().astype(str).unique()
    )

# 1. LOAD DATA
data = load_master_data(EXCEL_FILE)

# 2. APPLY FILTER
filtered_data = global_filter_sidebar(data)

# 3. COMPUTE PROJECTS FROM FILTERED DATA
projects = extract_projects(filtered_data)
project_count = len(projects)

# 4. BUILD KPIs (NOW IT WORKS)
kpis = build_kpis(filtered_data)

# 5. RENDER
render_kpi_cards(kpis)


st.write(type(filtered_data))
st.write(list(filtered_data.keys()))
# 5. RENDER UI AFTER KPI BUILD

inject_global_ui()


st.subheader("Data Source Overview")
cols = st.columns(3)
cols[0].metric("Data Sheets", len(data))
cols[1].metric("Last Refresh", st.session_state.get("last_refresh", "On load"))
cols[2].metric("Records Loaded", sum(len(df) for df in data.values()))


if "Daily Reports" in filtered_data:
    render_table(filtered_data["Daily Reports"].head(10), height=300)
else:
    st.info("Daily Reports sheet is not available in the data source.")


# render_workspace()

sheet_names = list(filtered_data.keys())

if len(sheet_names) > 0:
    first_df = filtered_data[sheet_names[0]]

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


# =========================
# FILTER UI
# =========================
selected_project = st.sidebar.selectbox(
    "Project",
    ["All"] + projects,
    index=(
        ["All"] + projects).index(st.session_state.global_project)
        if st.session_state.global_project in projects
        else 0,
    key="global_project_filter"
)

st.session_state.global_project = selected_project

# =========================
# FILTER LOGIC
# =========================
if selected_project == "All":
    filtered_data = data
else:
    filtered_data = {
        k: df[df["Project"] == selected_project]
        if isinstance(df, pd.DataFrame) and "Project" in df.columns
        else df
        for k, df in data.items()
    }