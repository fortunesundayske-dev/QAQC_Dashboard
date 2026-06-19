import streamlit as st
import pandas as pd
import plotly.express as px
from pathlib import Path
from utils import load_master_data, global_filter_sidebar, apply_filters, render_table, inject_global_ui, render_table_with_details_render_navigation
from auth import login
render_navigation()

if not login():
    st.stop()
DATA_FILE = Path(__file__).parents[1] / "data" / "QAQC_Master.xlsx"
BASE_DIR = Path(__file__).resolve().parent.parent
st.set_page_config(page_title="Concrete Tracker", layout="wide")
inject_global_ui()
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

st.title("Concrete Tracker")
st.markdown("Track concrete placements, volumes, and project delivery performance.")

filters = global_filter_sidebar(load_master_data(DATA_FILE))
data = load_master_data(DATA_FILE)
concrete = apply_filters(data.get("Concrete Tracker", pd.DataFrame()), filters, date_column="Date")

if concrete.empty:
    st.warning("No concrete tracker records available.")
    st.stop()
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
# ==========================================
# 🧹 CLEAN VOLUME COLUMN (CRITICAL FIX)
# ==========================================

if "Volume" in concrete.columns:

    concrete["Volume"] = (
        concrete["Volume"]
        .astype(str)
        .str.replace("m³", "", regex=False)
        .str.replace(",", "", regex=False)
        .str.strip()
    )

    concrete["Volume"] = pd.to_numeric(concrete["Volume"], errors="coerce")

    concrete["Volume"] = concrete["Volume"].fillna(0)
    
c1, c2, c3 = st.columns(3)
# ==========================================
# 🎯 SAFE PROJECT FILTER (NO ERROR VERSION)
# ==========================================

concrete_filtered = concrete.copy()  # 🔥 ALWAYS EXISTS

if "Project" in concrete.columns:

    projects = ["All"] + sorted(concrete["Project"].dropna().unique().tolist())

    selected_project = st.selectbox(
    "Filter by Project",
    projects,
    key="project_filter_select"
)

    if selected_project != "All":
        concrete_filtered = concrete[concrete["Project"] == selected_project]
else:
    total_volume = 0
    average_volume = 0

c1.metric("Concrete Pours", len(concrete_filtered))

concrete_filtered["Volume"] = pd.to_numeric(
    concrete_filtered["Volume"],
    errors="coerce"
)

total_volume = concrete_filtered["Volume"].sum()
average_volume = concrete_filtered["Volume"].mean()

c2.metric("Total Volume", f"{total_volume:.1f} m³")
c3.metric("Average Volume", f"{average_volume:.1f} m³")

st.markdown("---")

st.subheader("Concrete Tracking Table")
table_cols = [col for col in ["Pour_ID", "Date", "Project", "Location", "Volume"] if col in concrete.columns]
id_col = "Pour_ID" if "Pour_ID" in concrete.columns else None
selected = render_table_with_details(
    concrete_filtered,
    id_col=id_col,
    table_columns=table_cols,
    detail_label="Pour"
)
st.markdown("---")
project_volume = concrete.groupby("Project")["Volume"].sum().reset_index()
monthly_volume = concrete.copy()
if "Date" in monthly_volume.columns:
    monthly_volume["Date"] = pd.to_datetime(monthly_volume["Date"], errors="coerce")
    monthly_volume["Month"] = monthly_volume["Date"].dt.to_period("M").dt.to_timestamp()
    monthly_volume = monthly_volume.groupby("Month")["Volume"].sum().reset_index()

# ==========================================
# MONTHLY MATERIAL PROCUREMENT FORECAST
# ==========================================

st.markdown("---")
st.subheader("Monthly Material Procurement Forecast (C30)")
MIX_DESIGN = {
    "cement_kg_per_m3": 400,
    "sand_kg_per_m3": 728,
    "stone_5_15_kg_per_m3": 769,
    "stone_15_22_kg_per_m3": 395
}

WASTE_FACTOR = 1.10
JUMBO_BAG_KG = 1500


cement_content = st.number_input(
    "Cement Content (kg/m³)",
    min_value=250,
    max_value=600,
    value=380,
    step=5,
    help="Enter approved cement content from the mix design."
)

forecast_df = concrete.copy()

forecast_df["Date"] = pd.to_datetime(
    forecast_df["Date"],
    errors="coerce"
)

forecast_df["Month"] = (
    forecast_df["Date"]
    .dt.to_period("M")
    .dt.to_timestamp()
)

monthly_materials = (
    forecast_df
    .groupby("Month")["Volume"]
    .sum()
    .reset_index()
)

# ==========================================
# MATERIAL CALCULATION (FIXED - MIX DESIGN BASED)
# ==========================================

monthly_materials["Cement (kg)"] = (
    monthly_materials["Volume"] * MIX_DESIGN["cement_kg_per_m3"]
)

monthly_materials["Cement (t)"] = monthly_materials["Cement (kg)"] / 1000

monthly_materials["Cement Jumbo Bags"] = (
    monthly_materials["Cement (kg)"] / JUMBO_BAG_KG
)

monthly_materials["River Sand 0-4mm (t)"] = (
    monthly_materials["Volume"] * MIX_DESIGN["sand_kg_per_m3"] / 1000
)

monthly_materials["Stone 5-15mm (t)"] = (
    monthly_materials["Volume"] * MIX_DESIGN["stone_5_15_kg_per_m3"] / 1000
)

monthly_materials["Stone 15-22mm (t)"] = (
    monthly_materials["Volume"] * MIX_DESIGN["stone_15_22_kg_per_m3"] / 1000
)

st.dataframe(
    monthly_materials,
    use_container_width=True
)
# ==========================================
# 📦 MATERIAL RECEIPTS (INFLOW SYSTEM)
# ==========================================

st.markdown("---")
st.subheader("📦 Material Receipts (Inflow Tracking)")

# Load Material Receipts sheet
inflow = data.get("Material_Receipts", pd.DataFrame()).copy()

if inflow.empty:
    st.warning("No material receipt data available.")
    inflow_summary = pd.Series(dtype=float)
else:
    # Clean data
    inflow["Quantity (t)"] = pd.to_numeric(inflow["Quantity (t)"], errors="coerce").fillna(0)

    # Normalize material names (VERY IMPORTANT for matching)
    inflow["Material"] = inflow["Material"].str.strip()

    # Group inflow
    inflow_summary = inflow.groupby("Material")["Quantity (t)"].sum()

    # Show table
    st.dataframe(inflow, use_container_width=True)

# ==========================================
# 📊 INFLOW SUMMARY CARDS
# ==========================================

cement_inflow = inflow_summary.get("Cement", 0)
sand_inflow = inflow_summary.get("River Sand 0-4mm", 0)
stone_5_inflow = inflow_summary.get("5-15mm Stone", 0)
stone_22_inflow = inflow_summary.get("15-22mm Stone", 0)

col1, col2, col3, col4 = st.columns(4)

col1.metric("Cement Received (t)", f"{cement_inflow:.1f}")
col2.metric("Sand Received (t)", f"{sand_inflow:.1f}")
col3.metric("5-15mm Received (t)", f"{stone_5_inflow:.1f}")
col4.metric("15-22mm Received (t)", f"{stone_22_inflow:.1f}")

# ==========================================
# 📦 STOCK BALANCE (INFLOW - CONSUMPTION)
# ==========================================

st.markdown("---")
st.subheader("📦 Material Stock Balance")

cement_used = monthly_materials["Cement (t)"].sum()
sand_used = monthly_materials["River Sand 0-4mm (t)"].sum()
stone_5_used = monthly_materials["Stone 5-15mm (t)"].sum()
stone_22_used = monthly_materials["Stone 15-22mm (t)"].sum()

stock = {
    "Cement": cement_inflow - cement_used,
    "Sand": sand_inflow - sand_used,
    "5-15mm": stone_5_inflow - stone_5_used,
    "15-22mm": stone_22_inflow - stone_22_used
}

c1, c2, c3, c4 = st.columns(4)

c1.metric("Cement Stock (t)", f"{stock['Cement']:.1f}")
c2.metric("Sand Stock (t)", f"{stock['Sand']:.1f}")
c3.metric("5-15mm Stock (t)", f"{stock['5-15mm']:.1f}")
c4.metric("15-22mm Stock (t)", f"{stock['15-22mm']:.1f}")

st.markdown("---")
st.subheader("⚠️ Stock Alerts")

safety = {
    "Cement": 50,
    "Sand": 80,
    "5-15mm": 60,
    "15-22mm": 40
}

alerts = []

for key in stock:
    if stock[key] < safety[key]:
        alerts.append(f"⚠️ {key} below safety stock")

if alerts:
    for a in alerts:
        st.error(a)
else:
    st.success("All materials are within safe stock levels")

# ==========================================
# 🧠 PROCUREMENT INTELLIGENCE ENGINE
# ==========================================

st.markdown("---")
st.subheader("🧠 Procurement Intelligence System")
# -----------------------------
# SAFE AVERAGE VOLUME
# -----------------------------

avg_volume = 0  # default fallback

if "Volume" in monthly_materials.columns and not monthly_materials.empty:

    monthly_materials["Volume"] = pd.to_numeric(
        monthly_materials["Volume"],
        errors="coerce"
    )

    last_3 = monthly_materials["Volume"].dropna().tail(3)

    if len(last_3) > 0:
        avg_volume = last_3.mean()

# -----------------------------
# 1. FORECAST NEXT MONTH DEMAND
# -----------------------------
forecast_volume = avg_volume * WASTE_FACTOR

forecast = {
    "cement": forecast_volume * MIX_DESIGN["cement_kg_per_m3"] / 1000,
    "sand": forecast_volume * MIX_DESIGN["sand_kg_per_m3"] / 1000,
    "stone_5_15": forecast_volume * MIX_DESIGN["stone_5_15_kg_per_m3"] / 1000,
    "stone_15_22": forecast_volume * MIX_DESIGN["stone_15_22_kg_per_m3"] / 1000
}

# -----------------------------
# 2. PROCUREMENT NEED = FORECAST - STOCK
# -----------------------------
procurement = {
    "Cement": max(forecast["cement"] - stock["Cement"], 0),
    "Sand": max(forecast["sand"] - stock["Sand"], 0),
    "5-15mm": max(forecast["stone_5_15"] - stock["5-15mm"], 0),
    "15-22mm": max(forecast["stone_15_22"] - stock["15-22mm"], 0)
}

# -----------------------------
# 3. DISPLAY PROCUREMENT PLAN
# -----------------------------
c1, c2, c3, c4 = st.columns(4)

c1.metric("Buy Cement (t)", f"{procurement['Cement']:.1f}")
c2.metric("Buy Sand (t)", f"{procurement['Sand']:.1f}")
c3.metric("Buy 5-15mm (t)", f"{procurement['5-15mm']:.1f}")
c4.metric("Buy 15-22mm (t)", f"{procurement['15-22mm']:.1f}")
# ==========================================
# ⚠️ PROCUREMENT ALERT ENGINE
# ==========================================

st.markdown("---")
st.subheader("⚠️ Procurement Risk Alerts")

alerts = []

if procurement["Cement"] > 100:
    alerts.append("⚠️ High cement procurement required (>100t)")

if stock["Cement"] < 30:
    alerts.append("🚨 Critical cement shortage risk")

if any(v == 0 for v in procurement.values()):
    alerts.append("ℹ️ Some materials fully covered by stock (no purchase needed)")

if alerts:
    for a in alerts:
        st.warning(a)
else:
    st.success("Procurement risk is under control")

# ==========================================
# 📊 PROCUREMENT VISUAL DASHBOARD
# ==========================================

st.markdown("---")
st.subheader("📊 Procurement vs Stock Comparison")

chart_df = pd.DataFrame({
    "Material": ["Cement", "Sand", "5-15mm", "15-22mm"],
    "Stock": [
        stock["Cement"],
        stock["Sand"],
        stock["5-15mm"],
        stock["15-22mm"]
    ],
    "To Procure": [
        procurement["Cement"],
        procurement["Sand"],
        procurement["5-15mm"],
        procurement["15-22mm"]
    ]
})

fig = px.bar(
    chart_df,
    x="Material",
    y=["Stock", "To Procure"],
    barmode="group",
    title="Stock vs Procurement Requirement"
)

st.plotly_chart(fig, use_container_width=True)

# ==========================================
# NEXT MONTH PROCUREMENT FORECAST
# ==========================================

st.markdown("---")
st.subheader("Next Month Procurement Forecast")

if len(monthly_materials) >= 3:

    # Average of last 3 months concrete volume
    avg_volume = monthly_materials["Volume"].tail(3).mean()

elif len(monthly_materials) > 0:

    # Average of all available months
    avg_volume = monthly_materials["Volume"].mean()

else:
    avg_volume = 0

forecast_cement_kg = avg_volume * MIX_DESIGN["cement_kg_per_m3"] * WASTE_FACTOR
forecast_cement_jumbo_bags = forecast_cement_kg / JUMBO_BAG_KG

forecast_sand = avg_volume * MIX_DESIGN["sand_kg_per_m3"] / 1000 * WASTE_FACTOR
forecast_stone_5_15 = avg_volume * MIX_DESIGN["stone_5_15_kg_per_m3"] / 1000 * WASTE_FACTOR
forecast_stone_15_22 = avg_volume * MIX_DESIGN["stone_15_22_kg_per_m3"] / 1000 * WASTE_FACTOR

# Determine next month
if not monthly_materials.empty:

    latest_month = pd.to_datetime(monthly_materials["Month"].max())

    next_month = (
        latest_month + pd.DateOffset(months=1)
    ).strftime("%B %Y")

else:
    next_month = "Next Month"

st.info(
    f"Estimated procurement requirement for {next_month} "
    f"based on average concrete consumption."
)

fc1, fc2, fc3, fc4 = st.columns(4)

fc1.metric(
    "Jumbo Bags Required",
    f"{forecast_cement_jumbo_bags:,.1f}"
)

fc2.metric(
    "River Sand (t)",
    f"{forecast_sand:,.1f}"
)

fc3.metric(
    "5-15mm Stone (t)",
    f"{forecast_stone_5_15:,.1f}"
)

fc4.metric(
    "15-22mm Stone (t)",
    f"{forecast_stone_15_22:,.1f}"
)
# Latest month procurement requirement
if not monthly_materials.empty:

    latest = monthly_materials.iloc[-1]

    c1, c2, c3, c4 = st.columns(4)

    c1.metric(
        "Cement Jumbo Bags",
        f"{latest.get('Cement Jumbo Bags', 0):.1f}"
    )

    c2.metric(
        "River Sand (t)",
        f"{latest.get('River Sand 0-4mm (t)', 0):.1f}"
    )

    c3.metric(
        "5-15mm Stone (t)",
        f"{latest.get('Stone 5-15mm (t)', 0):.1f}"
    )

    c4.metric(
        "15-22mm Stone (t)",
        f"{latest.get('Stone 15-22mm (t)', 0):.1f}"
    )

    fig_materials = px.bar(
        monthly_materials,
        x="Month",
        y=[
            "River Sand 0-4mm (t)",
            "Stone 5-15mm (t)",
            "Stone 15-22mm (t)"
        ],
        barmode="group",
        title="Monthly Aggregate Requirement Forecast"
    )

    st.plotly_chart(
        fig_materials,
        use_container_width=True
    )

col1, col2 = st.columns(2)
col1.plotly_chart(px.line(monthly_volume, x="Month", y="Volume", title="Monthly Concrete Volume", markers=True), use_container_width=True)
col2.plotly_chart(px.bar(project_volume, x="Project", y="Volume", title="Total Concrete by Project"), use_container_width=True)
