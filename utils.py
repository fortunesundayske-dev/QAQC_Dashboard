from click import style
import streamlit as st
import pandas as pd
from pathlib import Path
import plotly.express as px
import uuid

BASE_DIR = Path(__file__).resolve().parent

EXCEL_FILE = BASE_DIR / "data" / "QAQC_Master.xlsx"
ASSETS = BASE_DIR / "assets"
EVOMEC_LOGO = ASSETS / "evomec_logo.png"
NLNG_LOGO = ASSETS / "nlng_logo.png"
# =========================
# DATA LOADING (DICT SYSTEM)
# =========================

def load_master_data(file_path):
    try:
        file_path = Path(file_path)

        if not file_path.exists():
            st.error("Excel file not found")
            return {}

        xls = pd.ExcelFile(file_path)

        return {
            sheet: pd.read_excel(xls, sheet)
            for sheet in xls.sheet_names
        }

    except Exception as e:
        st.error(f"Error loading master data: {e}")
        return {}
# =========================
# THEME
# =========================
def inject_enterprise_theme():
    st.markdown("""
    <style>

    .main {
        background: #e5e7eb;
    }

    #MainMenu, footer, header {
        visibility: hidden;
    }

    .block-container {
        padding: 1rem 2rem;
    }

    /* KPI CARD */
    .kpi {
        padding: 16px;
        border-radius: 14px;
        color: white;
        background: linear-gradient(135deg, #1f2937, #111827);
        box-shadow: 0 8px 20px rgba(0,0,0,0.35);
    }

    /* KPI CARD */
    .kpi {
        padding: 16px;
        border-radius: 14px;
        color: white;
        background: linear-gradient(135deg, #1f2937, #111827);
        box-shadow: 0 8px 20px rgba(0,0,0,0.35);
    }

    .kpi-card {
        transition: all 0.25s ease;
        cursor: pointer;
    }

    .kpi-card:hover {
        transform: translateY(-6px) scale(1.03);
        box-shadow: 0 0 25px rgba(255,255,255,0.15);
    }

 .kpi-title {
        font-size: 13px;
        opacity: 0.8;
    }

    .kpi-value {
        font-size: 26px;
        font-weight: 700;
        margin-top: 5px;
    }

    /* NAV TABS */
    .nav-bar {
        display:flex;
        gap:18px;
        padding:10px 0;
        font-weight:500;
        color:#cbd5e1;
    }

    .nav-item {
        cursor:pointer;
    }

    .nav-item:hover {
        color:white;
    }

    </style>
    """, unsafe_allow_html=True)

# =========================
# HEADER
# =========================
def render_header():
    col1, col2, col3 = st.columns([1,3,1])

    with col1:
        st.markdown("**🏗 EVOMEC**")

    with col2:
        st.markdown("<h3 style='text-align:center;color:white;'>QA/QC DASHBOARD</h3>", unsafe_allow_html=True)

    with col3:
        st.markdown("**NLNG 🔷**")
        
# =========================
# NAVIGATION (TOP)
# =========================
def render_top_nav():
    tabs = ["Dashboard", "Audit", "Concrete", "CTQ", "NCR", "OBS", "ITR", "Reports"]

    if "page" not in st.session_state:
        st.session_state.page = "Dashboard"

    cols = st.columns(len(tabs))

    for i, tab in enumerate(tabs):
        with cols[i]:
            if st.button(tab, key=f"nav_{tab}"):
                st.session_state.page = tab

# =========================
# MOBILE NAV
# =========================
def render_mobile_nav():
    st.selectbox("Quick Navigation",
        ["Dashboard","Audit","Concrete","CTQ","NCR","OBS","ITR","Reports"]
    )

# =========================
# KPI CARDS
# =========================
def render_kpi_cards(kpis):
    rows = [kpis[i:i+2] for i in range(0, len(kpis), 2)]

    for row in rows:
        cols = st.columns(2)

        for i, kpi in enumerate(row):
            with cols[i]:
                st.markdown(
                f"""
                <div class="kpi-card" style="
                    background: linear-gradient(135deg, {kpi.get('color', '#2563eb')}, #111827);
                    padding: 20px;
                    border-radius: 16px;
                    color: white;
                    border-left: 5px solid {kpi.get('color', '#2563eb')};
                    margin-bottom: 12px;
                ">
        <div style="font-size:14px; opacity:0.9;">
            {kpi['label']}
        </div>

        <div style="font-size:32px; font-weight:700; margin-top:8px;">
            {kpi['value']}
        </div>
    </div>
    """,
    unsafe_allow_html=True
)
                st.markdown(
    f"""
    <div class="kpi-card" style="
        background: linear-gradient(
            135deg,
            {kpi.get('color', '#2563eb')},
            #111827
        );
        padding:20px;
        border-radius:16px;
        color:white;
        border-left:5px solid {kpi.get('color', '#2563eb')};
    ">
        <div style="font-size:14px;">
            {kpi['label']}
        </div>

        <div style="
            font-size:32px;
            font-weight:700;
            margin-top:10px;
        ">
            {kpi['value']}
        </div>
    </div>
    """,
    unsafe_allow_html=True
)
st.divider()

st.subheader("📊 Executive Analytics")

# =========================
# SECTION WRAPPER
# =========================
def render_section_container(title):
    st.markdown(f"### {title}")
    st.markdown("---")


# =========================
# FILTERS (SAFE)
# =========================
def global_filter_sidebar(data, page="main"):
    
    st.sidebar.header("Global Filters")

    if not isinstance(data, dict):
        return data

    # =========================
    # EXTRACT PROJECTS SAFELY
    # =========================
    projects = set()

    for df in data.values():
        if isinstance(df, __import__("pandas").DataFrame) and "Project" in df.columns:
            projects.update(df["Project"].dropna().astype(str).unique())

    projects = sorted(list(projects))

    if not projects:
        st.sidebar.info("No projects found")
        return data

    # =========================
    # SESSION STATE FIX
    # =========================
    if "global_project" not in st.session_state:
        st.session_state.global_project = "All"

    # =========================
    # SAFE SELECTBOX (IMPORTANT FIX)
    # =========================
    selected_project = st.sidebar.selectbox(
        "Project",
        ["All"] + projects,
        index=0,
        key="global_project_selectbox"   # 🔥 FIXED STATIC KEY
    )

    st.session_state.global_project = selected_project

    # =========================
    # FILTER DATA
    # =========================
    if selected_project == "All":
        return data

    filtered = {}

    for k, df in data.items():
        if isinstance(df, __import__("pandas").DataFrame) and "Project" in df.columns:
            filtered[k] = df[df["Project"] == selected_project]
        else:
            filtered[k] = df

    return filtered

# =========================
# TABLES
# =========================
def render_table(df, height=300):
    if isinstance(df, pd.DataFrame) and not df.empty:
        st.dataframe(df, height=height, use_container_width=True)
    else:
        st.info("No data")


def render_table_with_details(
    df,
    id_col=None,
    table_columns=None,
    detail_label="Details"
):
    
    
    if df is None or df.empty:
        st.info("No data available")
        return

    display_df = df.copy()

    # filter columns safely
    if table_columns:
        valid_cols = [c for c in table_columns if c in display_df.columns]
        if valid_cols:
            display_df = display_df[valid_cols]

    st.subheader(detail_label)
    st.dataframe(display_df, use_container_width=True)

    # optional drill-down
    if id_col and id_col in df.columns:
        selected = st.selectbox(
            f"Select {id_col}",
            df[id_col].dropna().astype(str).unique()
        )

        st.dataframe(
            df[df[id_col].astype(str) == selected],
            use_container_width=True
        )

# =========================
# UTILITIES
# =========================
def _find_image_path(path):
    p = Path(path)
    return str(p) if p.exists() else None

def load_company_logo(path):
    p = Path(path)
    return str(p) if p.exists() else None


def extract_projects(data):
    projects = set()

    for df in data.values():
        if isinstance(df, pd.DataFrame) and "Project" in df.columns:
            projects.update(df["Project"].dropna().astype(str))

    return sorted(projects)

# =========================
# NAV (FULL)
# =========================

def render_navigation():
    st.markdown("### 🧭 Page Navigation")

    pages = {
        "🏗 Concrete": "pages/Concrete_Tracker.py",
        "📛 NCR": "pages/NCR_Tracker.py",
        "👁 OBS": "pages/OBS_Tracker.py",
        "📋 Audit": "pages/Audit_Surveillance.py",
        "🏠 Executive Dashboard": "app.py",
        "📊 CTQ Dashboard": "pages/CTR_Dashboard.py",
        "📅 Daily Reports": "pages/Daily_Reports.py",
        "🔧 Defect Rework": "pages/Defect_Rework_Tracker.py",
        "📄 Document Status": "pages/Document_Status.py",
        "📊 Executive Summary": "pages/Executive_Summary.py",
        "📦 ITR Tracker": "pages/ITR_Tracker.py",
        "📘 Lessons Learnt": "pages/Lessons_Learnt.py",
        "📋 Management Summary": "pages/Management_Summary.py"
    }

    for label, page in pages.items():
        if st.button(label, key=f"nav_{label}"):
            st.switch_page(page)

    
    st.markdown("""
    <div style="
        display:flex;
        justify-content:space-between;
        align-items:center;
        padding:10px 20px;
        background:#111827;
        border-radius:10px;
        margin-bottom:10px;
        color:white;
    ">
        <div><b>🏗 QA/QC Dashboard</b></div>
        <div>Executive View</div>
    </div>
    """, unsafe_allow_html=True)

# =========================
# KPI CARDS
# =========================

def build_gradient_cards(kpis):
    # split into rows of 2
    rows = [kpis[i:i+2] for i in range(0, len(kpis), 2)]

    for row in rows:
        cols = st.columns(2)

        for i, kpi in enumerate(row):
            with cols[i]:
                st.markdown(
                    f"""
                    <div style="
                        background: {kpi.get('color', '#1f2937')};
                        padding: 20px;
                        border-radius: 16px;
                        color: white;
                        box-shadow: 0 10px 20px rgba(0,0,0,0.15);
                        min-height: 110px;
                    ">
                        <div style="font-size:14px; opacity:0.9;">
                            {kpi['label']}
                        </div>
                        <div style="font-size:32px; font-weight:700; margin-top:10px;">
                            {kpi['value']}
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True
                )

    st.markdown('</div>', unsafe_allow_html=True)


# =========================
# UI STYLING
# =========================

def inject_global_ui():
    st.markdown("""
    <style>
    
    /* KPI Hover Effect */
    .kpi-card {
        transition: all 0.25s ease;
        cursor: pointer;
    }

    .kpi-card:hover {
        transform: translateY(-6px) scale(1.03);
        box-shadow: 0 0 25px rgba(255,255,255,0.15);
    }
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
        background: #2d2d2d;
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

# =========================
# IMAGE FINDER
# =========================



def apply_filters(df, filters=None, date_column=None):

    if not isinstance(df, pd.DataFrame):
        return df

    filtered_df = df.copy()

    # =========================
    # 1. GLOBAL FILTERS (SAFE)
    # =========================
    if isinstance(filters, dict):

        for col, value in filters.items():

            # 🚨 SAFE CHECK (FIXES YOUR ERROR)
            if value is not None and col in filtered_df.columns:

                filtered_df = filtered_df[filtered_df[col] == value]

    # =========================
    # 2. DATE FILTER (SAFE)
    # =========================
    if date_column and date_column in filtered_df.columns:
        filtered_df[date_column] = pd.to_datetime(
            filtered_df[date_column],
            errors="coerce"
        )

        filtered_df = filtered_df.dropna(subset=[date_column])

    return filtered_df
    """
    Flexible table renderer for QAQC dashboard pages.
    Supports:
    - column selection
    - ID column awareness
    - safe dataframe rendering
    """
    if not isinstance(df, pd.DataFrame) or df.empty:
        st.info("No data available")
        return None

    display_df = df.copy()

    # =========================
    # COLUMN FILTERING
    # =========================
    if table_columns:
        valid_cols = [c for c in table_columns if c in display_df.columns]
        if valid_cols:
            display_df = display_df[valid_cols]

    # =========================
    # DISPLAY TABLE
    # =========================
    st.subheader(detail_label)
    st.dataframe(display_df, use_container_width=True)

    # =========================
    # OPTIONAL ID INFO
    # =========================
    if id_col and id_col in df.columns:
        selected_id = st.selectbox(
            f"Select {detail_label} ID",
            df[id_col].dropna().astype(str).unique()
        )

        selected_row = df[df[id_col].astype(str) == selected_id]

        st.write("Selected Record:")
        st.dataframe(selected_row, use_container_width=True)

        return selected_row

    return display_df



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
import plotly.express as px

def render_line_chart(df, x, y, title="Trend"):
    if df.empty:
        st.info("No data for chart")
        return

    fig = px.line(df, x=x, y=y, title=title, markers=True)
    st.plotly_chart(fig, use_container_width=True)


def render_bar_chart(df, x, y, title="Bar Chart"):
    if df.empty:
        st.info("No data for chart")
        return

    fig = px.bar(df, x=x, y=y, title=title)
    st.plotly_chart(fig, use_container_width=True)


def render_pie_chart(df, names, values, title="Distribution"):
    if df.empty:
        st.info("No data for chart")
        return

    fig = px.pie(df, names=names, values=values, title=title)
    st.plotly_chart(fig, use_container_width=True)