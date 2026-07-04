import ctypes
import json
import os
import smtplib
import tempfile
import time
from datetime import date, timedelta
from email.message import EmailMessage
from email.utils import formataddr
from io import BytesIO
from pathlib import Path
from urllib.parse import quote

import pandas as pd


BASE_DIR = Path(__file__).resolve().parents[1]
EXCEL_FILE = BASE_DIR / "data" / "QAQC_Master.xlsx"
ACK_FILE = BASE_DIR / "data" / "calibration_acknowledgements.json"
SMTP_CONFIG_FILE = BASE_DIR / "data" / "smtp_config.json"
USERS_FILE = BASE_DIR / "data" / "users.json"
CLASSIC_OUTLOOK_EXE = Path(r"C:\Program Files\Microsoft Office\root\Office16\OUTLOOK.EXE")
CLASSIC_OUTLOOK_SHORTCUT = Path.home() / "AppData" / "Roaming" / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Outlook.lnk"
COMPLETE_TERMS = ("complete", "completed", "closed", "recalibrated", "renewed")


def classic_outlook_launcher():
    candidates = [
        CLASSIC_OUTLOOK_EXE,
        Path(r"C:\Program Files (x86)\Microsoft Office\root\Office16\OUTLOOK.EXE"),
        CLASSIC_OUTLOOK_SHORTCUT,
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def open_file_with_default_app(path):
    path = Path(path)
    try:
        result = ctypes.windll.shell32.ShellExecuteW(None, "openas", str(path), None, None, 1)
    except (AttributeError, OSError):
        result = 0
    if result and result > 32:
        return

    if not hasattr(os, "startfile"):
        raise RuntimeError("Windows app chooser is not available.")
    os.startfile(str(path))


def shell_execute_file(path, arguments=""):
    try:
        result = ctypes.windll.shell32.ShellExecuteW(None, "open", str(path), arguments, None, 1)
    except (AttributeError, OSError) as exc:
        raise OSError(f"Windows launcher is not available: {exc}") from exc
    if result <= 32:
        raise OSError(f"Windows launcher returned error code {result}.")


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
    config = None
    for encoding in ("utf-8-sig", "utf-16"):
        try:
            config = json.loads(SMTP_CONFIG_FILE.read_text(encoding=encoding))
            break
        except UnicodeError:
            continue
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
        return create_due_records_pdf_fallback(records)

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


def create_due_records_pdf_fallback(records):
    export = records.copy()
    if "Days_Until_Due" not in export.columns and "Next_Due_Date" in export.columns:
        today = pd.Timestamp(date.today())
        export["Next_Due_Date"] = pd.to_datetime(export["Next_Due_Date"], errors="coerce")
        export["Days_Until_Due"] = (export["Next_Due_Date"].dt.normalize() - today).dt.days

    def clean_pdf_text(value):
        text = clean_text(value).replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        return text.encode("latin-1", errors="replace").decode("latin-1")

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

    rows = [
        "Calibration Due Report",
        f"Generated on {date.today().strftime('%Y-%m-%d')} for {len(export)} due record(s).",
        "",
    ]
    for _, row in export.sort_values(["Days_Until_Due", "Equipment_Type"], na_position="last").iterrows():
        rows.append(
            " | ".join(
                [
                    clean_text(row.get("Calibration_ID", "")),
                    clean_text(row.get("Project", "")),
                    clean_text(row.get("Equipment_Type", "")),
                    clean_text(row.get("Serial_No", "")),
                    date_text(row.get("Next_Due_Date")),
                    due_status(row.get("Days_Until_Due")),
                ]
            )
        )

    page_width = 842
    page_height = 595
    margin_left = 36
    top = 550
    line_height = 13
    max_chars = 132
    pages = []
    current = []
    y = top
    for row in rows:
        chunks = [row[i : i + max_chars] for i in range(0, len(row), max_chars)] or [""]
        for chunk in chunks:
            if y < 40:
                pages.append(current)
                current = []
                y = top
            current.append((y, chunk))
            y -= line_height
    if current:
        pages.append(current)

    objects = []
    page_ids = []
    font_id = 3
    pages_id = 1
    catalog_id = 2
    next_id = 4
    for page in pages:
        content_lines = ["BT", "/F1 9 Tf", f"{margin_left} {top} Td", "12 TL"]
        previous_y = top
        for y_value, text in page:
            content_lines.append(f"0 -{previous_y - y_value} Td")
            content_lines.append(f"({clean_pdf_text(text)}) Tj")
            previous_y = y_value
        content_lines.append("ET")
        stream = "\n".join(content_lines).encode("latin-1", errors="replace")
        content_id = next_id
        next_id += 1
        page_id = next_id
        next_id += 1
        objects.append((content_id, b"<< /Length " + str(len(stream)).encode("ascii") + b" >>\nstream\n" + stream + b"\nendstream"))
        objects.append(
            (
                page_id,
                f"<< /Type /Page /Parent {pages_id} 0 R /MediaBox [0 0 {page_width} {page_height}] "
                f"/Resources << /Font << /F1 {font_id} 0 R >> >> /Contents {content_id} 0 R >>".encode("ascii"),
            )
        )
        page_ids.append(page_id)

    kids = " ".join(f"{page_id} 0 R" for page_id in page_ids)
    base_objects = [
        (pages_id, f"<< /Type /Pages /Kids [{kids}] /Count {len(page_ids)} >>".encode("ascii")),
        (catalog_id, f"<< /Type /Catalog /Pages {pages_id} 0 R >>".encode("ascii")),
        (font_id, b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"),
    ]
    all_objects = sorted(base_objects + objects, key=lambda item: item[0])

    output = BytesIO()
    output.write(b"%PDF-1.4\n")
    offsets = {0: 0}
    for obj_id, body in all_objects:
        offsets[obj_id] = output.tell()
        output.write(f"{obj_id} 0 obj\n".encode("ascii"))
        output.write(body)
        output.write(b"\nendobj\n")
    xref_position = output.tell()
    max_id = max(offsets)
    output.write(f"xref\n0 {max_id + 1}\n".encode("ascii"))
    output.write(b"0000000000 65535 f \n")
    for obj_id in range(1, max_id + 1):
        output.write(f"{offsets[obj_id]:010d} 00000 n \n".encode("ascii"))
    output.write(
        f"trailer\n<< /Size {max_id + 1} /Root {catalog_id} 0 R >>\nstartxref\n{xref_position}\n%%EOF\n".encode("ascii")
    )
    return output.getvalue()


def show_desktop_prompt(message):
    try:
        ctypes.windll.user32.MessageBoxW(None, str(message), "Calibration Reminder", 0x40)
    except (AttributeError, OSError):
        return


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


def send_email_via_classic_outlook(message, recipients, attachment_pdf=None, attachment_name="calibration_due_report.pdf"):
    if not recipients:
        raise RuntimeError("Cannot send Outlook email. Missing email recipients.")
    outlook_launcher = classic_outlook_launcher()
    if not outlook_launcher:
        raise RuntimeError(
            "Classic Outlook was not found. Expected Outlook.exe under Microsoft Office or Outlook.lnk in the Start Menu."
        )

    sender_name = smtp_setting("CALIBRATION_EMAIL_FROM_NAME", "KPKAUE Fortune QA")
    subject = "Calibration reminder - equipment due for calibration"
    with tempfile.TemporaryDirectory(prefix="qaqc_outlook_") as temp_dir:
        temp_path = Path(temp_dir)
        attachment_file = temp_path / attachment_name
        attachment_arg = ""
        if attachment_pdf:
            attachment_file.write_bytes(attachment_pdf)
            attachment_arg = str(attachment_file)

        try:
            import win32com.client
        except ImportError as exc:
            raise RuntimeError("Classic Outlook sending requires the pywin32 package.") from exc

        try:
            outlook = win32com.client.Dispatch("Outlook.Application")
        except Exception:
            try:
                shell_execute_file(outlook_launcher)
                time.sleep(5)
                outlook = win32com.client.Dispatch("Outlook.Application")
            except Exception as exc:
                raise RuntimeError(f"Classic Outlook send failed: {exc}") from exc

        try:
            mail = outlook.CreateItem(0)
            mail.To = ";".join(recipients)
            mail.Subject = subject
            mail.Body = f"{message}\r\n\r\nRegards,\r\n{sender_name}"
            if attachment_arg:
                mail.Attachments.Add(attachment_arg)
            mail.Send()
        except Exception as exc:
            raise RuntimeError(f"Classic Outlook send failed: {exc}") from exc
    return True


def open_classic_outlook_draft(message, recipients, attachment_pdf=None, attachment_name="calibration_due_report.pdf"):
    if not recipients:
        raise RuntimeError("Cannot open Outlook draft. Missing email recipients.")
    outlook_launcher = classic_outlook_launcher()
    if not outlook_launcher:
        raise RuntimeError(
            "Classic Outlook was not found. Expected Outlook.exe under Microsoft Office or Outlook.lnk in the Start Menu."
        )
    if not attachment_pdf:
        raise RuntimeError("Cannot open Outlook draft. Missing PDF attachment.")

    drafts_dir = BASE_DIR / "tmp" / "email_attachments"
    drafts_dir.mkdir(parents=True, exist_ok=True)
    safe_name = "".join(char if char.isalnum() or char in {"-", "_", "."} else "_" for char in attachment_name)
    timestamp = pd.Timestamp.now().strftime("%Y%m%d_%H%M%S")
    attachment_path = drafts_dir / f"{timestamp}_{safe_name}"
    body_path = drafts_dir / f"{timestamp}_email_body.txt"
    attachment_path.write_bytes(attachment_pdf)
    body_path.write_text(message, encoding="utf-8")

    recipient_text = ";".join(recipients)
    subject = "Calibration reminder - equipment due for calibration"
    mailto = f"{recipient_text}?subject={quote(subject)}"
    try:
        arguments = f'/c ipm.note /m "{mailto}" /a "{attachment_path}"'
        shell_execute_file(outlook_launcher, arguments)
    except OSError as exc:
        raise RuntimeError(f"Classic Outlook draft could not be opened: {exc}") from exc
    return attachment_path, body_path


def open_email_app_draft(message, recipients, attachment_pdf=None, attachment_name="calibration_due_report.pdf"):
    if not recipients:
        raise RuntimeError("Cannot create email draft. Missing email recipients.")
    if not attachment_pdf:
        raise RuntimeError("Cannot create email draft. Missing PDF attachment.")

    drafts_dir = BASE_DIR / "tmp" / "email_attachments"
    drafts_dir.mkdir(parents=True, exist_ok=True)
    safe_name = "".join(char if char.isalnum() or char in {"-", "_", "."} else "_" for char in attachment_name)
    timestamp = pd.Timestamp.now().strftime("%Y%m%d_%H%M%S")
    attachment_path = drafts_dir / f"{timestamp}_{safe_name}"
    eml_path = drafts_dir / f"{timestamp}_calibration_report_email.eml"
    attachment_path.write_bytes(attachment_pdf)

    sender_address = smtp_setting("SMTP_FROM") or smtp_setting("SMTP_USER") or "calibration-reminder@localhost"
    sender_name = smtp_setting("CALIBRATION_EMAIL_FROM_NAME", "KPKAUE Fortune QA")
    email = EmailMessage()
    email["Subject"] = "Calibration reminder - equipment due for calibration"
    email["From"] = formataddr((sender_name, sender_address))
    email["To"] = ", ".join(recipients)
    email.set_content(message)
    email.add_attachment(
        attachment_pdf,
        maintype="application",
        subtype="pdf",
        filename=safe_name,
    )
    eml_path.write_bytes(email.as_bytes())

    try:
        open_file_with_default_app(eml_path)
    except (OSError, RuntimeError) as exc:
        raise RuntimeError(f"Windows could not open the email draft file: {exc}") from exc
    return eml_path, attachment_path


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
                error_text = str(exc)
                if "SmtpClientAuthentication is disabled" in error_text or "5.7.139" in error_text:
                    return send_email_via_classic_outlook(
                        message,
                        recipients,
                        attachment_pdf=attachment_pdf,
                        attachment_name=attachment_name,
                    )
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
