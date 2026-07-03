from pathlib import Path

import pandas as pd
import streamlit as st

import auth
from utils import (
    acknowledge_calibration,
    get_calibration_log,
    get_calibration_reminders,
    get_calibration_summary,
    inject_global_ui,
    load_master_data,
    render_navigation,
    render_top_nav,
    snooze_calibration,
)


st.set_page_config(page_title="Calibration Log", layout="wide")
inject_global_ui()

if not auth.login():
    st.stop()

render_navigation()
render_top_nav()
getattr(auth, "render_user_sidebar", lambda: None)()

DATA_FILE = Path(__file__).parents[1] / "data" / "QAQC_Master.xlsx"
data = load_master_data(DATA_FILE)
log = get_calibration_log(data)
summary = get_calibration_summary(data)

st.title("Calibration Log")
st.markdown("Monitor equipment calibration status, overdue items, and reminder actions.")

if log.empty:
    st.warning("No calibration records are available in the master workbook.")
    st.stop()

metric_1, metric_2, metric_3, metric_4, metric_5 = st.columns(5)
metric_1.metric("Equipment records", summary["total"])
metric_2.metric("Active records", summary["active"])
metric_3.metric("Overdue", summary["overdue"])
metric_4.metric("Due in 21 days", summary["due_in_21_days"])
metric_5.metric("Snoozed", summary["snoozed"])

reminders = get_calibration_reminders(data)
overdue = reminders[reminders["Days_Until_Due"] < 0]
due_21 = reminders[reminders["Days_Until_Due"] == 21]
due_soon = reminders[(reminders["Days_Until_Due"] >= 0) & (reminders["Days_Until_Due"] < 21)]

display_cols = [
    "Calibration_ID",
    "Equipment_Category",
    "Project",
    "Equipment_Type",
    "Make_Model",
    "Serial_No",
    "Calibration_Date",
    "Next_Due_Date",
    "Days_Until_Due",
    "Alert_Status",
    "Status",
    "Acknowledged_On",
    "Snoozed_Until",
]

tab_alerts, tab_overdue, tab_all = st.tabs(["Reminder Actions", "Overdue Equipment", "All Calibration Records"])

with tab_alerts:
    if reminders.empty:
        st.success("No active calibration reminders today.")
    else:
        st.markdown("#### Active reminders")
        st.dataframe(reminders[display_cols], use_container_width=True, hide_index=True)

        st.markdown("#### Acknowledge or snooze")
        action_cols = st.columns([1.4, 1, 1, 1.3])
        with action_cols[0]:
            selected_id = st.selectbox(
                "Equipment record",
                reminders["Calibration_ID"].astype(str).tolist(),
                key="calibration_action_record",
            )
        with action_cols[1]:
            snooze_days = st.number_input("Snooze days", min_value=1, max_value=30, value=1, step=1)
        with action_cols[2]:
            st.write("")
            st.write("")
            if st.button("Acknowledge", use_container_width=True):
                acknowledge_calibration(selected_id)
                st.success("Reminder acknowledged.")
                st.rerun()
        with action_cols[3]:
            st.write("")
            st.write("")
            if st.button("Snooze", use_container_width=True):
                snooze_calibration(selected_id, snooze_days)
                st.success(f"Reminder snoozed for {snooze_days} day(s).")
                st.rerun()

        selected_row = reminders[reminders["Calibration_ID"].astype(str) == str(selected_id)].head(1)
        if not selected_row.empty:
            st.markdown("#### Selected equipment")
            st.dataframe(selected_row[display_cols], use_container_width=True, hide_index=True)

with tab_overdue:
    if overdue.empty:
        st.success("No overdue calibration items.")
    else:
        st.error(f"{len(overdue)} equipment item(s) are overdue for calibration.")
        st.dataframe(overdue[display_cols], use_container_width=True, hide_index=True)

with tab_all:
    filters = st.columns([1, 1, 1])
    with filters[0]:
        categories = ["All"] + sorted(log["Equipment_Category"].dropna().astype(str).unique().tolist())
        selected_category = st.selectbox("Category", categories)
    with filters[1]:
        statuses = ["All"] + sorted(log["Alert_Status"].dropna().astype(str).unique().tolist())
        selected_status = st.selectbox("Alert status", statuses)
    with filters[2]:
        search = st.text_input("Search equipment", placeholder="Equipment, serial number, certificate...")

    visible = log.copy()
    if selected_category != "All":
        visible = visible[visible["Equipment_Category"].astype(str) == selected_category]
    if selected_status != "All":
        visible = visible[visible["Alert_Status"].astype(str) == selected_status]
    if search:
        needle = search.strip().lower()
        search_cols = ["Equipment_Type", "Make_Model", "Serial_No", "Certificate_No", "Calibration_ID"]
        mask = pd.Series(False, index=visible.index)
        for column in search_cols:
            if column in visible.columns:
                mask = mask | visible[column].astype(str).str.lower().str.contains(needle, na=False)
        visible = visible[mask]

    st.dataframe(visible[display_cols], use_container_width=True, hide_index=True, height=520)
