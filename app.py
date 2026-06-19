import streamlit as st
import utils
from pathlib import Path
from utils import load_master_data, load_company_logo, render_table, global_filter_sidebar, build_gradient_cards, inject_global_ui, _find_image_path, render_navigation
from auth import login
from utils import extract_projects
from utils import render_navigation

render_navigation()
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


BASE_DIR = Path(__file__).resolve().parent

EXCEL_FILE = BASE_DIR / "data" / "QAQC_Master.xlsx"
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

st.set_page_config(page_title="QAQC Dashboard", layout="wide")

# ---------------------------
# DEVICE DETECTION (JS BRIDGE)
# ---------------------------
device_check = """
<script>
const width = window.innerWidth;
const isMobile = width < 768;

window.parent.postMessage(
    {type: "device_type", mobile: isMobile},
    "*"
);
</script>
"""

mode = st.query_params.get("mode", "auto")
is_mobile = (mode == "mobile")
if "is_mobile" not in st.session_state:
    st.session_state.is_mobile = False

query_params = st.query_params
mode = query_params.get("mode", "auto")

col1, col2, col3, col4, col5 = st.columns(5)

if col1.button("Dashboard"):
    st.session_state.page = "Dashboard"
if col2.button("Audit"):
    st.session_state.page = "Audit"
if col3.button("Concrete"):
    st.session_state.page = "Concrete"
if col4.button("Procurement"):
    st.session_state.page = "Procurement"
if col5.button("Reports"):
    st.session_state.page = "Reports"

page = st.session_state.get("page", "Dashboard")

st.set_page_config(page_title="QAQC Dashboard", layout="wide")

# ==========================
# TOP NAVIGATION BAR
# ==========================

col1, col2, col3, col4, col5 = st.columns(5)

with col1:
    st.page_link("app.py", label="📊 Dashboard")

with col2:
    st.page_link(
        "pages/Audit_Surveillance.py",
        label="📋 Audit"
    )

with col3:
    st.page_link(
        "pages/Concrete_Tracker.py",
        label="🏗 Concrete"
    )

with col4:
    st.page_link(
        "pages/CTQ_Dashboard.py",
        label="📦 CTQ"
    )

with col5:
    st.page_link(
        "pages/Daily_Reports.py",
        label="📑 Reports"
    )

st.divider()

# ==========================
# MOBILE NAVIGATION
# ==========================

page = st.selectbox(
    "📱 Navigate",
    [
        "Dashboard",
        "Audit",
        "Concrete",
        "CTQ",
        "Reports",
        "Rework Tracker",
        "Document Status",
        "ITR Tracker",
        "Lessons Learned",
        "Management Summary",
        "NCR Tracker",
        "OBS Tracker"
    ]
)

if page == "Dashboard":
    st.switch_page("app.py")

elif page == "Audit":
    st.switch_page("pages/Audit_Surveillance.py")

elif page == "Concrete":
    st.switch_page("pages/Concrete_Tracker.py")

elif page == "CTQ":
    st.switch_page("pages/CTQ_Dashboard.py")

elif page == "Reports":
    st.switch_page("pages/Daily_Reports.py")

elif page == "Rework Tracker":
    st.switch_page("pages/Defect_Rework_Tracker.py")

elif page == "Document Status":
    st.switch_page("pages/Document_Status.py")

elif page == "ITR Tracker":
    st.switch_page("pages/ITR_Tracker.py")

elif page == "Lessons Learned":
    st.switch_page("pages/Lessons_Learned.py")

elif page == "Management Summary":
    st.switch_page("pages/Management_Executive_Summary.py")

elif page == "NCR Tracker":
    st.switch_page("pages/NCR_Tracker.py")

elif page == "OBS Tracker":
    st.switch_page("pages/OBS_Tracker.py")
    
