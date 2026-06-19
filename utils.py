from pathlib import Path
import pandas as pd
import streamlit as st


# =========================
# DATA LOADING (DICT SYSTEM)
# =========================

def load_master_data(file_path):
    """
    Load Excel file and return a DICTIONARY of DataFrames
    based on sheet names (THIS MATCHES YOUR app.py design)
    """
    try:
        if not file_path or not Path(file_path).exists():
            st.error("Excel file not found")
            return {}

        xls = pd.ExcelFile(file_path)

        data = {}
        for sheet in xls.sheet_names:
            data[sheet] = pd.read_excel(xls, sheet)

        return data

    except Exception as e:
        st.error(f"Error loading master data: {e}")
        return {}


# =========================
# LOGO
# =========================

def load_company_logo(path):
    p = Path(path)
    return str(p) if p.exists() else None


# =========================
# TABLE RENDERING
# =========================

def render_table(df, height=300):
    if isinstance(df, pd.DataFrame) and not df.empty:
        st.dataframe(df, height=height, use_container_width=True)
    else:
        st.info("No data available")


# =========================
# GLOBAL FILTERS
# =========================
def global_filter_sidebar(data):
    """
    Safe global project filter for dict of DataFrames
    """

    st.sidebar.header("Global Filters")

    if not isinstance(data, dict):
        return data

    # =========================
    # STEP 1: COLLECT PROJECTS
    # =========================
    projects = set()

    for df in data.values():
        if isinstance(df, pd.DataFrame) and "Project" in df.columns:
            projects.update(
                df["Project"].dropna().astype(str).unique()
            )

    # FINAL SORT (ONLY ONCE)
    projects = extract_projects(data)
    project_count = len(projects)

    # Optional display (debug/info)
    st.sidebar.caption(f"Total Projects: {project_count}")

    # =========================
    # STEP 2: UI SELECTOR
    # =========================
    selected_project = st.sidebar.selectbox(
        "Project",
        ["All"] + projects
    )

    # =========================
    # STEP 3: RETURN DATA
    # =========================
    if selected_project == "All":
        return data

    filtered = {}

    for k, df in data.items():
        if isinstance(df, pd.DataFrame) and "Project" in df.columns:
            filtered[k] = df[df["Project"] == selected_project]
        else:
            filtered[k] = df

    return filtered


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
    st.markdown(
        """
        <style>
        .main {
            background-color: #0b1320;
        }

        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
        header {visibility: hidden;}

        .kpi-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
            gap: 1rem;
        }

        .kpi-card {
            padding: 1rem;
            border-radius: 16px;
            color: white;
            box-shadow: 0 10px 30px rgba(0,0,0,0.3);
        }

        .kpi-title {
            font-size: 0.9rem;
            opacity: 0.8;
        }

        .kpi-value {
            font-size: 1.8rem;
            font-weight: bold;
        }
        </style>
        """,
        unsafe_allow_html=True
    )


# =========================
# IMAGE FINDER
# =========================

def _find_image_path(path_like):
    p = Path(path_like)

    if p.exists():
        return str(p)

    for ext in [".png", ".jpg", ".jpeg", ".webp"]:
        if p.with_suffix(ext).exists():
            return str(p.with_suffix(ext))

    return None
def extract_projects(data):
    """
    Safely extract unique project names from dict of DataFrames
    """
    if not isinstance(data, dict):
        return []

    projects = set()

    for df in data.values():
        if isinstance(df, pd.DataFrame) and "Project" in df.columns:
            projects.update(df["Project"].dropna().astype(str).unique())

    return sorted(projects)

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


def render_table_with_details(
    df,
    id_col=None,
    table_columns=None,
    detail_label="Details"
):
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