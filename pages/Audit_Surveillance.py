import streamlit as st
import pandas as pd
import plotly.express as px
from pathlib import Path
from utils import load_master_data, global_filter_sidebar, apply_filters, render_table, inject_global_ui, render_table_with_details
from auth import login

if not login():
    st.stop()
BASE_DIR = Path(__file__).resolve().parent.parent    
DATA_FILE = Path(__file__).parents[1] / "data" / "QAQC_Master.xlsx"

st.set_page_config(page_title="Audit & Surveillance", layout="wide")
inject_global_ui()

st.title("Audit & Surveillance")
st.markdown("Track planned and actual audit/surveillance activities and compliance performance.")

filters = global_filter_sidebar(load_master_data(DATA_FILE)) # pyright: ignore[reportArgumentType]
data = load_master_data(DATA_FILE) # pyright: ignore[reportArgumentType]
audit = apply_filters(data.get("Audit Register", pd.DataFrame()), filters, date_column="Planned_Date")
surveillance = apply_filters(data.get("Surveillance Register", pd.DataFrame()), filters, date_column="Planned_Date")

if audit.empty and surveillance.empty:
    st.warning("No audit or surveillance records available.")
    st.stop()

st.subheader("Audit Performance")
c1, c2, c3 = st.columns(3)
c1.metric("Total Audits", len(audit))
completed_audits = int((audit["Status"].str.lower() == "completed").sum()) if "Status" in audit.columns else 0
c2.metric("Completed Audits", completed_audits)
c3.metric("Audit Compliance", f"{int(completed_audits / max(1, len(audit)) * 100)}%" if len(audit) else "0%")

st.markdown("---")
table_cols_audit = [col for col in ["Audit_ID", "Project", "Planned_Date", "Actual_Date", "Status"] if col in audit.columns]
id_col_audit = "Audit_ID" if "Audit_ID" in audit.columns else None
selected_audit = render_table_with_details(audit, id_col=id_col_audit, table_columns=table_cols_audit, detail_label="Audit") # pyright: ignore[reportArgumentType]

st.markdown("---")
if not audit.empty:
    planned_actual = audit["Status"].value_counts().reset_index()
    planned_actual.columns = ["Status", "Count"]
    st.plotly_chart(px.bar(planned_actual, x="Status", y="Count", title="Audit Planned vs Actual"), use_container_width=True)

st.markdown("---")
st.subheader("Surveillance Performance")
c1, c2, c3 = st.columns(3)
c1.metric("Total Surveys", len(surveillance))
completed_surv = int((surveillance["Status"].str.lower() == "completed").sum()) if "Status" in surveillance.columns else 0
c2.metric("Completed Surveillance", completed_surv)
c3.metric("Surveillance Compliance", f"{int(completed_surv / max(1, len(surveillance)) * 100)}%" if len(surveillance) else "0%")

st.markdown("---")
render_table(surveillance[[col for col in ["Surveillance_ID", "Project", "Planned_Date", "Actual_Date", "Status"] if col in surveillance.columns]])
table_cols_surv = [col for col in ["Surveillance_ID", "Project", "Planned_Date", "Actual_Date", "Status"] if col in surveillance.columns]
id_col_surv = "Surveillance_ID" if "Surveillance_ID" in surveillance.columns else None
selected_surv = render_table_with_details(surveillance, id_col=id_col_surv, table_columns=table_cols_surv, detail_label="Surveillance") # pyright: ignore[reportArgumentType]

if not surveillance.empty:
    planned_actual = surveillance["Status"].value_counts().reset_index()
    planned_actual.columns = ["Status", "Count"]
    st.plotly_chart(px.bar(planned_actual, x="Status", y="Count", title="Surveillance Planned vs Actual"), use_container_width=True)
