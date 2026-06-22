import streamlit as st
import pandas as pd
import plotly.express as px
import time
from click import style
from pathlib import Path
import uuid
import html

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
    inject_global_ui()
    return
    st.markdown("""
    <style>

    .main {
        background: #0b1320;
    }

    #MainMenu, footer, header {
        visibility: hidden;
    }

    [data-testid="stSidebarNav"],
    section[data-testid="stSidebar"] nav,
    div[data-testid="stSidebarNavItems"] {
        display: none !important;
    }

    [data-testid="stSidebarNav"],
    section[data-testid="stSidebar"] nav {
        display: none;
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
    st.markdown(
        """
<div class="app-bar">
    <div>
        <div class="app-bar__eyebrow">EVOMEC GLOBAL SERVICES</div>
        <div class="app-bar__title">QA/QC Executive Dashboard</div>
    </div>
    <div class="app-bar__status">Quality Control Management System</div>
</div>
""",
        unsafe_allow_html=True
    )

            
# =========================
# NAVIGATION (TOP)
# =========================

# =========================
# MOBILE NAV
# =========================
def get_navigation_pages():
    pages_dir = BASE_DIR / "pages"
    label_overrides = {
        "Access_Admin": "Access Admin",
        "Audit_Surveillance": "Audit & Surveillance",
        "Concrete_Tracker": "Concrete Tracker",
        "CTQ_Dashboard": "CTQ Dashboard",
        "Daily_Reports": "Daily Reports",
        "Defect_Rework_Tracker": "Defect & Rework",
        "Document_Status": "Document Status",
        "Executive_Dashboard": "Executive Analytics",
        "ITR_Tracker": "ITR Tracker",
        "Learning_Academy": "Learning Academy",
        "Lessons_Learned": "Lessons Learned",
        "Management_Executive_Summary": "Management Summary",
        "NCR_Tracker": "NCR Tracker",
        "OBS_Tracker": "OBS Tracker",
        "Quality_Tools": "Quality Tools",
        "Standards_Library": "Standards Library",
        "User_Profile": "User Profile",
    }
    preferred_order = [
        "Executive Home",
        "Executive Analytics",
        "Quality Tools",
        "Standards Library",
        "Learning Academy",
        "Concrete Tracker",
        "NCR Tracker",
        "OBS Tracker",
        "Audit & Surveillance",
        "CTQ Dashboard",
        "Daily Reports",
        "ITR Tracker",
        "Document Status",
        "Defect & Rework",
        "Lessons Learned",
        "Management Summary",
        "User Profile",
        "Access Admin",
    ]

    pages = {
        "Executive Home": "app.py",
    }

    if pages_dir.exists():
        for page_file in sorted(pages_dir.glob("*.py")):
            page_key = page_file.stem
            if page_key.startswith("_"):
                continue
            label = label_overrides.get(page_key, page_key.replace("_", " ").title())
            pages[label] = f"pages/{page_file.name}"

    role = st.session_state.get("auth", {}).get("role") or st.session_state.get("role")
    if role != "admin":
        pages.pop("Access Admin", None)

    ordered = {
        label: pages[label]
        for label in preferred_order
        if label in pages
    }
    for label in sorted(pages):
        if label not in ordered:
            ordered[label] = pages[label]
    return ordered


def render_mobile_nav():
    pages = get_navigation_pages()
    selected = st.selectbox("Quick Navigation", list(pages.keys()))
    if st.button("Open selected page", key="mobile_nav_open", use_container_width=True):
        st.switch_page(pages[selected])

# =========================
# KPI CARDS
# =========================
def render_kpi_cards(kpis):
    cols = st.columns(4)  # 4 per row grid
    accents = ["#38bdf8", "#22c55e", "#f59e0b", "#ef4444"]

    for i, kpi in enumerate(kpis):
        with cols[i % 4]:
            accent = accents[i % len(accents)]
            st.markdown(
                f"""
<div class="kpi-card" style="--accent: {accent};">
    <div class="kpi-card__topline"></div>
    <div class="kpi-title">{html.escape(str(kpi['label']))}</div>
    <div class="kpi-value">{html.escape(str(kpi['value']))}</div>
</div>
""",
                unsafe_allow_html=True
            )


    
def build_kpis(filtered_data):
    projects = set()

    for df in filtered_data.values():
        if isinstance(df, pd.DataFrame) and "Project" in df.columns:
            projects.update(df["Project"].dropna().astype(str))

    project_count = len(projects)

    ncr_df = filtered_data.get("NCR Log", pd.DataFrame())
    obs_df = filtered_data.get("OBS Log", pd.DataFrame())
    itr_df = filtered_data.get("ITR Log", pd.DataFrame())
    concrete_df = filtered_data.get("Concrete Tracker", pd.DataFrame())
    audit_df = filtered_data.get("Audit Register", pd.DataFrame())
    surv_df = filtered_data.get("Surveillance Register", pd.DataFrame())
    lessons_df = filtered_data.get("Lessons Learned", pd.DataFrame())

    return [
        {"label": "Total Projects", "value": project_count},
        {"label": "Daily Reports", "value": len(filtered_data.get("Daily Reports", pd.DataFrame()))},

        {"label": "Open NCR", "value": int((ncr_df["Status"] == "Open").sum()) if "Status" in ncr_df.columns else 0},
        {"label": "Closed NCR", "value": int((ncr_df["Status"] == "Closed").sum()) if "Status" in ncr_df.columns else 0},

        {"label": "Open OBS", "value": int((obs_df["Status"] == "Open").sum()) if "Status" in obs_df.columns else 0},
        {"label": "Closed OBS", "value": int((obs_df["Status"] == "Closed").sum()) if "Status" in obs_df.columns else 0},

        {"label": "Open ITR", "value": int((itr_df["Status"] == "Open").sum()) if "Status" in itr_df.columns else 0},
        {"label": "Closed ITR", "value": int((itr_df["Status"] == "Closed").sum()) if "Status" in itr_df.columns else 0},

        {"label": "Concrete Pours", "value": len(concrete_df)},
        {"label": "Audits Planned", "value": len(audit_df)},
        {"label": "Surveillance Planned", "value": len(surv_df)},
        {"label": "Lessons Learned", "value": len(lessons_df)},
    ]

# =========================
# SECTION WRAPPER
# =========================

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
    pages = get_navigation_pages()

    with st.expander("Page Navigation", expanded=False):
        selected = st.selectbox(
            "Select Page",
            list(pages.keys()),
            key="nav_dropdown"
        )

        if st.button("Go", key="nav_go", use_container_width=True):
            st.switch_page(pages[selected])
    return
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
    pages = get_navigation_pages()

    st.sidebar.markdown(
        """
<div class="side-brand">
    <div class="side-brand__mark">E</div>
    <div>
        <div class="side-brand__name">EVOMEC</div>
        <div class="side-brand__sub">QA/QC Command Centre</div>
    </div>
</div>
""",
        unsafe_allow_html=True,
    )
    st.sidebar.markdown('<div class="side-menu-title">Menu</div>', unsafe_allow_html=True)

    for label, page in pages.items():
        if st.sidebar.button(label, key=f"side_nav_{label}", use_container_width=True):
            st.switch_page(page)

    st.sidebar.markdown(
        f'<div class="side-status">System Status: <strong>Online</strong><br>{len(pages)} modules available</div>',
        unsafe_allow_html=True,
    )
    
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
    :root {
        --bg: #08111f;
        --panel: #0f1b2d;
        --panel-soft: #13243a;
        --line: rgba(148, 163, 184, 0.18);
        --text: #e5edf8;
        --muted: #94a3b8;
        --accent: #38bdf8;
        --success: #22c55e;
        --warning: #f59e0b;
        --danger: #ef4444;
    }

    #MainMenu, footer, header {
        visibility: hidden;
    }

    [data-testid="stSidebarNav"],
    [data-testid="stSidebarNavItems"],
    [data-testid="stSidebarNavLinkContainer"],
    [data-testid="stSidebarNavLink"] {
        display: none !important;
    }

    .stApp {
        background:
            radial-gradient(circle at top left, rgba(56, 189, 248, 0.16), transparent 34rem),
            linear-gradient(135deg, #07101e 0%, #0b1728 48%, #111827 100%);
        color: var(--text);
    }

    .block-container {
        max-width: 1480px;
        padding: 1.15rem 2.25rem 2.5rem;
    }

    h1, h2, h3, h4, p, label, span {
        letter-spacing: 0;
    }

    h1, h2, h3 {
        color: #f8fafc;
    }

    .app-bar {
        align-items: center;
        background: rgba(15, 27, 45, 0.82);
        border: 1px solid var(--line);
        border-radius: 8px;
        box-shadow: 0 18px 45px rgba(0, 0, 0, 0.26);
        display: flex;
        justify-content: space-between;
        margin-bottom: 0.9rem;
        padding: 0.85rem 1rem;
    }

    .app-bar__eyebrow, .hero-eyebrow {
        color: #7dd3fc;
        font-size: 0.72rem;
        font-weight: 760;
        letter-spacing: 0.06em;
        text-transform: uppercase;
    }

    .app-bar__title {
        color: #f8fafc;
        font-size: 1.05rem;
        font-weight: 780;
        margin-top: 0.12rem;
    }

    .app-bar__status {
        background: rgba(34, 197, 94, 0.12);
        border: 1px solid rgba(34, 197, 94, 0.28);
        border-radius: 999px;
        color: #bbf7d0;
        font-size: 0.78rem;
        font-weight: 700;
        padding: 0.42rem 0.72rem;
        white-space: nowrap;
    }

    .nav-hint {
        align-items: center;
        border: 1px solid var(--line);
        border-radius: 8px;
        color: var(--muted);
        display: flex;
        min-height: 2.65rem;
        padding: 0 0.9rem;
    }

    .dashboard-hero {
        background: linear-gradient(135deg, rgba(15, 27, 45, 0.96), rgba(19, 36, 58, 0.76));
        border: 1px solid var(--line);
        border-radius: 8px;
        box-shadow: 0 22px 55px rgba(0, 0, 0, 0.28);
        min-height: 9.25rem;
        padding: 1.35rem 1.5rem;
    }

    .dashboard-hero h1 {
        color: #f8fafc;
        font-size: 2.2rem;
        font-weight: 800;
        line-height: 1.08;
        margin: 0.35rem 0 0.55rem;
    }

    .dashboard-hero p {
        color: #b6c2d2;
        font-size: 0.98rem;
        margin: 0;
        max-width: 780px;
    }

    .logo-panel {
        align-items: center;
        background: rgba(248, 250, 252, 0.92);
        border: 1px solid rgba(255, 255, 255, 0.34);
        border-radius: 8px;
        display: flex;
        justify-content: center;
        min-height: 9.25rem;
        padding: 1rem;
    }

    .section-heading {
        color: #f8fafc;
        font-size: 1.05rem;
        font-weight: 780;
        margin: 1.25rem 0 0.55rem;
    }

    .section-caption {
        color: var(--muted);
        font-size: 0.86rem;
        margin-top: -0.3rem;
        margin-bottom: 0.65rem;
    }

    .kpi-card {
        background: linear-gradient(180deg, rgba(19, 36, 58, 0.96), rgba(10, 19, 33, 0.98));
        border: 1px solid var(--line);
        border-radius: 8px;
        box-shadow: 0 14px 32px rgba(0, 0, 0, 0.28);
        min-height: 104px;
        overflow: hidden;
        padding: 15px 16px 16px;
        position: relative;
        transition: transform 0.2s ease, border-color 0.2s ease, box-shadow 0.2s ease;
    }

    .kpi-card:hover {
        border-color: var(--accent);
        box-shadow: 0 18px 42px rgba(0, 0, 0, 0.34);
        transform: translateY(-3px);
    }

    .kpi-card__topline {
        background: var(--accent);
        height: 3px;
        left: 0;
        position: absolute;
        right: 0;
        top: 0;
    }

    .kpi-title {
        color: #aab8ca;
        font-size: 0.78rem;
        font-weight: 720;
        margin-top: 0.25rem;
        text-transform: uppercase;
    }

    .kpi-value {
        color: #f8fafc;
        font-size: 1.9rem;
        font-weight: 800;
        line-height: 1;
        margin-top: 0.75rem;
    }

    section[data-testid="stSidebar"] {
        background: linear-gradient(180deg, #0b1628, #101827);
        border-right: 1px solid var(--line);
    }

    section[data-testid="stSidebar"] h1,
    section[data-testid="stSidebar"] h2,
    section[data-testid="stSidebar"] h3,
    section[data-testid="stSidebar"] label,
    section[data-testid="stSidebar"] p,
    section[data-testid="stSidebar"] span {
        color: #e5edf8;
    }

    div[data-testid="stMetric"] {
        background: rgba(15, 27, 45, 0.88);
        border: 1px solid var(--line);
        border-radius: 8px;
        padding: 0.85rem 1rem;
    }

    div[data-testid="stMetricLabel"] {
        color: var(--muted);
    }

    div[data-testid="stDataFrame"] {
        border: 1px solid var(--line);
        border-radius: 8px;
        overflow: hidden;
    }

    .stButton button,
    div[data-testid="stPopover"] button {
        background: linear-gradient(135deg, #0ea5e9, #2563eb);
        border: 1px solid rgba(255, 255, 255, 0.12);
        border-radius: 8px;
        color: white;
        font-weight: 720;
        min-height: 2.45rem;
    }

    .stButton button:hover,
    div[data-testid="stPopover"] button:hover {
        border-color: rgba(125, 211, 252, 0.72);
        color: white;
        filter: brightness(1.06);
    }

    div[data-baseweb="select"] > div {
        background-color: rgba(15, 27, 45, 0.96);
        border-color: var(--line);
        border-radius: 8px;
    }

    div[data-baseweb="select"] span {
        color: #e5edf8;
    }

    .stAlert {
        border-radius: 8px;
    }

    div[role="radiogroup"] {
        display: flex;
        flex-wrap: wrap;
        gap: 0.45rem;
        margin: 0.35rem 0 0.85rem;
    }

    div[role="radiogroup"] label {
        background: rgba(14, 165, 233, 0.12);
        border: 1px solid rgba(56, 189, 248, 0.22);
        border-radius: 999px;
        color: var(--text);
        min-height: 2.35rem;
        padding: 0.35rem 0.65rem;
    }

    @media (max-width: 900px) {
        .block-container {
            padding: 0.8rem 1rem 2rem;
        }

        .app-bar {
            align-items: flex-start;
            flex-direction: column;
            gap: 0.65rem;
        }

        .dashboard-hero h1 {
            font-size: 1.65rem;
        }

        .auth-panel,
        .auth-panel--hero {
            padding: 1rem;
        }

        .auth-panel h1 {
            font-size: 1.45rem;
        }

        div[data-testid="stTabs"] div[role="tablist"] {
            gap: 0.35rem;
            overflow-x: auto;
            white-space: nowrap;
        }

        div[data-testid="stTabs"] button[role="tab"] {
            min-width: max-content;
        }
    }

    .auth-shell {
        margin: 0.25rem 0 1rem;
    }

    .auth-panel,
    .tool-card,
    .standard-card,
    .learning-card,
    .security-card {
        background: color-mix(in srgb, var(--panel) 92%, transparent);
        border: 1px solid var(--line);
        border-radius: 8px;
        box-shadow: 0 16px 38px rgba(2, 8, 23, 0.18);
        padding: 1rem;
    }

    .auth-panel--hero {
        padding: 1.35rem 1.4rem;
    }

    .auth-panel h1 {
        color: var(--text);
        font-size: 2rem;
        line-height: 1.1;
        margin: 0.35rem 0 0.55rem;
    }

    .auth-eyebrow,
    .card-eyebrow {
        color: var(--accent);
        font-size: 0.72rem;
        font-weight: 780;
        letter-spacing: 0.06em;
        text-transform: uppercase;
    }

    .security-list {
        display: flex;
        flex-wrap: wrap;
        gap: 0.5rem;
        margin-top: 1rem;
    }

    .security-list span,
    .standard-tag {
        background: rgba(56, 189, 248, 0.1);
        border: 1px solid rgba(56, 189, 248, 0.24);
        border-radius: 999px;
        color: var(--text);
        font-size: 0.78rem;
        font-weight: 700;
        padding: 0.34rem 0.58rem;
    }

    .profile-avatar {
        align-items: center;
        background: linear-gradient(135deg, #0ea5e9, #22c55e);
        border: 2px solid rgba(255, 255, 255, 0.44);
        border-radius: 999px;
        color: white;
        display: flex;
        font-size: 1.3rem;
        font-weight: 800;
        height: 86px;
        justify-content: center;
        margin-bottom: 0.7rem;
        width: 86px;
    }

    .tool-grid {
        display: grid;
        gap: 0.85rem;
        grid-template-columns: repeat(auto-fit, minmax(230px, 1fr));
        margin: 0.8rem 0 1rem;
    }

    .tool-card h3,
    .standard-card h3,
    .learning-card h3,
    .security-card h3 {
        color: var(--text);
        font-size: 1rem;
        margin: 0.35rem 0 0.35rem;
    }

    .tool-card p,
    .standard-card p,
    .learning-card p,
    .security-card p {
        color: var(--muted);
        font-size: 0.88rem;
        margin: 0;
    }

    .standard-card,
    .learning-card {
        margin-bottom: 0.75rem;
    }

    .spotlight-grid {
        display: grid;
        gap: 0.95rem;
        grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
        margin: 0.95rem 0 1.1rem;
    }

    .spotlight-card {
        background:
            linear-gradient(135deg, rgba(56, 189, 248, 0.16), transparent 46%),
            color-mix(in srgb, var(--panel) 94%, transparent);
        border: 1px solid var(--line);
        border-radius: 8px;
        box-shadow: 0 18px 46px rgba(2, 8, 23, 0.2);
        min-height: 154px;
        overflow: hidden;
        padding: 1.05rem;
        position: relative;
        transition: transform 0.28s ease, box-shadow 0.28s ease, border-color 0.28s ease;
    }

    .spotlight-card::after {
        background: radial-gradient(circle, rgba(255, 255, 255, 0.16), transparent 64%);
        content: "";
        height: 140px;
        position: absolute;
        right: -48px;
        top: -48px;
        transition: transform 0.32s ease, opacity 0.32s ease;
        width: 140px;
    }

    .spotlight-card:hover,
    .tool-card:hover,
    .standard-card:hover,
    .learning-card:hover,
    .security-card:hover {
        border-color: rgba(56, 189, 248, 0.58);
        box-shadow: 0 24px 60px rgba(2, 8, 23, 0.28);
        transform: translateY(-5px);
    }

    .spotlight-card:hover::after {
        opacity: 0.9;
        transform: scale(1.16);
    }

    .spotlight-card h3 {
        color: var(--text);
        font-size: 1.06rem;
        margin: 0.42rem 0 0.42rem;
        position: relative;
        z-index: 1;
    }

    .spotlight-card p {
        color: var(--muted);
        font-size: 0.88rem;
        margin: 0;
        position: relative;
        z-index: 1;
    }

    .interactive-chip {
        background: rgba(14, 165, 233, 0.12);
        border: 1px solid rgba(56, 189, 248, 0.22);
        border-radius: 999px;
        color: var(--text);
        display: inline-flex;
        font-size: 0.78rem;
        font-weight: 720;
        margin: 0.24rem 0.24rem 0 0;
        padding: 0.34rem 0.58rem;
    }

    .smooth-panel {
        animation: panelFadeIn 0.42s ease both;
    }

    @keyframes panelFadeIn {
        from {
            opacity: 0;
            transform: translateY(8px);
        }
        to {
            opacity: 1;
            transform: translateY(0);
        }
    }

    @media (prefers-color-scheme: light) {
        :root {
            --bg: #f6f8fb;
            --panel: #ffffff;
            --panel-soft: #edf3f8;
            --line: rgba(15, 23, 42, 0.12);
            --text: #0f172a;
            --muted: #475569;
            --accent: #0369a1;
            --success: #15803d;
            --warning: #b45309;
            --danger: #b91c1c;
        }

        .stApp {
            background:
                radial-gradient(circle at top left, rgba(14, 165, 233, 0.14), transparent 30rem),
                linear-gradient(135deg, #f8fafc 0%, #edf3f8 52%, #ffffff 100%);
            color: var(--text);
        }

        h1, h2, h3,
        .app-bar__title,
        .dashboard-hero h1,
        .kpi-value,
        .tool-card h3,
        .standard-card h3,
        .learning-card h3 {
            color: var(--text);
        }

        .app-bar,
        .dashboard-hero,
        .kpi-card,
        div[data-testid="stMetric"],
        .auth-panel,
        .tool-card,
        .standard-card,
        .learning-card,
        .security-card {
            background: rgba(255, 255, 255, 0.92);
            box-shadow: 0 14px 34px rgba(15, 23, 42, 0.08);
        }

        .dashboard-hero p,
        .section-caption,
        .kpi-title,
        .nav-hint,
        .tool-card p,
        .standard-card p,
        .learning-card p,
        .security-card p {
            color: var(--muted);
        }

        section[data-testid="stSidebar"] {
            background: linear-gradient(180deg, #ffffff, #eef5fb);
        }

        section[data-testid="stSidebar"] h1,
        section[data-testid="stSidebar"] h2,
        section[data-testid="stSidebar"] h3,
        section[data-testid="stSidebar"] label,
        section[data-testid="stSidebar"] p,
        section[data-testid="stSidebar"] span {
            color: var(--text);
        }
    }

    /* Executive dashboard skin */
    .stApp {
        background: #f3f6fb;
        color: #102033;
    }

    .block-container {
        max-width: 1560px;
        padding: 0.9rem 1.15rem 2rem;
    }

    h1, h2, h3 {
        color: #102033;
    }

    .app-bar {
        background: rgba(255, 255, 255, 0.96);
        border: 1px solid rgba(15, 23, 42, 0.08);
        border-radius: 8px;
        box-shadow: 0 10px 26px rgba(15, 23, 42, 0.08);
        color: #102033;
        margin-bottom: 0.75rem;
    }

    .app-bar__eyebrow {
        color: #0f6eb8;
    }

    .app-bar__title {
        color: #102033;
        font-size: 1.12rem;
    }

    .app-bar__status {
        background: #eef6ff;
        border-color: #cfe7ff;
        color: #0f6eb8;
    }

    section[data-testid="stSidebar"] {
        background: linear-gradient(180deg, #09213b 0%, #06182e 100%);
        border-right: 1px solid rgba(255, 255, 255, 0.08);
    }

    section[data-testid="stSidebar"] .stButton button {
        background: transparent;
        border: 0;
        border-radius: 8px;
        box-shadow: none;
        color: #d7e7f7;
        font-size: 0.88rem;
        font-weight: 650;
        justify-content: flex-start;
        min-height: 2.35rem;
        padding-left: 0.85rem;
        text-align: left;
        width: 100%;
    }

    section[data-testid="stSidebar"] .stButton button:hover {
        background: linear-gradient(135deg, #1d73e8, #1596d4);
        color: #ffffff;
        filter: none;
    }

    .side-brand {
        align-items: center;
        border-bottom: 1px solid rgba(255, 255, 255, 0.1);
        display: flex;
        gap: 0.7rem;
        margin-bottom: 0.9rem;
        padding: 0.35rem 0 0.95rem;
    }

    .side-brand__mark {
        align-items: center;
        background: linear-gradient(135deg, #f97316, #0ea5e9);
        border-radius: 8px;
        color: #ffffff;
        display: flex;
        font-size: 1.1rem;
        font-weight: 900;
        height: 2.35rem;
        justify-content: center;
        width: 2.35rem;
    }

    .side-brand__name {
        color: #ffffff;
        font-size: 1.05rem;
        font-weight: 820;
        letter-spacing: 0.02em;
    }

    .side-brand__sub {
        color: #9fb8d3;
        font-size: 0.72rem;
        margin-top: 0.1rem;
    }

    .side-menu-title {
        color: #6fd3ff;
        font-size: 0.72rem;
        font-weight: 800;
        letter-spacing: 0.08em;
        margin: 0.35rem 0 0.45rem;
        text-transform: uppercase;
    }

    .side-status {
        background: rgba(15, 118, 110, 0.18);
        border: 1px solid rgba(45, 212, 191, 0.24);
        border-radius: 8px;
        color: #b7f5ef;
        font-size: 0.78rem;
        margin-top: 0.9rem;
        padding: 0.75rem;
    }

    .dashboard-shell {
        display: grid;
        gap: 0.9rem;
        grid-template-columns: minmax(0, 1fr) 250px;
    }

    .dashboard-main {
        min-width: 0;
    }

    .dashboard-side {
        min-width: 0;
    }

    .metric-grid {
        display: grid;
        gap: 0.75rem;
        grid-template-columns: repeat(4, minmax(0, 1fr));
        margin-bottom: 0.75rem;
    }

    .exec-metric {
        align-items: center;
        background: #ffffff;
        border: 1px solid rgba(15, 23, 42, 0.08);
        border-radius: 8px;
        box-shadow: 0 10px 24px rgba(15, 23, 42, 0.06);
        display: flex;
        gap: 0.8rem;
        min-height: 5.6rem;
        padding: 0.85rem;
    }

    .exec-metric__icon {
        align-items: center;
        background: var(--metric-color, #2563eb);
        border-radius: 8px;
        box-shadow: 0 10px 22px color-mix(in srgb, var(--metric-color, #2563eb) 28%, transparent);
        color: #ffffff;
        display: flex;
        font-size: 1.15rem;
        font-weight: 900;
        height: 2.7rem;
        justify-content: center;
        width: 2.7rem;
    }

    .exec-metric__label {
        color: #1f2f44;
        font-size: 0.78rem;
        font-weight: 800;
    }

    .exec-metric__value {
        color: #0f172a;
        font-size: 1.95rem;
        font-weight: 900;
        line-height: 1;
        margin-top: 0.25rem;
    }

    .exec-metric__sub {
        color: #64748b;
        font-size: 0.72rem;
        margin-top: 0.25rem;
    }

    .exec-panel {
        background: #ffffff;
        border: 1px solid rgba(15, 23, 42, 0.08);
        border-radius: 8px;
        box-shadow: 0 10px 24px rgba(15, 23, 42, 0.06);
        padding: 0.95rem;
    }

    .exec-panel h3 {
        color: #102033;
        font-size: 0.95rem;
        font-weight: 900;
        margin: 0 0 0.75rem;
        text-transform: uppercase;
    }

    .score-ring {
        align-items: center;
        background:
            radial-gradient(circle at center, #ffffff 55%, transparent 57%),
            conic-gradient(#27ae60 0 83%, #e5edf5 83% 100%);
        border-radius: 999px;
        color: #102033;
        display: flex;
        flex-direction: column;
        font-size: 2rem;
        font-weight: 900;
        height: 8.25rem;
        justify-content: center;
        margin: 0.6rem auto;
        width: 8.25rem;
    }

    .score-ring span {
        color: #64748b;
        font-size: 0.72rem;
        font-weight: 800;
    }

    .status-row {
        align-items: center;
        border-bottom: 1px solid #edf2f7;
        display: flex;
        justify-content: space-between;
        padding: 0.45rem 0;
    }

    .status-dot {
        border-radius: 999px;
        display: inline-flex;
        height: 0.62rem;
        margin-right: 0.42rem;
        width: 0.62rem;
    }

    .module-grid {
        display: grid;
        gap: 0.75rem;
        grid-template-columns: repeat(5, minmax(0, 1fr));
        margin-top: 0.75rem;
    }

    .module-card {
        background: #ffffff;
        border: 1px solid rgba(15, 23, 42, 0.08);
        border-radius: 8px;
        box-shadow: 0 10px 24px rgba(15, 23, 42, 0.06);
        min-height: 9.75rem;
        padding: 0.85rem;
    }

    .module-card h3 {
        color: var(--module-color, #2563eb);
        font-size: 0.78rem;
        font-weight: 900;
        margin: 0 0 0.7rem;
        text-transform: uppercase;
    }

    .module-card__stat {
        align-items: center;
        border: 1px solid #edf2f7;
        border-radius: 8px;
        display: flex;
        justify-content: space-between;
        margin-bottom: 0.45rem;
        padding: 0.42rem 0.5rem;
    }

    .module-card__stat strong {
        color: #0f172a;
        font-size: 1rem;
    }

    .module-card__bar {
        background: #eaf1f8;
        border-radius: 999px;
        height: 0.42rem;
        margin: 0.55rem 0;
        overflow: hidden;
    }

    .module-card__bar div,
    .module-card__bar span {
        background: var(--module-color, #2563eb);
        display: block;
        height: 100%;
    }

    @media (max-width: 1180px) {
        .dashboard-shell {
            grid-template-columns: 1fr;
        }

        .metric-grid,
        .module-grid {
            grid-template-columns: repeat(2, minmax(0, 1fr));
        }
    }

    @media (max-width: 760px) {
        .metric-grid,
        .module-grid {
            grid-template-columns: 1fr;
        }

        .app-bar {
            display: block;
        }

        .block-container {
            padding: 0.75rem 0.75rem 1.5rem;
        }
    }
    </style>
    """, unsafe_allow_html=True)


# =========================
# IMAGE FINDER
# =========================


def style_chart(fig):
    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="rgba(15, 27, 45, 0.92)",
        plot_bgcolor="rgba(8, 17, 31, 0.5)",
        font=dict(color="#dbe7f5", family="Inter, Arial, sans-serif"),
        title=dict(font=dict(size=16, color="#f8fafc")),
        margin=dict(l=32, r=24, t=54, b=34),
        legend=dict(bgcolor="rgba(0,0,0,0)", font=dict(color="#cbd5e1")),
    )
    fig.update_xaxes(
        gridcolor="rgba(148, 163, 184, 0.14)",
        linecolor="rgba(148, 163, 184, 0.22)",
        zerolinecolor="rgba(148, 163, 184, 0.18)",
    )
    fig.update_yaxes(
        gridcolor="rgba(148, 163, 184, 0.14)",
        linecolor="rgba(148, 163, 184, 0.22)",
        zerolinecolor="rgba(148, 163, 184, 0.18)",
    )
    return fig


def render_line_chart(df, x, y, title="Trend"):
    if df.empty:
        st.info("No data for chart")
        return

    fig = px.line(df, x=x, y=y, title=title, markers=True)
    fig.update_traces(line=dict(color="#38bdf8", width=3), marker=dict(size=7))
    style_chart(fig)
    st.plotly_chart(fig, use_container_width=True)


def render_bar_chart(df, x, y, title="Bar Chart"):
    if df.empty:
        st.info("No data for chart")
        return

    fig = px.bar(df, x=x, y=y, title=title)
    fig.update_traces(marker_color="#22c55e")
    style_chart(fig)
    st.plotly_chart(fig, use_container_width=True)


def render_pie_chart(df, names, values, title="Distribution"):
    if df.empty:
        st.info("No data for chart")
        return

    fig = px.pie(df, names=names, values=values, title=title)
    fig.update_traces(
        marker=dict(colors=["#38bdf8", "#22c55e", "#f59e0b", "#ef4444", "#a78bfa"])
    )
    style_chart(fig)
    st.plotly_chart(fig, use_container_width=True)


# =========================
# FILTERS (SAFE)
# =========================
def global_filter_sidebar(data):
    st.sidebar.header("Global Filters")

    if not isinstance(data, dict):
        return data

    projects = set()

    for df in data.values():
        if isinstance(df, pd.DataFrame) and "Project" in df.columns:
            projects.update(df["Project"].dropna().astype(str).unique())

    projects = sorted(list(projects))

    if "global_project" not in st.session_state:
        st.session_state.global_project = "All"

    selected_project = st.sidebar.selectbox(
        "Project",
        ["All"] + projects,
        index=0,
        key="global_project_selectbox"
    )

    st.session_state.global_project = selected_project

    # ✅ IMPORTANT FIX STARTS HERE
    if selected_project == "All":
        return data

    filtered = {}

    for k, df in data.items():
        if isinstance(df, pd.DataFrame) and "Project" in df.columns:
            filtered[k] = df[df["Project"] == selected_project]
        else:
            filtered[k] = df

    return filtered   # 🔥 THIS WAS MISSING


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
