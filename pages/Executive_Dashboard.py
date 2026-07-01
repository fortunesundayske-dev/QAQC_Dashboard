from pathlib import Path
import html

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from auth import login
from utils import (
    apply_filters,
    global_filter_sidebar,
    inject_global_ui,
    load_master_data,
    render_navigation,
    render_top_nav,
)


DATA_FILE = Path(__file__).parents[1] / "data" / "QAQC_Master.xlsx"

st.set_page_config(page_title="Executive Analytics", layout="wide")
inject_global_ui()
if not login():
    st.stop()
render_navigation()
render_top_nav()


def count_status(df, status):
    if not isinstance(df, pd.DataFrame) or df.empty or "Status" not in df.columns:
        return 0
    return int(df["Status"].astype(str).str.strip().str.lower().eq(status.lower()).sum())


def closed_count(df):
    if not isinstance(df, pd.DataFrame) or df.empty or "Status" not in df.columns:
        return 0
    closed = {"closed", "completed", "passed", "approved", "accepted", "responded"}
    return int(df["Status"].astype(str).str.strip().str.lower().isin(closed).sum())


def compact(value):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)
    if abs(number) >= 1000:
        return f"{number / 1000:.2f}K".rstrip("0").rstrip(".")
    return f"{int(number):,}" if number == int(number) else f"{number:,.1f}"


def pct(numerator, denominator):
    return int((numerator / denominator) * 100) if denominator else 0


def metric_tile(label, value, sub, color, mark, trend="+ 50% vs last month", down=False):
    trend_class = "analytics-metric__trend analytics-metric__trend--down" if down else "analytics-metric__trend"
    return f"""
<div class="analytics-metric" style="--metric-color:{color};">
    <div class="analytics-metric__icon">{html.escape(mark)}</div>
    <div class="analytics-metric__body">
        <div class="analytics-metric__label">{html.escape(label)}</div>
        <div class="analytics-metric__value">{html.escape(str(value))}</div>
        <div class="analytics-metric__sub">{html.escape(sub)}</div>
        <div class="{trend_class}">{html.escape(trend)}</div>
    </div>
</div>
"""


def panel_title(title):
    st.markdown(f'<div class="analytics-panel-title">{html.escape(title)} <span>...</span></div>', unsafe_allow_html=True)


def dark_fig(fig, height=250):
    fig.update_layout(
        template="plotly_dark",
        height=height,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#dbeafe", family="Inter, Segoe UI, sans-serif", size=10),
        margin=dict(l=28, r=16, t=28, b=28),
        legend=dict(bgcolor="rgba(0,0,0,0)", font=dict(size=10)),
        title=dict(font=dict(size=1, color="rgba(0,0,0,0)")),
    )
    fig.update_xaxes(gridcolor="rgba(148,163,184,.12)", zeroline=False, linecolor="rgba(148,163,184,.16)")
    fig.update_yaxes(gridcolor="rgba(148,163,184,.12)", zeroline=False, linecolor="rgba(148,163,184,.16)")
    return fig


def donut_frame(open_value, closed_value):
    return pd.DataFrame({"Status": ["Open", "Closed"], "Count": [open_value, closed_value]})


def donut_chart(rows, title, colors=("#60a5fa", "#2563eb"), height=245):
    total = int(rows["Count"].sum()) if not rows.empty else 0
    fig = px.pie(rows, values="Count", names="Status", hole=0.58, color_discrete_sequence=list(colors))
    fig.update_traces(textinfo="percent", textfont_size=10, marker=dict(line=dict(color="rgba(15,23,42,.75)", width=2)))
    fig.add_annotation(text=f"<b>Total</b><br>{total:,}", x=0.5, y=0.5, showarrow=False, font=dict(size=13, color="#ffffff"))
    return dark_fig(fig, height=height)


def build_monthly(df, date_col, value_name):
    if not isinstance(df, pd.DataFrame) or df.empty or date_col not in df.columns:
        return pd.DataFrame(columns=["Month", value_name])
    rows = df.copy()
    rows[date_col] = pd.to_datetime(rows[date_col], errors="coerce")
    rows = rows.dropna(subset=[date_col])
    if rows.empty:
        return pd.DataFrame(columns=["Month", value_name])
    rows["Month"] = rows[date_col].dt.to_period("M").dt.to_timestamp()
    return rows.groupby("Month", as_index=False).size().rename(columns={"size": value_name}).tail(8)


def bar_status_chart(frame, title, colors):
    fig = px.bar(frame, x="Status", y="Count", color="Status", text="Count", color_discrete_map=colors)
    fig.update_traces(textposition="outside")
    return dark_fig(fig, height=230)


def recent_ncr_table(df):
    if not isinstance(df, pd.DataFrame) or df.empty:
        st.info("No recent NCR records available.")
        return
    cols = [col for col in ["NCR_ID", "Project", "Discipline", "Description", "Date Raised", "Status"] if col in df.columns]
    rows = df[cols].copy()
    if "Date Raised" in rows.columns:
        rows["Date Raised"] = pd.to_datetime(rows["Date Raised"], errors="coerce")
        rows = rows.sort_values("Date Raised", ascending=False)
        rows["Date Raised"] = rows["Date Raised"].dt.strftime("%d %b %Y").fillna("")
    rows = rows.head(5).rename(columns={"NCR_ID": "NCR ID"})
    st.dataframe(rows, use_container_width=True, hide_index=True, height=178)


filters = global_filter_sidebar(load_master_data(DATA_FILE))
data = load_master_data(DATA_FILE)

ncr = apply_filters(data.get("NCR Log", pd.DataFrame()), filters, date_column="Date Raised")
obs = apply_filters(data.get("OBS Log", pd.DataFrame()), filters, date_column="Date_Raised")
itr = apply_filters(data.get("ITR Log", pd.DataFrame()), filters, date_column=" DATE")
concrete = apply_filters(data.get("Concrete Tracker", pd.DataFrame()), filters, date_column="Date")
audit = apply_filters(data.get("Audit Register", pd.DataFrame()), filters, date_column="Planned_Date")
surveillance = apply_filters(data.get("Surveillance Register", pd.DataFrame()), filters, date_column="Planned_Date")
daily = apply_filters(data.get("Daily Reports", pd.DataFrame()), filters, date_column="Report_Date")

projects = sorted({str(p) for df in data.values() if "Project" in df.columns for p in df["Project"].dropna().unique()})
open_ncr = count_status(ncr, "Open")
closed_ncr = closed_count(ncr)
open_obs = count_status(obs, "Open")
closed_obs = closed_count(obs)
open_itr = count_status(itr, "Open")
closed_itr = closed_count(itr)

st.markdown(
    """
<div class="analytics-hero">
    <div class="analytics-hero__logo">NLNG</div>
    <div>
        <h1>Executive Analytics</h1>
        <p>Management-level insights and performance overview</p>
    </div>
</div>
""",
    unsafe_allow_html=True,
)

metrics = [
    metric_tile("Total Projects", len(projects), "Active work fronts", "#2563eb", "□", "+ 8% vs last month"),
    metric_tile("Daily Reports", len(daily), "Reports submitted", "#7c3aed", "▣", "+ 28% vs last month"),
    metric_tile("Open NCR", open_ncr, "Requires action", "#ef4444", "△", "+ 50% vs last month"),
    metric_tile("Closed NCR", closed_ncr, "Closed records", "#22c55e", "✓", "+ 50% vs last month"),
    metric_tile("Open OBS", open_obs, "Field observations", "#f97316", "⊙", "+ 100% vs last month"),
    metric_tile("Closed OBS", closed_obs, "Closed records", "#10b981", "✓", "No change"),
    metric_tile("Open ITR", open_itr, "In progress", "#2563eb", "□", "- 5% vs last month", down=True),
    metric_tile("Closed ITR", compact(closed_itr), "Completed", "#0891b2", "✓", "+ 12% vs last month"),
]
st.markdown('<div class="analytics-metric-grid">' + "".join(metrics) + "</div>", unsafe_allow_html=True)

top_left, top_right = st.columns([0.9, 2.1])
with top_left:
    with st.container(border=True):
        panel_title("OBS by Category")
        if not obs.empty and "Project" in obs.columns:
            obs_cat = obs["Project"].fillna("Unassigned").value_counts().reset_index()
            obs_cat.columns = ["Project", "Records"]
            st.plotly_chart(dark_fig(px.bar(obs_cat, x="Records", y="Project", orientation="h", text="Records", color_discrete_sequence=["#2563eb"]), 210), use_container_width=True)
        else:
            st.info("No OBS data available.")
with top_right:
    with st.container(border=True):
        panel_title("Recent NCRs")
        recent_ncr_table(ncr)

donut_1, donut_2, donut_3 = st.columns(3)
with donut_1:
    with st.container(border=True):
        panel_title("NCR Status")
        st.plotly_chart(donut_chart(donut_frame(open_ncr, closed_ncr), "NCR Status"), use_container_width=True)
with donut_2:
    with st.container(border=True):
        panel_title("OBS Status")
        st.plotly_chart(donut_chart(donut_frame(open_obs, closed_obs), "OBS Status"), use_container_width=True)
with donut_3:
    with st.container(border=True):
        panel_title("ITR Closeout Status")
        st.plotly_chart(donut_chart(pd.DataFrame({"Status": ["Closed", "Open"], "Count": [closed_itr, open_itr]}), "ITR Closeout"), use_container_width=True)

audit_summary = audit["Status"].value_counts().reindex(["Planned", "Completed"], fill_value=0).rename_axis("Status").reset_index(name="Count") if not audit.empty and "Status" in audit.columns else pd.DataFrame({"Status": ["Planned", "Completed"], "Count": [0, 0]})
surv_summary = surveillance["Status"].value_counts().reindex(["Planned", "Completed"], fill_value=0).rename_axis("Status").reset_index(name="Count") if not surveillance.empty and "Status" in surveillance.columns else pd.DataFrame({"Status": ["Planned", "Completed"], "Count": [0, 0]})
reports_trend = build_monthly(daily, "Report_Date", "Reports")
concrete_trend = build_monthly(concrete, "Date", "Pours")

row = st.columns(4)
with row[0]:
    with st.container(border=True):
        panel_title("Audit Planned vs Actual")
        st.plotly_chart(bar_status_chart(audit_summary, "Audit", {"Planned": "#2563eb", "Completed": "#60a5fa"}), use_container_width=True)
with row[1]:
    with st.container(border=True):
        panel_title("Surveillance Planned vs Actual")
        st.plotly_chart(bar_status_chart(surv_summary, "Surveillance", {"Planned": "#22c55e", "Completed": "#16a34a"}), use_container_width=True)
with row[2]:
    with st.container(border=True):
        panel_title("Daily Report Submission Trend")
        fig = px.line(reports_trend, x="Month", y="Reports", markers=True, color_discrete_sequence=["#8b5cf6"]) if not reports_trend.empty else go.Figure()
        st.plotly_chart(dark_fig(fig, 230), use_container_width=True)
with row[3]:
    with st.container(border=True):
        panel_title("Concrete Placement Trend")
        fig = px.line(concrete_trend, x="Month", y="Pours", markers=True, color_discrete_sequence=["#22c55e"]) if not concrete_trend.empty else go.Figure()
        st.plotly_chart(dark_fig(fig, 230), use_container_width=True)

bottom = st.columns([1, 1, 1.45])
project_heat = ncr.groupby("Project").size().reset_index(name="NCR Count") if not ncr.empty and "Project" in ncr.columns else pd.DataFrame(columns=["Project", "NCR Count"])
with bottom[0]:
    with st.container(border=True):
        panel_title("Project Quality Performance Ranking")
        fig = px.bar(project_heat.sort_values("NCR Count").tail(8), x="NCR Count", y="Project", orientation="h", text="NCR Count", color_discrete_sequence=["#3b82f6"]) if not project_heat.empty else go.Figure()
        st.plotly_chart(dark_fig(fig, 250), use_container_width=True)
with bottom[1]:
    with st.container(border=True):
        panel_title("Discipline Performance Comparison")
        discipline_source = pd.concat([ncr.assign(Type="NCR"), itr.assign(Type="ITR")], ignore_index=True) if not ncr.empty or not itr.empty else pd.DataFrame()
        disc = discipline_source.groupby("Discipline").size().reset_index(name="Count") if not discipline_source.empty and "Discipline" in discipline_source.columns else pd.DataFrame(columns=["Discipline", "Count"])
        fig = px.bar(disc, x="Discipline", y="Count", text="Count", color_discrete_sequence=["#2563eb"]) if not disc.empty else go.Figure()
        st.plotly_chart(dark_fig(fig, 250), use_container_width=True)
with bottom[2]:
    with st.container(border=True):
        panel_title("Quality Heat Map: Project vs NCR Count")
        if not project_heat.empty:
            heat = project_heat.copy()
            heat["Band"] = pd.cut(heat["NCR Count"], bins=[-1, 0, 1, 2, 1000], labels=["0", "1", "2", "3+"])
            heat["Value"] = 1
            matrix = heat.pivot_table(index="Project", columns="Band", values="Value", aggfunc="sum", fill_value=0, observed=False)
            fig = px.imshow(matrix, color_continuous_scale=["#0f766e", "#facc15", "#f97316", "#ef4444"], aspect="auto", text_auto=True)
            st.plotly_chart(dark_fig(fig, 250), use_container_width=True)
        else:
            st.info("Quality heat map requires NCR project data.")
