import json
from datetime import datetime, time, timedelta, timezone

import pandas as pd
import streamlit as st

import auth
from database.audit_log import activity_csv, activity_filter_values, paginate_activities
from utils import inject_global_ui, render_navigation, render_top_nav, render_table


st.set_page_config(page_title="Activity Log", page_icon="🛡️", layout="wide")
inject_global_ui()

if not auth.login():
    st.stop()

auth.require_role(["admin"])
render_navigation()
render_top_nav()

st.markdown(
    """
<div class="dashboard-hero">
    <div class="hero-eyebrow">Security · Administration · Traceability</div>
    <h1>Activity logs</h1>
    <p>Investigate account and system activity, narrow the timeline, and export exactly what you need.</p>
</div>
""",
    unsafe_allow_html=True,
)

today = datetime.now(timezone.utc).date()
if "activity_page" not in st.session_state:
    st.session_state.activity_page = 1

try:
    filters = activity_filter_values()
except Exception as exc:
    st.error(f"The activity log could not be loaded: {exc}")
    st.stop()

with st.container(border=True):
    st.markdown("#### Filter activity")
    st.caption("Dates use UTC. The export includes every matching row, not only the page on screen.")
    date_col, user_col, action_col, status_col, size_col = st.columns([1.55, 1, 1.15, 1, .7])
    with date_col:
        selected_dates = st.date_input(
            "Date range",
            value=(today - timedelta(days=6), today),
            max_value=today,
            help="Choose the first and last UTC date to include.",
        )
    with user_col:
        selected_user = st.selectbox("User", ["All users"] + filters["usernames"])
    with action_col:
        selected_action = st.selectbox("Action", ["All actions"] + filters["actions"])
    with status_col:
        selected_status = st.selectbox("Result", ["All results"] + filters["statuses"])
    with size_col:
        page_size = st.selectbox("Rows", [10, 25, 50, 100], index=1)

if isinstance(selected_dates, (tuple, list)):
    start_date = selected_dates[0]
    end_date = selected_dates[-1]
else:
    start_date = end_date = selected_dates

start_at = datetime.combine(start_date, time.min, tzinfo=timezone.utc)
end_at = datetime.combine(end_date + timedelta(days=1), time.min, tzinfo=timezone.utc)
username = None if selected_user == "All users" else selected_user
action = None if selected_action == "All actions" else selected_action
result = None if selected_status == "All results" else selected_status

filter_signature = (start_date, end_date, username, action, result, page_size)
if st.session_state.get("activity_filter_signature") != filter_signature:
    st.session_state.activity_filter_signature = filter_signature
    st.session_state.activity_page = 1

try:
    result_page = paginate_activities(
        start_at, end_at, username, action, result,
        page=st.session_state.activity_page, page_size=page_size,
    )
except Exception as exc:
    st.error(f"The filtered activity could not be loaded: {exc}")
    st.stop()

st.session_state.activity_page = result_page["page"]
records = result_page["items"]
frame = pd.DataFrame(records)

if not frame.empty:
    frame["Details"] = frame.get("details", pd.Series(dtype=object)).apply(
        lambda value: json.dumps(value, default=str, ensure_ascii=False) if value else "—"
    )
    frame["Timestamp (UTC)"] = pd.to_datetime(frame["occurred_at"], utc=True).dt.strftime(
        "%d %b %Y · %H:%M:%S"
    )
    display = frame.rename(columns={
        "username": "Username", "name": "Name", "role": "Role", "action": "Action",
        "category": "Category", "page": "Page", "target": "Target", "status": "Result",
        "cloud_archive_status": "Archive",
    })
    columns = [
        "Timestamp (UTC)", "Username", "Name", "Role", "Action", "Category",
        "Page", "Target", "Result", "Archive", "Details",
    ]
else:
    display, columns = pd.DataFrame(), None

metric_total, metric_page, metric_range, export_col = st.columns([1, 1, 1.25, 1.5])
metric_total.metric("Matching events", f"{result_page['total']:,}")
metric_page.metric("Current page", f"{result_page['page']} of {result_page['total_pages']}")
metric_range.metric("UTC range", f"{start_date:%d %b} – {end_date:%d %b %Y}")
with export_col:
    csv_bytes = activity_csv(start_at, end_at, username, action, result)
    st.download_button(
        "⬇ Download filtered CSV",
        csv_bytes,
        file_name=f"qaqc_activity_logs_{start_date}_{end_date}.csv",
        mime="text/csv",
        type="primary",
        use_container_width=True,
        disabled=result_page["total"] == 0,
        help="Downloads all records matching the filters.",
    )

render_table(
    display,
    height=540,
    columns=columns,
    empty_message="No activity was found in this range. Try widening the dates or clearing a filter.",
    include_internal=True,
)

previous_col, position_col, next_col = st.columns([1, 2, 1])
with previous_col:
    if st.button(
        "← Previous", disabled=not result_page["has_previous"], use_container_width=True,
    ):
        st.session_state.activity_page -= 1
        st.rerun()
with position_col:
    first_row = (result_page["page"] - 1) * result_page["page_size"] + 1 if result_page["total"] else 0
    last_row = min(result_page["page"] * result_page["page_size"], result_page["total"])
    st.markdown(
        f"<p style='text-align:center;margin:.7rem 0 0'>Showing <b>{first_row:,}–{last_row:,}</b> "
        f"of <b>{result_page['total']:,}</b></p>",
        unsafe_allow_html=True,
    )
with next_col:
    if st.button("Next →", disabled=not result_page["has_next"], use_container_width=True):
        st.session_state.activity_page += 1
        st.rerun()

st.caption(
    "Access is restricted to administrators. Timestamps and date filters use UTC. "
    "CSV exports are UTF-8 encoded for Excel compatibility."
)
