import streamlit as st
import pandas as pd
import plotly.express as px
import time
from click import style
from pathlib import Path
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
        background: #0b1320;
    }

    #MainMenu, footer, header {
        visibility: hidden;
    }

    .block-container {
        padding: 1rem 2rem;
    }

    /* KPI CARD */
    .kpi-card {
        padding: 16px;
        border-radius: 14px;
        color: white;
        background: linear-gradient(135deg, #1f2937, #111827);
        box-shadow: 0 8px 20px rgba(0,0,0,0.35);
        transition: all 0.25s ease-in-out;
    }

    /* ✅ THIS is your hover effect (correct place) */
    .kpi-card:hover {
        transform: translateY(-6px) scale(1.03);
        box-shadow: 0 10px 30px rgba(0,0,0,0.4);
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

    </style>
    """, unsafe_allow_html=True)

# =========================
# HEADER
# =========================
def render_header():
    col1, col2, col3 = st.columns([1,3,1])

    
    with col2:
        st.markdown("<h3 style='text-align:center;color:white;'>QA/QC DASHBOARD</h3>", unsafe_allow_html=True)

            
# =========================
# NAVIGATION (TOP)
# =========================

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
def render_kpi_cards(kpis, cols_per_row=2):

    # split into rows of 2
    rows = [kpis[i:i + cols_per_row] for i in range(0, len(kpis), cols_per_row)]

    for row in rows:
        cols = st.columns(cols_per_row)

        for i, kpi in enumerate(row):

            with cols[i]:

                label = kpi.get("label", "")
                value = kpi.get("value", 0)
                color = kpi.get("color", "#2563eb")
                delta = kpi.get("delta", None)

                st.markdown(
                    f"""
                    <div style="
                        background: linear-gradient(135deg, {color}, #111827);
                        padding: 18px;
                        border-radius: 16px;
                        color: white;
                        box-shadow: 0 8px 20px rgba(0,0,0,0.35);
                    ">
                        <div style="font-size:13px; opacity:0.8;">
                            {label}
                        </div>

                        <div style="font-size:30px; font-weight:700; margin-top:6px;">
                            {value}
                        </div>

                        {f"<div style='font-size:12px;color:#22c55e;'>▲ {delta}%</div>" if delta is not None else ""}
                    </div>
                    """,
                    unsafe_allow_html=True
                )

# =========================
# SECTION WRAPPER
# =========================
def render_section_container(title):
    st.markdown(f"### {title}", unsafe_allow_html=True)
    st.markdown("---", unsafe_allow_html=True)


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
    if not isinstance(df, pd.DataFrame) or df.empty:
        st.info("No data available")
        return None

    display_df = df.copy()

    if table_columns:
        valid_cols = [c for c in table_columns if c in display_df.columns]
        if valid_cols:
            display_df = display_df[valid_cols]

    st.subheader(detail_label)
    st.dataframe(display_df, use_container_width=True)

    if id_col and id_col in df.columns:
        selected_id = st.selectbox(
            f"Select {detail_label} ID",
            df[id_col].dropna().astype(str).unique()
        )

        selected_row = df[df[id_col].astype(str) == selected_id]

        st.write("Selected Record")
        st.dataframe(selected_row, use_container_width=True)

        return selected_row


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
    st.markdown("### 🧭 Page Navigation", unsafe_allow_html=True)

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

 


def render_top_nav():
    st.markdown("### QA/QC Dashboard Navigation", unsafe_allow_html=True)

    if st.button("🏠 Dashboard"):
        st.switch_page("app.py")

    if st.button("🏗 Concrete Tracker"):
        st.switch_page("pages/Concrete_Tracker.py")

    if st.button("📛 NCR Log"):
        st.switch_page("pages/NCR_Tracker.py")

    if st.button("👁 OBS Log"):
        st.switch_page("pages/OBS_Tracker.py")

    if st.button("📋 Audit"):
        st.switch_page("pages/Audit.py")

    if st.button("🔍 Surveillance"):
        st.switch_page("pages/Surveillance.py")

    if st.button("📚 Lessons Learned"):
        st.switch_page("pages/Lessons_Learned.py")

    if st.button("📁 Document Register"):
        st.switch_page("pages/Document_Register.py")
    
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
# UI STYLING
# =========================
def inject_global_ui():
    
    st.markdown(
        """
        <style>
    
            /* KPI Hover Effect */
            .kpi-card {
            transition: all 0.25s ease;
            cursor: pointer;
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
        transform: translateY(-6px) scale(1.03);
        box-shadow: 0 10px 30px rgba(0,0,0,0.4);
    }
    .kpi-card {
    transition: all 0.25s ease;
}
    </style>
    """, unsafe_allow_html=True)


# =========================
# IMAGE FINDER
# =========================



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



def apply_filters(df, filters=None, date_column=None):

    if not isinstance(df, pd.DataFrame):
        return df

    filtered_df = df.copy()

    if isinstance(filters, dict):
        for col, value in filters.items():
            if value is not None and col in filtered_df.columns:
                filtered_df = filtered_df[
                    filtered_df[col] == value
                ]

    if date_column and date_column in filtered_df.columns:
        filtered_df[date_column] = pd.to_datetime(
            filtered_df[date_column],
            errors="coerce"
        )
        filtered_df = filtered_df.dropna(
            subset=[date_column]
        )

    return filtered_df
