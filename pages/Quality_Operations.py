from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

import auth
from utils import (
    get_calibration_log,
    get_calibration_summary,
    global_filter_sidebar,
    inject_global_ui,
    load_master_data,
    render_navigation,
    render_page_header,
    render_table,
    render_table_with_details,
    render_top_nav,
    style_chart,
)


BASE_DIR = Path(__file__).resolve().parent.parent
DATA_FILE = BASE_DIR / "data" / "QAQC_Master.xlsx"

st.set_page_config(page_title="Quality Operations", layout="wide")
inject_global_ui()

if not auth.login():
    st.stop()

render_navigation()
render_top_nav()
getattr(auth, "render_user_sidebar", lambda: None)()

render_page_header(
    "Quality operations",
    "Review quality records, engineering controls, materials, and equipment from one workspace.",
    "Integrated operations",
)

try:
    master_data = load_master_data(DATA_FILE)
except FileNotFoundError as exc:
    st.error(exc)
    st.stop()

data = global_filter_sidebar(master_data)


def status_series(frame):
    if "Status" not in frame.columns:
        return pd.Series("", index=frame.index, dtype="object")
    return frame["Status"].fillna("").astype(str).str.strip().str.casefold()


def render_status_module(title, frame, id_column, columns, date_column=None, detail_label=None):
    """Render one record set within the combined workspace."""
    st.subheader(title)
    if not isinstance(frame, pd.DataFrame) or frame.empty:
        st.info(f"No {title.lower()} records match the active global filters.")
        return

    status = status_series(frame)
    closed = status.isin({"closed", "completed", "approved", "accepted", "passed", "pass", "compliant"})
    open_records = status.isin({"open", "pending", "in progress", "in-progress", "under review"})
    total = len(frame)

    total_col, open_col, closed_col, rate_col = st.columns(4)
    total_col.metric("Total records", total)
    open_col.metric("Open / pending", int(open_records.sum()))
    closed_col.metric("Closed / accepted", int(closed.sum()))
    rate_col.metric("Closeout", f"{int(closed.sum() / max(total, 1) * 100)}%")

    render_table_with_details(
        frame,
        id_col=id_column if id_column in frame.columns else None,
        table_columns=[column for column in columns if column in frame.columns],
        detail_label=detail_label or title,
    )

    chart_col, project_col = st.columns(2)
    with chart_col:
        counts = status.replace("", "Not set").value_counts().reset_index()
        counts.columns = ["Status", "Count"]
        st.plotly_chart(
            style_chart(px.pie(counts, names="Status", values="Count", title=f"{title} status")),
            width="stretch",
            key=f"quality_operations_{title.lower().replace(' ', '_')}_status",
        )
    with project_col:
        if "Project" in frame.columns:
            by_project = frame.groupby("Project").size().reset_index(name="Count")
            st.plotly_chart(
                style_chart(px.bar(by_project, x="Project", y="Count", title=f"{title} by project")),
                width="stretch",
                key=f"quality_operations_{title.lower().replace(' ', '_')}_projects",
            )

    if date_column and date_column in frame.columns:
        trend = frame.copy()
        trend[date_column] = pd.to_datetime(trend[date_column], errors="coerce")
        trend = trend.dropna(subset=[date_column])
        if not trend.empty:
            trend["Month"] = trend[date_column].dt.to_period("M").dt.to_timestamp()
            monthly = trend.groupby("Month").size().reset_index(name="Count")
            st.plotly_chart(
                style_chart(px.line(monthly, x="Month", y="Count", markers=True, title=f"{title} monthly trend")),
                width="stretch",
                key=f"quality_operations_{title.lower().replace(' ', '_')}_trend",
            )


def render_defect_module(frame):
    render_status_module(
        "Defect & rework",
        frame,
        "Defect_ID",
        [
            "Defect_ID", "Project", "Discipline", "Area/Location", "Description", "Root_Cause",
            "Date Identified", "Date Closed", "Status", "Rework Cost", "Rework Manhours",
        ],
        date_column="Date Identified",
    )
    if not isinstance(frame, pd.DataFrame) or frame.empty:
        return
    cost = pd.to_numeric(frame.get("Rework Cost", pd.Series(dtype=float)), errors="coerce").fillna(0).sum()
    hours = pd.to_numeric(frame.get("Rework Manhours", pd.Series(dtype=float)), errors="coerce").fillna(0).sum()
    cost_col, hours_col = st.columns(2)
    cost_col.metric("Total rework cost", f"${cost:,.2f}")
    hours_col.metric("Total rework manhours", f"{hours:,.1f}")


def render_document_module(frame):
    st.subheader("Document status")
    if not isinstance(frame, pd.DataFrame) or frame.empty:
        st.info("No document register records match the active global filters.")
        return

    document_type = frame.get("Document_Type", pd.Series("", index=frame.index)).fillna("").astype(str).str.upper()
    afc = int(document_type.eq("AFC").sum())
    total_col, afc_col, other_col, rate_col = st.columns(4)
    total_col.metric("Total documents", len(frame))
    afc_col.metric("AFC documents", afc)
    other_col.metric("Other documents", len(frame) - afc)
    rate_col.metric("AFC compliance", f"{int(afc / max(len(frame), 1) * 100)}%")

    render_table_with_details(
        frame,
        id_col="Document_ID" if "Document_ID" in frame.columns else None,
        table_columns=[
            column
            for column in ["Document_ID", "Project", "Document_Type", "Status", "Revision", "Issue_Date", "Due_Date"]
            if column in frame.columns
        ],
        detail_label="Document",
    )

    chart_col, project_col = st.columns(2)
    with chart_col:
        type_counts = document_type.replace("", "Not set").value_counts().reset_index()
        type_counts.columns = ["Document type", "Count"]
        st.plotly_chart(
            style_chart(px.pie(type_counts, names="Document type", values="Count", title="Document type breakdown")),
            width="stretch",
            key="quality_operations_document_types",
        )
    with project_col:
        if "Project" in frame.columns:
            project_counts = frame.groupby("Project").size().reset_index(name="Count")
            st.plotly_chart(
                style_chart(px.bar(project_counts, x="Project", y="Count", title="Documents by project")),
                width="stretch",
                key="quality_operations_documents_by_project",
            )


def render_concrete_and_materials(concrete, receipts):
    concrete_tab, receipts_tab = st.tabs(["Concrete", "Material receipts"])
    with concrete_tab:
        st.subheader("Concrete tracker")
        if not isinstance(concrete, pd.DataFrame) or concrete.empty:
            st.info("No concrete records match the active global filters.")
        else:
            volume = pd.to_numeric(concrete.get("Volume", pd.Series(dtype=float)), errors="coerce").fillna(0)
            total_col, volume_col, average_col = st.columns(3)
            total_col.metric("Concrete pours", len(concrete))
            volume_col.metric("Concrete volume", f"{volume.sum():,.1f} m³")
            average_col.metric("Average pour", f"{volume.mean():,.1f} m³")
            render_table(
                concrete,
                columns=[column for column in ["Pour_ID", "Project", "Date", "Location", "Volume"] if column in concrete.columns],
                empty_message="No concrete pour records are available.",
            )
            trend = concrete.copy()
            if "Date" in trend.columns:
                trend["Date"] = pd.to_datetime(trend["Date"], errors="coerce")
                trend = trend.dropna(subset=["Date"])
                if not trend.empty:
                    trend["Month"] = trend["Date"].dt.to_period("M").dt.to_timestamp()
                    monthly = trend.assign(Volume=volume.loc[trend.index]).groupby("Month", as_index=False)["Volume"].sum()
                    st.plotly_chart(
                        style_chart(px.line(monthly, x="Month", y="Volume", markers=True, title="Monthly concrete volume")),
                        width="stretch",
                        key="quality_operations_concrete_trend",
                    )
        st.page_link("pages/Concrete_Tracker.py", label="Open detailed concrete planning", width="stretch")

    with receipts_tab:
        st.subheader("Material receipts")
        if not isinstance(receipts, pd.DataFrame) or receipts.empty:
            st.info("No material receipt records match the active global filters.")
            return
        quantity = pd.to_numeric(receipts.get("Quantity (t)", pd.Series(dtype=float)), errors="coerce").fillna(0)
        total_col, quantity_col = st.columns(2)
        total_col.metric("Receipt records", len(receipts))
        quantity_col.metric("Received quantity", f"{quantity.sum():,.1f} t")
        render_table(
            receipts,
            columns=[
                column
                for column in ["Date", "Material", "Quantity (t)", "Supplier", "Delivery Note", "Project/Area", "Remarks"]
                if column in receipts.columns
            ],
            empty_message="No material receipt records are available.",
        )


def render_calibration_module(frame, summary):
    st.subheader("Calibration equipment")
    total_col, active_col, overdue_col, soon_col = st.columns(4)
    total_col.metric("Equipment records", summary.get("total", 0))
    active_col.metric("Active equipment", summary.get("active", 0))
    overdue_col.metric("Overdue calibration", summary.get("overdue", 0))
    soon_col.metric("Due within 21 days", summary.get("reminders", 0))
    if isinstance(frame, pd.DataFrame) and not frame.empty:
        render_table(
            frame,
            columns=[
                column
                for column in [
                    "Calibration_ID", "Equipment_Category", "Project", "Equipment_Type", "Serial_No",
                    "Next_Due_Date", "Days_Until_Due", "Alert_Status", "Status",
                ]
                if column in frame.columns
            ],
            empty_message="No calibration equipment records are available.",
        )
    else:
        st.info("No calibration equipment records are available.")
    st.page_link("pages/Calibration_Log.py", label="Open calibration actions and reports", width="stretch")


quality_tab, engineering_tab, materials_tab = st.tabs(["Quality records", "Engineering", "Materials & equipment"])

with quality_tab:
    ncr_tab, obs_tab, itr_tab, defects_tab = st.tabs(["NCR", "OBS", "ITR", "Defect & rework"])
    with ncr_tab:
        render_status_module(
            "NCR", data.get("NCR Log", pd.DataFrame()), "NCR_ID",
            ["NCR_ID", "Project", "Discipline", "Description", "Date Raised", "Due_Date", "Status", "Responsible_Person"],
            date_column="Date Raised",
        )
    with obs_tab:
        render_status_module(
            "OBS", data.get("OBS Log", pd.DataFrame()), "OBS_ID",
            ["OBS_ID", "Project", "Date_Raised", "Due_Date", "Status", "Responsible_Person"],
            date_column="Date_Raised",
        )
    with itr_tab:
        render_status_module(
            "ITR", data.get("ITR Log", pd.DataFrame()), "ITR_ID",
            ["ITR_ID", "Project", "Discipline", "Activity", "Status", "Inspector", "DATE"],
            date_column="DATE",
        )
    with defects_tab:
        render_defect_module(data.get("Defect-Rework Log", data.get("Defect/Rework Log", pd.DataFrame())))

with engineering_tab:
    ctq_tab, documents_tab = st.tabs(["CTQ", "Documents"])
    with ctq_tab:
        render_status_module(
            "CTQ", data.get("CTQ Log", pd.DataFrame()), "CTQ_ID",
            [
                "CTQ_ID", "Project", "Discipline", "Activity", "CTQ Description", "Acceptance Criteria",
                "Target Value", "Actual Value", "Status", "Date", "Responsible Inspector",
            ],
            date_column="Date",
        )
    with documents_tab:
        render_document_module(data.get("Document Register", pd.DataFrame()))

with materials_tab:
    material_tab, calibration_tab = st.tabs(["Concrete & materials", "Calibration equipment"])
    with material_tab:
        render_concrete_and_materials(
            data.get("Concrete Tracker", pd.DataFrame()),
            data.get("Material_Receipts", pd.DataFrame()),
        )
    with calibration_tab:
        render_calibration_module(get_calibration_log(data), get_calibration_summary(data))
