import streamlit as st
import utils
from pathlib import Path
from utils import load_master_data, load_company_logo, render_line_chart, render_table, global_filter_sidebar, build_gradient_cards, inject_global_ui, _find_image_path, render_navigation, inject_enterprise_theme, render_top_nav, extract_projects, render_bar_chart, render_kpi_cards, render_header, render_kpi_strip, render_workspace, render_top_nav, render_drilldown
from auth import login
# =========================
# PATHS
# =========================
BASE_DIR = Path(__file__).resolve().parent

EXCEL_FILE = BASE_DIR / "data" / "QAQC_Master.xlsx"
ASSETS = BASE_DIR / "assets"

EVOMEC_LOGO = ASSETS / "evomec_logo.png"
NLNG_LOGO = ASSETS / "nlng_logo.png"

render_navigation()
# =========================
# DATA LOAD
# =========================
data = load_master_data("data/QAQC_Master.xlsx")

# =========================
# CONFIG (MUST BE FIRST)
# =========================
st.set_page_config(
    page_title="Evomec QA/QC Executive Dashboard",
    page_icon="🏗️",
    layout="wide",
    initial_sidebar_state="expanded",
)
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
render_workspace()

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

projects = extract_projects(data)
project_count = len(projects)

ncr_df = data.get("NCR Log", pd.DataFrame())
obs_df = data.get("OBS Log", pd.DataFrame())
itr_df = data.get("ITR Log", pd.DataFrame())
concrete_df = data.get("Concrete Tracker", pd.DataFrame())
audit_df = data.get("Audit Register", pd.DataFrame())
surv_df = data.get("Surveillance Register", pd.DataFrame())
doc_df = data.get("Document Register", pd.DataFrame())
lessons_df = data.get("Lessons Learned", pd.DataFrame())

kpis = [
    {"label": "Total Projects", "value": project_count, "color": "#2563eb"},
    {"label": "Daily Reports", "value": len(data.get("Daily Reports", pd.DataFrame())), "color": "#047857"},
    {"label": "Open NCR", "value": int((ncr_df["Status"] == "Open").sum()) if "Status" in ncr_df.columns else 0, "color": "#dc2626"},
    {"label": "Closed NCR", "value": int((ncr_df["Status"] == "Closed").sum()) if "Status" in ncr_df.columns else 0, "color": "#14b8a6"},
    {"label": "Open OBS", "value": int((obs_df["Status"] == "Open").sum()) if "Status" in obs_df.columns else 0, "color": "#f59e0b"},
    {"label": "Closed OBS", "value": int((obs_df["Status"] == "Closed").sum()) if "Status" in obs_df.columns else 0, "color": "#10b981"},
    {"label": "Open ITR", "value": int((itr_df["Status"] == "Open").sum()) if "Status" in itr_df.columns else 0, "color": "#f97316"},
    {"label": "Closed ITR", "value": int((itr_df["Status"] == "Closed").sum()) if "Status" in itr_df.columns else 0, "color": "#22c55e"},
    {"label": "Cancelled ITR", "value": int((itr_df["Status"] == "Cancelled").sum()) if "Status" in itr_df.columns else 0, "color": "#e22b13"},
    {"label": "Awaiting Survey Report ITR", "value": int((itr_df["Status"] == "Awaiting Survey Report").sum()) if "Status" in itr_df.columns else 0, "color": "#e0d63e"},
    {"label": "Concrete Pours", "value": len(concrete_df), "color": "#0ea5e9"},
    {"label": "Audits Planned", "value": int(audit_df["Status"].notna().sum()) if "Status" in audit_df.columns else 0, "color": "#8b5cf6"},
    {"label": "Surveillance Planned", "value": int(surv_df["Status"].notna().sum()) if "Status" in surv_df.columns else 0, "color": "#a855f7"},
    {"label": "Lessons Learned", "value": len(lessons_df), "color": "#22d3ee"},
]

render_kpi_cards(kpis)
inject_global_ui()

st.markdown("---")
st.subheader("Data Source Overview")
cols = st.columns(3)
cols[0].metric("Data Sheets", len(data))
cols[1].metric("Last Refresh", st.session_state.get("last_refresh", "On load"))
cols[2].metric("Records Loaded", sum(len(df) for df in data.values()))


if "Daily Reports" in data:
    render_table(data["Daily Reports"].head(10), height=300)
else:
    st.info("Daily Reports sheet is not available in the data source.")

st.markdown("---")

render_top_nav()
render_workspace()



sheet_names = list(data.keys())

if len(sheet_names) > 0:
    first_df = data[sheet_names[0]]

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
projects = extract_projects(data)
project_count = len(projects)

st.sidebar.caption(f"Total Projects: {project_count}")

# =========================
# SESSION STATE
# =========================
if "global_project" not in st.session_state:
    st.session_state.global_project = "All"

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