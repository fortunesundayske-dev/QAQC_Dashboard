import streamlit as st
import pandas as pd
import utils
import plotly.express as px
from pathlib import Path
from utils import (
    load_master_data,
    global_filter_sidebar,
    apply_filters,
    render_table,
    inject_global_ui,
    render_table_with_details,
    render_navigation,
    render_top_nav
)
from auth import login


DATA_FILE = Path(__file__).parents[1] / "data" / "QAQC_Master.xlsx"
BASE_DIR = Path(__file__).resolve().parent.parent
st.set_page_config(page_title="Lessons Learned", layout="wide")
inject_global_ui()
if not login():
    st.stop()
render_navigation()
render_top_nav()
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
st.title("Lessons Learned")
st.markdown("Capture project lessons, impacts, and recommendations for continuous improvement.")

filters = global_filter_sidebar(load_master_data(DATA_FILE))
data = load_master_data(DATA_FILE)
lessons = apply_filters(data.get("Lessons Learned", pd.DataFrame()), filters, date_column="Date_Logged")

if lessons.empty:
    st.warning("No lessons learned records available.")
    st.stop()

table_cols = [col for col in ["Lesson_ID","Project", "Category", "Lesson", "Impact", "Recommendation", "Date_Logged"] if col in lessons.columns]
id_col = "Lesson_ID" if "Lesson_ID" in lessons.columns else None
selected = render_table_with_details(lessons, id_col=id_col, table_columns=table_cols, detail_label="Lesson")

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

st.markdown("---")
if "Discipline" in lessons.columns:
    discipline_data = lessons["Discipline"].value_counts().reset_index()
    discipline_data.columns = ["Discipline", "Count"]
    st.plotly_chart(px.bar(discipline_data, x="Discipline", y="Count", title="Lessons by Discipline"), use_container_width=True)

if "Project" in lessons.columns:
    project_data = lessons["Project"].value_counts().reset_index()
    project_data.columns = ["Project", "Count"]
    st.plotly_chart(px.bar(project_data, x="Project", y="Count", title="Lessons by Project"), use_container_width=True)

if "Category" in lessons.columns:
    category_data = lessons["Category"].value_counts().reset_index()
    category_data.columns = ["Category", "Count"]
    st.plotly_chart(px.bar(category_data, x="Category", y="Count", title="Lessons by Category"), use_container_width=True)
