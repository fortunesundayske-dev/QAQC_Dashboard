from pathlib import Path
from datetime import date
from email.message import EmailMessage
from email.utils import formataddr
from io import BytesIO
import json
import sys
from urllib.parse import quote, urlencode

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


BASE_DIR = Path(__file__).parents[1]
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))


st.set_page_config(page_title="Calibration Log", layout="wide")
inject_global_ui()

if not auth.login():
    st.stop()

render_navigation()
render_top_nav()
getattr(auth, "render_user_sidebar", lambda: None)()

DATA_FILE = BASE_DIR / "data" / "QAQC_Master.xlsx"
USERS_FILE = BASE_DIR / "data" / "users.json"
CALIBRATION_REPORT_DIR = BASE_DIR / "outputs" / "calibration_reports"
data = load_master_data(DATA_FILE)
log = get_calibration_log(data)
summary = get_calibration_summary(data)


def registered_account_emails():
    try:
        users = json.loads(USERS_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    emails = [
        str(user.get("email", "")).strip()
        for user in users.values()
        if str(user.get("email", "")).strip()
    ]
    return sorted(set(emails))


def clean_pdf_value(value):
    if pd.isna(value):
        return ""
    if isinstance(value, pd.Timestamp):
        return value.strftime("%Y-%m-%d")
    if hasattr(value, "strftime") and not isinstance(value, str):
        try:
            return value.strftime("%Y-%m-%d")
        except (TypeError, ValueError):
            pass
    return str(value).strip()


def safe_report_filename(title):
    safe = "".join(char if char.isalnum() or char in {"-", "_"} else "_" for char in str(title))
    return safe.strip("_").lower() or "calibration_report"


def generate_calibration_pdf(records, report_title="Calibration Log Report"):
    if not isinstance(records, pd.DataFrame) or records.empty:
        raise RuntimeError("No calibration records are available for PDF export.")

    CALIBRATION_REPORT_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = pd.Timestamp.now().strftime("%Y%m%d_%H%M%S")
    pdf_path = CALIBRATION_REPORT_DIR / f"{timestamp}_{safe_report_filename(report_title)}.pdf"

    export = records.copy()
    columns = [
        column
        for column in [
            "Calibration_ID",
            "Equipment_Category",
            "Project",
            "Equipment_Type",
            "Make_Model",
            "Serial_No",
            "Certificate_No",
            "Calibration_Date",
            "Next_Due_Date",
            "Days_Until_Due",
            "Alert_Status",
            "Status",
        ]
        if column in export.columns
    ]
    export = export[columns or list(export.columns[:10])].copy()

    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4, landscape
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.lib.units import mm
        from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

        buffer = BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=landscape(A4),
            rightMargin=9 * mm,
            leftMargin=9 * mm,
            topMargin=9 * mm,
            bottomMargin=9 * mm,
            title=report_title,
        )
        styles = getSampleStyleSheet()
        cell_style = styles["BodyText"]
        cell_style.fontSize = 7
        cell_style.leading = 8
        table_rows = [[column.replace("_", " ") for column in export.columns]]
        for _, row in export.iterrows():
            table_rows.append([Paragraph(clean_pdf_value(row.get(column)), cell_style) for column in export.columns])

        story = [
            Paragraph(report_title, styles["Title"]),
            Paragraph(f"Generated on {date.today().strftime('%Y-%m-%d')} for {len(export)} record(s).", styles["Normal"]),
            Spacer(1, 5 * mm),
        ]
        table = Table(table_rows, repeatRows=1)
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#111827")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, -1), 7),
                    ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#d1d5db")),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f9fafb")]),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 3),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 3),
                    ("TOPPADDING", (0, 0), (-1, -1), 3),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ]
            )
        )
        story.append(table)
        doc.build(story)
        pdf_path.write_bytes(buffer.getvalue())
    except ImportError as exc:
        raise RuntimeError("PDF generation needs the reportlab package installed.") from exc

    return pdf_path


def calibration_email_body(report_title, pdf_name):
    return (
        "Dear Team,\n\n"
        f"Please find the {report_title.lower()} ready for review.\n\n"
        f"PDF file: {pdf_name}\n\n"
        "Regards,"
    )


def email_draft_bytes(recipient, cc, subject, body, pdf_path):
    email = EmailMessage()
    email["Subject"] = subject.strip() or "Calibration Log Report"
    email["From"] = formataddr(("QA/QC Dashboard", "no-reply@qaqc.local"))
    if recipient.strip():
        email["To"] = recipient.strip()
    if cc.strip():
        email["Cc"] = cc.strip()
    email.set_content(body)
    email.add_attachment(
        pdf_path.read_bytes(),
        maintype="application",
        subtype="pdf",
        filename=pdf_path.name,
    )
    return email.as_bytes()


def mailto_url(recipient, cc, subject, body):
    query = {"subject": subject, "body": body}
    if cc.strip():
        query["cc"] = cc.strip()
    return f"mailto:{quote(recipient.strip(), safe='@,;')}" + "?" + urlencode(query)


def render_calibration_pdf_email_popup(pdf_path, report_title, key_prefix):
    @st.dialog("Calibration PDF")
    def _dialog():
        if not pdf_path.exists():
            st.error("The generated calibration PDF could not be found.")
            return

        pdf_bytes = pdf_path.read_bytes()
        open_tab, email_tab = st.tabs(["Download/Open PDF", "Open Email App"])

        with open_tab:
            st.download_button(
                "Download/Open PDF",
                data=pdf_bytes,
                file_name=pdf_path.name,
                mime="application/pdf",
                use_container_width=True,
                key=f"{key_prefix}_dialog_download_pdf",
            )
            st.caption("The PDF is saved in outputs/calibration_reports and can be opened from your browser downloads.")

        with email_tab:
            default_cc = ", ".join(registered_account_emails())
            recipient = st.text_input("Recipient", key=f"{key_prefix}_mailto_recipient")
            cc = st.text_input("CC", value=default_cc, key=f"{key_prefix}_mailto_cc")
            subject = st.text_input("Subject", value=report_title, key=f"{key_prefix}_mailto_subject")
            body = st.text_area(
                "Email body",
                value=calibration_email_body(report_title, pdf_path.name),
                height=180,
                key=f"{key_prefix}_mailto_body",
            )
            st.download_button(
                "Download Email Draft with PDF Attached",
                data=email_draft_bytes(recipient, cc, subject, body, pdf_path),
                file_name=f"{pdf_path.stem}_email_draft.eml",
                mime="message/rfc822",
                use_container_width=True,
                key=f"{key_prefix}_download_eml_draft",
            )
            st.caption("Open the downloaded email draft in Outlook or another mail app; the PDF is already attached inside the draft file.")
            st.warning("The direct email-app link below cannot attach files. Use the email draft download above when you want the PDF attached automatically without SMTP.")
            if recipient.strip() or cc.strip():
                st.link_button("Open Email App", mailto_url(recipient, cc, subject, body), use_container_width=True)
            else:
                st.info("Enter a recipient or keep registered account emails in CC to open your email app.")

    _dialog()


def render_calibration_report_actions(records, title, key_prefix):
    st.markdown(f"#### {title}")
    action_cols = st.columns([1, 1, 2])

    with action_cols[0]:
        if st.button("Create PDF", use_container_width=True, key=f"{key_prefix}_create_pdf"):
            try:
                pdf_path = generate_calibration_pdf(records, report_title=f"{title} Calibration Report")
                st.success(f"PDF created: {pdf_path.name}")
                st.download_button(
                    "Download/Open PDF",
                    data=pdf_path.read_bytes(),
                    file_name=pdf_path.name,
                    mime="application/pdf",
                    use_container_width=True,
                    key=f"{key_prefix}_download_pdf",
                )
            except Exception as exc:
                st.error(f"PDF could not be created: {exc}")
    with action_cols[1]:
        if st.button("Create PDF and Email", use_container_width=True, key=f"{key_prefix}_email_pdf"):
            try:
                report_title = f"{title} Calibration Report"
                pdf_path = generate_calibration_pdf(records, report_title=report_title)
                st.session_state[f"{key_prefix}_calibration_pdf_path"] = str(pdf_path)
                render_calibration_pdf_email_popup(pdf_path, report_title, key_prefix)
            except Exception as exc:
                st.error(f"PDF could not be created: {exc}")
    with action_cols[2]:
        st.caption("PDF covers the records shown below. Email opens through your browser using your default email app.")


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
        render_calibration_report_actions(reminders, "Reminder report actions", "due")
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
        render_calibration_report_actions(overdue, "Overdue report actions", "overdue")
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
