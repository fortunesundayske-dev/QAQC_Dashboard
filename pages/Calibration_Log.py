from pathlib import Path
from datetime import date, timedelta
from email.message import EmailMessage
from email.utils import formataddr
from io import BytesIO
import html
import json
import os
import sys
from urllib.parse import quote, urlencode

import pandas as pd
import streamlit as st

import auth
from database.audit_log import record_activity
from database.calibration_records import update_calibration_record
from utils import (
    acknowledge_calibration,
    generate_calibration_pdf as shared_generate_calibration_pdf,
    get_calibration_log,
    get_calibration_reminders,
    get_calibration_summary,
    get_teams_webhook_url,
    inject_global_ui,
    load_master_data,
    mask_teams_webhook_url,
    post_to_teams,
    read_teams_notification_log,
    render_navigation,
    render_page_header,
    render_top_nav,
    send_calibration_teams_alerts,
    snooze_calibration,
    write_teams_config,
)


BASE_DIR = Path(__file__).parents[1]
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))


st.set_page_config(page_title="Calibration Log", layout="wide")
inject_global_ui()


def render_calibration_page_styles():
    st.markdown(
        """
<style>
.calibration-shell {
    margin-top: -0.35rem;
}

.cal-title-row {
    align-items: end;
    display: flex;
    gap: 1rem;
    justify-content: space-between;
    margin: 0.55rem 0 0.7rem;
}

.cal-title h1 {
    color: #e5edf8;
    font-size: 1.75rem;
    font-weight: 850;
    letter-spacing: 0;
    margin: 0;
}

.cal-title p {
    color: #9fb0c7;
    font-size: 0.78rem;
    margin: 0.3rem 0 0;
}

.cal-title__info {
    border: 1px solid rgba(148, 163, 184, 0.42);
    border-radius: 999px;
    color: #9fb0c7;
    display: inline-flex;
    font-size: 0.68rem;
    height: 1rem;
    justify-content: center;
    margin-left: 0.35rem;
    vertical-align: middle;
    width: 1rem;
}

.cal-toolbar {
    align-items: center;
    display: flex;
    gap: 0.55rem;
    justify-content: flex-end;
}

.cal-toolbar--status {
    margin: 0 0 0.75rem;
}

.cal-chip {
    align-items: center;
    background: var(--qaqc-surface-2);
    border: 1px solid var(--qaqc-line);
    border-radius: 7px;
    color: var(--qaqc-text);
    display: inline-flex;
    font-size: 0.72rem;
    font-weight: 750;
    gap: 0.4rem;
    min-height: 2rem;
    padding: 0.45rem 0.7rem;
}

.cal-metric-grid {
    display: grid;
    gap: 0.7rem;
    grid-template-columns: repeat(5, minmax(0, 1fr));
    margin: 0.75rem 0 0.65rem;
}

.cal-metric {
    align-items: center;
    background: var(--qaqc-surface);
    border: 1px solid var(--qaqc-line);
    border-radius: 8px;
    box-shadow: var(--qaqc-shadow);
    color: var(--qaqc-text);
    display: grid;
    gap: 0.78rem;
    grid-template-columns: auto 1fr;
    min-height: 5.25rem;
    padding: 0.85rem;
}

.cal-metric__icon {
    align-items: center;
    background: var(--metric-color, #2563eb);
    border-radius: 999px;
    box-shadow: 0 0 22px color-mix(in srgb, var(--metric-color, #2563eb) 44%, transparent);
    color: #ffffff;
    display: flex;
    font-size: 1rem;
    font-weight: 950;
    height: 2.7rem;
    justify-content: center;
    width: 2.7rem;
}

.cal-metric__label {
    color: var(--qaqc-muted);
    font-size: 0.72rem;
    font-weight: 850;
}

.cal-metric__value {
    color: var(--qaqc-navy);
    font-size: 1.65rem;
    font-weight: 950;
    line-height: 1;
    margin-top: 0.25rem;
}

.cal-metric__sub {
    color: var(--qaqc-muted);
    font-size: 0.66rem;
    margin-top: 0.28rem;
}

.cal-metric--danger .cal-metric__value,
.cal-alert strong {
    color: #ff4d5e;
}

.cal-alert {
    align-items: center;
    background: linear-gradient(90deg, rgba(127, 29, 29, 0.45), rgba(88, 28, 64, 0.28));
    border: 1px solid rgba(248, 113, 113, 0.24);
    border-radius: 7px;
    color: #fecaca;
    display: flex;
    font-size: 0.76rem;
    font-weight: 780;
    gap: 0.55rem;
    justify-content: space-between;
    margin: 0.55rem 0 0.65rem;
    padding: 0.75rem 0.9rem;
}

.cal-alert__text {
    align-items: center;
    display: flex;
    gap: 0.5rem;
}

.cal-action-panel {
    background: var(--qaqc-surface);
    border: 1px solid var(--qaqc-line);
    border-radius: 8px;
    box-shadow: var(--qaqc-shadow);
    color: var(--qaqc-text);
    margin: 0.65rem 0;
    padding: 1rem;
}

.cal-action-panel h3 {
    color: var(--qaqc-navy);
    font-size: 1rem;
    font-weight: 850;
    margin: 0 0 0.72rem;
}

.cal-action-panel p,
.cal-table-caption {
    color: var(--qaqc-muted);
    font-size: 0.72rem;
    margin: 0;
}

.cal-table-toolbar {
    align-items: center;
    background: var(--qaqc-surface-2);
    border: 1px solid var(--qaqc-line);
    border-radius: 8px 8px 0 0;
    display: flex;
    justify-content: space-between;
    margin-top: 0.65rem;
    padding: 0.55rem 0.7rem;
}

.cal-search-label,
.cal-table-tools {
    color: var(--qaqc-muted);
    font-size: 0.72rem;
}

.cal-table-tools {
    display: flex;
    gap: 0.6rem;
}

div[data-testid="stTabs"] div[role="tablist"] {
    border-bottom: 1px solid var(--qaqc-line);
    gap: 0.35rem;
}

div[data-testid="stTabs"] button[role="tab"] {
    border-radius: 7px 7px 0 0;
    color: var(--qaqc-muted);
    font-size: 0.78rem;
    font-weight: 800;
    min-height: 2.25rem;
}

div[data-testid="stTabs"] button[aria-selected="true"] {
    background: color-mix(in srgb, var(--qaqc-blue) 14%, var(--qaqc-surface));
    border-bottom: 2px solid var(--qaqc-blue);
    color: var(--qaqc-blue);
}

div[data-testid="stDataFrame"] {
    border-radius: 0 0 8px 8px !important;
    overflow: hidden;
}

@media (max-width: 1100px) {
    .cal-metric-grid {
        grid-template-columns: repeat(2, minmax(0, 1fr));
    }

    .cal-title-row {
        align-items: flex-start;
        flex-direction: column;
    }
}

@media (max-width: 620px) {
    .cal-metric-grid {
        grid-template-columns: 1fr;
    }

    .cal-toolbar,
    .cal-alert,
    .cal-table-toolbar {
        align-items: flex-start;
        flex-direction: column;
    }
}
</style>
""",
        unsafe_allow_html=True,
    )


render_calibration_page_styles()

if not auth.login():
    st.stop()

render_navigation()
render_top_nav()
getattr(auth, "render_user_sidebar", lambda: None)()

render_page_header(
    "Calibration log",
    "Monitor equipment status, overdue items, upcoming due dates, certificates, and reminder actions.",
    "Materials and equipment",
)

DATA_FILE = BASE_DIR / "data" / "QAQC_Master.xlsx"
CALIBRATION_REPORT_DIR = BASE_DIR / "outputs" / "calibration_reports"
data = load_master_data(DATA_FILE)
log = get_calibration_log(data)
summary = get_calibration_summary(data)


def registered_account_emails():
    try:
        users = auth.all_users()
    except Exception:
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
    return shared_generate_calibration_pdf(records, report_title=report_title, output_dir=CALIBRATION_REPORT_DIR)


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


def render_metric_grid(summary, overdue_count, due_21_count):
    metrics = [
        ("Equipment Records", summary["total"], "Total registered equipment", "▣", "#1d73e8", False),
        ("Active Records", summary["active"], "Currently in use", "⌁", "#22c55e", False),
        ("Overdue", overdue_count, "Require immediate attention", "!", "#ef4444", True),
        ("Due in 21 Days", due_21_count, "Upcoming calibrations", "▦", "#d97706", False),
        ("Snoozed", summary["snoozed"], "Snoozed reminders", "Z", "#7c3aed", False),
    ]
    cards = []
    for label, value, sublabel, icon, color, danger in metrics:
        danger_class = " cal-metric--danger" if danger else ""
        accessible_label = html.escape(f"{label}: {value}", quote=True)
        cards.append(
            f"""
<div class="cal-metric{danger_class}" role="group" aria-label="{accessible_label}" style="--metric-color: {html.escape(color, quote=True)};">
    <div class="cal-metric__icon" aria-hidden="true">{html.escape(icon)}</div>
    <div>
        <div class="cal-metric__label">{html.escape(label)}</div>
        <div class="cal-metric__value">{html.escape(str(value))}</div>
        <div class="cal-metric__sub">{html.escape(sublabel)}</div>
    </div>
</div>
"""
        )
    st.markdown('<div class="cal-metric-grid">' + "".join(cards) + "</div>", unsafe_allow_html=True)


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
                width="stretch",
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
                width="stretch",
                key=f"{key_prefix}_download_eml_draft",
            )
            st.caption("Open the downloaded email draft in Outlook or another mail app; the PDF is already attached inside the draft file.")
            st.warning("The direct email-app link below cannot attach files. Use the email draft download above when you want the PDF attached through your Exchange email application.")
            if recipient.strip() or cc.strip():
                st.link_button("Open Email App", mailto_url(recipient, cc, subject, body), width="stretch")
            else:
                st.info("Enter a recipient or keep registered account emails in CC to open your email app.")

    _dialog()


def render_calibration_report_actions(records, title, key_prefix):
    with st.container():
        st.markdown(
            f"""
<div class="cal-action-panel">
    <h3>{html.escape(title)}</h3>
    <p>PDF covers the records shown below. Email opens through your browser using your default email app.</p>
</div>
""",
            unsafe_allow_html=True,
        )
        action_cols = st.columns([1, 1, 2.2])

        with action_cols[0]:
            if st.button("▣  Create PDF", width="stretch", key=f"{key_prefix}_create_pdf"):
                try:
                    pdf_path = generate_calibration_pdf(records, report_title=f"{title} Calibration Report")
                    st.success(f"PDF created: {pdf_path.name}")
                    st.download_button(
                        "Download/Open PDF",
                        data=pdf_path.read_bytes(),
                        file_name=pdf_path.name,
                        mime="application/pdf",
                        width="stretch",
                        key=f"{key_prefix}_download_pdf",
                    )
                except Exception as exc:
                    st.error(f"PDF could not be created: {exc}")
        with action_cols[1]:
            if st.button("✉  Create PDF and Email", width="stretch", key=f"{key_prefix}_email_pdf"):
                try:
                    report_title = f"{title} Calibration Report"
                    pdf_path = generate_calibration_pdf(records, report_title=report_title)
                    st.session_state[f"{key_prefix}_calibration_pdf_path"] = str(pdf_path)
                    render_calibration_pdf_email_popup(pdf_path, report_title, key_prefix)
                except Exception as exc:
                    st.error(f"PDF could not be created: {exc}")
        with action_cols[2]:
            st.markdown('<p class="cal-table-caption">Review, export, then attach the generated report or email draft.</p>', unsafe_allow_html=True)


def render_alert_banner(overdue_count):
    if overdue_count <= 0:
        st.markdown(
            """
<div class="cal-alert">
    <div class="cal-alert__text"><span>✓</span><span>No overdue calibration items.</span></div>
</div>
""",
            unsafe_allow_html=True,
        )
        return
    st.markdown(
        f"""
<div class="cal-alert">
    <div class="cal-alert__text"><span>▲</span><span><strong>{overdue_count}</strong> equipment item(s) are overdue for calibration.</span></div>
    <span class="cal-chip">View Overdue Equipment ›</span>
</div>
""",
        unsafe_allow_html=True,
    )


def render_table_toolbar(record_count):
    st.markdown(
        f"""
<div class="cal-table-toolbar">
    <div class="cal-search-label">⌕ Search calibration records...</div>
    <div class="cal-table-tools"><span>Columns</span><span>Export</span><span>Show 10</span></div>
</div>
<div class="cal-table-caption">Showing calibration records for the selected view. Total records: {record_count}</div>
""",
        unsafe_allow_html=True,
    )


def filter_calibration_records(records, key_prefix, include_status=True):
    if not isinstance(records, pd.DataFrame) or records.empty:
        return records

    controls = st.columns([1, 1, 2])
    with controls[0]:
        category_values = records.get("Equipment_Category", pd.Series(dtype=str)).dropna().astype(str)
        categories = ["All"] + sorted(category_values.unique().tolist())
        selected_category = st.selectbox("Category", categories, key=f"{key_prefix}_category")
    with controls[1]:
        if include_status:
            status_values = records.get("Alert_Status", pd.Series(dtype=str)).dropna().astype(str)
            statuses = ["All"] + sorted(status_values.unique().tolist())
            selected_status = st.selectbox("Alert status", statuses, key=f"{key_prefix}_status")
        else:
            selected_status = "All"
            st.empty()
    with controls[2]:
        search = st.text_input(
            "Search calibration records",
            placeholder="Equipment, tag, serial, certificate, model...",
            key=f"{key_prefix}_search",
        )

    visible = records.copy()
    if selected_category != "All" and "Equipment_Category" in visible.columns:
        visible = visible[visible["Equipment_Category"].astype(str) == selected_category]
    if selected_status != "All" and "Alert_Status" in visible.columns:
        visible = visible[visible["Alert_Status"].astype(str) == selected_status]
    if search:
        needle = search.strip().lower()
        search_cols = [
            "Equipment_Type",
            "Instrument_Name",
            "Make_Model",
            "Serial_No",
            "Certificate_No",
            "Calibration_ID",
            "Tag_Number",
            "Tag_No",
            "Tag",
            "Instrument_ID",
            "Equipment_ID",
            "Project",
        ]
        mask = pd.Series(False, index=visible.index)
        for column in search_cols:
            if column in visible.columns:
                mask = mask | visible[column].astype(str).str.lower().str.contains(needle, na=False)
        visible = visible[mask]
    return visible


def dataframe_for_display(records):
    if not isinstance(records, pd.DataFrame) or records.empty:
        return records
    display = records.copy()
    for column in display.columns:
        if pd.api.types.is_object_dtype(display[column]):
            display[column] = display[column].fillna("").astype(str)
    return display


def is_admin_user():
    role = getattr(auth, "get_role", lambda: None)() or st.session_state.get("role")
    return str(role or "").strip().lower() == "admin"


def run_startup_teams_notifications(records):
    if records.empty:
        return
    if st.session_state.get("calibration_teams_checked"):
        return
    st.session_state["calibration_teams_checked"] = True
    result = send_calibration_teams_alerts(records)
    st.session_state["calibration_teams_result"] = result


def render_teams_settings(records, is_admin=False):
    webhook_url = get_teams_webhook_url()
    if is_admin and webhook_url:
        st.success(f"Microsoft Teams Incoming Webhook configured: {mask_teams_webhook_url(webhook_url)}")
    elif is_admin:
        st.warning("Microsoft Teams webhook is not configured. Calibration Teams alerts will be skipped, but the app will keep running.")
    elif webhook_url:
        st.success("Microsoft Teams notifications are configured.")
    else:
        st.warning("Microsoft Teams notifications are not configured. Please contact an admin.")

    if is_admin:
        st.info("Power Automate setup: if your workflow has an Attachments check, set the Teams action Adaptive Card field to triggerBody()?['attachments']?[0]?['content']. If you are not using attachments, use triggerBody()?['adaptiveCard'].")
        with st.form("teams_webhook_settings"):
            saved_value = "" if webhook_url and "TEAMS_WEBHOOK_URL" in os.environ else webhook_url
            st.caption("Use the TEAMS_WEBHOOK_URL environment variable, or save a webhook URL to data/teams_config.json.")
            webhook_input = st.text_input(
                "Microsoft Teams Incoming Webhook URL",
                value=saved_value,
                type="password",
                placeholder="https://...",
            )
            save_clicked = st.form_submit_button("Save Teams Webhook", width="stretch")
        if save_clicked:
            write_teams_config(webhook_input)
            st.success("Teams webhook settings saved.")
            st.rerun()
        if st.button("Send Teams Connection Test", disabled=not bool(webhook_url), width="stretch"):
            ok, test_result = post_to_teams(
                webhook_url,
                "**QAQC Calibration Notification Test**\n\n"
                "This is a connection test from the Calibration Log app. "
                "If this card appears in Teams, the saved workflow URL is working.",
            )
            if ok:
                st.success("Power Automate accepted the Teams test card. If the flow still fails, set the Teams action Adaptive Card field to triggerBody()?['attachments']?[0]?['content'] or triggerBody()?['adaptiveCard'].")
            else:
                st.error(f"Teams connection test failed: {test_result}")

    result = st.session_state.get("calibration_teams_result")
    if result:
        if not result.get("configured"):
            st.info("Automatic Teams alert check skipped because no webhook is configured.")
        elif result.get("failed"):
            st.error(f"Teams alert check completed with {result['failed']} failed alert(s). {result.get('sent', 0)} alert(s) were accepted.")
        elif result.get("sent"):
            st.success(f"Teams alert check sent {result['sent']} alert(s).")
        else:
            st.info("Teams alert check completed. No new Teams alerts needed sending.")
        result_rows = result.get("results") or []
        if is_admin and result_rows:
            with st.expander("Teams delivery details", expanded=bool(result.get("failed"))):
                st.dataframe(dataframe_for_display(pd.DataFrame(result_rows)), width="stretch", hide_index=True)

    if st.button("Send Teams Alerts Now", width="stretch"):
        result = send_calibration_teams_alerts(records, force=True)
        st.session_state["calibration_teams_result"] = result
        if not result.get("configured"):
            st.warning("No Teams webhook is configured.")
        elif result.get("failed"):
            st.error(f"{result['failed']} Teams alert(s) failed. {result.get('sent', 0)} alert(s) were accepted. See the notification log below.")
        else:
            st.success(f"{result['sent']} Teams alert(s) sent. {result['skipped']} duplicate or ineligible item(s) skipped.")

    if not is_admin:
        return

    st.markdown("#### Notification log")
    log_entries = read_teams_notification_log()
    if not log_entries:
        st.info("No Teams notifications have been logged yet.")
        return
    log_df = pd.DataFrame(log_entries)
    visible_columns = [
        "sent_at",
        "date_sent",
        "equipment",
        "status",
        "teams_delivery_result",
        "tag_number_or_id",
        "record_id",
    ]
    visible_columns = [column for column in visible_columns if column in log_df.columns]
    st.dataframe(dataframe_for_display(log_df[visible_columns].sort_values("sent_at", ascending=False)), width="stretch", hide_index=True)


CALIBRATION_STATUS_OPTIONS = [
    "Calibrated / Active",
    "Pending Calibration",
    "Under Calibration",
    "Out of Service",
    "Decommissioned / Closed",
]


def _display_value(value):
    return "" if value is None or pd.isna(value) else str(value).strip()


def _calibration_cycle_days(row):
    calibrated_on = pd.to_datetime(row.get("Calibration_Date"), errors="coerce")
    due_on = pd.to_datetime(row.get("Next_Due_Date"), errors="coerce")
    if pd.notna(calibrated_on) and pd.notna(due_on):
        existing_cycle = int((due_on.normalize() - calibrated_on.normalize()).days)
        if 1 <= existing_cycle <= 3650:
            return existing_cycle

    calibration_type = _display_value(row.get("Calibration_Type")).lower()
    if any(term in calibration_type for term in ("biennial", "two year", "2 year", "24 month")):
        return 730
    if any(term in calibration_type for term in ("semiannual", "semi-annual", "six month", "6 month", "biannual")):
        return 182
    if "quarter" in calibration_type or "3 month" in calibration_type:
        return 91
    if "month" in calibration_type:
        return 30
    return 365


def _equipment_option_label(record_id, records):
    selected = records[records["Calibration_ID"].astype(str) == str(record_id)].head(1)
    if selected.empty:
        return str(record_id)
    row = selected.iloc[0]
    equipment = _display_value(row.get("Equipment_Type")) or "Equipment"
    serial = _display_value(row.get("Serial_No"))
    return f"{record_id} · {equipment}" + (f" · Serial {serial}" if serial else "")


def render_admin_calibration_update(records, key_prefix):
    st.markdown("#### Admin equipment update")
    if not isinstance(records, pd.DataFrame) or records.empty:
        st.info("No calibration records are available for this view.")
        return

    record_ids = records["Calibration_ID"].dropna().astype(str).drop_duplicates().tolist()
    selected_id = st.selectbox(
        "Equipment record",
        record_ids,
        format_func=lambda record_id: _equipment_option_label(record_id, records),
        key=f"{key_prefix}_admin_record",
    )
    selected = records[records["Calibration_ID"].astype(str) == str(selected_id)].head(1)
    if selected.empty:
        st.error("The selected calibration record is no longer available.")
        return
    row = selected.iloc[0]
    current_status = _display_value(row.get("Status"))
    current_calibration_date = pd.to_datetime(row.get("Calibration_Date"), errors="coerce")
    current_due_date = pd.to_datetime(row.get("Next_Due_Date"), errors="coerce")
    st.caption(
        f"Current status: {current_status or 'Not set'} · "
        f"Calibration date: {current_calibration_date:%Y-%m-%d} · "
        f"Due date: {current_due_date:%Y-%m-%d}"
    )
    st.caption(
        "Saving updates the Calibration Log in the Cloudinary master workbook and the local Excel copy. "
        "Use Calibrated / Active after successful calibration so future due-date reminders remain enabled."
    )

    status_options = list(CALIBRATION_STATUS_OPTIONS)
    if current_status and current_status not in status_options:
        status_options.insert(0, current_status)
    status_index = status_options.index(current_status) if current_status in status_options else 0
    calibrated_default = date.today()
    due_default = calibrated_default + timedelta(days=_calibration_cycle_days(row))

    with st.form(f"{key_prefix}_admin_update_form"):
        date_columns = st.columns(3)
        with date_columns[0]:
            new_status = st.selectbox("New equipment status", status_options, index=status_index)
        with date_columns[1]:
            new_calibration_date = st.date_input("Calibration completed on", value=calibrated_default)
        with date_columns[2]:
            new_due_date = st.date_input("Next calibration due", value=due_default)
        certificate_no = st.text_input(
            "Calibration certificate number",
            value=_display_value(row.get("Certificate_No")),
        )
        notes = st.text_area(
            "Update notes (optional)",
            max_chars=500,
            placeholder="Calibration provider, work order, certificate notes, or other record details",
        )
        submitted = st.form_submit_button(
            "Save calibration update",
            type="primary",
            width="stretch",
        )

    if not submitted:
        return

    actor = auth.current_user() or {}
    try:
        updated, storage = update_calibration_record(
            record_id=selected_id,
            calibration_date=new_calibration_date,
            next_due_date=new_due_date,
            status=new_status,
            username=actor.get("username", "admin"),
            certificate_no=certificate_no,
            notes=notes,
        )
        record_activity(
            "update_calibration_record",
            category="quality_record",
            page="Calibration Log",
            target=selected_id,
            details={
                "previous": updated["previous"],
                "status": updated["status"],
                "calibration_date": updated["calibration_date"],
                "next_due_date": updated["next_due_date"],
                "certificate_no": updated["certificate_no"],
                "notes_added": bool(notes.strip()),
                "storage": storage,
            },
            actor=actor,
        )
        st.session_state["calibration_update_success"] = (
            f"Updated {selected_id}: {updated['status']}, calibrated {updated['calibration_date']}, "
            f"next due {updated['next_due_date']} ({storage})."
        )
        st.cache_data.clear()
        st.rerun()
    except Exception as exc:
        record_activity(
            "update_calibration_record",
            category="quality_record",
            page="Calibration Log",
            target=selected_id,
            status="failed",
            details={"error": str(exc)},
            actor=actor,
        )
        st.error(f"The calibration record could not be updated: {exc}")


if log.empty:
    st.warning("No calibration records are available in the master workbook.")
    st.stop()

reminders = get_calibration_reminders(data)
overdue = reminders[reminders["Days_Until_Due"] < 0]
due_21 = reminders[reminders["Days_Until_Due"] == 21]
due_soon = reminders[(reminders["Days_Until_Due"] >= 0) & (reminders["Days_Until_Due"] < 21)]
is_admin = is_admin_user()
run_startup_teams_notifications(reminders)

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

st.markdown(
    f"""
<div class="cal-toolbar cal-toolbar--status" role="status">
    <span class="cal-chip">Live workbook</span>
    <span class="cal-chip">Reviewed {date.today():%d %b %Y}</span>
</div>
""",
    unsafe_allow_html=True,
)

render_metric_grid(summary, len(overdue), len(due_21))

calibration_update_success = st.session_state.pop("calibration_update_success", None)
if calibration_update_success:
    st.success(calibration_update_success)

if is_admin and not reminders.empty and not get_teams_webhook_url():
    st.warning("Microsoft Teams webhook is not configured. Teams calibration alerts are skipped until a webhook URL is saved in Teams Notifications.")

tab_labels = ["Reminder Actions", f"Overdue Equipment ({len(overdue)})", "All Calibration Records", "Teams Notifications"]

tabs = st.tabs(tab_labels)
tab_alerts, tab_overdue, tab_all, tab_notifications = tabs

with tab_alerts:
    if reminders.empty:
        st.success("No active calibration reminders today.")
    else:
        render_alert_banner(len(overdue))
        filtered_reminders = filter_calibration_records(reminders, "due")
        render_calibration_report_actions(filtered_reminders, "Reminder report actions", "due")
        st.markdown("#### Active reminders")
        render_table_toolbar(len(filtered_reminders))
        st.dataframe(dataframe_for_display(filtered_reminders[display_cols]), width="stretch", hide_index=True)

        st.markdown("#### Acknowledge or snooze")
        if filtered_reminders.empty:
            st.info("No reminder records match the current filters.")
        else:
            action_cols = st.columns([1.4, 1, 1, 1.3])
            with action_cols[0]:
                selected_id = st.selectbox(
                    "Equipment record",
                    filtered_reminders["Calibration_ID"].astype(str).tolist(),
                    key="calibration_action_record",
                )
            with action_cols[1]:
                snooze_days = st.number_input("Snooze days", min_value=1, max_value=30, value=1, step=1)
            with action_cols[2]:
                st.write("")
                st.write("")
                if st.button("Acknowledge", width="stretch"):
                    acknowledge_calibration(selected_id)
                    st.success("Reminder acknowledged.")
                    st.rerun()
            with action_cols[3]:
                st.write("")
                st.write("")
                if st.button("Snooze", width="stretch"):
                    snooze_calibration(selected_id, snooze_days)
                    st.success(f"Reminder snoozed for {snooze_days} day(s).")
                    st.rerun()

            selected_row = filtered_reminders[filtered_reminders["Calibration_ID"].astype(str) == str(selected_id)].head(1)
            if not selected_row.empty:
                st.markdown("#### Selected equipment")
                st.dataframe(dataframe_for_display(selected_row[display_cols]), width="stretch", hide_index=True)

with tab_overdue:
    if overdue.empty:
        render_alert_banner(0)
    else:
        render_alert_banner(len(overdue))
        filtered_overdue = filter_calibration_records(overdue, "overdue", include_status=False)
        render_calibration_report_actions(filtered_overdue, "Overdue report actions", "overdue")
        render_table_toolbar(len(filtered_overdue))
        st.dataframe(dataframe_for_display(filtered_overdue[display_cols]), width="stretch", hide_index=True)
        if is_admin:
            render_admin_calibration_update(filtered_overdue, "overdue")

with tab_all:
    visible = filter_calibration_records(log, "all")

    render_table_toolbar(len(visible))
    st.dataframe(dataframe_for_display(visible[display_cols]), width="stretch", hide_index=True, height=520)
    if is_admin:
        render_admin_calibration_update(visible, "all")
    else:
        st.caption("Calibration record changes are restricted to administrators.")

with tab_notifications:
    render_teams_settings(reminders, is_admin=is_admin)

st.markdown("</div>", unsafe_allow_html=True)
