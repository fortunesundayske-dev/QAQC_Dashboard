import streamlit as st

# =========================
# CONFIG (MUST BE FIRST)
# =========================
st.set_page_config(
    page_title="Evomec QA/QC Executive Dashboard",
    page_icon="QA",
    layout="wide",
    initial_sidebar_state="expanded",
)

from pathlib import Path
import html

import pandas as pd
import plotly.express as px

import auth
from utils import (
    extract_projects,
    global_filter_sidebar,
    inject_enterprise_theme,
    load_master_data,
    render_header,
    render_table,
    render_top_nav,
    get_navigation_pages,
    render_navigation
)


BASE_DIR = Path(__file__).resolve().parent
EXCEL_FILE = BASE_DIR / "data" / "QAQC_Master.xlsx"
get_navigation_pages()

def status_count(df, status):
    if not isinstance(df, pd.DataFrame) or df.empty or "Status" not in df.columns:
        return 0
    return int(df["Status"].astype(str).str.lower().eq(status.lower()).sum())


def status_count_any(df, statuses):
    if not isinstance(df, pd.DataFrame) or df.empty or "Status" not in df.columns:
        return 0
    wanted = {status.lower() for status in statuses}
    return int(df["Status"].astype(str).str.strip().str.lower().isin(wanted).sum())


def open_count(df):
    return status_count(df, "Open")


def closed_count(df):
    return status_count(df, "Closed") + status_count(df, "Completed")


def pct(numerator, denominator):
    return int((numerator / denominator) * 100) if denominator else 0


def metric_card(label, value, subtitle, accent, mark):
    return f"""
<div class="exec-metric" style="--metric-color: {accent};">
    <div class="exec-metric__icon">{mark}</div>
    <div>
        <div class="exec-metric__label">{label}</div>
        <div class="exec-metric__value">{value}</div>
        <div class="exec-metric__sub">{subtitle}</div>
    </div>
</div>
"""


def module_card(title, stats, color="#2563eb", progress=70):
    stat_html = "".join(
        f'<div class="module-card__stat"><span>{html.escape(str(label))}</span><strong>{html.escape(str(value))}</strong></div>'
        for label, value in stats
    )
    safe_progress = max(0, min(int(progress), 100))
    return (
        f'<div class="module-card" style="--module-color: {color};">'
        f'<h3>{html.escape(str(title))}</h3>'
        f'{stat_html}'
        f'<div class="module-card__bar"><div style="width:{safe_progress}%;"></div></div>'
        f'</div>'
    )


def trend_frame(df, label, date_candidates):
    if not isinstance(df, pd.DataFrame) or df.empty:
        return pd.DataFrame(columns=["Month", "Count", "Type"])
    date_col = next((col for col in date_candidates if col in df.columns), None)
    if not date_col:
        return pd.DataFrame(columns=["Month", "Count", "Type"])
    frame = df.copy()
    frame[date_col] = pd.to_datetime(frame[date_col], errors="coerce")
    frame = frame.dropna(subset=[date_col])
    if frame.empty:
        return pd.DataFrame(columns=["Month", "Count", "Type"])
    frame["Month"] = frame[date_col].dt.to_period("M").dt.to_timestamp()
    return frame.groupby("Month").size().reset_index(name="Count").assign(Type=label)


def project_performance(data):
    rows = []
    for name in ["ITR Log", "NCR Log", "OBS Log", "CTQ Log"]:
        df = data.get(name, pd.DataFrame())
        if not isinstance(df, pd.DataFrame) or df.empty or "Project" not in df.columns or "Status" not in df.columns:
            continue
        temp = df.copy()
        temp["ClosedFlag"] = temp["Status"].astype(str).str.strip().str.lower().isin(
            ["closed", "completed", "accepted", "approved", "passed", "pass", "compliant"]
        )
        grouped = temp.groupby("Project").agg(Total=("Status", "size"), Closed=("ClosedFlag", "sum")).reset_index()
        grouped["Compliance %"] = grouped.apply(lambda row: pct(row["Closed"], row["Total"]), axis=1)
        rows.append(grouped[["Project", "Compliance %"]])
    if not rows:
        return pd.DataFrame(columns=["Project", "Compliance %"])
    merged = pd.concat(rows, ignore_index=True)
    return merged.groupby("Project", as_index=False)["Compliance %"].mean().sort_values("Compliance %", ascending=False)


inject_enterprise_theme()
if not auth.login():
    st.stop()

render_header()
render_navigation()
render_top_nav()
getattr(auth, "render_user_sidebar", lambda: None)()

try:
    data = load_master_data(EXCEL_FILE)
except FileNotFoundError as err:
    st.error(err)
    st.stop()

filtered_data = global_filter_sidebar(data)
projects = extract_projects(filtered_data)

ncr = filtered_data.get("NCR Log", pd.DataFrame())
obs = filtered_data.get("OBS Log", pd.DataFrame())
itr = filtered_data.get("ITR Log", pd.DataFrame())
ctq = filtered_data.get("CTQ Log", pd.DataFrame())
concrete = filtered_data.get("Concrete Tracker", pd.DataFrame())
daily = filtered_data.get("Daily Reports", pd.DataFrame())
docs = filtered_data.get("Document Register", pd.DataFrame())
lessons = filtered_data.get("Lessons Learned", pd.DataFrame())

open_ncr = open_count(ncr)
closed_ncr = closed_count(ncr)
open_obs = open_count(obs)
closed_obs = closed_count(obs)
open_itr = open_count(itr)
closed_itr = closed_count(itr)
ctq_total = len(ctq) if isinstance(ctq, pd.DataFrame) else 0
ctq_passed = status_count_any(ctq, ["Passed", "Pass", "Compliant", "Approved", "Accepted"])
ctq_failed = status_count_any(ctq, ["Failed", "Fail", "Non-Compliant", "Nonconforming", "Rejected"])
ctq_pending = max(ctq_total - ctq_passed - ctq_failed, 0)
ctq_compliance = pct(ctq_passed, ctq_total)
quality_score = pct(
    closed_ncr + closed_obs + closed_itr + ctq_passed,
    open_ncr + closed_ncr + open_obs + closed_obs + open_itr + closed_itr + ctq_total,
)

metric_html = [
    metric_card("Total Projects", len(projects), "Active projects", "#2563eb", "P"),
    metric_card("Daily Reports", len(daily), "Records loaded", "#16a34a", "D"),
    metric_card("Open NCR", open_ncr, "Requires action", "#ef4444", "N"),
    metric_card("Closed NCR", closed_ncr, "Closed records", "#14b8a6", "C"),
    metric_card("Open OBS", open_obs, "Requires action", "#f97316", "O"),
    metric_card("Closed OBS", closed_obs, "Closed records", "#22c55e", "O"),
    metric_card("Open ITR", open_itr, "Requires action", "#f97316", "I"),
    metric_card("Closed ITR", closed_itr, "Closed records", "#16a34a", "I"),
]

left, right = st.columns([4.4, 1.15], gap="small")

with left:
    st.markdown('<div class="metric-grid">' + "".join(metric_html) + "</div>", unsafe_allow_html=True)

    trend = pd.concat(
        [
            trend_frame(ncr, "NCR", ["Date Raised", "Date_Raised", "Date"]),
            trend_frame(obs, "OBS", ["Date Raised", "Date_Raised", "Date"]),
        ],
        ignore_index=True,
    )
    performance = project_performance(filtered_data)

    chart_left, chart_right = st.columns(2)
    with chart_left:
        st.markdown('<div class="exec-panel"><h3>NCR / OBS Trend</h3>', unsafe_allow_html=True)
        if not trend.empty:
            fig = px.line(trend, x="Month", y="Count", color="Type", markers=True, template="plotly_white")
            fig.update_layout(height=310, margin=dict(l=20, r=12, t=8, b=20), legend_title_text="")
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No dated NCR/OBS records available.")
        st.markdown("</div>", unsafe_allow_html=True)

    with chart_right:
        st.markdown('<div class="exec-panel"><h3>Project Performance</h3>', unsafe_allow_html=True)
        if not performance.empty:
            fig = px.bar(performance.head(8), x="Project", y="Compliance %", template="plotly_white", color="Compliance %", color_continuous_scale=["#ef4444", "#f59e0b", "#22c55e"])
            fig.update_layout(height=310, margin=dict(l=20, r=12, t=8, b=20), coloraxis_showscale=False)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No project performance data available.")
        st.markdown("</div>", unsafe_allow_html=True)

    concrete_volume = 0
    if isinstance(concrete, pd.DataFrame) and "Volume" in concrete.columns:
        concrete_volume = pd.to_numeric(concrete["Volume"], errors="coerce").fillna(0).sum()

    module_cards = [
        module_card("Audit Register", [("Planned audits", len(filtered_data.get("Audit Register", pd.DataFrame()))), ("Documents", len(docs))], "#2563eb", 83),
        module_card("NCR Dashboard", [("Open NCR", open_ncr), ("Closed NCR", closed_ncr)], "#ef4444", pct(closed_ncr, open_ncr + closed_ncr)),
        module_card("OBS Dashboard", [("Open OBS", open_obs), ("Closed OBS", closed_obs)], "#f97316", pct(closed_obs, open_obs + closed_obs)),
        module_card("ITR Dashboard", [("Open ITR", open_itr), ("Closed ITR", closed_itr)], "#14b8a6", pct(closed_itr, open_itr + closed_itr)),
        module_card("Concrete Tracker", [("Total pours", len(concrete)), ("Volume m3", f"{concrete_volume:,.0f}")], "#1d8fe8", 74),
        module_card(
            "CTQ Register",
            [
                ("Total CTQ", ctq_total),
                ("Passed", ctq_passed),
                ("Failed", ctq_failed),
                ("Pending", ctq_pending),
                ("Compliance", f"{ctq_compliance}%"),
            ],
            "#7c3aed",
            ctq_compliance,
        ),
        module_card("Learning", [("Lessons", len(lessons)), ("Library", "Active")], "#0f6eb8", 88),
        module_card("Standards", [("PDFs", "214"), ("Viewer", "Ready")], "#0891b2", 92),
    ]
    st.markdown('<div class="module-grid">' + "".join(module_cards) + "</div>", unsafe_allow_html=True)

with right:
    st.markdown(
        f"""
<div class="exec-panel">
    <h3>Management Summary</h3>
    <div class="score-ring">{quality_score}%<span>Quality Score</span></div>
    <div class="status-row"><span><i class="status-dot" style="background:#22c55e;"></i>On Track</span><strong>{max(len(projects) - open_ncr - open_obs, 0)}</strong></div>
    <div class="status-row"><span><i class="status-dot" style="background:#f59e0b;"></i>At Risk</span><strong>{open_obs}</strong></div>
    <div class="status-row"><span><i class="status-dot" style="background:#ef4444;"></i>Critical</span><strong>{open_ncr}</strong></div>
</div>
""",
        unsafe_allow_html=True,
    )

    if isinstance(ncr, pd.DataFrame) and not ncr.empty and "Project" in ncr.columns:
        ncr_for_summary = ncr.copy()
        if "Status" in ncr_for_summary.columns:
            ncr_for_summary = ncr_for_summary[ncr_for_summary["Status"].astype(str).str.lower().eq("open")]
        top_ncr = ncr_for_summary["Project"].value_counts().head(5)
        if not top_ncr.empty:
            st.markdown('<div class="exec-panel" style="margin-top:0.75rem;"><h3>Top NCR Projects</h3>', unsafe_allow_html=True)
            for project, count in top_ncr.items():
                st.markdown(
                    f'<div class="status-row"><span>{project}</span><strong>{count}</strong></div>',
                    unsafe_allow_html=True,
                )
            st.markdown("</div>", unsafe_allow_html=True)

st.markdown('<div class="section-heading">Recent Daily Reports</div>', unsafe_allow_html=True)
if isinstance(daily, pd.DataFrame) and not daily.empty:
    render_table(daily.head(8), height=260)
else:
    st.info("Daily Reports sheet is not available in the data source.")

st.sidebar.caption(f"Total Projects: {len(projects)}")
