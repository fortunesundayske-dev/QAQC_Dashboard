from pathlib import Path
import re

import pandas as pd
import plotly.express as px
import streamlit as st

from auth import login
from utils import (
    global_filter_sidebar,
    inject_global_ui,
    load_master_data,
    render_navigation,
    render_top_nav,
    render_page_header,
    render_table,
    style_chart,
)


DATA_FILE = Path(__file__).parents[1] / "data" / "QAQC_Master.xlsx"

st.set_page_config(page_title="KPI KRA Register", layout="wide")
inject_global_ui()

if not login():
    st.stop()

render_navigation()
render_top_nav()


def number_from_value(value):
    if pd.isna(value):
        return None
    text = str(value).strip()
    if not text:
        return None
    match = re.search(r"-?\d+(?:\.\d+)?", text.replace(",", ""))
    return float(match.group(0)) if match else None


def performance_status(row):
    planned = row.get("Planned Value")
    actual = row.get("Actual Value")
    if planned is None or actual is None:
        return "Awaiting actual"
    target_text = str(row.get("Target", "")).strip()
    lower_is_better = target_text in {"0", "0%"} or planned == 0
    if lower_is_better:
        return "On track" if actual <= planned else "Off track"
    return "On track" if actual >= planned else "Off track"


def variance_text(row):
    planned = row.get("Planned Value")
    actual = row.get("Actual Value")
    if planned is None or actual is None:
        return ""
    diff = actual - planned
    suffix = "%" if "%" in str(row.get("Target", "")) or "%" in str(row.get("Current Performance", "")) else ""
    sign = "+" if diff > 0 else ""
    return f"{sign}{diff:g}{suffix}"


render_page_header(
    "KPI KRA Register",
    "Keep KPI/KRA performance visible and compare actual performance against planned targets.",
    "Executive",
)

data = load_master_data(DATA_FILE)
global_filter_sidebar(data)
kpi = data.get("KPI KRA Register", pd.DataFrame())

if not isinstance(kpi, pd.DataFrame) or kpi.empty:
    st.warning("No KPI KRA records are available in the master workbook.")
    st.stop()

visible = kpi.copy()
for column in ["KRA", "KPI", "Target", "Frequency", "Current Performance"]:
    if column not in visible.columns:
        visible[column] = ""

visible["Planned"] = visible["Target"]
visible["Actual"] = visible["Current Performance"]
visible["Planned Value"] = visible["Target"].apply(number_from_value)
visible["Actual Value"] = visible["Current Performance"].apply(number_from_value)
visible["Variance"] = visible.apply(variance_text, axis=1)
visible["Performance Status"] = visible.apply(performance_status, axis=1)

total = len(visible)
actual_count = int(visible["Actual Value"].notna().sum())
on_track = int(visible["Performance Status"].eq("On track").sum())
off_track = int(visible["Performance Status"].eq("Off track").sum())

m1, m2, m3, m4 = st.columns(4)
m1.metric("KPI/KRA records", total)
m2.metric("Actuals entered", actual_count)
m3.metric("On track", on_track)
m4.metric("Off track", off_track)

filters = st.columns([1, 1, 1])
with filters[0]:
    selected_kra = st.selectbox("KRA", ["All"] + sorted(visible["KRA"].dropna().astype(str).unique().tolist()))
with filters[1]:
    selected_status = st.selectbox("Performance status", ["All"] + sorted(visible["Performance Status"].unique().tolist()))
with filters[2]:
    search = st.text_input("Search KPI", placeholder="Search KPI or KRA")

filtered = visible.copy()
if selected_kra != "All":
    filtered = filtered[filtered["KRA"].astype(str) == selected_kra]
if selected_status != "All":
    filtered = filtered[filtered["Performance Status"] == selected_status]
if search:
    needle = search.strip().lower()
    filtered = filtered[
        filtered["KRA"].astype(str).str.lower().str.contains(needle, na=False)
        | filtered["KPI"].astype(str).str.lower().str.contains(needle, na=False)
    ]

display_cols = [
    "KRA",
    "KPI",
    "Frequency",
    "Planned",
    "Actual",
    "Variance",
    "Performance Status",
]

st.subheader("Actual vs Planned KPI/KRA")
render_table(filtered, columns=display_cols, height=520, empty_message="No KPI/KRA records match the selected filters.")

chart_rows = filtered[filtered["Planned Value"].notna() | filtered["Actual Value"].notna()].copy()
if chart_rows.empty:
    st.info("Enter current performance values to chart actual versus planned.")
else:
    chart_rows["Short KPI"] = chart_rows["KPI"].astype(str).str.slice(0, 42)
    comparison = chart_rows.melt(
        id_vars=["Short KPI", "KRA"],
        value_vars=["Planned Value", "Actual Value"],
        var_name="Measure",
        value_name="Value",
    ).dropna(subset=["Value"])
    comparison["Measure"] = comparison["Measure"].replace({"Planned Value": "Planned", "Actual Value": "Actual"})
    st.plotly_chart(
        style_chart(px.bar(
            comparison,
            x="Short KPI",
            y="Value",
            color="Measure",
            barmode="group",
            title="KPI/KRA Actual vs Planned",
            hover_data=["KRA"],
        )),
        width="stretch",
    )
