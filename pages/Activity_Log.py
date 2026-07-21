import json
from datetime import datetime, time, timedelta, timezone
from pathlib import Path
import tempfile

import pandas as pd
import streamlit as st

import auth
from database.activity_workbook import build_activity_workbook
from database.audit_log import activity_filter_values, list_activities
from utils import inject_global_ui, render_navigation, render_top_nav, render_table


st.set_page_config(page_title="Activity Log", layout="wide")
inject_global_ui()

if not auth.login():
    st.stop()

auth.require_role(["admin"])
render_navigation()
render_top_nav()

st.markdown(
    """
<div class="dashboard-hero">
    <div class="hero-eyebrow">Administration and traceability</div>
    <h1>User Activity Log</h1>
    <p>Review daily sign-ins, page access, account administration, profile changes, support actions, and record updates.</p>
</div>
""",
    unsafe_allow_html=True,
)

today = datetime.now(timezone.utc).date()
date_col, user_col, action_col, status_col = st.columns([1.4, 1, 1.2, 1])
with date_col:
    selected_dates = st.date_input(
        "Activity date (UTC)",
        value=(today, today),
        max_value=today,
    )

try:
    filters = activity_filter_values()
except Exception as exc:
    st.error(f"The activity log could not be loaded: {exc}")
    st.stop()

with user_col:
    selected_user = st.selectbox("User", ["All users"] + filters["usernames"])
with action_col:
    selected_action = st.selectbox("Action", ["All actions"] + filters["actions"])
with status_col:
    selected_status = st.selectbox("Result", ["All results"] + filters["statuses"])

if isinstance(selected_dates, (tuple, list)):
    start_date = selected_dates[0]
    end_date = selected_dates[-1]
else:
    start_date = end_date = selected_dates
start_at = datetime.combine(start_date, time.min, tzinfo=timezone.utc)
end_at = datetime.combine(end_date + timedelta(days=1), time.min, tzinfo=timezone.utc)

records = list_activities(
    start_at=start_at,
    end_at=end_at,
    username=None if selected_user == "All users" else selected_user,
    action=None if selected_action == "All actions" else selected_action,
    status=None if selected_status == "All results" else selected_status,
)

frame = pd.DataFrame(records)
if not frame.empty:
    frame["Details"] = frame.get("details", pd.Series(dtype=object)).apply(
        lambda value: json.dumps(value, default=str) if value else ""
    )
    frame["Timestamp (UTC)"] = pd.to_datetime(frame["occurred_at"], utc=True).dt.strftime("%d %b %Y %H:%M:%S")
    display = frame.rename(
        columns={
            "username": "Username",
            "name": "Name",
            "role": "Role",
            "action": "Action",
            "category": "Category",
            "page": "Page",
            "target": "Target",
            "status": "Result",
            "cloud_archive_status": "Cloud Archive",
        }
    )
    columns = [
        "Timestamp (UTC)", "Username", "Name", "Role", "Action", "Category",
        "Page", "Target", "Result", "Cloud Archive", "Details",
    ]
else:
    display = pd.DataFrame()
    columns = None

c1, c2, c3, c4 = st.columns(4)
c1.metric("Recorded activities", len(frame))
c2.metric("Active users", int(frame["username"].nunique()) if not frame.empty else 0)
c3.metric("Successful", int((frame["status"] == "success").sum()) if not frame.empty else 0)
c4.metric("Failed / denied", int(frame["status"].isin(["failed", "denied"]).sum()) if not frame.empty else 0)

render_table(display, height=560, columns=columns, empty_message="No activities match the selected daily filters.", include_internal=True)

if not frame.empty:
    export = display[columns].to_csv(index=False).encode("utf-8")
    with tempfile.TemporaryDirectory(prefix="qaqc-activity-download-") as temp_dir:
        workbook_path = Path(temp_dir) / "QAQC_Activity_Log.xlsx"
        build_activity_workbook(records, workbook_path)
        excel_export = workbook_path.read_bytes()
    csv_col, excel_col = st.columns(2)
    csv_col.download_button(
        "Download filtered activity log (CSV)", export,
        file_name=f"qaqc_activity_log_{start_date}_{end_date}.csv",
        mime="text/csv", use_container_width=True,
    )
    excel_col.download_button(
        "Download filtered activity log (Excel)", excel_export,
        file_name=f"qaqc_activity_log_{start_date}_{end_date}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
    )

st.caption(
    "Times are recorded and filtered in UTC. Activity records are visible only to administrators. "
    "The complete workbook is archived in Cloudinary as "
    "qaqc-dashboard/activity-logs/QAQC_Activity_Log.xlsx."
)
