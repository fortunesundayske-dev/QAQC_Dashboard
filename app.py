import streamlit as st
import utils
from pathlib import Path
from utils import load_master_data, load_company_logo, render_table, global_filter_sidebar, build_gradient_cards, inject_global_ui, _find_image_path, render_navigation
from auth import login
from utils import extract_projects
from utils import render_navigation

def render_navigation():
    st.markdown("""
    <div class="topbar">
        <div class="brand">🏗 QAQC ENTERPRISE DASHBOARD</div>
    </div>
    """, unsafe_allow_html=True)

    col1, col2, col3, col4, col5 = st.columns(5)

    pages = [
        ("📊 Dashboard", "app.py"),
        ("📋 Audit", "pages/Audit_Surveillance.py"),
        ("🏗 Concrete", "pages/Concrete_Tracker.py"),
        ("📦 CTQ", "pages/CTQ_Dashboard.py"),
        ("📑 Reports", "pages/Daily_Reports.py"),
    ]

    for i, (label, page) in enumerate(pages):
        with [col1, col2, col3, col4, col5][i]:
            if st.button(label):
                st.switch_page(page)

    st.divider()

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
def inject_global_ui():
    st.markdown("""
    <style>

    /* =========================
       ENTERPRISE DARK THEME
    ========================== */
    .main {
        background: #0a0f1c;
        color: #e5e7eb;
        font-family: "Inter", sans-serif;
    }

    /* Hide Streamlit chrome */
    #MainMenu, footer, header {
        visibility: hidden;
    }

    /* =========================
       TOP APP BAR
    ========================== */
    .topbar {
        background: #0f172a;
        padding: 12px 20px;
        border-bottom: 1px solid #1f2937;
        display: flex;
        justify-content: space-between;
        align-items: center;
    }

    .brand {
        font-size: 18px;
        font-weight: 700;
        color: #60a5fa;
    }

    /* =========================
       KPI STRIP
    ========================== */
    .kpi-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
        gap: 12px;
        margin-top: 10px;
    }

    .kpi-card {
        background: linear-gradient(145deg, #111827, #0b1220);
        border: 1px solid #1f2937;
        border-radius: 14px;
        padding: 14px;
        box-shadow: 0 8px 18px rgba(0,0,0,0.25);
    }

    .kpi-title {
        font-size: 12px;
        color: #94a3b8;
    }

    .kpi-value {
        font-size: 22px;
        font-weight: 700;
        margin-top: 6px;
        color: #f8fafc;
    }

    /* =========================
       FILTER BAR
    ========================== */
    section[data-testid="stSidebar"] {
        background: #0f172a;
        border-right: 1px solid #1e293b;
    }

    /* =========================
       DATA TABLE
    ========================== */
    .stDataFrame {
        border-radius: 12px;
        overflow: hidden;
        border: 1px solid #1f2937;
    }

    /* =========================
       BUTTONS
    ========================== */
    .stButton button {
        background: #2563eb;
        color: white;
        border-radius: 8px;
        border: none;
        padding: 6px 12px;
    }

    .stButton button:hover {
        background: #1d4ed8;
    }

    /* =========================
       CARDS HOVER EFFECT
    ========================== */
    .kpi-card:hover {
        transform: translateY(-2px);
        border: 1px solid #3b82f6;
        transition: 0.2s ease-in-out;
    }

    </style>
    """, unsafe_allow_html=True)

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
def render_kpi_strip(kpis):
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
        options=["-- Select --"] + ids
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
