import json
import os
import smtplib
import subprocess
from datetime import date, timedelta
from email.message import EmailMessage
from email.utils import formataddr
from pathlib import Path
from urllib import request

import pandas as pd


BASE_DIR = Path(__file__).resolve().parents[1]
EXCEL_FILE = BASE_DIR / "data" / "QAQC_Master.xlsx"
ACK_FILE = BASE_DIR / "data" / "calibration_acknowledgements.json"
USERS_FILE = BASE_DIR / "data" / "users.json"
COMPLETE_TERMS = ("complete", "completed", "closed", "recalibrated", "renewed")
MANDATORY_RECIPIENTS = [
    "allison.okosun@evomeclimited.com",
    "lawrence.esievo@evomeclimited.com",
    "PMC.QAQC@evomeclimited.com",
    "theophilus.o@evomeclimited.com",
]


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
    recipients = list(MANDATORY_RECIPIENTS)
    if not USERS_FILE.exists():
        return sorted(set(recipients))
    try:
        users = json.loads(USERS_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return sorted(set(recipients))
    for user in users.values():
        email = str(user.get("email", "")).strip()
        if email and user.get("status") == "approved":
            recipients.append(email)
    return sorted(set(recipients))


def send_email(message):
    configured = os.getenv("CALIBRATION_EMAIL_TO", "")
    recipients = [item.strip() for item in configured.split(",") if item.strip()]
    if not recipients:
        recipients = registered_email_recipients()
    host = os.getenv("SMTP_HOST") or os.getenv("QAQC_SMTP_HOST")
    if not recipients or not host:
        return

    email = EmailMessage()
    email["Subject"] = "Calibration reminder - equipment due for calibration"
    smtp_user = os.getenv("SMTP_USER") or os.getenv("QAQC_SMTP_USER")
    smtp_password = os.getenv("SMTP_PASSWORD") or os.getenv("QAQC_SMTP_PASSWORD")
    sender_address = os.getenv("SMTP_FROM") or os.getenv("QAQC_SMTP_FROM") or smtp_user or "calibration-reminder@localhost"
    sender_name = os.getenv("CALIBRATION_EMAIL_FROM_NAME", "KPKAUE Fortune QA")
    email["From"] = formataddr((sender_name, sender_address))
    email["To"] = ", ".join(recipients)
    email.set_content(message)

    port = int(os.getenv("SMTP_PORT") or os.getenv("QAQC_SMTP_PORT") or "587")
    use_ssl = os.getenv("SMTP_SSL") == "1" or os.getenv("QAQC_SMTP_SSL") == "1" or port == 465
    smtp_class = smtplib.SMTP_SSL if use_ssl else smtplib.SMTP
    with smtp_class(host, port, timeout=20) as smtp:
        if not use_ssl and os.getenv("SMTP_STARTTLS", "1") == "1":
            smtp.starttls()
        if smtp_user and smtp_password:
            smtp.login(smtp_user, smtp_password)
        smtp.send_message(email)


def send_teams(message):
    webhook = os.getenv("CALIBRATION_TEAMS_WEBHOOK")
    if not webhook:
        return
    payload = json.dumps({"text": message}).encode("utf-8")
    req = request.Request(webhook, data=payload, headers={"Content-Type": "application/json"})
    with request.urlopen(req, timeout=20):
        pass


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
    show_desktop_prompt(popup_message)
    send_email(email_message)
    send_teams(popup_message)
    mark_notified(records)


if __name__ == "__main__":
    main()
