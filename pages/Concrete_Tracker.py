from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

import auth
from utils import global_filter_sidebar, inject_global_ui, load_master_data, render_top_nav


DATA_FILE = Path(__file__).parents[1] / "data" / "QAQC_Master.xlsx"
BASE_DIR = Path(__file__).resolve().parent.parent
ASSETS = BASE_DIR / "assets"
EVOMEC_LOGO = ASSETS / "evomec_logo.png"
NLNG_LOGO = ASSETS / "nlng_logo.png"

MATERIAL_COLUMNS = {
    "Cement": "Cement (t)",
    "River Sand 0-4mm": "River Sand 0-4mm (t)",
    "5-15mm Stone": "5-15mm Stone (t)",
    "15-22mm Stone": "15-22mm Stone (t)",
}

MIX_DESIGNS = {
    "C25 typical": {
        "cement_kg_per_m3": 340,
        "sand_kg_per_m3": 760,
        "stone_5_15_kg_per_m3": 760,
        "stone_15_22_kg_per_m3": 420,
    },
    "C30 typical": {
        "cement_kg_per_m3": 380,
        "sand_kg_per_m3": 728,
        "stone_5_15_kg_per_m3": 769,
        "stone_15_22_kg_per_m3": 395,
    },
    "C35 typical": {
        "cement_kg_per_m3": 420,
        "sand_kg_per_m3": 700,
        "stone_5_15_kg_per_m3": 780,
        "stone_15_22_kg_per_m3": 390,
    },
}

SERVICE_LEVEL_Z = {
    "90%": 1.28,
    "95%": 1.65,
    "98%": 2.05,
}


st.set_page_config(page_title="Concrete Tracker", layout="wide")
inject_global_ui()

if not auth.login():
    st.stop()

render_top_nav()
getattr(auth, "render_user_sidebar", lambda: None)()


def safe_path(path):
    return str(path) if path.exists() else None


def clean_volume(series):
    return (
        series.astype(str)
        .str.replace("m3", "", regex=False)
        .str.replace("m³", "", regex=False)
        .str.replace("mÂ³", "", regex=False)
        .str.replace(",", "", regex=False)
        .str.strip()
        .replace({"nan": None, "None": None, "": None})
        .pipe(pd.to_numeric, errors="coerce")
        .fillna(0)
    )


def monthly_actuals(df):
    frame = df.copy()
    frame["Date"] = pd.to_datetime(frame["Date"], errors="coerce")
    frame = frame.dropna(subset=["Date"])
    if frame.empty:
        return pd.DataFrame(columns=["Month", "Volume"])

    monthly = (
        frame.assign(Month=frame["Date"].dt.to_period("M").dt.to_timestamp())
        .groupby("Month", as_index=False)["Volume"]
        .sum()
        .sort_values("Month")
    )
    month_index = pd.date_range(monthly["Month"].min(), monthly["Month"].max(), freq="MS")
    return (
        monthly.set_index("Month")
        .reindex(month_index, fill_value=0)
        .rename_axis("Month")
        .reset_index()
    )


def forecast_monthly_volume(monthly, months, intensity):
    if monthly.empty:
        return pd.DataFrame(columns=["Month", "Forecast Volume"])

    history = monthly["Volume"].astype(float).tail(6).reset_index(drop=True)
    recent = history.tail(3)
    if len(recent) >= 3:
        base = recent.mul([0.2, 0.3, 0.5]).sum()
    else:
        base = recent.mean()

    if len(history) >= 2:
        trend = history.diff().dropna().tail(3).mean()
        trend = max(min(trend, base * 0.35), -base * 0.25)
    else:
        trend = 0

    start = pd.to_datetime(monthly["Month"].max()) + pd.DateOffset(months=1)
    rows = []
    for index in range(months):
        projected = max((base + trend * (index + 1)) * intensity, 0)
        rows.append(
            {
                "Month": start + pd.DateOffset(months=index),
                "Forecast Volume": projected,
                "Method": "Recent weighted average with capped trend",
            }
        )
    return pd.DataFrame(rows)


def add_material_columns(df, mix, waste_multiplier=1.0, source_col="Volume"):
    frame = df.copy()
    volume = frame[source_col].astype(float) * waste_multiplier
    frame["Concrete Volume incl. Waste (m3)"] = volume
    frame["Cement (t)"] = volume * mix["cement_kg_per_m3"] / 1000
    frame["Cement Jumbo Bags"] = frame["Cement (t)"] / 1.5
    frame["Cement 50kg Bags"] = frame["Cement (t)"] * 1000 / 50
    frame["River Sand 0-4mm (t)"] = volume * mix["sand_kg_per_m3"] / 1000
    frame["5-15mm Stone (t)"] = volume * mix["stone_5_15_kg_per_m3"] / 1000
    frame["15-22mm Stone (t)"] = volume * mix["stone_15_22_kg_per_m3"] / 1000
    return frame


def clean_receipts(df):
    if df.empty:
        return df
    frame = df.copy()
    frame["Quantity (t)"] = pd.to_numeric(frame.get("Quantity (t)", 0), errors="coerce").fillna(0)
    frame["Material"] = frame.get("Material", "").astype(str).str.strip()
    if "Date" in frame.columns:
        frame["Date"] = pd.to_datetime(frame["Date"], errors="coerce")
    return frame


def material_requirement_from_volume(volume, mix):
    return {
        "Cement": volume * mix["cement_kg_per_m3"] / 1000,
        "River Sand 0-4mm": volume * mix["sand_kg_per_m3"] / 1000,
        "5-15mm Stone": volume * mix["stone_5_15_kg_per_m3"] / 1000,
        "15-22mm Stone": volume * mix["stone_15_22_kg_per_m3"] / 1000,
    }


logo_col1, logo_col2 = st.columns(2)
with logo_col1:
    if safe_path(EVOMEC_LOGO):
        st.image(safe_path(EVOMEC_LOGO), width=150)
with logo_col2:
    if safe_path(NLNG_LOGO):
        st.image(safe_path(NLNG_LOGO), width=140)

st.markdown(
    """
<div class="dashboard-hero">
    <div class="hero-eyebrow">Concrete production intelligence</div>
    <h1>Concrete Tracker and Forecast Centre</h1>
    <p>Track pours, calculate material consumption, review stock balance, and forecast procurement using recent production trend, lead time, safety stock, and approved mix design assumptions.</p>
</div>
""",
    unsafe_allow_html=True,
)

data = load_master_data(DATA_FILE)
filtered_data = global_filter_sidebar(data)
concrete = filtered_data.get("Concrete Tracker", pd.DataFrame()).copy()

if concrete.empty:
    st.warning("No concrete tracker records available.")
    st.stop()

if "Volume" not in concrete.columns:
    st.error("Concrete Tracker must contain a Volume column.")
    st.stop()

concrete["Date"] = pd.to_datetime(concrete.get("Date"), errors="coerce")
concrete["Volume"] = clean_volume(concrete["Volume"])

projects = ["All"]
if "Project" in concrete.columns:
    projects += sorted(concrete["Project"].dropna().astype(str).unique().tolist())
selected_project = st.selectbox("Project focus", projects, key="concrete_project_focus")
concrete_filtered = concrete.copy()
if selected_project != "All" and "Project" in concrete_filtered.columns:
    concrete_filtered = concrete_filtered[concrete_filtered["Project"].astype(str) == selected_project]

missing_volume_count = int((concrete_filtered["Volume"] <= 0).sum())
valid_pours = concrete_filtered[concrete_filtered["Volume"] > 0].copy()
monthly_volume = monthly_actuals(valid_pours)

settings_col1, settings_col2, settings_col3, settings_col4 = st.columns(4)
with settings_col1:
    mix_name = st.selectbox("Mix design basis", list(MIX_DESIGNS.keys()) + ["Custom"], index=1)
with settings_col2:
    waste_pct = st.slider("Waste / overbreak allowance (%)", 0, 20, 7)
with settings_col3:
    intensity = st.slider("Construction intensity factor", 0.50, 1.75, 1.00, 0.05)
with settings_col4:
    service_level = st.selectbox("Stock service level", list(SERVICE_LEVEL_Z.keys()), index=1)

if mix_name == "Custom":
    custom_cols = st.columns(4)
    mix = {
        "cement_kg_per_m3": custom_cols[0].number_input("Cement kg/m3", 250, 600, 380, 5),
        "sand_kg_per_m3": custom_cols[1].number_input("Sand kg/m3", 400, 1100, 728, 5),
        "stone_5_15_kg_per_m3": custom_cols[2].number_input("5-15mm kg/m3", 400, 1200, 769, 5),
        "stone_15_22_kg_per_m3": custom_cols[3].number_input("15-22mm kg/m3", 200, 900, 395, 5),
    }
else:
    mix = MIX_DESIGNS[mix_name]

with st.expander("Forecast and procurement controls", expanded=False):
    c1, c2, c3, c4 = st.columns(4)
    forecast_months = c1.number_input("Forecast months", 1, 6, 3, 1)
    coverage_months = c2.number_input("Procurement coverage months", 1, 6, 2, 1)
    lead_time_days = c3.number_input("Supplier lead time (days)", 1, 120, 21, 1)
    safety_days = c4.number_input("Extra site safety days", 0, 60, 10, 1)

waste_multiplier = 1 + waste_pct / 100
monthly_materials = add_material_columns(monthly_volume, mix, waste_multiplier=1.0)
forecast_volume = forecast_monthly_volume(monthly_volume, int(forecast_months), intensity)
forecast_materials = add_material_columns(
    forecast_volume.rename(columns={"Forecast Volume": "Volume"}),
    mix,
    waste_multiplier=waste_multiplier,
)

total_volume = valid_pours["Volume"].sum()
average_volume = valid_pours["Volume"].mean() if not valid_pours.empty else 0
latest_month = monthly_volume["Month"].max() if not monthly_volume.empty else None

k1, k2, k3, k4 = st.columns(4)
k1.metric("Concrete pours", len(concrete_filtered))
k2.metric("Valid volume", f"{total_volume:,.1f} m3")
k3.metric("Average pour", f"{average_volume:,.1f} m3")
k4.metric("Missing/zero volumes", missing_volume_count)

tab_overview, tab_forecast, tab_stock, tab_receipts, tab_records = st.tabs(
    ["Overview", "Forecast", "Material Balance", "Receipts", "Pour Records"]
)

with tab_overview:
    c1, c2 = st.columns(2)
    project_volume = (
        valid_pours.groupby("Project", as_index=False)["Volume"].sum()
        if "Project" in valid_pours.columns and not valid_pours.empty
        else pd.DataFrame(columns=["Project", "Volume"])
    )
    with c1:
        if not monthly_volume.empty:
            fig = px.line(monthly_volume, x="Month", y="Volume", markers=True, title="Monthly concrete volume")
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No dated valid pours available for trend analysis.")
    with c2:
        if not project_volume.empty:
            fig = px.bar(project_volume, x="Project", y="Volume", title="Concrete volume by project")
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No project volume distribution available.")

    st.markdown("#### Consumption by month")
    st.dataframe(monthly_materials, use_container_width=True, hide_index=True)

with tab_forecast:
    st.markdown("#### Realistic production forecast")
    if forecast_materials.empty:
        st.warning("Not enough dated concrete history to build a forecast.")
    else:
        actual_plot = monthly_volume.rename(columns={"Volume": "Actual Volume"}).copy()
        forecast_plot = forecast_volume.copy()
        chart_df = pd.concat(
            [
                actual_plot[["Month", "Actual Volume"]].rename(columns={"Actual Volume": "Volume"}).assign(Type="Actual"),
                forecast_plot[["Month", "Forecast Volume"]].rename(columns={"Forecast Volume": "Volume"}).assign(Type="Forecast"),
            ],
            ignore_index=True,
        )
        fig = px.line(chart_df, x="Month", y="Volume", color="Type", markers=True, title="Actual vs forecast concrete volume")
        st.plotly_chart(fig, use_container_width=True)

        next_month = forecast_materials.iloc[0]
        f1, f2, f3, f4 = st.columns(4)
        f1.metric("Next month concrete", f"{next_month['Concrete Volume incl. Waste (m3)']:,.1f} m3")
        f2.metric("Cement", f"{next_month['Cement (t)']:,.1f} t")
        f3.metric("Sand", f"{next_month['River Sand 0-4mm (t)']:,.1f} t")
        f4.metric("Aggregates", f"{next_month['5-15mm Stone (t)'] + next_month['15-22mm Stone (t)']:,.1f} t")

        st.dataframe(
            forecast_materials[
                [
                    "Month",
                    "Concrete Volume incl. Waste (m3)",
                    "Cement (t)",
                    "Cement Jumbo Bags",
                    "Cement 50kg Bags",
                    "River Sand 0-4mm (t)",
                    "5-15mm Stone (t)",
                    "15-22mm Stone (t)",
                ]
            ],
            use_container_width=True,
            hide_index=True,
        )
        st.caption(
            "Forecast basis: recent weighted monthly volume, capped trend, construction intensity factor, and waste allowance. Replace assumptions with approved project planning data when available."
        )

with tab_stock:
    inflow = clean_receipts(data.get("Material_Receipts", pd.DataFrame()))
    inflow_summary = (
        inflow.groupby("Material")["Quantity (t)"].sum() if not inflow.empty else pd.Series(dtype=float)
    )

    historical_consumption = {
        material: monthly_materials[column].sum() if column in monthly_materials.columns else 0
        for material, column in MATERIAL_COLUMNS.items()
    }
    current_stock = {
        material: float(inflow_summary.get(material, 0)) - historical_consumption.get(material, 0)
        for material in MATERIAL_COLUMNS
    }

    horizon = max(1, min(int(coverage_months), len(forecast_materials))) if not forecast_materials.empty else 1
    horizon_volume = (
        forecast_materials["Concrete Volume incl. Waste (m3)"].head(horizon).sum()
        if not forecast_materials.empty
        else 0
    )
    avg_forecast_monthly = (
        forecast_materials["Concrete Volume incl. Waste (m3)"].mean()
        if not forecast_materials.empty
        else monthly_volume["Volume"].tail(3).mean()
        if not monthly_volume.empty
        else 0
    )
    monthly_std = monthly_volume["Volume"].tail(6).std() if len(monthly_volume) > 1 else avg_forecast_monthly * 0.15
    monthly_std = 0 if pd.isna(monthly_std) else monthly_std
    z_score = SERVICE_LEVEL_Z[service_level]
    lead_time_volume = avg_forecast_monthly * lead_time_days / 30.4
    safety_volume = (monthly_std / 30.4) * (lead_time_days ** 0.5) * z_score + avg_forecast_monthly * safety_days / 30.4

    horizon_demand = material_requirement_from_volume(horizon_volume, mix)
    lead_demand = material_requirement_from_volume(lead_time_volume, mix)
    safety_stock = material_requirement_from_volume(safety_volume, mix)

    rows = []
    avg_daily_volume = avg_forecast_monthly / 30.4 if avg_forecast_monthly else 0
    avg_daily_material = material_requirement_from_volume(avg_daily_volume, mix)
    for material in MATERIAL_COLUMNS:
        stock = current_stock[material]
        reorder_point = lead_demand[material] + safety_stock[material]
        recommended_order = max(horizon_demand[material] + safety_stock[material] - stock, 0)
        days_cover = stock / avg_daily_material[material] if avg_daily_material[material] > 0 else 0
        if stock <= lead_demand[material]:
            status = "Critical"
        elif stock < reorder_point:
            status = "Order now"
        elif days_cover < lead_time_days + safety_days:
            status = "Watch"
        else:
            status = "Covered"
        rows.append(
            {
                "Material": material,
                "Stock (t)": stock,
                "Lead-time demand (t)": lead_demand[material],
                "Safety stock (t)": safety_stock[material],
                "Reorder point (t)": reorder_point,
                f"{horizon}-month demand (t)": horizon_demand[material],
                "Recommended order (t)": recommended_order,
                "Days of cover": days_cover,
                "Status": status,
            }
        )

    stock_plan = pd.DataFrame(rows)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Lead-time concrete demand", f"{lead_time_volume:,.1f} m3")
    c2.metric("Safety concrete allowance", f"{safety_volume:,.1f} m3")
    c3.metric("Coverage horizon", f"{horizon} month(s)")
    c4.metric("Service level", service_level)

    st.dataframe(stock_plan, use_container_width=True, hide_index=True)

    chart_df = stock_plan.melt(
        id_vars="Material",
        value_vars=["Stock (t)", "Reorder point (t)", "Recommended order (t)"],
        var_name="Measure",
        value_name="Tonnes",
    )
    fig = px.bar(chart_df, x="Material", y="Tonnes", color="Measure", barmode="group", title="Stock, reorder point, and order recommendation")
    st.plotly_chart(fig, use_container_width=True)

    critical = stock_plan[stock_plan["Status"].isin(["Critical", "Order now"])]
    if critical.empty:
        st.success("Procurement position is currently covered against the selected forecast assumptions.")
    else:
        st.warning("Procurement action is required for: " + ", ".join(critical["Material"].tolist()))

    if not inflow.empty and not valid_pours.empty and "Date" in inflow.columns:
        latest_receipt = inflow["Date"].max()
        latest_pour = valid_pours["Date"].max()
        if pd.notna(latest_receipt) and pd.notna(latest_pour) and latest_receipt > latest_pour + pd.DateOffset(months=3):
            st.info(
                "Receipt records are much newer than the pour history. Validate opening stock before using this as a purchase order basis."
            )

with tab_receipts:
    inflow = clean_receipts(data.get("Material_Receipts", pd.DataFrame()))
    if inflow.empty:
        st.warning("No material receipt data available.")
    else:
        receipt_summary = inflow.groupby("Material", as_index=False)["Quantity (t)"].sum()
        c1, c2 = st.columns(2)
        with c1:
            fig = px.bar(receipt_summary, x="Material", y="Quantity (t)", title="Material receipts by material")
            st.plotly_chart(fig, use_container_width=True)
        with c2:
            if "Date" in inflow.columns:
                receipt_timeline = (
                    inflow.dropna(subset=["Date"])
                    .assign(Month=lambda df: df["Date"].dt.to_period("M").dt.to_timestamp())
                    .groupby(["Month", "Material"], as_index=False)["Quantity (t)"]
                    .sum()
                )
                fig = px.line(receipt_timeline, x="Month", y="Quantity (t)", color="Material", markers=True, title="Receipt trend")
                st.plotly_chart(fig, use_container_width=True)
        st.dataframe(inflow, use_container_width=True, hide_index=True)

with tab_records:
    display_cols = [col for col in ["Pour_ID", "Date", "Project", "Location", "Volume"] if col in concrete_filtered.columns]
    st.dataframe(concrete_filtered[display_cols], use_container_width=True, hide_index=True)
    if missing_volume_count:
        st.warning(f"{missing_volume_count} records have missing or zero concrete volume. Correct these rows to improve forecast accuracy.")
