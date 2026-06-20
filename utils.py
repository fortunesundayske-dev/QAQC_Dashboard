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
        background: #f3f4f6;
        color: #111827;
    }

    section[data-testid="stSidebar"] {
        background: #e5e7eb;
    }

    .kpi-card {
        transition: all 0.25s ease;
        cursor: pointer;
    }

    .kpi-card:hover {
        transform: translateY(-6px) scale(1.03);
        box-shadow: 0 10px 30px rgba(0,0,0,0.2);
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
def render_kpi_cards(kpis):
    rows = [kpis[i:i+2] for i in range(0, len(kpis), 2)]

    for row in rows:
        cols = st.columns(2)

        for i, kpi in enumerate(row):
            with cols[i]:

                color = kpi.get("color", "#2563eb")

                st.markdown(f"""
                <div style="
                    background: linear-gradient(135deg, {color}, #111827);
                    padding: 20px;
                    border-radius: 16px;
                    color: white;
                    border-left: 6px solid {color};
                    box-shadow: 0 8px 20px rgba(0,0,0,0.25);
                ">
                    <div style="font-size:13px; opacity:0.8;">
                        {kpi['label']}
                    </div>

                    <div style="font-size:32px; font-weight:700; margin-top:6px;">
                        {kpi['value']}
                    </div>
                </div>
                """, unsafe_allow_html=True)

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

#def build_gradient_cards(kpis):
    # split into rows of 2
    #rows = [kpis[i:i+2] for i in range(0, len(kpis), 2)]

    #for row in rows:
        #cols = st.columns(2)

        #for i, kpi in enumerate(row):
            #with cols[i]:
                #st.markdown(
                    #f"""
                    #<div style="
                      #  background: {kpi.get('color', '#1f2937')};
                       # padding: 20px;
                       # border-radius: 16px;
                       # color: white;
                      #  box-shadow: 0 10px 20px rgba(0,0,0,0.15);
                       # min-height: 110px;
                    #">
                     #   <div style="font-size:14px; opacity:0.9;">
                       #     {kpi['label']}
                      #  </div>
                      #  <div style="font-size:32px; font-weight:700; margin-top:10px;">
                      #      {kpi['value']}
                      #  </div>
                   # </div>
                   # """,
                   # unsafe_allow_html=True
              #  )



def render_top_nav():
    st.markdown("### QA/QC Dashboard Navigation")

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
    
    st.markdown("""
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



def apply_filters(df, filters=None, date_column=None):
    if not isinstance(df, pd.DataFrame):
        return df

    filtered_df = df.copy()

    # =========================
    # 1. COLUMN FILTERS
    # =========================
    if isinstance(filters, dict) and filters:

        for col, value in filters.items():

            if (
                value is not None
                and col in filtered_df.columns
                and value != "All"
            ):
                filtered_df = filtered_df[filtered_df[col] == value]

    # =========================
    # 2. DATE CLEANING (SAFE)
    # =========================
    if date_column and date_column in filtered_df.columns:

        filtered_df = filtered_df.copy()

        filtered_df[date_column] = pd.to_datetime(
            filtered_df[date_column],
            errors="coerce"
        )

        filtered_df = filtered_df.dropna(subset=[date_column])

        # OPTIONAL: sort for charts (VERY IMPORTANT)
        filtered_df = filtered_df.sort_values(by=date_column)

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