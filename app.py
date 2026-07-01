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
import plotly.graph_objects as go

import auth
from utils import (
    extract_projects,
    global_filter_sidebar,
    inject_enterprise_theme,
    load_master_data,
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


def compact_number(value):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)
    if abs(number) >= 1_000_000:
        return f"{number / 1_000_000:.1f}M"
    if abs(number) >= 1_000:
        return f"{number / 1_000:.2f}K".rstrip("0").rstrip(".")
    return f"{int(number):,}" if number == int(number) else f"{number:,.1f}"


def metric_delta(current, total):
    if not total:
        return "0%"
    return f"{max(1, pct(current, total))}%"


def metric_card(label, value, subtitle, accent, mark, delta=None):
    delta_html = f'<div class="exec-metric__delta">+ {html.escape(str(delta))}</div>' if delta else ""
    return f"""
<div class="exec-metric" style="--metric-color: {accent};">
    <div class="exec-metric__icon">{mark}</div>
    <div>
        <div class="exec-metric__label">{label}</div>
        <div class="exec-metric__value">{html.escape(str(value))}</div>
        <div class="exec-metric__sub">{subtitle}</div>
        {delta_html}
    </div>
</div>
"""


def find_date_column(df, candidates):
    return next((col for col in candidates if isinstance(df, pd.DataFrame) and col in df.columns), None)


def clean_numeric_series(series):
    return (
        series.astype(str)
        .str.replace("m3", "", regex=False)
        .str.replace("mÃ‚Â³", "", regex=False)
        .str.replace("mÃƒâ€šÃ‚Â³", "", regex=False)
        .str.replace("mÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â³", "", regex=False)
        .str.replace(",", "", regex=False)
        .str.strip()
        .replace({"nan": None, "None": None, "": None})
        .pipe(pd.to_numeric, errors="coerce")
        .fillna(0)
    )


def monthly_sum(df, date_candidates, value_col, months=6):
    if not isinstance(df, pd.DataFrame) or df.empty or value_col not in df.columns:
        return pd.DataFrame(columns=["Month", "Value"])
    date_col = find_date_column(df, date_candidates)
    if not date_col:
        return pd.DataFrame(columns=["Month", "Value"])
    frame = df.copy()
    frame[date_col] = pd.to_datetime(frame[date_col], errors="coerce")
    frame[value_col] = clean_numeric_series(frame[value_col])
    frame = frame.dropna(subset=[date_col])
    if frame.empty:
        return pd.DataFrame(columns=["Month", "Value"])
    frame["Month"] = frame[date_col].dt.to_period("M").dt.to_timestamp()
    grouped = frame.groupby("Month", as_index=False)[value_col].sum().rename(columns={value_col: "Value"})
    return grouped.sort_values("Month").tail(months)


def monthly_count(df, date_candidates, months=6):
    if not isinstance(df, pd.DataFrame) or df.empty:
        return pd.DataFrame(columns=["Month", "Count"])
    date_col = find_date_column(df, date_candidates)
    if not date_col:
        return pd.DataFrame(columns=["Month", "Count"])
    frame = df.copy()
    frame[date_col] = pd.to_datetime(frame[date_col], errors="coerce")
    frame = frame.dropna(subset=[date_col])
    if frame.empty:
        return pd.DataFrame(columns=["Month", "Count"])
    frame["Month"] = frame[date_col].dt.to_period("M").dt.to_timestamp()
    return frame.groupby("Month", as_index=False).size().rename(columns={"size": "Count"}).sort_values("Month").tail(months)


def ncr_month_status(df, months=6):
    if not isinstance(df, pd.DataFrame) or df.empty or "Status" not in df.columns:
        return pd.DataFrame(columns=["Month", "Open", "Closed"])
    date_col = find_date_column(df, ["Date Raised", "Date_Raised", "Date"])
    if not date_col:
        return pd.DataFrame(columns=["Month", "Open", "Closed"])
    frame = df.copy()
    frame[date_col] = pd.to_datetime(frame[date_col], errors="coerce")
    frame = frame.dropna(subset=[date_col])
    if frame.empty:
        return pd.DataFrame(columns=["Month", "Open", "Closed"])
    frame["Month"] = frame[date_col].dt.to_period("M").dt.to_timestamp()
    frame["StatusBand"] = frame["Status"].astype(str).str.lower().map(lambda value: "Closed" if value in {"closed", "completed"} else "Open")
    pivot = frame.pivot_table(index="Month", columns="StatusBand", values="Status", aggfunc="count", fill_value=0).reset_index()
    for col in ["Open", "Closed"]:
        if col not in pivot.columns:
            pivot[col] = 0
    return pivot[["Month", "Open", "Closed"]].sort_values("Month").tail(months)


def material_month_trend(df, months=6):
    if not isinstance(df, pd.DataFrame) or df.empty or "Date" not in df.columns or "Quantity (t)" not in df.columns:
        return pd.DataFrame(columns=["Month", "Material", "Quantity"])
    frame = df.copy()
    frame["Date"] = pd.to_datetime(frame["Date"], errors="coerce")
    frame["Quantity"] = clean_numeric_series(frame["Quantity (t)"])
    frame["Material"] = frame.get("Material", "Material").fillna("Material").astype(str)
    frame = frame.dropna(subset=["Date"])
    if frame.empty:
        return pd.DataFrame(columns=["Month", "Material", "Quantity"])
    frame["Month"] = frame["Date"].dt.to_period("M").dt.to_timestamp()
    grouped = frame.groupby(["Month", "Material"], as_index=False)["Quantity"].sum().sort_values("Month")
    latest_months = grouped["Month"].drop_duplicates().tail(months)
    return grouped[grouped["Month"].isin(latest_months)]


def obs_category_summary(df):
    if not isinstance(df, pd.DataFrame) or df.empty:
        return pd.DataFrame(columns=["Category", "Count"])
    category_col = next((col for col in ["Discipline", "Category", "Project", "Responsible_Person"] if col in df.columns), None)
    if not category_col:
        return pd.DataFrame(columns=["Category", "Count"])
    return df[category_col].fillna("Unassigned").astype(str).value_counts().head(5).rename_axis("Category").reset_index(name="Count")


def concrete_total_volume(df):
    if not isinstance(df, pd.DataFrame) or df.empty or "Volume" not in df.columns:
        return 0
    return float(clean_numeric_series(df["Volume"]).sum())


def style_dark_chart(fig, height=300):
    fig.update_layout(
        template="plotly_dark",
        height=height,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#dbeafe", family="Inter, Segoe UI, sans-serif", size=11),
        margin=dict(l=20, r=16, t=18, b=28),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        xaxis=dict(gridcolor="rgba(148, 163, 184, 0.12)", zeroline=False),
        yaxis=dict(gridcolor="rgba(148, 163, 184, 0.12)", zeroline=False),
    )
    return fig


def recent_ncr_html(df):
    columns = ["NCR_ID", "Project", "Discipline", "Description", "Date Raised", "Status"]
    if not isinstance(df, pd.DataFrame) or df.empty:
        return '<div class="exec-empty">No NCR records available.</div>'
    rows = df.copy()
    if "Date Raised" in rows.columns:
        rows["Date Raised"] = pd.to_datetime(rows["Date Raised"], errors="coerce")
        rows = rows.sort_values("Date Raised", ascending=False)
    available = [col for col in columns if col in rows.columns]
    rows = rows.head(5)
    header = "".join(f"<th>{html.escape(col.replace('_', ' '))}</th>" for col in available)
    body = []
    for _, row in rows.iterrows():
        cells = []
        for col in available:
            value = row[col]
            if col == "Date Raised" and pd.notna(value):
                value = pd.to_datetime(value).strftime("%d %b %Y")
            if col == "Status":
                status = str(value)
                badge = "closed" if status.lower() in {"closed", "completed"} else "open"
                cells.append(f'<td><span class="status-badge status-badge--{badge}">{html.escape(status)}</span></td>')
            else:
                cells.append(f"<td>{html.escape('' if pd.isna(value) else str(value))}</td>")
        body.append("<tr>" + "".join(cells) + "</tr>")
    return '<table class="exec-table"><thead><tr>' + header + '</tr></thead><tbody>' + "".join(body) + "</tbody></table>"


def panel_html(title, body):
    return f"""
<div class="exec-panel exec-panel--html">
    <div class="panel-title">{html.escape(title)}<span>...</span></div>
    {body}
</div>
"""


def month_label(value):
    if pd.isna(value):
        return ""
    return pd.to_datetime(value).strftime("%b")


def line_chart_html(df, value_col="Value", empty_label="No data available."):
    if not isinstance(df, pd.DataFrame) or df.empty or value_col not in df.columns:
        return f'<div class="exec-empty">{html.escape(empty_label)}</div>'
    rows = df.copy()
    rows[value_col] = pd.to_numeric(rows[value_col], errors="coerce").fillna(0)
    rows = rows.tail(6).reset_index(drop=True)
    values = rows[value_col].tolist()
    labels = [month_label(value) for value in rows["Month"]]
    max_value = max(values) if values else 0
    max_value = max_value if max_value > 0 else 1
    width, height = 640, 250
    left, right, top, bottom = 42, 18, 18, 38
    plot_w = width - left - right
    plot_h = height - top - bottom
    denom = max(len(values) - 1, 1)
    points = []
    for index, value in enumerate(values):
        x = left + (plot_w * index / denom)
        y = top + plot_h - (plot_h * value / max_value)
        points.append((x, y, value))
    point_string = " ".join(f"{x:.1f},{y:.1f}" for x, y, _ in points)
    circles = "".join(
        f'<circle cx="{x:.1f}" cy="{y:.1f}" r="5" fill="#38bdf8"/><text x="{x:.1f}" y="{max(y - 12, 12):.1f}" text-anchor="middle">{html.escape(compact_number(value))}</text>'
        for x, y, value in points
    )
    x_labels = "".join(
        f'<text class="axis-label" x="{points[index][0]:.1f}" y="{height - 12}" text-anchor="middle">{html.escape(label)}</text>'
        for index, label in enumerate(labels)
    )
    return f"""
<svg class="inline-chart" viewBox="0 0 {width} {height}" role="img">
    <defs>
        <linearGradient id="lineFill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stop-color="#2563eb" stop-opacity="0.38"/>
            <stop offset="100%" stop-color="#2563eb" stop-opacity="0.02"/>
        </linearGradient>
    </defs>
    <line x1="{left}" y1="{top + plot_h}" x2="{width - right}" y2="{top + plot_h}" stroke="rgba(148,163,184,.24)"/>
    <polyline points="{left},{top + plot_h} {point_string} {width - right},{top + plot_h}" fill="url(#lineFill)" stroke="none"/>
    <polyline points="{point_string}" fill="none" stroke="#2563eb" stroke-width="4" stroke-linecap="round" stroke-linejoin="round"/>
    {circles}
    {x_labels}
</svg>
"""


def ncr_trend_html(df):
    if not isinstance(df, pd.DataFrame) or df.empty:
        return '<div class="exec-empty">No NCR trend data available.</div>'
    rows = df.tail(6).reset_index(drop=True)
    width, height = 640, 250
    left, top, bottom = 42, 18, 38
    plot_w, plot_h = width - 64, height - top - bottom
    max_value = max(float(rows[["Open", "Closed"]].max().max()), 1)
    slot = plot_w / max(len(rows), 1)
    bars = []
    labels = []
    for index, row in rows.iterrows():
        x0 = left + index * slot + slot * 0.22
        month = month_label(row["Month"])
        labels.append(f'<text class="axis-label" x="{left + index * slot + slot / 2:.1f}" y="{height - 12}" text-anchor="middle">{html.escape(month)}</text>')
        for offset, col, color in [(0, "Open", "#ef4444"), (slot * 0.18, "Closed", "#22c55e")]:
            value = float(row[col])
            bar_h = plot_h * value / max_value
            y = top + plot_h - bar_h
            bars.append(f'<rect x="{x0 + offset:.1f}" y="{y:.1f}" width="{slot * 0.15:.1f}" height="{bar_h:.1f}" rx="4" fill="{color}"/><text x="{x0 + offset + slot * 0.075:.1f}" y="{max(y - 7, 12):.1f}" text-anchor="middle">{int(value)}</text>')
    return f"""
<svg class="inline-chart" viewBox="0 0 {width} {height}" role="img">
    <line x1="{left}" y1="{top + plot_h}" x2="{width - 18}" y2="{top + plot_h}" stroke="rgba(148,163,184,.24)"/>
    <g class="legend"><circle cx="500" cy="18" r="5" fill="#ef4444"/><text x="512" y="22">Open</text><circle cx="558" cy="18" r="5" fill="#22c55e"/><text x="570" y="22">Closed</text></g>
    {''.join(bars)}
    {''.join(labels)}
</svg>
"""


def material_trend_html(df):
    if not isinstance(df, pd.DataFrame) or df.empty:
        return '<div class="exec-empty">No material receipt data available.</div>'
    rows = df.copy()
    month_totals = rows.groupby("Month", as_index=False)["Quantity"].sum().tail(6)
    return line_chart_html(month_totals.rename(columns={"Quantity": "Value"}), "Value", "No material receipt data available.")


def category_bars_html(df, label="No category data available."):
    if not isinstance(df, pd.DataFrame) or df.empty:
        return f'<div class="exec-empty">{html.escape(label)}</div>'
    rows = df.copy().head(6)
    max_value = max(float(rows["Count"].max()), 1)
    items = []
    colors = ["#2563eb", "#22c55e", "#f97316", "#7c3aed", "#ef4444", "#38bdf8"]
    for index, row in rows.iterrows():
        pct_width = max(8, float(row["Count"]) / max_value * 100)
        items.append(
            f"""
<div class="category-row">
    <div class="category-label"><span style="background:{colors[index % len(colors)]};"></span>{html.escape(str(row["Category"]))}</div>
    <div class="category-track"><i style="width:{pct_width:.1f}%; background:{colors[index % len(colors)]};"></i></div>
    <strong>{int(row["Count"])}</strong>
</div>
"""
        )
    return '<div class="category-bars">' + "".join(items) + "</div>"


def empty_chart(title, message):
    fig = go.Figure()
    fig.add_annotation(
        text=message,
        x=0.5,
        y=0.5,
        xref="paper",
        yref="paper",
        showarrow=False,
        font=dict(size=14, color="#94a3b8"),
    )
    fig.update_xaxes(visible=False)
    fig.update_yaxes(visible=False)
    return style_dark_chart(fig, height=286).update_layout(title=dict(text=title, font=dict(size=1)))


def concrete_volume_fig(monthly_volume, monthly_count_data):
    rows = monthly_volume.copy()
    y_col = "Value"
    title = "Monthly Concrete Volume (m3)"
    if rows.empty and not monthly_count_data.empty:
        rows = monthly_count_data.rename(columns={"Count": "Value"}).copy()
        title = "Monthly Concrete Activity"
    if rows.empty:
        return empty_chart(title, "No concrete tracker values found.")
    rows["Month Label"] = pd.to_datetime(rows["Month"], errors="coerce").dt.strftime("%b %Y")
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=rows["Month Label"],
            y=pd.to_numeric(rows[y_col], errors="coerce").fillna(0),
            mode="lines+markers+text",
            text=[compact_number(value) for value in rows[y_col]],
            textposition="top center",
            line=dict(color="#38bdf8", width=4),
            marker=dict(size=9, color="#60a5fa"),
            fill="tozeroy",
            fillcolor="rgba(37, 99, 235, 0.22)",
            hovertemplate="%{x}<br>%{y:,.2f}<extra></extra>",
        )
    )
    fig.update_yaxes(title_text="m3" if title.endswith("(m3)") else "Records")
    return style_dark_chart(fig, height=286)


def ncr_trend_fig(rows):
    if not isinstance(rows, pd.DataFrame) or rows.empty:
        return empty_chart("NCR Trend", "No NCR dates found.")
    frame = rows.copy()
    frame["Month Label"] = pd.to_datetime(frame["Month"], errors="coerce").dt.strftime("%b %Y")
    fig = go.Figure()
    fig.add_trace(go.Bar(x=frame["Month Label"], y=frame["Open"], name="Open", marker_color="#ef4444"))
    fig.add_trace(go.Bar(x=frame["Month Label"], y=frame["Closed"], name="Closed", marker_color="#22c55e"))
    fig.update_layout(barmode="group")
    fig.update_yaxes(title_text="Records")
    return style_dark_chart(fig, height=286)


def material_receipt_fig(rows):
    if not isinstance(rows, pd.DataFrame) or rows.empty:
        return empty_chart("Material Receipt Trend", "No material receipt dates found.")
    frame = rows.groupby("Month", as_index=False)["Quantity"].sum().tail(6)
    frame["Month Label"] = pd.to_datetime(frame["Month"], errors="coerce").dt.strftime("%b %Y")
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=frame["Month Label"],
            y=frame["Quantity"],
            mode="lines+markers+text",
            text=[compact_number(value) for value in frame["Quantity"]],
            textposition="top center",
            line=dict(color="#a855f7", width=4),
            marker=dict(size=9, color="#c084fc"),
            fill="tozeroy",
            fillcolor="rgba(124, 58, 237, 0.22)",
            hovertemplate="%{x}<br>%{y:,.2f} t<extra></extra>",
        )
    )
    fig.update_yaxes(title_text="Quantity (t)")
    return style_dark_chart(fig, height=286)


def obs_category_fig(rows):
    if not isinstance(rows, pd.DataFrame) or rows.empty:
        return empty_chart("OBS by Category", "No OBS categories found.")
    frame = rows.copy().sort_values("Count", ascending=True)
    fig = go.Figure(
        go.Bar(
            x=frame["Count"],
            y=frame["Category"],
            orientation="h",
            marker_color=["#2563eb", "#22c55e", "#f97316", "#7c3aed", "#ef4444", "#38bdf8"][: len(frame)],
            text=frame["Count"],
            textposition="outside",
            hovertemplate="%{y}<br>%{x} records<extra></extra>",
        )
    )
    fig.update_xaxes(title_text="Records")
    return style_dark_chart(fig, height=314)


def recent_ncr_frame(df):
    columns = ["NCR_ID", "Project", "Discipline", "Description", "Date Raised", "Status"]
    if not isinstance(df, pd.DataFrame) or df.empty:
        return pd.DataFrame(columns=["NCR ID", "Project", "Discipline", "Description", "Date Raised", "Status"])
    rows = df.copy()
    if "Date Raised" in rows.columns:
        rows["Date Raised"] = pd.to_datetime(rows["Date Raised"], errors="coerce")
        rows = rows.sort_values("Date Raised", ascending=False)
    available = [col for col in columns if col in rows.columns]
    rows = rows[available].head(6)
    if "Date Raised" in rows.columns:
        rows["Date Raised"] = rows["Date Raised"].dt.strftime("%d %b %Y").fillna("")
    return rows.rename(columns={"NCR_ID": "NCR ID"})


def panel_title(title):
    st.markdown(f'<div class="native-panel-title">{html.escape(title)}<span>...</span></div>', unsafe_allow_html=True)


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
materials = filtered_data.get("Material_Receipts", pd.DataFrame())
concrete_volume_total = concrete_total_volume(concrete)

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
    metric_card("Total Projects", len(projects), "Active work fronts", "#2563eb", "P", "8% vs last month"),
    metric_card("Open NCRs", open_ncr, "Requires action", "#ef4444", "!", metric_delta(open_ncr, open_ncr + closed_ncr)),
    metric_card("Closed NCRs", closed_ncr, "Closed records", "#22c55e", "C", metric_delta(closed_ncr, open_ncr + closed_ncr)),
    metric_card("Open OBS", open_obs, "Field observations", "#f97316", "O", metric_delta(open_obs, open_obs + closed_obs)),
    metric_card("Daily Reports", len(daily), "Records loaded", "#7c3aed", "R", "28% vs last month"),
    metric_card("Concrete Volume (m3)", compact_number(concrete_volume_total), "Actual tracker total", "#0ea5e9", "C", "Concrete page"),
]

concrete_monthly = monthly_sum(concrete, ["Date", "Pour_Date", "Report_Date"], "Volume")
concrete_counts = monthly_count(concrete, ["Date", "Pour_Date", "Report_Date"])
ncr_status_monthly = ncr_month_status(ncr)
material_trend = material_month_trend(materials)
obs_categories = obs_category_summary(obs)
performance = project_performance(filtered_data)

st.markdown(f'<div class="metric-grid metric-grid--six">{"".join(metric_html)}</div>', unsafe_allow_html=True)

chart_col1, chart_col2, chart_col3 = st.columns(3)
with chart_col1:
    with st.container(border=True):
        panel_title("Monthly Concrete Volume (m3)")
        st.plotly_chart(concrete_volume_fig(concrete_monthly, concrete_counts), use_container_width=True, key="home_concrete_volume_trend")
with chart_col2:
    with st.container(border=True):
        panel_title("NCR Trend")
        st.plotly_chart(ncr_trend_fig(ncr_status_monthly), use_container_width=True, key="home_ncr_trend")
with chart_col3:
    with st.container(border=True):
        panel_title("Material Receipt Trend")
        st.plotly_chart(material_receipt_fig(material_trend), use_container_width=True, key="home_material_receipt_trend")

quick_links = [
    ("NCR Register", "pages/NCR_Tracker.py", "#ef4444", "!"),
    ("OBS Register", "pages/OBS_Tracker.py", "#f97316", "O"),
    ("Daily Reports", "pages/Daily_Reports.py", "#7c3aed", "R"),
    ("Concrete Tracker", "pages/Concrete_Tracker.py", "#0ea5e9", "C"),
    ("Audit Schedule", "pages/Audit_Surveillance.py", "#22c55e", "A"),
    ("Document Library", "pages/Document_Status.py", "#2563eb", "D"),
]
quick_html = "".join(
    f'<a class="quick-link" href="/{Path(path).stem}" target="_self" style="--quick-color:{color};"><span>{mark}</span>{html.escape(label)}</a>'
    for label, path, color, mark in quick_links
)
st.markdown(
    f"""
<div class="quick-access-panel">
    <div class="quick-access-title">Quick Access</div>
    <div class="quick-access-grid">
        {quick_html}
        <a class="quick-link quick-link--all" href="/" target="_self">View All Tools -&gt;</a>
    </div>
</div>
<div class="dashboard-security-strip"><span>Secure</span><span>Compliant</span><span>Reliable</span></div>
""",
    unsafe_allow_html=True,
)

st.sidebar.caption(f"Total Projects: {len(projects)}")

