import streamlit as st
import pandas as pd
import plotly.express as px
import time
import base64
from click import style
from pathlib import Path
import uuid
import html
from urllib.parse import quote

BASE_DIR = Path(__file__).resolve().parent

EXCEL_FILE = BASE_DIR / "data" / "QAQC_Master.xlsx"
ASSETS = BASE_DIR / "assets"
EVOMEC_LOGO = ASSETS / "evomec_logo.png"
NLNG_LOGO = ASSETS / "nlng_logo.png"


def _image_data_uri(path):
    p = Path(path)
    if not p.exists():
        return ""
    suffix = p.suffix.lower().lstrip(".")
    mime = "jpeg" if suffix in {"jpg", "jpeg"} else suffix
    return f"data:image/{mime};base64,{base64.b64encode(p.read_bytes()).decode('ascii')}"
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
    nlng_src = _image_data_uri(NLNG_LOGO)
    evomec_src = _image_data_uri(EVOMEC_LOGO)
    nlng_logo = f'<img src="{nlng_src}" alt="NLNG">' if nlng_src else '<span>NLNG</span>'
    evomec_logo = f'<img src="{evomec_src}" alt="EVOMEC">' if evomec_src else '<span>EVOMEC</span>'
    user = st.session_state.get("auth") or {}
    profile_html = ""
    if user.get("logged_in"):
        photo = user.get("profile_photo")
        if photo and Path(photo).exists():
            avatar = f'<img class="header-profile__photo" src="{_image_data_uri(photo)}" alt="Profile photo">'
        else:
            initials = "".join(part[:1] for part in str(user.get("name", "User")).split()[:2]).upper() or "U"
            avatar = f'<div class="header-profile__initials">{html.escape(initials)}</div>'
        profile_html = f"""
<div class="header-profile">
    {avatar}
    <div>
        <div class="header-profile__name">{html.escape(str(user.get("name", "User")))}</div>
        <div class="header-profile__meta">{html.escape(str(user.get("role", "user")).title())}</div>
    </div>
</div>
"""
    st.html(
        f"""
<div class="app-bar">
    <div class="app-brand-lockup">
        <div class="app-logo-img app-logo-img--nlng">{nlng_logo}</div>
        <div>
            <div class="app-bar__welcome">Welcome back, <span>{html.escape(str(user.get("name", "System Administrator")))}</span></div>
            <div class="app-bar__eyebrow">NLNG Project</div>
            <div class="app-bar__title">QA/QC Executive Dashboard</div>
            <div class="app-bar__project">Quality Control Management System</div>
        </div>
    </div>
    <div class="app-bar__right">
        {profile_html}
        <div class="app-logo-img app-logo-img--evomec">{evomec_logo}</div>
    </div>
</div>
"""
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
    st.page_link(pages[selected], label="Open selected page")


def _auth_query_suffix():
    token = st.session_state.get("auth", {}).get("auth_token") or st.session_state.get("auth_token")
    if not token:
        try:
            token = st.query_params.get("auth_token")
        except Exception:
            token = None
    if isinstance(token, list):
        token = token[0] if token else None
    return f"?auth_token={quote(str(token))}" if token else ""

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

    nav_col, tool_col = st.columns([0.78, 0.22], gap="small")
    with nav_col:
        with st.popover("›  Page Navigation", use_container_width=True):
            suffix = _auth_query_suffix()
            links = []
            for label, page in pages.items():
                href = "/" + suffix if page == "app.py" else "/" + quote(Path(page).stem) + suffix
                links.append(f'<a class="nav-popover-link" href="{href}" target="_self">{html.escape(label)}</a>')
            st.markdown('<div class="nav-popover-menu">' + "".join(links) + "</div>", unsafe_allow_html=True)
    with tool_col:
        st.markdown(
            '<div class="command-tools command-tools--compact"><span>⌕</span><span>•</span><span>● Online</span></div>',
            unsafe_allow_html=True,
        )
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
    render_header()

    pages = get_navigation_pages()
    user = st.session_state.get("auth")
    nlng_src = _image_data_uri(NLNG_LOGO)
    nlng_brand = f'<img class="side-brand__logo" src="{nlng_src}" alt="NLNG">' if nlng_src else '<div class="side-brand__name">NLNG</div>'

    st.sidebar.markdown(
        f"""
<div class="side-brand">
    {nlng_brand}
    <div>
        <div class="side-brand__name">NLNG</div>
        <div class="side-brand__sub">QA/QC Command Centre</div>
    </div>
</div>
""",
        unsafe_allow_html=True,
    )

    if user:
        photo = user.get("profile_photo")
        photo_html = ""
        if photo and Path(photo).exists():
            photo_html = f'<img class="sidebar-profile__photo" src="{_image_data_uri(photo)}" alt="Profile photo">'
        else:
            initials = "".join(part[:1] for part in str(user.get("name", "User")).split()[:2]).upper() or "U"
            photo_html = f'<div class="profile-avatar sidebar-profile__initials">{html.escape(initials)}</div>'
        st.sidebar.markdown(
            f"""
<div class="sidebar-profile">
    {photo_html}
    <div>
        <div class="sidebar-profile__name">{html.escape(str(user.get("name", "User")))}</div>
        <div class="sidebar-profile__meta">{html.escape(str(user.get("role", "user")).title())} | {html.escape(str(user.get("discipline", "QA/QC")))}</div>
    </div>
</div>
""",
            unsafe_allow_html=True,
        )
        if st.sidebar.button("Sign out", key="global_sidebar_sign_out", use_container_width=True):
            st.session_state.auth = {
                "logged_in": False,
                "username": None,
                "name": None,
                "role": None,
                "email": None,
                "discipline": "QA/QC",
                "profile_photo": None,
                "auth_token": None,
            }
            for key in ["logged_in", "username", "name", "role", "email", "discipline", "profile_photo", "auth_token"]:
                st.session_state.pop(key, None)
            try:
                if "auth_token" in st.query_params:
                    del st.query_params["auth_token"]
            except Exception:
                pass
            st.rerun()

    st.sidebar.markdown('<div class="side-menu-title">Menu</div>', unsafe_allow_html=True)

    for label, page in pages.items():
        suffix = _auth_query_suffix()
        if page == "app.py":
            href = "/" + suffix
        else:
            href = "/" + quote(Path(page).stem) + suffix
        st.sidebar.markdown(
            f'<a class="side-nav-link" href="{href}" target="_self">{html.escape(label)}</a>',
            unsafe_allow_html=True,
        )

    st.sidebar.markdown(
        f"""
<div class="side-status side-status--footer">
    <strong>Evomec Global</strong><br>
    Services Limited<br><br>
    © 2026 Evomec Global Services Limited.<br>
    All rights reserved.<br>
    {len(pages)} modules available
</div>
""",
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

    section[data-testid="stSidebar"] a,
    section[data-testid="stSidebar"] a:visited,
    section[data-testid="stSidebar"] a span,
    section[data-testid="stSidebar"] [data-testid="stPageLink"] a,
    section[data-testid="stSidebar"] [data-testid="stPageLink"] a:visited,
    section[data-testid="stSidebar"] [data-testid="stPageLink"] a span,
    section[data-testid="stSidebar"] [data-testid="stPageLink"] p {
        color: #eaf6ff !important;
        opacity: 1 !important;
    }

    section[data-testid="stSidebar"] [data-testid="stPageLink"] a {
        border-radius: 8px;
        min-height: 2.35rem;
        padding: 0.45rem 0.7rem;
        transition: background 0.18s ease, box-shadow 0.18s ease, color 0.18s ease, transform 0.18s ease;
    }

    section[data-testid="stSidebar"] [data-testid="stPageLink"] a:hover,
    section[data-testid="stSidebar"] [data-testid="stPageLink"] a[aria-current="page"] {
        background: linear-gradient(135deg, rgba(37, 99, 235, 0.82), rgba(14, 165, 233, 0.82));
        box-shadow: 0 12px 24px rgba(8, 26, 51, 0.34);
        color: #ffffff !important;
        transform: translateX(3px);
    }

    section[data-testid="stSidebar"] [data-testid="stPageLink"] a:hover span,
    section[data-testid="stSidebar"] [data-testid="stPageLink"] a:hover p,
    section[data-testid="stSidebar"] [data-testid="stPageLink"] a[aria-current="page"] span,
    section[data-testid="stSidebar"] [data-testid="stPageLink"] a[aria-current="page"] p {
        color: #ffffff !important;
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

    .side-nav-link {
        border-radius: 8px;
        color: #d7e7f7 !important;
        display: block;
        font-size: 0.88rem;
        font-weight: 650;
        margin: 0.08rem 0;
        padding: 0.58rem 0.85rem;
        text-decoration: none !important;
        transition: background 0.18s ease, color 0.18s ease;
    }

    .side-nav-link:hover {
        background: linear-gradient(135deg, #1d73e8, #1596d4);
        color: #ffffff !important;
    }

    .nav-go-link {
        background: linear-gradient(135deg, #0ea5e9, #2563eb);
        border-radius: 8px;
        color: #ffffff !important;
        display: block;
        font-weight: 760;
        margin-top: 0.65rem;
        padding: 0.68rem 0.85rem;
        text-align: center;
        text-decoration: none !important;
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
        gap: 1rem;
        grid-template-columns: repeat(4, minmax(0, 1fr));
        margin-bottom: 1rem;
        padding-bottom: 0.35rem;
    }

    .exec-metric {
        align-items: center;
        background: linear-gradient(145deg, #ffffff 0%, #f8fbff 100%);
        border: 1px solid rgba(15, 23, 42, 0.12);
        border-radius: 8px;
        box-shadow:
            0 1px 0 rgba(255, 255, 255, 0.98) inset,
            0 4px 0 rgba(148, 163, 184, 0.36),
            0 14px 24px rgba(15, 23, 42, 0.18),
            0 24px 44px rgba(15, 23, 42, 0.09);
        display: flex;
        gap: 0.8rem;
        min-height: 5.6rem;
        padding: 0.85rem;
        position: relative;
        transform: translateY(0);
        transform-style: preserve-3d;
        transition: border-color 0.18s ease, box-shadow 0.18s ease, transform 0.18s ease;
        z-index: 0;
    }

    .exec-metric::after {
        background: linear-gradient(180deg, rgba(148, 163, 184, 0.28), rgba(15, 23, 42, 0.16));
        border-radius: 8px;
        bottom: -0.45rem;
        box-shadow: 0 14px 24px rgba(15, 23, 42, 0.16);
        content: "";
        height: 0.9rem;
        left: 0.5rem;
        position: absolute;
        right: 0.5rem;
        transform: skewX(-8deg);
        transition: background 0.18s ease, box-shadow 0.18s ease, transform 0.18s ease;
        z-index: -1;
    }

    .exec-metric:hover {
        border-color: color-mix(in srgb, var(--metric-color, #2563eb) 34%, rgba(15, 23, 42, 0.08));
        box-shadow:
            0 1px 0 rgba(255, 255, 255, 0.98) inset,
            0 8px 0 color-mix(in srgb, var(--metric-color, #2563eb) 36%, rgba(15, 23, 42, 0.18)),
            0 26px 40px rgba(15, 23, 42, 0.24),
            0 18px 32px color-mix(in srgb, var(--metric-color, #2563eb) 26%, transparent);
        transform: perspective(850px) translateY(-7px) rotateX(3deg);
    }

    .exec-metric:hover::after {
        background: linear-gradient(180deg, color-mix(in srgb, var(--metric-color, #2563eb) 26%, rgba(148, 163, 184, 0.2)), rgba(15, 23, 42, 0.2));
        box-shadow: 0 22px 32px color-mix(in srgb, var(--metric-color, #2563eb) 18%, rgba(15, 23, 42, 0.18));
        transform: translateY(0.18rem) skewX(-8deg);
    }

    .exec-metric__icon {
        align-items: center;
        background: var(--metric-color, #2563eb);
        border-radius: 8px;
        box-shadow:
            0 4px 0 color-mix(in srgb, var(--metric-color, #2563eb) 62%, #0f172a),
            0 12px 22px color-mix(in srgb, var(--metric-color, #2563eb) 32%, transparent);
        color: #ffffff;
        display: flex;
        font-size: 1.15rem;
        font-weight: 900;
        height: 2.7rem;
        justify-content: center;
        transition: box-shadow 0.18s ease, transform 0.18s ease;
        width: 2.7rem;
    }

    .exec-metric:hover .exec-metric__icon {
        box-shadow:
            0 6px 0 color-mix(in srgb, var(--metric-color, #2563eb) 62%, #0f172a),
            0 18px 28px color-mix(in srgb, var(--metric-color, #2563eb) 38%, transparent);
        transform: translateY(-2px) scale(1.04);
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
        background: linear-gradient(145deg, #ffffff 0%, #f8fbff 100%);
        border: 1px solid rgba(15, 23, 42, 0.09);
        border-radius: 8px;
        box-shadow:
            0 2px 0 rgba(255, 255, 255, 0.98) inset,
            0 7px 0 rgba(15, 23, 42, 0.08),
            0 24px 38px rgba(15, 23, 42, 0.16),
            inset 0 1px 0 rgba(255, 255, 255, 0.95);
        padding: 0.95rem;
        position: relative;
        transform: translateY(0);
        transform-style: preserve-3d;
        transition: border-color 0.18s ease, box-shadow 0.18s ease, transform 0.18s ease;
    }

    .exec-panel:hover {
        border-color: rgba(14, 165, 233, 0.3);
        box-shadow:
            0 2px 0 rgba(255, 255, 255, 0.98) inset,
            0 11px 0 rgba(14, 165, 233, 0.16),
            0 36px 54px rgba(15, 23, 42, 0.24),
            0 18px 34px rgba(14, 165, 233, 0.16),
            inset 0 1px 0 rgba(255, 255, 255, 0.98);
        transform: perspective(900px) translateY(-7px) rotateX(2deg);
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
        box-shadow:
            0 18px 30px rgba(39, 174, 96, 0.18),
            inset 0 0 0 1px rgba(15, 23, 42, 0.04);
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
        color: #102033;
        display: flex;
        justify-content: space-between;
        padding: 0.45rem 0;
    }

    .status-row strong {
        color: #0f172a;
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
        background: linear-gradient(145deg, #ffffff 0%, #f8fbff 100%);
        border: 1px solid rgba(15, 23, 42, 0.09);
        border-radius: 8px;
        box-shadow:
            0 2px 0 rgba(255, 255, 255, 0.98) inset,
            0 7px 0 rgba(15, 23, 42, 0.08),
            0 22px 34px rgba(15, 23, 42, 0.16),
            inset 0 1px 0 rgba(255, 255, 255, 0.95);
        min-height: 9.75rem;
        padding: 0.85rem;
        position: relative;
        transform: translateY(0);
        transform-style: preserve-3d;
        transition: border-color 0.18s ease, box-shadow 0.18s ease, transform 0.18s ease;
    }

    .module-card:hover {
        border-color: color-mix(in srgb, var(--module-color, #2563eb) 34%, rgba(15, 23, 42, 0.08));
        box-shadow:
            0 2px 0 rgba(255, 255, 255, 0.98) inset,
            0 11px 0 color-mix(in srgb, var(--module-color, #2563eb) 22%, rgba(15, 23, 42, 0.12)),
            0 34px 48px rgba(15, 23, 42, 0.24),
            0 18px 32px color-mix(in srgb, var(--module-color, #2563eb) 22%, transparent),
            inset 0 1px 0 rgba(255, 255, 255, 0.98);
        transform: perspective(900px) translateY(-8px) rotateX(2deg);
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

    @media (prefers-color-scheme: dark) {
        .exec-metric,
        .exec-panel,
        .module-card {
            background: linear-gradient(145deg, #102033 0%, #0b1727 100%);
            border-color: rgba(148, 163, 184, 0.2);
            box-shadow:
                0 18px 34px rgba(0, 0, 0, 0.35),
                inset 0 1px 0 rgba(255, 255, 255, 0.06);
        }

        .exec-metric__label,
        .exec-panel h3,
        .status-row,
        .module-card__stat,
        .module-card__stat strong,
        .status-row strong,
        .score-ring {
            color: #f8fafc;
        }

        .exec-metric__value {
            color: #ffffff;
        }

        .exec-metric__sub,
        .score-ring span {
            color: #cbd5e1;
        }

        .score-ring {
            background:
                radial-gradient(circle at center, #102033 55%, transparent 57%),
                conic-gradient(#27ae60 0 83%, #334155 83% 100%);
        }

        .status-row {
            border-bottom-color: rgba(148, 163, 184, 0.22);
        }

        .module-card__stat {
            border-color: rgba(148, 163, 184, 0.22);
        }

        .module-card__bar {
            background: #253449;
        }
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

    section[data-testid="stSidebar"] a,
    section[data-testid="stSidebar"] a:visited,
    section[data-testid="stSidebar"] a *,
    section[data-testid="stSidebar"] [role="link"],
    section[data-testid="stSidebar"] [role="link"] *,
    section[data-testid="stSidebar"] [data-testid*="stPageLink"],
    section[data-testid="stSidebar"] [data-testid*="stPageLink"] *,
    section[data-testid="stSidebar"] [data-testid*="stSidebarNavLink"],
    section[data-testid="stSidebar"] [data-testid*="stSidebarNavLink"] * {
        color: #eaf6ff !important;
        opacity: 1 !important;
        text-shadow: 0 1px 1px rgba(0, 0, 0, 0.2);
    }

    section[data-testid="stSidebar"] a,
    section[data-testid="stSidebar"] [role="link"],
    section[data-testid="stSidebar"] [data-testid*="stPageLink"] a {
        border-radius: 8px !important;
        color: #eaf6ff !important;
        transition: background 0.18s ease, box-shadow 0.18s ease, color 0.18s ease, transform 0.18s ease !important;
    }

    section[data-testid="stSidebar"] a[href="/"],
    section[data-testid="stSidebar"] a[href$="localhost:8501/"],
    section[data-testid="stSidebar"] a[href$="/QAQC_Dashboard/"] {
        background: rgba(148, 163, 184, 0.14) !important;
        box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.08) !important;
    }

    section[data-testid="stSidebar"] a:hover,
    section[data-testid="stSidebar"] a:focus-visible,
    section[data-testid="stSidebar"] [role="link"]:hover,
    section[data-testid="stSidebar"] [data-testid*="stPageLink"]:hover,
    section[data-testid="stSidebar"] a[aria-current="page"] {
        background: linear-gradient(135deg, #2563eb 0%, #0ea5e9 100%) !important;
        box-shadow:
            0 2px 0 rgba(255, 255, 255, 0.16) inset,
            0 6px 0 rgba(4, 21, 44, 0.34),
            0 18px 28px rgba(2, 132, 199, 0.28) !important;
        color: #ffffff !important;
        transform: perspective(600px) translateX(5px) translateY(-2px) rotateY(-3deg) !important;
    }

    section[data-testid="stSidebar"] a:hover *,
    section[data-testid="stSidebar"] a:focus-visible *,
    section[data-testid="stSidebar"] [role="link"]:hover *,
    section[data-testid="stSidebar"] [data-testid*="stPageLink"]:hover *,
    section[data-testid="stSidebar"] a[aria-current="page"] * {
        color: #ffffff !important;
    }

    section[data-testid="stSidebar"] {
        background: linear-gradient(180deg, #f3f4f6 0%, #e5e7eb 100%) !important;
        border-right: 1px solid rgba(148, 163, 184, 0.42) !important;
    }

    section[data-testid="stSidebar"] h1,
    section[data-testid="stSidebar"] h2,
    section[data-testid="stSidebar"] h3,
    section[data-testid="stSidebar"] label,
    section[data-testid="stSidebar"] p,
    section[data-testid="stSidebar"] span,
    section[data-testid="stSidebar"] a,
    section[data-testid="stSidebar"] a:visited,
    section[data-testid="stSidebar"] a *,
    section[data-testid="stSidebar"] [role="link"],
    section[data-testid="stSidebar"] [role="link"] * {
        color: #111827 !important;
        opacity: 1 !important;
        text-shadow: none !important;
    }

    .side-brand {
        border-bottom-color: rgba(148, 163, 184, 0.5) !important;
    }

    .side-brand__name {
        color: #0f172a !important;
    }

    .side-brand__sub {
        color: #334155 !important;
    }

    .side-menu-title {
        color: #0369a1 !important;
    }

    .side-nav-link {
        color: #111827 !important;
    }

    .side-nav-link[href="/"] {
        background: rgba(148, 163, 184, 0.28) !important;
        box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.72) !important;
    }

    .side-nav-link:hover,
    .side-nav-link:focus-visible,
    section[data-testid="stSidebar"] a:hover,
    section[data-testid="stSidebar"] a:focus-visible {
        background: linear-gradient(135deg, #2563eb 0%, #0ea5e9 100%) !important;
        color: #ffffff !important;
        text-shadow: none !important;
    }

    .side-nav-link:hover *,
    .side-nav-link:focus-visible *,
    section[data-testid="stSidebar"] a:hover *,
    section[data-testid="stSidebar"] a:focus-visible * {
        color: #ffffff !important;
    }

    .side-status {
        background: rgba(255, 255, 255, 0.62) !important;
        border-color: rgba(148, 163, 184, 0.5) !important;
        color: #0f172a !important;
    }

    @media (prefers-color-scheme: light) {
        .exec-metric,
        .exec-panel,
        .module-card {
            background: linear-gradient(145deg, #ffffff 0%, #f8fbff 100%);
            color: #102033;
        }
    }

    @media (prefers-color-scheme: dark) {
        .exec-metric,
        .exec-panel,
        .module-card {
            background: linear-gradient(145deg, #102033 0%, #0b1727 100%) !important;
            border-color: rgba(148, 163, 184, 0.26) !important;
            box-shadow:
                0 2px 0 rgba(255, 255, 255, 0.08) inset,
                0 7px 0 rgba(0, 0, 0, 0.34),
                0 24px 38px rgba(0, 0, 0, 0.42) !important;
        }

        .exec-metric__label,
        .exec-panel h3,
        .status-row,
        .module-card__stat,
        .module-card__stat strong,
        .status-row strong,
        .score-ring {
            color: #f8fafc !important;
        }

        .exec-metric__value {
            color: #ffffff !important;
        }

        .exec-metric__sub,
        .score-ring span {
            color: #cbd5e1 !important;
        }

        .score-ring {
            background:
                radial-gradient(circle at center, #102033 55%, transparent 57%),
                conic-gradient(#27ae60 0 83%, #334155 83% 100%) !important;
        }

        .status-row,
        .module-card__stat {
            border-color: rgba(148, 163, 184, 0.24) !important;
        }
    }

    /* NLNG-inspired command dashboard skin */
    .stApp {
        background:
            radial-gradient(circle at 18% 0%, rgba(59, 130, 246, 0.14), transparent 26rem),
            radial-gradient(circle at 82% 8%, rgba(34, 197, 94, 0.07), transparent 24rem),
            linear-gradient(135deg, #111827 0%, #1f2937 52%, #0f172a 100%) !important;
        color: #e5edf8 !important;
    }

    .block-container {
        max-width: 1580px !important;
        padding: 0.75rem 1rem 1.4rem !important;
    }

    h1, h2, h3, h4, p, label, span {
        letter-spacing: 0 !important;
    }

    .app-bar {
        align-items: center !important;
        background: rgba(17, 24, 39, 0.88) !important;
        border: 1px solid rgba(148, 163, 184, 0.18) !important;
        border-radius: 0 !important;
        box-shadow: 0 16px 42px rgba(0, 0, 0, 0.34) !important;
        display: flex !important;
        justify-content: space-between !important;
        margin: -0.25rem -0.15rem 0.55rem !important;
        min-height: 4.3rem;
        padding: 0.8rem 1rem !important;
    }

    .app-brand-lockup {
        align-items: center;
        display: flex;
        gap: 0.85rem;
    }

    .app-logo-mark {
        background: linear-gradient(135deg, #2563eb, #0ea5e9);
        border-radius: 8px;
        box-shadow: 0 12px 28px rgba(37, 99, 235, 0.34);
        height: 2.5rem;
        position: relative;
        width: 2.5rem;
    }

    .app-logo-mark::after {
        background: rgba(2, 6, 23, 0.9);
        border-radius: 6px;
        content: "";
        height: 1rem;
        left: 0.72rem;
        position: absolute;
        top: 0.72rem;
        transform: rotate(-35deg);
        width: 1.6rem;
    }

    .app-logo-img {
        align-items: center;
        display: flex;
        justify-content: center;
    }

    .app-logo-img img {
        display: block;
        max-height: 2.85rem;
        object-fit: contain;
        width: auto;
    }

    .app-logo-img--nlng img {
        max-height: 3rem;
        max-width: 8rem;
    }

    .app-logo-img--evomec img {
        max-height: 2.75rem;
        max-width: 10rem;
    }

    .app-bar__right {
        align-items: center;
        display: flex;
        gap: 0.9rem;
    }

    .header-profile {
        align-items: center;
        background: rgba(15, 23, 42, 0.78);
        border: 1px solid rgba(148, 163, 184, 0.2);
        border-radius: 999px;
        display: flex;
        gap: 0.55rem;
        padding: 0.38rem 0.68rem 0.38rem 0.42rem;
    }

    .header-profile__photo,
    .header-profile__initials {
        align-items: center;
        background: linear-gradient(135deg, #2563eb, #22c55e);
        border: 2px solid rgba(96, 165, 250, 0.46);
        border-radius: 999px;
        color: #ffffff;
        display: flex;
        font-size: 0.76rem;
        font-weight: 900;
        height: 2.05rem;
        justify-content: center;
        object-fit: cover;
        width: 2.05rem;
    }

    .header-profile__name {
        color: #ffffff;
        font-size: 0.78rem;
        font-weight: 900;
        line-height: 1.05;
        max-width: 9rem;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
    }

    .header-profile__meta {
        color: #93c5fd;
        font-size: 0.62rem;
        font-weight: 760;
        margin-top: 0.1rem;
    }

    .app-bar__eyebrow {
        color: #ffffff !important;
        font-size: 1.05rem !important;
        font-weight: 900 !important;
    }

    .app-bar__title {
        color: #ffffff !important;
        font-size: 1rem !important;
        font-weight: 900 !important;
        line-height: 1.1;
        text-transform: uppercase;
    }

    .app-bar__project {
        color: #38bdf8;
        font-size: 0.72rem;
        font-weight: 780;
        margin-top: 0.12rem;
        text-transform: uppercase;
    }

    .app-bar__partner {
        color: #ffffff;
        font-size: 1.42rem;
        font-weight: 950;
        letter-spacing: 0.02em;
    }

    .top-module-nav {
        align-items: center;
        background: rgba(8, 17, 31, 0.78);
        border: 1px solid rgba(148, 163, 184, 0.16);
        border-radius: 0;
        display: flex;
        gap: 0.35rem;
        margin: 0 0 0.75rem;
        overflow-x: auto;
        padding: 0.42rem 0.55rem;
        scrollbar-width: thin;
    }

    .top-module-nav a {
        border-bottom: 2px solid transparent;
        color: #cbd5e1 !important;
        flex: 0 0 auto;
        font-size: 0.72rem;
        font-weight: 740;
        padding: 0.48rem 0.62rem;
        text-decoration: none !important;
        transition: color 0.18s ease, border-color 0.18s ease, background 0.18s ease;
    }

    .top-module-nav a:first-child,
    .top-module-nav a:hover {
        background: rgba(37, 99, 235, 0.12);
        border-color: #2563eb;
        color: #ffffff !important;
    }

    section[data-testid="stSidebar"] {
        background:
            radial-gradient(circle at top left, rgba(37, 99, 235, 0.16), transparent 15rem),
            linear-gradient(180deg, #1f2937 0%, #111827 100%) !important;
        border-right: 1px solid rgba(148, 163, 184, 0.16) !important;
    }

    section[data-testid="stSidebar"] h1,
    section[data-testid="stSidebar"] h2,
    section[data-testid="stSidebar"] h3,
    section[data-testid="stSidebar"] label,
    section[data-testid="stSidebar"] p,
    section[data-testid="stSidebar"] span,
    section[data-testid="stSidebar"] a,
    section[data-testid="stSidebar"] a:visited,
    section[data-testid="stSidebar"] a *,
    section[data-testid="stSidebar"] [role="link"],
    section[data-testid="stSidebar"] [role="link"] * {
        color: #dbeafe !important;
        text-shadow: none !important;
    }

    .side-brand {
        border-bottom-color: rgba(148, 163, 184, 0.2) !important;
        padding-top: 0.7rem !important;
    }

    .side-brand__name {
        color: #ffffff !important;
        font-size: 1.05rem !important;
        font-weight: 950 !important;
    }

    .side-brand__logo {
        display: block;
        max-height: 2.4rem;
        object-fit: contain;
        width: 3rem;
    }

    .side-brand__sub {
        color: #93c5fd !important;
    }

    .side-menu-title {
        color: #38bdf8 !important;
    }

    .sidebar-profile {
        align-items: center;
        background: rgba(15, 23, 42, 0.68);
        border: 1px solid rgba(148, 163, 184, 0.18);
        border-radius: 8px;
        display: flex;
        gap: 0.72rem;
        margin: 0.75rem 0 0.8rem;
        padding: 0.72rem;
    }

    .sidebar-profile__photo,
    .sidebar-profile__initials {
        border: 2px solid rgba(96, 165, 250, 0.45);
        border-radius: 999px;
        flex: 0 0 auto;
        height: 3rem !important;
        margin: 0 !important;
        object-fit: cover;
        width: 3rem !important;
    }

    .sidebar-profile__initials {
        font-size: 1rem !important;
    }

    .sidebar-profile__name {
        color: #ffffff;
        font-size: 0.88rem;
        font-weight: 900;
        line-height: 1.15;
    }

    .sidebar-profile__meta {
        color: #93c5fd;
        font-size: 0.68rem;
        font-weight: 720;
        margin-top: 0.18rem;
    }

    .side-nav-link {
        border-radius: 7px !important;
        color: #dbeafe !important;
        display: block !important;
        margin: 0.18rem 0 !important;
        padding: 0.58rem 0.75rem !important;
    }

    .side-nav-link[href="/"],
    .side-nav-link:hover,
    .side-nav-link:focus-visible {
        background: linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%) !important;
        box-shadow: 0 12px 26px rgba(37, 99, 235, 0.28) !important;
        color: #ffffff !important;
        transform: translateX(3px) !important;
    }

    .side-status {
        background: rgba(15, 23, 42, 0.76) !important;
        border-color: rgba(148, 163, 184, 0.22) !important;
        color: #cbd5e1 !important;
    }

    .dashboard-command {
        padding-bottom: 0.6rem;
    }

    .command-topbar {
        align-items: center;
        background: rgba(8, 17, 31, 0.82);
        border: 1px solid rgba(96, 165, 250, 0.16);
        border-radius: 8px;
        box-shadow: 0 14px 34px rgba(0, 0, 0, 0.22);
        display: flex;
        justify-content: space-between;
        margin: -0.1rem 0 0.55rem;
        min-height: 2.4rem;
        padding: 0 0.8rem;
    }

    .command-crumb {
        color: #94a3b8;
        font-size: 0.76rem;
        font-weight: 800;
    }

    .command-crumb span {
        color: #e5edf8 !important;
        margin-left: 0.3rem;
    }

    .command-tools {
        align-items: center;
        color: #cbd5e1;
        display: flex;
        font-size: 0.72rem;
        font-weight: 800;
        gap: 0.75rem;
    }

    .command-tools span:last-child {
        color: #22c55e !important;
    }

    div[data-testid="stPopover"] button {
        background: rgba(8, 17, 31, 0.82) !important;
        border: 1px solid rgba(96, 165, 250, 0.16) !important;
        border-radius: 8px !important;
        box-shadow: 0 14px 34px rgba(0, 0, 0, 0.22) !important;
        color: #e5edf8 !important;
        justify-content: flex-start !important;
        min-height: 2.4rem !important;
        padding: 0 0.8rem !important;
    }

    div[data-testid="stPopover"] button:hover {
        border-color: rgba(56, 189, 248, 0.38) !important;
        color: #ffffff !important;
    }

    .command-tools--compact {
        align-items: center;
        background: rgba(8, 17, 31, 0.82);
        border: 1px solid rgba(96, 165, 250, 0.16);
        border-radius: 8px;
        box-shadow: 0 14px 34px rgba(0, 0, 0, 0.22);
        display: flex;
        justify-content: flex-end;
        min-height: 2.4rem;
        padding: 0 0.8rem;
    }

    .nav-popover-menu {
        display: grid;
        gap: 0.35rem;
        min-width: 16rem;
        padding: 0.2rem;
    }

    .nav-popover-link {
        background: rgba(15, 23, 42, 0.72);
        border: 1px solid rgba(148, 163, 184, 0.16);
        border-radius: 7px;
        color: #e5edf8 !important;
        display: block;
        font-size: 0.82rem;
        font-weight: 800;
        padding: 0.55rem 0.7rem;
        text-decoration: none !important;
    }

    .nav-popover-link:hover {
        background: linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%);
        color: #ffffff !important;
    }

    .app-bar {
        background:
            linear-gradient(90deg, rgba(10, 25, 47, 0.98), rgba(9, 28, 57, 0.92)),
            radial-gradient(circle at 72% 50%, rgba(14, 165, 233, 0.2), transparent 16rem) !important;
        border-radius: 8px !important;
        min-height: 6.6rem !important;
        overflow: hidden;
        position: relative;
    }

    .app-bar::after {
        background:
            linear-gradient(90deg, transparent, rgba(56, 189, 248, 0.14)),
            repeating-linear-gradient(90deg, rgba(56, 189, 248, 0.18) 0 2px, transparent 2px 10px);
        content: "";
        height: 5.2rem;
        opacity: 0.35;
        position: absolute;
        right: 13rem;
        top: 0.8rem;
        transform: skewX(-12deg);
        width: 21rem;
    }

    .app-bar > * {
        position: relative;
        z-index: 1;
    }

    .app-logo-img--nlng {
        background: #ffffff;
        border-radius: 8px;
        box-shadow: 0 18px 38px rgba(0, 0, 0, 0.28);
        min-height: 3.9rem;
        padding: 0.55rem;
        width: 4.1rem;
    }

    .app-bar__title {
        font-size: 1.55rem !important;
    }

    .metric-grid--six {
        grid-template-columns: repeat(6, minmax(0, 1fr)) !important;
        gap: 0.7rem !important;
        margin-bottom: 0.7rem !important;
    }

    .exec-metric,
    .exec-panel,
    .module-card,
    div[data-testid="stVerticalBlockBorderWrapper"] {
        background: linear-gradient(145deg, rgba(31, 41, 55, 0.96), rgba(17, 24, 39, 0.9)) !important;
        border: 1px solid rgba(96, 165, 250, 0.16) !important;
        border-radius: 8px !important;
        box-shadow:
            0 1px 0 rgba(255, 255, 255, 0.08) inset,
            0 14px 34px rgba(0, 0, 0, 0.28) !important;
        color: #e5edf8 !important;
    }

    .exec-metric {
        min-height: 6.55rem !important;
        padding: 0.85rem !important;
    }

    .exec-metric::after {
        display: none !important;
    }

    .exec-metric:hover,
    .exec-panel:hover,
    .module-card:hover,
    div[data-testid="stVerticalBlockBorderWrapper"]:hover {
        border-color: color-mix(in srgb, var(--metric-color, #2563eb) 46%, rgba(96, 165, 250, 0.18)) !important;
        box-shadow:
            0 1px 0 rgba(255, 255, 255, 0.1) inset,
            0 22px 46px rgba(0, 0, 0, 0.42),
            0 0 24px color-mix(in srgb, var(--metric-color, #2563eb) 18%, transparent) !important;
        transform: translateY(-4px) !important;
    }

    div[data-testid="stVerticalBlockBorderWrapper"] {
        margin-bottom: 0.75rem !important;
        min-height: 19.4rem !important;
        overflow: hidden !important;
        padding: 0.15rem !important;
        transition: transform 0.22s ease, box-shadow 0.22s ease, border-color 0.22s ease !important;
    }

    .native-panel-title {
        align-items: center;
        color: #f8fafc !important;
        display: flex;
        font-size: 0.82rem;
        font-weight: 900;
        justify-content: space-between;
        margin: 0 0 0.35rem;
    }

    .native-panel-title span {
        color: #94a3b8 !important;
        font-weight: 900;
    }

    .exec-metric__icon {
        border-radius: 8px !important;
        height: 3rem !important;
        width: 3rem !important;
    }

    .exec-metric__label {
        color: #f8fafc !important;
        font-size: 0.72rem !important;
        font-weight: 880 !important;
    }

    .exec-metric__value {
        color: #ffffff !important;
        font-size: 1.65rem !important;
        margin-top: 0.3rem !important;
    }

    .exec-metric__sub,
    .exec-metric__delta {
        color: #cbd5e1 !important;
        font-size: 0.66rem !important;
    }

    .exec-metric__delta {
        color: #22c55e !important;
        font-weight: 800;
        margin-top: 0.18rem;
    }

    .exec-panel {
        min-height: 19.4rem;
        padding: 0.85rem !important;
    }

    .exec-panel--html {
        overflow: hidden;
    }

    .exec-chart-grid {
        display: grid;
        gap: 0.75rem;
        grid-template-columns: repeat(3, minmax(0, 1fr));
        margin-bottom: 0.75rem;
    }

    .exec-bottom-grid {
        display: grid;
        gap: 0.75rem;
        grid-template-columns: minmax(280px, 0.9fr) minmax(0, 1.8fr);
        margin-bottom: 0.75rem;
    }

    .inline-chart {
        display: block;
        height: 15.4rem;
        margin-top: 0.2rem;
        overflow: visible;
        width: 100%;
    }

    .inline-chart text {
        fill: #dbeafe;
        font-size: 0.72rem;
        font-weight: 760;
    }

    .inline-chart .axis-label {
        fill: #94a3b8;
        font-size: 0.68rem;
        font-weight: 700;
    }

    .inline-chart .legend text {
        fill: #cbd5e1;
        font-size: 0.68rem;
    }

    .category-bars {
        display: grid;
        gap: 0.74rem;
        padding-top: 0.65rem;
    }

    .category-row {
        align-items: center;
        display: grid;
        gap: 0.65rem;
        grid-template-columns: 8rem minmax(0, 1fr) 2rem;
    }

    .category-label {
        align-items: center;
        color: #dbeafe;
        display: flex;
        font-size: 0.76rem;
        font-weight: 780;
        gap: 0.42rem;
        min-width: 0;
    }

    .category-label span {
        border-radius: 999px;
        flex: 0 0 auto;
        height: 0.62rem;
        width: 0.62rem;
    }

    .category-track {
        background: rgba(148, 163, 184, 0.14);
        border-radius: 999px;
        height: 0.56rem;
        overflow: hidden;
    }

    .category-track i {
        border-radius: 999px;
        display: block;
        height: 100%;
    }

    .category-row strong {
        color: #ffffff;
        font-size: 0.82rem;
        text-align: right;
    }

    .panel-title {
        align-items: center;
        color: #f8fafc;
        display: flex;
        font-size: 0.86rem;
        font-weight: 900;
        justify-content: space-between;
        margin-bottom: 0.35rem;
    }

    .panel-title span {
        color: #94a3b8 !important;
        letter-spacing: 0.12em !important;
    }

    .panel-total {
        background: rgba(15, 23, 42, 0.76);
        border: 1px solid rgba(148, 163, 184, 0.16);
        border-radius: 8px;
        color: #dbeafe;
        font-weight: 800;
        margin-top: 0.35rem;
        padding: 0.55rem;
        text-align: center;
    }

    .exec-empty {
        align-items: center;
        color: #94a3b8;
        display: flex;
        min-height: 14rem;
        justify-content: center;
    }

    .exec-table {
        border-collapse: collapse;
        color: #cbd5e1;
        font-size: 0.72rem;
        width: 100%;
    }

    .exec-table th,
    .exec-table td {
        border-bottom: 1px solid rgba(148, 163, 184, 0.12);
        padding: 0.62rem 0.55rem;
        text-align: left;
    }

    .exec-table th {
        color: #bfdbfe;
        font-size: 0.66rem;
        font-weight: 850;
        text-transform: uppercase;
    }

    .status-badge {
        border-radius: 5px;
        display: inline-flex;
        font-size: 0.68rem;
        font-weight: 820;
        padding: 0.2rem 0.4rem;
    }

    .status-badge--open {
        background: rgba(239, 68, 68, 0.12);
        border: 1px solid rgba(239, 68, 68, 0.42);
        color: #fca5a5;
    }

    .status-badge--closed {
        background: rgba(34, 197, 94, 0.12);
        border: 1px solid rgba(34, 197, 94, 0.42);
        color: #86efac;
    }

    .module-grid--compact {
        grid-template-columns: repeat(4, minmax(0, 1fr)) !important;
        margin-top: 0.75rem !important;
    }

    .module-card {
        min-height: 7.3rem !important;
    }

    .module-card__stat {
        background: rgba(15, 23, 42, 0.6);
        border-color: rgba(148, 163, 184, 0.16) !important;
        color: #cbd5e1 !important;
    }

    .module-card__stat strong {
        color: #ffffff !important;
    }

    .quick-access-panel {
        background: linear-gradient(145deg, rgba(31, 41, 55, 0.96), rgba(17, 24, 39, 0.9));
        border: 1px solid rgba(96, 165, 250, 0.16);
        border-radius: 8px;
        box-shadow: 0 14px 34px rgba(0, 0, 0, 0.28);
        margin-top: 0.75rem;
        padding: 0.85rem;
    }

    .quick-access-title {
        color: #f8fafc;
        font-size: 0.82rem;
        font-weight: 900;
        margin-bottom: 0.65rem;
        text-transform: uppercase;
    }

    .quick-access-grid {
        display: grid;
        gap: 0.55rem;
        grid-template-columns: repeat(7, minmax(0, 1fr));
    }

    .quick-link {
        align-items: center;
        background: rgba(15, 23, 42, 0.64);
        border: 1px solid rgba(148, 163, 184, 0.16);
        border-radius: 7px;
        color: #e5edf8 !important;
        display: flex;
        font-size: 0.74rem;
        font-weight: 840;
        gap: 0.45rem;
        min-height: 2.55rem;
        padding: 0.35rem 0.6rem;
        text-decoration: none !important;
    }

    .quick-link:hover {
        border-color: var(--quick-color, #2563eb);
        box-shadow: 0 12px 28px color-mix(in srgb, var(--quick-color, #2563eb) 22%, transparent);
        color: #ffffff !important;
        transform: translateY(-2px);
    }

    .quick-link span {
        align-items: center;
        background: var(--quick-color, #2563eb);
        border-radius: 6px;
        color: #ffffff !important;
        display: flex;
        flex: 0 0 auto;
        font-size: 0.68rem;
        font-weight: 900;
        height: 1.35rem;
        justify-content: center;
        width: 1.35rem;
    }

    .quick-link--all {
        border-color: rgba(37, 99, 235, 0.46);
        color: #38bdf8 !important;
        justify-content: center;
    }

    .dashboard-security-strip {
        align-items: center;
        color: #94a3b8;
        display: flex;
        font-size: 0.72rem;
        font-weight: 780;
        gap: 1.6rem;
        justify-content: center;
        padding: 0.75rem 0 0.1rem;
    }

    .dashboard-security-strip span::before {
        color: #22c55e;
        content: "◆";
        font-size: 0.6rem;
        margin-right: 0.42rem;
    }

    .app-bar__welcome {
        color: #f8fafc;
        font-size: 0.78rem;
        font-weight: 850;
        margin-bottom: 0.38rem;
    }

    .app-bar__welcome span {
        color: #22d3ee !important;
    }

    .side-status--footer {
        background:
            radial-gradient(circle at 50% 0%, rgba(14, 165, 233, 0.18), transparent 7rem),
            rgba(15, 23, 42, 0.76) !important;
        margin-top: 1.2rem !important;
        padding-top: 3.6rem !important;
    }

    .analytics-hero {
        align-items: center;
        background:
            linear-gradient(90deg, rgba(8, 17, 31, 0.96), rgba(10, 35, 68, 0.72)),
            radial-gradient(circle at 72% 30%, rgba(14, 165, 233, 0.28), transparent 18rem);
        border: 1px solid rgba(96, 165, 250, 0.18);
        border-radius: 8px;
        box-shadow: 0 18px 44px rgba(0, 0, 0, 0.28);
        display: flex;
        gap: 1rem;
        margin-bottom: 0.75rem;
        min-height: 5.6rem;
        overflow: hidden;
        padding: 0.9rem 1.05rem;
    }

    .analytics-hero__logo {
        align-items: center;
        background: #ffffff;
        border-radius: 8px;
        color: #063c63;
        display: flex;
        font-size: 0.72rem;
        font-weight: 950;
        height: 3.8rem;
        justify-content: center;
        width: 4.2rem;
    }

    .analytics-hero h1 {
        color: #ffffff !important;
        font-size: 1.48rem;
        font-weight: 950;
        line-height: 1.1;
        margin: 0;
        text-transform: uppercase;
    }

    .analytics-hero p {
        color: #b7c9dd !important;
        font-size: 0.78rem;
        font-weight: 760;
        margin: 0.3rem 0 0;
    }

    .analytics-metric-grid {
        display: grid;
        gap: 0.65rem;
        grid-template-columns: repeat(8, minmax(0, 1fr));
        margin-bottom: 0.7rem;
    }

    .analytics-metric {
        align-items: center;
        background: linear-gradient(145deg, rgba(31, 41, 55, 0.96), rgba(17, 24, 39, 0.9));
        border: 1px solid rgba(96, 165, 250, 0.16);
        border-radius: 8px;
        box-shadow: 0 14px 34px rgba(0, 0, 0, 0.28);
        display: flex;
        gap: 0.65rem;
        min-height: 5.45rem;
        padding: 0.72rem;
    }

    .analytics-metric__icon {
        align-items: center;
        background: var(--metric-color, #2563eb);
        border-radius: 8px;
        box-shadow: 0 14px 28px color-mix(in srgb, var(--metric-color, #2563eb) 36%, transparent);
        color: #ffffff;
        display: flex;
        flex: 0 0 auto;
        font-weight: 950;
        height: 2.45rem;
        justify-content: center;
        width: 2.45rem;
    }

    .analytics-metric__label {
        color: #f8fafc;
        font-size: 0.68rem;
        font-weight: 900;
    }

    .analytics-metric__value {
        color: #ffffff;
        font-size: 1.45rem;
        font-weight: 950;
        line-height: 1;
        margin-top: 0.22rem;
    }

    .analytics-metric__sub,
    .analytics-metric__trend {
        color: #cbd5e1;
        font-size: 0.62rem;
        margin-top: 0.2rem;
    }

    .analytics-metric__trend {
        color: #22c55e;
        font-weight: 850;
    }

    .analytics-metric__trend--down {
        color: #ef4444;
    }

    .analytics-panel-title {
        align-items: center;
        color: #f8fafc;
        display: flex;
        font-size: 0.78rem;
        font-weight: 900;
        justify-content: space-between;
        margin: 0 0 0.35rem;
    }

    .analytics-panel-title span {
        color: #94a3b8 !important;
    }

    div[data-testid="stDataFrame"] {
        background: rgba(15, 23, 42, 0.64) !important;
        border: 1px solid rgba(148, 163, 184, 0.14) !important;
        border-radius: 8px !important;
        overflow: hidden !important;
    }

    .stMarkdown hr {
        border-color: rgba(96, 165, 250, 0.14) !important;
        margin: 0.7rem 0 !important;
    }

    [data-testid="stMetric"] {
        background: linear-gradient(145deg, rgba(31, 41, 55, 0.96), rgba(17, 24, 39, 0.9)) !important;
        border: 1px solid rgba(96, 165, 250, 0.16) !important;
        border-radius: 8px !important;
        box-shadow: 0 14px 34px rgba(0, 0, 0, 0.24) !important;
        padding: 0.85rem !important;
    }

    @media (max-width: 1320px) {
        .metric-grid--six {
            grid-template-columns: repeat(3, minmax(0, 1fr)) !important;
        }

        .analytics-metric-grid {
            grid-template-columns: repeat(4, minmax(0, 1fr));
        }

        .exec-chart-grid,
        .exec-bottom-grid,
        .quick-access-grid {
            grid-template-columns: 1fr !important;
        }
    }

    @media (max-width: 760px) {
        .metric-grid--six,
        .module-grid--compact,
        .analytics-metric-grid {
            grid-template-columns: 1fr !important;
        }

        .top-module-nav {
            margin-left: -0.25rem;
            margin-right: -0.25rem;
        }

        .app-bar {
            align-items: flex-start !important;
            display: flex !important;
            flex-direction: column !important;
            gap: 0.9rem;
            min-height: auto !important;
        }

        .app-bar::after {
            display: none;
        }

        .app-bar__right {
            width: 100%;
        }

        .command-tools {
            display: none;
        }
    }

    /* Final global shell override for Streamlit's visible containers */
    html,
    body,
    #root,
    .stApp,
    [data-testid="stApp"],
    [data-testid="stAppViewContainer"],
    [data-testid="stMain"],
    [data-testid="stMainBlockContainer"] {
        background:
            radial-gradient(circle at 18% 0%, rgba(59, 130, 246, 0.13), transparent 28rem),
            linear-gradient(135deg, #111827 0%, #1f2937 55%, #111827 100%) !important;
        color: #e5edf8 !important;
    }

    [data-testid="stHeader"],
    header[data-testid="stHeader"] {
        background: rgba(17, 24, 39, 0.82) !important;
    }

    [data-testid="stSidebarContent"] {
        background:
            radial-gradient(circle at top left, rgba(37, 99, 235, 0.16), transparent 16rem),
            linear-gradient(180deg, #1f2937 0%, #111827 100%) !important;
    }

    .stButton button,
    section[data-testid="stSidebar"] .stButton button {
        border-radius: 8px !important;
        font-weight: 800 !important;
    }

    section[data-testid="stSidebar"] .stButton button {
        background: rgba(15, 23, 42, 0.78) !important;
        border: 1px solid rgba(148, 163, 184, 0.22) !important;
        color: #dbeafe !important;
    }

    section[data-testid="stSidebar"] .stButton button:hover {
        background: linear-gradient(135deg, #ef4444 0%, #b91c1c 100%) !important;
        border-color: rgba(248, 113, 113, 0.42) !important;
        color: #ffffff !important;
    }

    .auth-panel,
    div[data-testid="stForm"],
    div[data-testid="stExpander"] {
        background: rgba(31, 41, 55, 0.92) !important;
        border-color: rgba(148, 163, 184, 0.18) !important;
        color: #e5edf8 !important;
    }

    .auth-panel h1,
    .auth-panel h2,
    .auth-panel h3,
    div[data-testid="stForm"] label,
    div[data-testid="stForm"] p {
        color: #f8fafc !important;
    }

    .auth-page {
        margin: -0.7rem -1.7rem -2.5rem;
        min-height: calc(100vh - 1rem);
        padding: 2.2rem 2.25rem 1rem;
        background:
            radial-gradient(circle at 8% 16%, rgba(30, 144, 255, 0.18), transparent 20rem),
            radial-gradient(circle at 86% 12%, rgba(37, 99, 235, 0.42), transparent 32rem),
            linear-gradient(135deg, #061225 0%, #071a34 48%, #082a59 100%);
        color: #e5edf8;
    }

    .auth-page + div,
    .auth-page ~ div {
        position: relative;
    }

    div[data-testid="column"]:has(.auth-card-head) {
        align-self: center;
        background:
            linear-gradient(145deg, rgba(16, 32, 55, 0.86), rgba(10, 23, 42, 0.94));
        border: 1px solid rgba(148, 163, 184, 0.34);
        border-radius: 8px;
        box-shadow: 0 28px 80px rgba(0, 0, 0, 0.32);
        min-height: 31rem;
        padding: 1.9rem 2rem 1.65rem;
    }

    div[data-testid="column"]:has(.auth-hero-panel) {
        align-self: center;
    }

    .auth-hero-panel {
        padding: 0.2rem 0 0;
    }

    .auth-logo {
        display: block;
        height: 3.6rem;
        margin: 0 0 2.2rem;
        object-fit: contain;
        object-position: left center;
        width: auto;
    }

    .auth-logo-text {
        color: #ffffff;
        font-size: 1.8rem;
        font-weight: 800;
        letter-spacing: 0.08em;
        margin-bottom: 2.3rem;
    }

    .auth-eyebrow--pill {
        align-items: center;
        background: rgba(37, 99, 235, 0.22);
        border: 1px solid rgba(59, 130, 246, 0.28);
        border-radius: 999px;
        color: #60a5fa;
        display: inline-flex;
        font-size: 0.7rem;
        gap: 0.35rem;
        margin-bottom: 0.9rem;
        padding: 0.36rem 0.72rem;
    }

    .auth-eyebrow--pill::before {
        content: "◆";
        color: #3b82f6;
        font-size: 0.66rem;
    }

    .auth-hero-panel h1 {
        color: #f8fafc !important;
        font-size: clamp(2.15rem, 4vw, 3.6rem);
        font-weight: 850;
        line-height: 1.05;
        margin: 0 0 1.1rem;
    }

    .auth-hero-panel h1 span {
        color: #2f86ff !important;
    }

    .auth-hero-panel p {
        color: #c3cfdf !important;
        font-size: 1rem;
        line-height: 1.65;
        margin: 0;
        max-width: 34rem;
    }

    .auth-feature-grid {
        display: grid;
        gap: 1.15rem 1.3rem;
        grid-template-columns: repeat(2, minmax(0, 1fr));
        margin: 1.8rem 0 1.7rem;
        max-width: 38rem;
    }

    .auth-feature {
        min-height: 4.4rem;
        padding-left: 3.15rem;
        position: relative;
    }

    .auth-feature::before,
    .auth-access-note::before {
        align-items: center;
        background: rgba(37, 99, 235, 0.22);
        border: 1px solid rgba(59, 130, 246, 0.38);
        border-radius: 999px;
        color: #38bdf8;
        content: "✓";
        display: flex;
        font-weight: 900;
        height: 2.25rem;
        justify-content: center;
        left: 0;
        position: absolute;
        top: 0.05rem;
        width: 2.25rem;
    }

    .auth-feature:nth-child(2)::before {
        background: rgba(16, 185, 129, 0.18);
        border-color: rgba(16, 185, 129, 0.32);
        color: #34d399;
    }

    .auth-feature:nth-child(3)::before {
        background: rgba(124, 58, 237, 0.2);
        border-color: rgba(124, 58, 237, 0.36);
        color: #a78bfa;
    }

    .auth-feature:nth-child(4)::before {
        background: rgba(234, 179, 8, 0.15);
        border-color: rgba(234, 179, 8, 0.32);
        color: #facc15;
    }

    .auth-feature b {
        color: #f8fafc;
        display: block;
        font-size: 0.9rem;
        line-height: 1.25;
        margin-bottom: 0.32rem;
    }

    .auth-feature small {
        color: #b4c1d2;
        display: block;
        font-size: 0.78rem;
        line-height: 1.45;
    }

    .auth-access-note {
        background: rgba(22, 50, 88, 0.58);
        border: 1px solid rgba(96, 165, 250, 0.26);
        border-radius: 8px;
        max-width: 38rem;
        min-height: 5.35rem;
        padding: 1rem 1rem 1rem 4.2rem;
        position: relative;
    }

    .auth-access-note::before {
        height: 2.7rem;
        left: 1rem;
        top: 1.15rem;
        width: 2.7rem;
    }

    .auth-access-note b,
    .auth-access-note span {
        display: block;
    }

    .auth-access-note b {
        color: #7dd3fc;
        font-size: 0.88rem;
        margin-bottom: 0.35rem;
    }

    .auth-access-note span {
        color: #b8c4d4;
        font-size: 0.78rem;
        line-height: 1.55;
    }

    .auth-card-head {
        text-align: center;
    }

    .auth-shield {
        align-items: center;
        background: radial-gradient(circle, rgba(37, 99, 235, 0.28), rgba(15, 23, 42, 0.92));
        border: 1px solid rgba(59, 130, 246, 0.44);
        border-radius: 999px;
        box-shadow: 0 0 34px rgba(37, 99, 235, 0.36);
        color: #38bdf8;
        display: inline-flex;
        font-size: 1.9rem;
        font-weight: 900;
        height: 4.2rem;
        justify-content: center;
        margin-bottom: 1rem;
        width: 4.2rem;
    }

    .auth-card-head h2 {
        color: #f8fafc !important;
        font-size: 1.55rem;
        font-weight: 850;
        line-height: 1.15;
        margin: 0 0 0.35rem;
    }

    .auth-card-head p {
        color: #b7c2d2 !important;
        font-size: 0.86rem;
        margin: 0 0 1.15rem;
    }

    div[data-testid="column"]:has(.auth-card-head) div[role="radiogroup"] {
        background: rgba(30, 50, 78, 0.74);
        border: 1px solid rgba(148, 163, 184, 0.14);
        border-radius: 8px;
        display: grid;
        gap: 0;
        grid-template-columns: repeat(2, minmax(0, 1fr));
        margin: 0 0 1rem;
        overflow: hidden;
        padding: 0;
    }

    div[data-testid="column"]:has(.auth-card-head) div[role="radiogroup"] label {
        background: transparent;
        border: 0;
        border-radius: 0;
        color: #d7e2f0 !important;
        justify-content: center;
        margin: 0;
        min-height: 2.8rem;
        padding: 0.55rem 0.7rem;
    }

    div[data-testid="column"]:has(.auth-card-head) div[role="radiogroup"] label:has(input:checked) {
        background: linear-gradient(180deg, rgba(59, 130, 246, 0.22), rgba(14, 165, 233, 0.14));
        border-bottom: 2px solid #38bdf8;
        color: #7dd3fc !important;
    }

    div[data-testid="column"]:has(.auth-card-head) label,
    div[data-testid="column"]:has(.auth-card-head) p,
    div[data-testid="column"]:has(.auth-card-head) span {
        color: #dbe7f5 !important;
    }

    div[data-testid="column"]:has(.auth-card-head) div[data-baseweb="input"] > div,
    div[data-testid="column"]:has(.auth-card-head) div[data-baseweb="select"] > div {
        background: rgba(9, 20, 38, 0.74) !important;
        border: 1px solid rgba(148, 163, 184, 0.26) !important;
        border-radius: 8px !important;
        min-height: 2.75rem;
    }

    div[data-testid="column"]:has(.auth-card-head) input {
        color: #e5edf8 !important;
    }

    div[data-testid="column"]:has(.auth-card-head) input::placeholder {
        color: #7f8fa3 !important;
    }

    div[data-testid="column"]:has(.auth-card-head) .stCheckbox {
        margin-top: -0.15rem;
    }

    .auth-forgot {
        color: #38bdf8;
        font-size: 0.78rem;
        margin: -2.05rem 0 1.45rem;
        pointer-events: none;
        text-align: right;
    }

    div[data-testid="column"]:has(.auth-card-head) .stButton button,
    div[data-testid="column"]:has(.auth-card-head) div[data-testid="stFormSubmitButton"] button {
        background: linear-gradient(135deg, #2388ff 0%, #2563eb 100%) !important;
        border: 1px solid rgba(96, 165, 250, 0.32) !important;
        border-radius: 8px !important;
        box-shadow: 0 18px 38px rgba(37, 99, 235, 0.22);
        color: #ffffff !important;
        min-height: 2.9rem;
    }

    .auth-card-foot {
        border-top: 1px solid rgba(148, 163, 184, 0.18);
        color: #8ea0b5;
        font-size: 0.78rem;
        margin-top: 1.55rem;
        padding-top: 0.85rem;
        text-align: center;
    }

    .auth-footer {
        align-items: center;
        border-top: 1px solid rgba(148, 163, 184, 0.1);
        color: #9fb0c3;
        display: flex;
        font-size: 0.78rem;
        justify-content: space-between;
        margin: 1.35rem -2.25rem -1rem;
        padding: 1rem 2.25rem 0;
    }

    .auth-footer b,
    .auth-footer span {
        display: block;
    }

    .auth-footer b {
        color: #f8fafc;
        margin-bottom: 0.32rem;
    }

    @media (max-width: 900px) {
        .auth-page {
            margin: -0.8rem -1rem -2rem;
            padding: 1.3rem 1rem 0.8rem;
        }

        div[data-testid="column"]:has(.auth-card-head) {
            margin-top: 1rem;
            min-height: auto;
            padding: 1.35rem 1rem;
        }

        .auth-logo {
            height: 3rem;
            margin-bottom: 1.35rem;
        }

        .auth-hero-panel h1 {
            font-size: 2.2rem;
        }

        .auth-feature-grid {
            grid-template-columns: 1fr;
            margin: 1.3rem 0;
        }

        .auth-access-note {
            padding-right: 0.85rem;
        }

        .auth-forgot {
            margin-top: 0;
            text-align: left;
        }

        .auth-footer {
            align-items: flex-start;
            flex-direction: column;
            gap: 0.8rem;
            margin-left: -1rem;
            margin-right: -1rem;
            padding-left: 1rem;
            padding-right: 1rem;
        }
    }

    /* Login reference screen override */
    .auth-page {
        background:
            radial-gradient(circle at 15% 8%, rgba(37, 99, 235, 0.2), transparent 25rem),
            radial-gradient(circle at 88% 10%, rgba(37, 99, 235, 0.3), transparent 30rem),
            linear-gradient(135deg, #061329 0%, #071d3d 50%, #082c5f 100%) !important;
        margin: -0.75rem -1rem 0 !important;
        min-height: auto !important;
        padding: 0.9rem 2.15rem 0.75rem !important;
    }

    .auth-page .stHorizontalBlock {
        align-items: center;
        gap: 4.7rem !important;
        max-width: 1380px;
        margin: 0 auto;
    }

    .auth-logo {
        height: 4rem !important;
        margin-bottom: 2.45rem !important;
    }

    .auth-eyebrow--pill {
        background: rgba(37, 99, 235, 0.26) !important;
        border-color: rgba(59, 130, 246, 0.28) !important;
        color: #38bdf8 !important;
        margin-bottom: 1.05rem !important;
    }

    .auth-hero-panel h1 {
        color: #ffffff !important;
        font-size: clamp(2.65rem, 4.2vw, 3.9rem) !important;
        font-weight: 900 !important;
        line-height: 1.06 !important;
        margin-bottom: 1.05rem !important;
    }

    .auth-hero-panel h1 span {
        color: #2f86ff !important;
    }

    .auth-hero-panel p {
        color: #c9d5e5 !important;
        font-size: 1rem !important;
        line-height: 1.7 !important;
        max-width: 34.5rem !important;
    }

    .auth-feature-grid {
        gap: 1.55rem 2.05rem !important;
        margin: 1.95rem 0 1.75rem !important;
        max-width: 40rem !important;
    }

    .auth-feature {
        min-height: 4.3rem !important;
        padding-left: 3.8rem !important;
    }

    .auth-feature::before,
    .auth-access-note::before {
        content: "▣" !important;
        font-size: 1rem;
        height: 2.7rem !important;
        width: 2.7rem !important;
    }

    .auth-feature b {
        font-size: 0.86rem !important;
    }

    .auth-feature small {
        color: #c0ccdc !important;
        font-size: 0.77rem !important;
    }

    .auth-access-note {
        background: rgba(16, 43, 79, 0.76) !important;
        border-color: rgba(96, 165, 250, 0.32) !important;
        max-width: 40rem !important;
        min-height: 5.9rem !important;
        padding: 1rem 1.35rem 1rem 4.95rem !important;
    }

    .auth-access-note::before {
        content: "✓" !important;
        left: 1rem !important;
        top: 1.45rem !important;
    }

    .auth-access-note b {
        color: #7dd3fc !important;
        font-size: 0.9rem !important;
    }

    div[data-testid="column"]:has(.auth-card-head) {
        background:
            radial-gradient(circle at 50% 6%, rgba(37, 99, 235, 0.16), transparent 14rem),
            linear-gradient(145deg, rgba(15, 32, 56, 0.92), rgba(9, 21, 39, 0.96)) !important;
        border: 1px solid rgba(148, 163, 184, 0.3) !important;
        border-radius: 12px !important;
        box-shadow: 0 28px 90px rgba(0, 0, 0, 0.34) !important;
        max-width: 38.8rem;
        min-height: auto !important;
        padding: 1.55rem 2.55rem 1.35rem !important;
    }

    .auth-shield {
        background:
            radial-gradient(circle, rgba(37, 99, 235, 0.3), rgba(15, 23, 42, 0.92)) !important;
        border-color: rgba(59, 130, 246, 0.48) !important;
        color: #2f86ff !important;
        font-size: 2.2rem !important;
        height: 5rem !important;
        margin-bottom: 1.25rem !important;
        width: 5rem !important;
    }

    .auth-card-head h2 {
        font-size: 1.75rem !important;
        margin-bottom: 0.45rem !important;
    }

    .auth-card-head p {
        color: #b8c5d7 !important;
        margin-bottom: 1.45rem !important;
    }

    div[data-testid="column"]:has(.auth-card-head) div[role="radiogroup"] {
        margin-bottom: 1.25rem !important;
    }

    div[data-testid="column"]:has(.auth-card-head) div[role="radiogroup"] label {
        min-height: 3rem !important;
    }

    div[data-testid="column"]:has(.auth-card-head) div[data-baseweb="input"] > div {
        min-height: 3rem !important;
    }

    div[data-testid="column"]:has(.auth-card-head) .stButton button {
        min-height: 3.25rem !important;
        margin-top: 0.55rem !important;
    }

    .auth-forgot {
        color: #38bdf8 !important;
        margin-bottom: 1.35rem !important;
    }

    .auth-card-foot {
        color: #9aaac0 !important;
        margin-top: 1.95rem !important;
    }

    .auth-footer {
        background: rgba(7, 20, 40, 0.3);
        margin: 0.95rem -2.15rem 0 !important;
        padding: 0.85rem 2.15rem 0.75rem !important;
    }

    @media (max-width: 900px) {
        .auth-page {
            padding: 1rem !important;
        }

        .auth-page .stHorizontalBlock {
            gap: 1rem !important;
        }

        div[data-testid="column"]:has(.auth-card-head) {
            max-width: none;
            min-height: auto !important;
            padding: 1.4rem 1rem !important;
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
