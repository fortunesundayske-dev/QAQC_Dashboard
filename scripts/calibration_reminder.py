import json
import os
import smtplib
import subprocess
from datetime import date, timedelta
from email.message import EmailMessage
from email.utils import formataddr
from io import BytesIO
from pathlib import Path

import pandas as pd


BASE_DIR = Path(__file__).resolve().parents[1]
EXCEL_FILE = BASE_DIR / "data" / "QAQC_Master.xlsx"
ACK_FILE = BASE_DIR / "data" / "calibration_acknowledgements.json"
SMTP_CONFIG_FILE = BASE_DIR / "data" / "smtp_config.json"
USERS_FILE = BASE_DIR / "data" / "users.json"
COMPLETE_TERMS = ("complete", "completed", "closed", "recalibrated", "renewed")


def read_acknowledgements():
    if not ACK_FILE.exists():
        return {}
    try:
        return json.loads(ACK_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def write_acknowledgements(payload):
    ACK_FILE.parent.mkdir(parents=True, exist_ok=True)
    ACK_FILE.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def read_smtp_config():
    if not SMTP_CONFIG_FILE.exists():
        return {}
    try:
        config = json.loads(SMTP_CONFIG_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return config if isinstance(config, dict) else {}


def write_smtp_config(config):
    SMTP_CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    SMTP_CONFIG_FILE.write_text(json.dumps(config, indent=2, sort_keys=True), encoding="utf-8")


def smtp_setting(name, fallback=None):
    if os.getenv(name):
        return os.getenv(name)
    aliases = {
        "SMTP_HOST": "QAQC_SMTP_HOST",
        "SMTP_PORT": "QAQC_SMTP_PORT",
        "SMTP_USER": "QAQC_SMTP_USER",
        "SMTP_PASSWORD": "QAQC_SMTP_PASSWORD",
        "SMTP_FROM": "QAQC_SMTP_FROM",
        "SMTP_SSL": "QAQC_SMTP_SSL",
        "SMTP_STARTTLS": "QAQC_SMTP_STARTTLS",
    }
    alias = aliases.get(name)
    if alias and os.getenv(alias):
        return os.getenv(alias)
    config = read_smtp_config()
    return config.get(name, fallback)


def is_completed(value):
    status = str(value or "").lower()
    return any(term in status for term in COMPLETE_TERMS)


def clean_text(value):
    if pd.isna(value):
        return ""
    return str(value).strip()


def load_due_records():
    if not EXCEL_FILE.exists():
        return pd.DataFrame()

    df = pd.read_excel(EXCEL_FILE, sheet_name="Calibration Log")
    if df.empty or "Next_Due_Date" not in df.columns:
        return pd.DataFrame()

    today = pd.Timestamp(date.today())
    df["Next_Due_Date"] = pd.to_datetime(df["Next_Due_Date"], errors="coerce")
    df["Days_Until_Due"] = (df["Next_Due_Date"].dt.normalize() - today).dt.days
    df["Status"] = df.get("Status", "")
    df = df[df["Next_Due_Date"].notna() & (~df["Status"].apply(is_completed)) & (df["Days_Until_Due"] <= 21)].copy()

    acknowledgements = read_acknowledgements()
    active_rows = []
    for _, row in df.iterrows():
        record_id = str(row.get("Calibration_ID", "")).strip()
        saved = acknowledgements.get(record_id, {})
        snoozed_until = pd.to_datetime(saved.get("snoozed_until"), errors="coerce")
        if pd.notna(snoozed_until) and snoozed_until.date() >= date.today():
            continue
        if saved.get("last_notified_on") == date.today().isoformat():
            continue
        active_rows.append(row)

    return pd.DataFrame(active_rows)


def message_from_records(records, limit=8):
    if records is None or records.empty:
        return "No active calibration reminders today."
    overdue = int((records["Days_Until_Due"] < 0).sum())
    due_21 = int((records["Days_Until_Due"] == 21).sum())
    due_soon = int(((records["Days_Until_Due"] >= 0) & (records["Days_Until_Due"] < 21)).sum())
    lines = [
        f"{len(records)} calibration reminder(s)",
        f"Overdue: {overdue}",
        f"Due exactly 21 days from today: {due_21}",
        f"Due within 21 days: {due_soon}",
        "",
    ]
    visible_records = records if limit is None else records.head(limit)
    for _, row in visible_records.iterrows():
        due_date = pd.Timestamp(row["Next_Due_Date"]).strftime("%Y-%m-%d")
        project = clean_text(row.get("Project", ""))
        category = clean_text(row.get("Equipment_Category", ""))
        equipment = clean_text(row.get("Equipment_Type", "Equipment")) or "Equipment"
        model = clean_text(row.get("Make_Model", ""))
        serial = clean_text(row.get("Serial_No", ""))
        cert = clean_text(row.get("Certificate_No", ""))
        days = int(row.get("Days_Until_Due", 0))
        status = "Overdue" if days < 0 else f"Due in {days} day(s)"
        details = [
            f"Equipment: {equipment}",
            f"Serial: {serial or 'N/A'}",
            f"Due: {due_date}",
            f"Status: {status}",
        ]
        if project:
            details.append(f"Project: {project}")
        if category:
            details.append(f"Category: {category}")
        if model:
            details.append(f"Model: {model}")
        if cert:
            details.append(f"Certificate: {cert}")
        lines.append("- " + " | ".join(details))
    if limit is not None and len(records) > limit:
        lines.append(f"- plus {len(records) - limit} more")
    return "\n".join(lines)


def create_due_records_pdf(records):
    if records is None or records.empty:
        raise RuntimeError("No due calibration records are available for PDF export.")
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4, landscape
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.lib.units import mm
        from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
    except ImportError as exc:
        raise RuntimeError("PDF export requires reportlab. Install project requirements and try again.") from exc

    export = records.copy()
    if "Days_Until_Due" not in export.columns and "Next_Due_Date" in export.columns:
        today = pd.Timestamp(date.today())
        export["Next_Due_Date"] = pd.to_datetime(export["Next_Due_Date"], errors="coerce")
        export["Days_Until_Due"] = (export["Next_Due_Date"].dt.normalize() - today).dt.days

    def due_status(days):
        try:
            days = int(days)
        except (TypeError, ValueError):
            return ""
        if days < 0:
            return f"Overdue by {abs(days)} day(s)"
        if days == 0:
            return "Due today"
        return f"Due in {days} day(s)"

    def date_text(value):
        timestamp = pd.to_datetime(value, errors="coerce")
        return "" if pd.isna(timestamp) else timestamp.strftime("%Y-%m-%d")

    report_rows = [
        [
            "Calibration ID",
            "Project",
            "Equipment",
            "Model",
            "Serial No",
            "Certificate No",
            "Next Due",
            "Status",
        ]
    ]
    for _, row in export.sort_values(["Days_Until_Due", "Equipment_Type"], na_position="last").iterrows():
        report_rows.append(
            [
                clean_text(row.get("Calibration_ID", "")),
                clean_text(row.get("Project", "")),
                clean_text(row.get("Equipment_Type", "")),
                clean_text(row.get("Make_Model", "")),
                clean_text(row.get("Serial_No", "")),
                clean_text(row.get("Certificate_No", "")),
                date_text(row.get("Next_Due_Date")),
                due_status(row.get("Days_Until_Due")),
            ]
        )

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        rightMargin=10 * mm,
        leftMargin=10 * mm,
        topMargin=10 * mm,
        bottomMargin=10 * mm,
        title="Calibration Due Report",
    )
    styles = getSampleStyleSheet()
    story = [
        Paragraph("Calibration Due Report", styles["Title"]),
        Paragraph(f"Generated on {date.today().strftime('%Y-%m-%d')} for {len(export)} due record(s).", styles["Normal"]),
        Spacer(1, 6 * mm),
    ]
    cell_style = styles["BodyText"]
    cell_style.fontSize = 7
    cell_style.leading = 8
    wrapped_rows = [report_rows[0]]
    for row in report_rows[1:]:
        wrapped_rows.append([Paragraph(str(value), cell_style) for value in row])
    table = Table(wrapped_rows, repeatRows=1, colWidths=[27 * mm, 38 * mm, 42 * mm, 38 * mm, 30 * mm, 34 * mm, 24 * mm, 32 * mm])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1f2937")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 7),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#d1d5db")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f9fafb")]),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    story.append(table)
    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()


def show_desktop_prompt(message):
    script = (
        "$ws = New-Object -ComObject WScript.Shell; "
        "$ws.Popup($args[0], 20, 'Calibration Reminder', 0x40) | Out-Null"
    )
    subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script, message],
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def registered_email_recipients():
    if not USERS_FILE.exists():
        return []
    try:
        users = json.loads(USERS_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    recipients = []
    for user in users.values():
        email = str(user.get("email", "")).strip()
        if email and user.get("status") == "approved":
            recipients.append(email)
    return sorted(set(recipients))


def send_email(message, attachment_pdf=None, attachment_name="calibration_due_report.pdf"):
    recipients = registered_email_recipients()
    host = smtp_setting("SMTP_HOST")
    if not recipients or not host:
        missing = []
        if not recipients:
            missing.append("email recipients")
        if not host:
            missing.append("SMTP host")
        raise RuntimeError("Cannot send calibration email. Missing " + " and ".join(missing) + ".")

    email = EmailMessage()
    email["Subject"] = "Calibration reminder - equipment due for calibration"
    smtp_user = smtp_setting("SMTP_USER")
    smtp_password = smtp_setting("SMTP_PASSWORD")
    sender_address = smtp_setting("SMTP_FROM") or smtp_user or "calibration-reminder@localhost"
    sender_name = smtp_setting("CALIBRATION_EMAIL_FROM_NAME", "KPKAUE Fortune QA")
    email["From"] = formataddr((sender_name, sender_address))
    email["To"] = ", ".join(recipients)
    email.set_content(message)
    if attachment_pdf:
        email.add_attachment(
            attachment_pdf,
            maintype="application",
            subtype="pdf",
            filename=attachment_name,
        )

    port = int(smtp_setting("SMTP_PORT", "587"))
    use_ssl = smtp_setting("SMTP_SSL", "0") == "1" or port == 465
    if use_ssl and port != 465:
        raise RuntimeError("SSL is only for port 465. For Outlook port 587, uncheck SSL and check STARTTLS.")
    smtp_class = smtplib.SMTP_SSL if use_ssl else smtplib.SMTP
    with smtp_class(host, port, timeout=20) as smtp:
        if not use_ssl and smtp_setting("SMTP_STARTTLS", "1") == "1":
            smtp.starttls()
        if smtp_user and smtp_password:
            try:
                smtp.login(smtp_user, smtp_password)
            except smtplib.SMTPAuthenticationError as exc:
                raise RuntimeError(
                    "Outlook rejected the SMTP login. Check the full sender email address, password/app password, "
                    "and confirm SMTP sending is enabled for that mailbox."
                ) from exc
        smtp.send_message(email)


def mark_notified(records):
    payload = read_acknowledgements()
    today = date.today().isoformat()
    for record_id in records["Calibration_ID"].astype(str):
        payload.setdefault(record_id, {})["last_notified_on"] = today
    write_acknowledgements(payload)


def main():
    records = load_due_records()
    if records.empty:
        return
    popup_message = message_from_records(records, limit=8)
    email_message = message_from_records(records, limit=None)
    pdf_report = create_due_records_pdf(records)
    show_desktop_prompt(popup_message)
    send_email(email_message, attachment_pdf=pdf_report)
    mark_notified(records)


if __name__ == "__main__":
    main()
