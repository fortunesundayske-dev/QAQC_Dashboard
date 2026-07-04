from pathlib import Path
import json
import os
import sys

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
from scripts import calibration_reminder


st.set_page_config(page_title="Calibration Log", layout="wide")
inject_global_ui()

if not auth.login():
    st.stop()

render_navigation()
render_top_nav()
getattr(auth, "render_user_sidebar", lambda: None)()

DATA_FILE = BASE_DIR / "data" / "QAQC_Master.xlsx"
USERS_FILE = BASE_DIR / "data" / "users.json"
data = load_master_data(DATA_FILE)
log = get_calibration_log(data)
summary = get_calibration_summary(data)


def approved_notification_emails():
    try:
        users = json.loads(USERS_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    recipients = [
        str(user.get("email", "")).strip()
        for user in users.values()
        if user.get("status") == "approved" and str(user.get("email", "")).strip()
    ]
    return sorted(set(recipients))


def smtp_configured():
    return bool(calibration_reminder.smtp_setting("SMTP_HOST"))


def render_calibration_report_actions(records, title, key_prefix):
    st.markdown(f"#### {title}")
    action_cols = st.columns([1, 1, 2])
    try:
        pdf_bytes = calibration_reminder.create_due_records_pdf(records)
    except Exception as exc:
        st.error(f"PDF could not be created: {exc}")
        return

    with action_cols[0]:
        st.download_button(
            "Create PDF",
            data=pdf_bytes,
            file_name=f"{key_prefix}_calibration_report.pdf",
            mime="application/pdf",
            use_container_width=True,
            key=f"{key_prefix}_download_pdf",
        )
    with action_cols[1]:
        if st.button("Create PDF and Email", use_container_width=True, key=f"{key_prefix}_email_pdf"):
            if not email_recipients:
                st.error("No approved user email is available.")
            else:
                try:
                    message = calibration_reminder.message_from_records(records, limit=None)
                    attachment_path, body_path = calibration_reminder.open_classic_outlook_draft(
                        message,
                        email_recipients,
                        attachment_pdf=pdf_bytes,
                        attachment_name=f"{key_prefix}_calibration_report.pdf",
                    )
                    st.success("Outlook email draft opened with the PDF attached. Review it in Outlook and click Send.")
                    st.caption(f"PDF saved at: {attachment_path}")
                    st.caption(f"Email body saved at: {body_path}")
                except Exception as exc:
                    st.error(f"Outlook draft could not be opened: {exc}")
    with action_cols[2]:
        st.caption("PDF covers the records shown below. Email opens in classic Outlook with the PDF attached.")


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

email_recipients = approved_notification_emails()
smtp_ready = smtp_configured()

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

tab_alerts, tab_overdue, tab_all, tab_email = st.tabs(["Reminder Actions", "Overdue Equipment", "All Calibration Records", "Email Setup"])

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

with tab_email:
    st.markdown("#### Calibration email setup")
    st.caption("Settings are saved on this PC for the scheduled reminder and trial email.")
    st.info(
        "For Outlook.com/Hotmail, use `smtp-mail.outlook.com`, port `587`, STARTTLS enabled. "
        "For Microsoft 365 work mail, use `smtp.office365.com`, port `587`, STARTTLS enabled. "
        "Use the full sender email address as the username. If MFA is on, use an app password."
    )
    existing = calibration_reminder.read_smtp_config()

    with st.form("smtp_setup_form"):
        col_a, col_b = st.columns(2)
        with col_a:
            smtp_host = st.text_input("SMTP host", value=existing.get("SMTP_HOST", "smtp-mail.outlook.com"))
            smtp_port = st.text_input("SMTP port", value=str(existing.get("SMTP_PORT", "587")))
            smtp_user = st.text_input("Sender mailbox / username", value=existing.get("SMTP_USER", ""))
            smtp_from = st.text_input("Sender email address", value=existing.get("SMTP_FROM", existing.get("SMTP_USER", "")))
        with col_b:
            from_name = st.text_input("Sender display name", value=existing.get("CALIBRATION_EMAIL_FROM_NAME", "KPKAUE Fortune QA"))
            smtp_password = st.text_input("SMTP password or app password", type="password", value=existing.get("SMTP_PASSWORD", ""))
            starttls = st.checkbox("Use STARTTLS", value=existing.get("SMTP_STARTTLS", "1") == "1")
            ssl = st.checkbox("Use SSL", value=existing.get("SMTP_SSL", "0") == "1")

        save_col, test_col = st.columns(2)
        save_clicked = save_col.form_submit_button("Save SMTP settings", use_container_width=True)
        test_clicked = test_col.form_submit_button("Save and send trial email", use_container_width=True)

    if save_clicked or test_clicked:
        port_value = str(smtp_port).strip()
        if not smtp_host or not smtp_port or not smtp_user or not smtp_password:
            st.error("SMTP host, port, sender mailbox, and password are required.")
        elif ssl and port_value != "465":
            st.error("SSL is only for port 465. For Outlook port 587, uncheck SSL and keep STARTTLS checked.")
        elif starttls and ssl:
            st.error("Choose either STARTTLS or SSL, not both. For Outlook port 587, use STARTTLS only.")
        else:
            config = {
                "SMTP_HOST": smtp_host.strip(),
                "SMTP_PORT": port_value,
                "SMTP_USER": smtp_user.strip(),
                "SMTP_PASSWORD": smtp_password,
                "SMTP_FROM": (smtp_from or smtp_user).strip(),
                "SMTP_STARTTLS": "1" if starttls else "0",
                "SMTP_SSL": "1" if ssl else "0",
                "CALIBRATION_EMAIL_FROM_NAME": from_name.strip() or "KPKAUE Fortune QA",
            }
            calibration_reminder.write_smtp_config(config)
            st.success("SMTP settings saved.")

            if test_clicked:
                try:
                    records = calibration_reminder.load_due_records()
                    sample = records.head(10) if not records.empty else records
                    message = calibration_reminder.message_from_records(sample, limit=None)
                    pdf_report = calibration_reminder.create_due_records_pdf(sample) if not sample.empty else None
                    calibration_reminder.send_email(message, attachment_pdf=pdf_report)
                    st.success(f"Trial email sent to: {', '.join(calibration_reminder.registered_email_recipients())}")
                except Exception as exc:
                    st.error(f"Trial email failed: {exc}")

    st.markdown("#### Email loop")
    st.write(", ".join(approved_notification_emails()))
