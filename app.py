import streamlit as st
from pathlib import Path
from utils import load_master_data, load_company_logo, render_table, global_filter_sidebar, build_gradient_cards, inject_global_ui, _find_image_path
from auth import login

if not login():
    st.stop()

BASE_DIR = Path(__file__).resolve().parent

EXCEL_FILE = BASE_DIR / "data" / "QAQC_Master.xlsx"
LOGO_PATH = BASE_DIR / "assets" / "evomec_logo.png"

asset_dir = Path(__file__).parent / "assets"
LOGO_PATH = _find_image_path(asset_dir / "evomec_logo")

st.set_page_config(
    page_title="Evomec QA/QC Executive Dashboard",
    page_icon="🏗️",
    layout="wide",
    initial_sidebar_state="expanded",
)

inject_global_ui()

st.markdown(
    """
    <style>
        .reportview-container { background-color: #0b1320; color: #e2e8f0; }
        .sidebar .sidebar-content { background: #0f172a; }
        .stButton>button { background-color: #1d4ed8; color: white; }
        .kpi-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(240px, 1fr)); gap: 1rem; }
        .kpi-card { padding: 1.2rem; border-radius: 18px; color: #fff; min-height: 120px; box-shadow: 0 18px 40px rgba(0,0,0,0.2); }
        .kpi-title { font-size: 0.95rem; opacity: 0.8; margin-bottom: 0.5rem; }
        .kpi-value { font-size: 2rem; font-weight: 700; margin-bottom: 0.35rem; }
        .kpi-subtitle { font-size: 0.9rem; opacity: 0.75; }
    </style>
    """,
    unsafe_allow_html=True,
)

st.sidebar.title("Evomec QA/QC Executive")

st.title("Evomec QA/QC Executive Dashboard")
st.markdown("A consolidated quality management console for construction projects with automated analytics and executive insights.")

try:
    data = load_master_data(EXCEL_FILE)
except FileNotFoundError as err:
    st.error(err)
    st.stop()

filters = global_filter_sidebar(data)

projects = sorted({
    row
    for df in data.values()
    if hasattr(df, "columns") and "Project" in df.columns
    for row in df["Project"].dropna().astype(str).unique()
})
project_count = len(projects)

import pandas as pd

projects = set()

for df in data.values():
    if isinstance(df, pd.DataFrame) and "Project" in df.columns:
        projects.update(
            df["Project"].dropna().astype(str).unique()
        )

projects = sorted(projects)
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
    {"label": "Daily Reports", "value": len(data.get("Daily Reports", [])), "color": "#047857"},
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
