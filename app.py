import streamlit as st
import utils
from pathlib import Path
from utils import load_master_data, load_company_logo, render_line_chart, render_table, global_filter_sidebar, build_gradient_cards, inject_global_ui, _find_image_path, render_navigation, inject_enterprise_theme, render_top_nav, extract_projects, render_bar_chart, render_kpi_cards, render_header, render_kpi_strip
from auth import login
# =========================
# CONFIG (MUST BE FIRST)
# =========================
st.set_page_config(
    page_title="Evomec QA/QC Executive Dashboard",
    page_icon="🏗️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# =========================
# AUTH (DO FIRST)
# =========================
if not login():
    st.stop()

# =========================
# THEME
# =========================
inject_enterprise_theme()

# =========================
# HEADER + NAV
# =========================
render_top_nav()

st.divider()

# =========================
# PATHS
# =========================
BASE_DIR = Path(__file__).resolve().parent

EXCEL_FILE = BASE_DIR / "data" / "QAQC_Master.xlsx"
ASSETS = BASE_DIR / "assets"

EVOMEC_LOGO = ASSETS / "evomec_logo.png"
NLNG_LOGO = ASSETS / "nlng_logo.png"
# =========================
# DATA LOAD
# =========================
data = load_master_data(EXCEL_FILE)

# =========================
# FILTERS
# =========================
data = global_filter_sidebar(data)
# =========================
# KPIs (EXAMPLE)
# =========================

st.divider()

# =========================
# DATA PREVIEW
# =========================
for name, df in data.items():
    st.markdown(f"### {name}")
    render_table(df, height=250)

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

build_gradient_cards(kpis)
def render_kpi_card(kpis):
    st.markdown('<div class="kpi-grid">', unsafe_allow_html=True)

    cols = st.columns(len(kpis))

    for i, kpi in enumerate(kpis):
        with cols[i]:
            st.markdown(f"""
            <div class="kpi-card">
                <div class="kpi-title">{kpi['label']}</div>
                <div class="kpi-value">{kpi['value']}</div>
            </div>
            """, unsafe_allow_html=True)

    st.markdown('</div>', unsafe_allow_html=True)

st.markdown("---")
st.subheader("Data Source Overview")
cols = st.columns(3)
cols[0].metric("Data Sheets", len(data))
cols[1].metric("Last Refresh", st.session_state.get("last_refresh", "On load"))
cols[2].metric("Records Loaded", sum(len(df) for df in data.values()))

st.markdown("---")
st.subheader("Source Data Preview")
if "Daily Reports" in data:
    render_table(data["Daily Reports"].head(10), height=300)
else:
    st.info("Daily Reports sheet is not available in the data source.")

st.markdown("---")
st.write("Use the Streamlit sidebar to navigate to modules and apply global filters across pages.")

def render_workspace():
    tab1, tab2, tab3 = st.tabs([
        "📊 Overview",
        "📁 Data Explorer",
        "📈 Analytics"
    ])

    with tab1:
        st.subheader("Project Overview")
        st.write("KPIs, trends, and summary insights go here")

    with tab2:
        st.subheader("Raw Data")
        st.dataframe(st.session_state.get("data", {}))

    with tab3:
        st.subheader("Analytics")
        st.write("Charts (Plotly recommended)")
with st.sidebar:
    st.title("🔍 Global Controls")
    data = global_filter_sidebar(data)

def render_drilldown(df, id_col="ID"):

    if not isinstance(df, pd.DataFrame) or df.empty:
        st.info("No data available")
        return

    if id_col not in df.columns:
        st.error(f"Column '{id_col}' not found")
        return

    # =========================
    # SAFE ID CLEANING
    # =========================
    ids = df[id_col].dropna().astype(str).unique().tolist()

    selected = st.selectbox(
    f"Select {id_col}",
    options=["-- Select --"] + ids,
    key=f"drilldown_{id_col}"
)

    if selected == "-- Select --":
        st.warning("Please select a record to view details")
        return

    # =========================
    # FILTER SAFE MATCH
    # =========================
    selected_row = df[df[id_col].astype(str) == selected]

    # =========================
    # UX IMPROVEMENT: SUMMARY FIRST
    # =========================
    st.subheader("🔎 Record Summary")

    st.dataframe(
        selected_row.head(1),
        use_container_width=True
    )

    # =========================
    # FULL DETAIL EXPANDER
    # =========================
    with st.expander("📄 Full Record Details", expanded=True):
        st.dataframe(
            selected_row,
            use_container_width=True
        )

    return selected_row
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

def project_filter_sidebar(projects, page="main"):
    if "global_project" not in st.session_state:
        st.session_state.global_project = "All"

    selected = st.sidebar.selectbox(
        "Project",
        ["All"] + projects,
        index=(
            ["All"] + projects).index(st.session_state.global_project)
            if st.session_state.global_project in projects
            else 0,
        key=f"global_project_filter_{page}"
    )

    st.session_state.global_project = selected
    return selected

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