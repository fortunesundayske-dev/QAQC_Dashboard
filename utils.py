import streamlit as st
import pandas as pd
import plotly.express as px
import time
import base64
import json
import os
from click import style
from datetime import date, datetime, timedelta
from pathlib import Path
import uuid
import html
import inspect
from urllib import request, error
from urllib.parse import quote, urlparse
from io import BytesIO

from database.cloudinary_storage import (
    DEFAULT_MASTER_WORKBOOK_PUBLIC_ID,
    get_master_workbook_reference,
    private_asset_url,
)
from database.settings import get_setting

from ui_theme import (
    CHART_COLORS_DARK,
    CHART_COLORS_LIGHT,
    DARK_THEME,
    LIGHT_THEME,
    css_variables,
)

BASE_DIR = Path(__file__).resolve().parent

EXCEL_FILE = BASE_DIR / "data" / "QAQC_Master.xlsx"
CALIBRATION_ACK_FILE = BASE_DIR / "data" / "calibration_acknowledgements.json"
CALIBRATION_REPORT_DIR = BASE_DIR / "outputs" / "calibration_reports"
TEAMS_CONFIG_FILE = BASE_DIR / "data" / "teams_config.json"
TEAMS_NOTIFICATION_LOG_FILE = BASE_DIR / "data" / "teams_notification_log.json"
ASSETS = BASE_DIR / "assets"
EVOMEC_LOGO = ASSETS / "evomec_logo.png"
NLNG_LOGO = ASSETS / "nlng_logo.png"
BACKGROUND_DIR = ASSETS / "backgrounds"
BACKGROUND_PUBLIC_IDS = {
    "quality-ai": "qaqc-dashboard/backgrounds/quality-ai",
    "quality-wins": "qaqc-dashboard/backgrounds/quality-wins",
    "quality-growth": "qaqc-dashboard/backgrounds/quality-growth",
    "quality-assurance": "qaqc-dashboard/backgrounds/quality-assurance",
    "quality-compliance": "qaqc-dashboard/backgrounds/quality-compliance",
    "quality-qa": "qaqc-dashboard/backgrounds/quality-qa",
}
PAGE_BACKGROUND_ASSETS = {
    "app": "quality-growth",
    "Executive_Dashboard": "quality-growth",
    "Management_Executive_Summary": "quality-growth",
    "KPI_KRA_Register": "quality-growth",
    "Daily_Reports": "quality-wins",
    "Concrete_Tracker": "quality-wins",
    "ITR_Tracker": "quality-wins",
    "Audit_Surveillance": "quality-assurance",
    "Calibration_Log": "quality-assurance",
    "Activity_Log": "quality-assurance",
    "CTQ_Dashboard": "quality-compliance",
    "NCR_Tracker": "quality-compliance",
    "OBS_Tracker": "quality-compliance",
    "Defect_Rework_Tracker": "quality-compliance",
    "Document_Status": "quality-compliance",
    "Standards_Library": "quality-compliance",
    "Learning_Academy": "quality-ai",
    "Lessons_Learned": "quality-ai",
    "Quality_Tools": "quality-ai",
    "Customer_Support": "quality-qa",
    "Access_Admin": "quality-qa",
    "User_Profile": "quality-qa",
}


def _current_page_name():
    for frame in inspect.stack():
        path = Path(frame.filename)
        if path.suffix.lower() == ".py" and path.parent.name.lower() == "pages":
            return path.stem
    return "app"


def _page_background_source():
    asset_name = PAGE_BACKGROUND_ASSETS.get(_current_page_name(), "quality-ai")
    cloudinary_url = str(get_setting("CLOUDINARY_URL", "")).strip()
    parsed = urlparse(cloudinary_url) if cloudinary_url else None
    if parsed and parsed.scheme == "cloudinary" and parsed.hostname:
        public_id = quote(BACKGROUND_PUBLIC_IDS[asset_name], safe="/")
        return (
            f"https://res.cloudinary.com/{parsed.hostname}/image/upload/"
            f"f_auto,q_auto,w_1920,c_limit/{public_id}"
        )
    return _image_data_uri(BACKGROUND_DIR / f"{asset_name}.png")


def record_site_activity(action, **kwargs):
    """Best-effort activity logging without coupling dashboard utilities to storage."""
    try:
        from database.audit_log import record_activity

        return record_activity(action, **kwargs)
    except Exception:
        return False


def _image_data_uri(path):
    p = Path(path)
    if not p.exists():
        return ""
    suffix = p.suffix.lower().lstrip(".")
    mime = "jpeg" if suffix in {"jpg", "jpeg"} else suffix
    return f"data:image/{mime};base64,{base64.b64encode(p.read_bytes()).decode('ascii')}"


def _profile_photo_src(photo):
    if isinstance(photo, dict):
        for key in ("url", "secure_url"):
            saved_url = str(photo.get(key) or "").strip()
            if saved_url.startswith(("https://", "http://")):
                return saved_url
        try:
            return private_asset_url(photo, expires_in=300)
        except Exception:
            return ""
    value = str(photo or "").strip()
    if value.startswith(("https://", "http://")):
        return value
    path = Path(value) if value else None
    return _image_data_uri(path) if path and path.exists() else ""
# =========================
# DATA LOADING (DICT SYSTEM)
# =========================

@st.cache_data(show_spinner=False)
def _load_master_data_cached(file_path, modified_ns):
    del modified_ns
    file_path = Path(file_path)
    xls = pd.ExcelFile(file_path)
    return {
        sheet: pd.read_excel(xls, sheet)
        for sheet in xls.sheet_names
    }


@st.cache_data(ttl=60, show_spinner=False)
def _cloud_master_reference(public_id):
    return get_master_workbook_reference(public_id)


@st.cache_data(show_spinner=False)
def _load_cloud_master_data(url, version):
    del version
    from io import BytesIO
    from urllib.request import urlopen

    with urlopen(url, timeout=30) as response:
        workbook = BytesIO(response.read())
    xls = pd.ExcelFile(workbook)
    return {
        sheet: pd.read_excel(xls, sheet)
        for sheet in xls.sheet_names
    }


def load_master_data(file_path):
    try:
        cloudinary_configured = bool(str(get_setting("CLOUDINARY_URL", "")).strip())
        public_id = str(
            get_setting("QAQC_MASTER_WORKBOOK_PUBLIC_ID", DEFAULT_MASTER_WORKBOOK_PUBLIC_ID)
        ).strip()
        if cloudinary_configured and public_id:
            try:
                reference = _cloud_master_reference(public_id)
                return _load_cloud_master_data(reference["url"], reference["version"])
            except Exception:
                # Preserve dashboard availability if Cloudinary is temporarily unavailable.
                pass

        file_path = Path(file_path)

        if not file_path.exists():
            st.error("The QA/QC master workbook could not be found.")
            return {}
        resolved = file_path.resolve()
        return _load_master_data_cached(str(resolved), resolved.stat().st_mtime_ns)

    except Exception:
        st.error("The QA/QC master workbook could not be loaded. Contact an administrator if this continues.")
        return {}


# =========================
# CALIBRATION REMINDERS
# =========================

CALIBRATION_COMPLETE_TERMS = ("complete", "completed", "closed", "recalibrated", "renewed")


def _today():
    return pd.Timestamp(date.today())


def _read_calibration_acknowledgements():
    if not CALIBRATION_ACK_FILE.exists():
        return {}
    try:
        with CALIBRATION_ACK_FILE.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
        return payload if isinstance(payload, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _write_calibration_acknowledgements(payload):
    CALIBRATION_ACK_FILE.parent.mkdir(parents=True, exist_ok=True)
    with CALIBRATION_ACK_FILE.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)


def calibration_record_completed(status):
    value = str(status or "").strip().lower()
    return any(term in value for term in CALIBRATION_COMPLETE_TERMS)


def _calibration_alert_status(row):
    if calibration_record_completed(row.get("Status")):
        return "Completed"
    due_date = row.get("Next_Due_Date")
    if pd.isna(due_date):
        return "No due date"
    days = int((pd.Timestamp(due_date).normalize() - _today()).days)
    if days < 0:
        return "Overdue"
    if days == 21:
        return "Due in 21 days"
    if days < 21:
        return "Due soon"
    return "OK"


def get_calibration_log(data):
    df = data.get("Calibration Log", pd.DataFrame()) if isinstance(data, dict) else pd.DataFrame()
    if not isinstance(df, pd.DataFrame) or df.empty:
        return pd.DataFrame()

    log = df.copy()
    if "Calibration_ID" not in log.columns:
        log["Calibration_ID"] = [f"CAL-{index + 1:03d}" for index in range(len(log))]

    for column in ["Calibration_Date", "Next_Due_Date", "Reminder_Date", "Acknowledged_On", "Snoozed_Until", "Last_Notified_On"]:
        if column in log.columns:
            log[column] = pd.to_datetime(log[column], errors="coerce")
        else:
            log[column] = pd.NaT

    if "Status" not in log.columns:
        log["Status"] = ""

    acknowledgements = _read_calibration_acknowledgements()
    for index, row in log.iterrows():
        record_id = str(row.get("Calibration_ID", "")).strip()
        saved = acknowledgements.get(record_id, {})
        for column, key in [
            ("Acknowledged_On", "acknowledged_on"),
            ("Snoozed_Until", "snoozed_until"),
            ("Last_Notified_On", "last_notified_on"),
        ]:
            if saved.get(key):
                log.at[index, column] = pd.to_datetime(saved.get(key), errors="coerce")
        if saved.get("note"):
            log.at[index, "Notification_Notes"] = saved.get("note")

    missing_reminders = log["Reminder_Date"].isna() & log["Next_Due_Date"].notna()
    log.loc[missing_reminders, "Reminder_Date"] = log.loc[missing_reminders, "Next_Due_Date"] - pd.Timedelta(days=21)
    log["Days_Until_Due"] = (log["Next_Due_Date"].dt.normalize() - _today()).dt.days
    log["Alert_Status"] = log.apply(_calibration_alert_status, axis=1)
    log["Is_Completed"] = log["Status"].apply(calibration_record_completed)
    log["Is_Snoozed"] = log["Snoozed_Until"].notna() & (log["Snoozed_Until"].dt.normalize() >= _today())
    return log


def get_calibration_reminders(data, include_snoozed=False):
    log = get_calibration_log(data)
    if log.empty or "Next_Due_Date" not in log.columns:
        return log

    reminders = log[
        log["Next_Due_Date"].notna()
        & (~log["Is_Completed"])
        & (log["Days_Until_Due"] <= 21)
    ].copy()
    if not include_snoozed:
        reminders = reminders[~reminders["Is_Snoozed"]]
    return reminders.sort_values(["Days_Until_Due", "Equipment_Type"], na_position="last")


def get_calibration_summary(data):
    log = get_calibration_log(data)
    reminders = get_calibration_reminders(data)
    if log.empty:
        return {
            "total": 0,
            "active": 0,
            "overdue": 0,
            "due_in_21_days": 0,
            "due_soon": 0,
            "snoozed": 0,
        }

    active = log[~log["Is_Completed"]]
    return {
        "total": int(len(log)),
        "active": int(len(active)),
        "overdue": int((active["Days_Until_Due"] < 0).sum()),
        "due_in_21_days": int((active["Days_Until_Due"] == 21).sum()),
        "due_soon": int(((active["Days_Until_Due"] >= 0) & (active["Days_Until_Due"] < 21)).sum()),
        "snoozed": int(log["Is_Snoozed"].sum()),
        "reminders": int(len(reminders)),
    }


def save_calibration_log_to_excel(records, excel_file=EXCEL_FILE):
    if not isinstance(records, pd.DataFrame):
        raise RuntimeError("Calibration records must be a table before saving.")

    excel_file = Path(excel_file)
    if not excel_file.exists():
        raise RuntimeError(f"Excel workbook was not found: {excel_file}")

    export = records.copy()
    for column in export.columns:
        if "date" in str(column).lower() or str(column) in {"Acknowledged_On", "Snoozed_Until", "Last_Notified_On"}:
            export[column] = pd.to_datetime(export[column], errors="coerce")

    try:
        with pd.ExcelWriter(excel_file, engine="openpyxl", mode="a", if_sheet_exists="replace") as writer:
            export.to_excel(writer, sheet_name="Calibration Log", index=False)
    except PermissionError as exc:
        raise RuntimeError("The Excel workbook is open or locked. Close QAQC_Master.xlsx, then save again.") from exc
    except Exception as exc:
        raise RuntimeError(f"Calibration log could not be saved to Excel: {exc}") from exc
    record_site_activity(
        "save_calibration_log",
        category="quality_record",
        page="Calibration Log",
        target="Calibration Log",
        details={"record_count": len(export)},
    )


def acknowledge_calibration(record_id, note=""):
    payload = _read_calibration_acknowledgements()
    record = payload.setdefault(str(record_id), {})
    record["acknowledged_on"] = date.today().isoformat()
    if note:
        record["note"] = note
    _write_calibration_acknowledgements(payload)
    record_site_activity(
        "acknowledge_calibration", category="quality_record", page="Calibration Log",
        target=str(record_id), details={"note_added": bool(note)},
    )


def snooze_calibration(record_id, days=1, note=""):
    payload = _read_calibration_acknowledgements()
    record = payload.setdefault(str(record_id), {})
    record["snoozed_until"] = (date.today() + timedelta(days=int(days))).isoformat()
    if note:
        record["note"] = note
    _write_calibration_acknowledgements(payload)
    record_site_activity(
        "snooze_calibration", category="quality_record", page="Calibration Log",
        target=str(record_id), details={"days": int(days), "note_added": bool(note)},
    )


def mark_calibration_notified(record_ids):
    payload = _read_calibration_acknowledgements()
    today_value = date.today().isoformat()
    for record_id in record_ids:
        payload.setdefault(str(record_id), {})["last_notified_on"] = today_value
    _write_calibration_acknowledgements(payload)
    record_site_activity(
        "mark_calibration_notified", category="notification", page="Calibration Log",
        details={"record_count": len(record_ids)},
    )


# =========================
# MICROSOFT TEAMS NOTIFICATIONS
# =========================

def read_teams_config():
    if not TEAMS_CONFIG_FILE.exists():
        return {}
    try:
        with TEAMS_CONFIG_FILE.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
        return payload if isinstance(payload, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def write_teams_config(webhook_url):
    TEAMS_CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    payload = {"webhook_url": str(webhook_url or "").strip(), "updated_at": datetime.now().isoformat(timespec="seconds")}
    with TEAMS_CONFIG_FILE.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
    record_site_activity(
        "update_teams_configuration", category="configuration", page="Calibration Log",
        details={"configured": bool(payload["webhook_url"])},
    )


def get_teams_webhook_url():
    env_url = os.getenv("TEAMS_WEBHOOK_URL", "").strip()
    if env_url:
        return env_url
    return str(read_teams_config().get("webhook_url", "")).strip()


def mask_teams_webhook_url(webhook_url):
    value = str(webhook_url or "").strip()
    if not value:
        return ""
    if len(value) <= 18:
        return "*" * len(value)
    return f"{value[:10]}...{value[-8:]}"


def read_teams_notification_log():
    if not TEAMS_NOTIFICATION_LOG_FILE.exists():
        return []
    try:
        with TEAMS_NOTIFICATION_LOG_FILE.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
        return payload if isinstance(payload, list) else []
    except (OSError, json.JSONDecodeError):
        return []


def _write_teams_notification_log(entries):
    TEAMS_NOTIFICATION_LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with TEAMS_NOTIFICATION_LOG_FILE.open("w", encoding="utf-8") as handle:
        json.dump(entries[-1000:], handle, indent=2, sort_keys=True)


def _calibration_identifier(row):
    for column in ("Tag_Number", "Tag_No", "Tag", "Instrument_ID", "Equipment_ID", "Serial_No", "Calibration_ID"):
        value = row.get(column)
        if pd.notna(value) and str(value).strip():
            return str(value).strip()
    return "N/A"


def _calibration_equipment_name(row):
    parts = []
    for column in ("Equipment_Type", "Instrument_Name", "Make_Model"):
        value = row.get(column)
        if pd.notna(value) and str(value).strip():
            parts.append(str(value).strip())
    return " - ".join(dict.fromkeys(parts)) or "Equipment"


def _calibration_date_text(value):
    timestamp = pd.to_datetime(value, errors="coerce")
    return "N/A" if pd.isna(timestamp) else timestamp.strftime("%Y-%m-%d")


def teams_alert_status(row):
    days = int(row.get("Days_Until_Due", 0))
    return "Overdue" if days < 0 else "Due Soon"


def teams_alert_days_text(row):
    days = int(row.get("Days_Until_Due", 0))
    if days < 0:
        return f"{abs(days)} day(s) overdue"
    if days == 0:
        return "Due today"
    return f"{days} day(s) remaining"


def should_send_teams_alert(row):
    if calibration_record_completed(row.get("Status")):
        return False
    due_date = pd.to_datetime(row.get("Next_Due_Date"), errors="coerce")
    if pd.isna(due_date):
        return False
    days = int(row.get("Days_Until_Due", (due_date.normalize() - _today()).days))
    return days <= 21


def teams_alert_frequency(row):
    days = int(row.get("Days_Until_Due", 0))
    if days < 0:
        return "daily_overdue", 1
    if days <= 7:
        return "daily_final_week", 1
    return "weekly_due_soon", 7


def _parse_log_date(value):
    timestamp = pd.to_datetime(value, errors="coerce")
    return None if pd.isna(timestamp) else timestamp.date()


def teams_alert_recently_sent(record_id, status, row, sent_date=None):
    sent_date = sent_date or date.today()
    if isinstance(sent_date, str):
        sent_date = date.fromisoformat(sent_date)
    record_id = str(record_id)
    status = str(status)
    frequency, interval_days = teams_alert_frequency(row)
    for entry in read_teams_notification_log():
        if str(entry.get("record_id")) != record_id or str(entry.get("status")) != status:
            continue
        if not str(entry.get("teams_delivery_result", "")).lower().startswith("success"):
            continue
        entry_frequency = entry.get("notification_frequency")
        if entry_frequency and entry_frequency != frequency:
            continue
        last_sent = _parse_log_date(entry.get("date_sent"))
        if last_sent and (sent_date - last_sent).days < interval_days:
            return True
    return False


def build_teams_calibration_message(row):
    equipment = _calibration_equipment_name(row)
    identifier = _calibration_identifier(row)
    status = teams_alert_status(row)
    days_text = teams_alert_days_text(row)
    last_date = _calibration_date_text(row.get("Calibration_Date"))
    next_date = _calibration_date_text(row.get("Next_Due_Date"))
    return (
        f"**Calibration Alert: {status}**\n\n"
        f"- **Equipment/Instrument Name:** {equipment}\n"
        f"- **Tag Number / ID:** {identifier}\n"
        f"- **Last Calibration Date:** {last_date}\n"
        f"- **Next Calibration Due Date:** {next_date}\n"
        f"- **Status:** {status}\n"
        f"- **Timing:** {days_text}"
    )


TEAMS_ALERT_CARD_CHUNK_SIZE = 5
TEAMS_ALERT_POST_RETRIES = 2
TEAMS_ALERT_RETRY_DELAY_SECONDS = 2
TEAMS_ALERT_BATCH_DELAY_SECONDS = 1


def build_teams_calibration_batch_message(records, batch_number=None, batch_total=None):
    if records is None or not isinstance(records, pd.DataFrame) or records.empty:
        return "No calibration equipment is due or overdue."

    export = records.copy()
    if "Days_Until_Due" in export.columns:
        export = export.sort_values(["Days_Until_Due", "Equipment_Type"], na_position="last")

    overdue_count = int((export["Days_Until_Due"] < 0).sum()) if "Days_Until_Due" in export.columns else 0
    due_soon_count = int((export["Days_Until_Due"] >= 0).sum()) if "Days_Until_Due" in export.columns else len(export)
    lines = [
        "**QAQC Calibration Notification**",
        f"Total equipment requiring attention: {len(export)}",
        f"Overdue: {overdue_count}",
        f"Due soon: {due_soon_count}",
        "",
    ]
    if batch_number and batch_total:
        lines.insert(1, f"Batch {batch_number} of {batch_total}")

    for index, (_, row) in enumerate(export.iterrows(), start=1):
        status = teams_alert_status(row)
        lines.extend(
            [
                f"**{index}. {_calibration_equipment_name(row)}**",
                f"- Tag Number / ID: {_calibration_identifier(row)}",
                f"- Last Calibration Date: {_calibration_date_text(row.get('Calibration_Date'))}",
                f"- Next Calibration Due Date: {_calibration_date_text(row.get('Next_Due_Date'))}",
                f"- Status: {status}",
                f"- Timing: {teams_alert_days_text(row)}",
            ]
        )
        project = row.get("Project")
        if pd.notna(project) and str(project).strip():
            lines.append(f"- Project: {str(project).strip()}")
        certificate = row.get("Certificate_No")
        if pd.notna(certificate) and str(certificate).strip():
            lines.append(f"- Certificate No: {str(certificate).strip()}")
        lines.append("")

    return "\n".join(lines)


def chunk_dataframe(records, chunk_size=TEAMS_ALERT_CARD_CHUNK_SIZE):
    for start in range(0, len(records), chunk_size):
        yield records.iloc[start : start + chunk_size]


def build_teams_adaptive_card(message):
    lines = [line.strip() for line in str(message).splitlines() if line.strip()]
    body = [
        {
            "type": "TextBlock",
            "text": "QAQC Calibration Notification",
            "weight": "Bolder",
            "size": "Medium",
            "wrap": True,
        }
    ]
    for line in lines:
        clean_line = line.replace("**", "")
        if clean_line.startswith("- "):
            clean_line = clean_line[2:]
        body.append({"type": "TextBlock", "text": clean_line, "wrap": True, "spacing": "Small"})

    return {
        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
        "type": "AdaptiveCard",
        "version": "1.2",
        "body": body,
    }


def build_teams_webhook_payload(message):
    adaptive_card = build_teams_adaptive_card(message)
    plain_message = str(message or "").replace("**", "").strip()
    message_html = "<br>".join(html.escape(line) for line in plain_message.splitlines())
    adaptive_card_json = json.dumps(adaptive_card, ensure_ascii=False)
    attachment = {
        "contentType": "application/vnd.microsoft.card.adaptive",
        "contentUrl": None,
        "content": adaptive_card,
        "contentJson": adaptive_card_json,
        "name": "QAQC Calibration Notification",
    }
    return {
        **adaptive_card,
        "summary": "QAQC Calibration Notification",
        "notificationType": "QAQCCalibrationNotification",
        "adaptiveCard": adaptive_card,
        "adaptiveCardJson": adaptive_card_json,
        "card": adaptive_card,
        "cardJson": adaptive_card_json,
        "attachments": [attachment],
        "teamsMessage": {
            "type": "message",
            "attachments": [attachment],
        },
        "message": plain_message,
        "messageHtml": message_html,
        "text": plain_message,
    }


def post_to_teams(webhook_url, message, retries=TEAMS_ALERT_POST_RETRIES, retry_delay_seconds=TEAMS_ALERT_RETRY_DELAY_SECONDS):
    payload = json.dumps(build_teams_webhook_payload(message), ensure_ascii=False).encode("utf-8")
    attempts = max(1, int(retries or 0) + 1)
    retryable_http_codes = {408, 425, 429, 500, 502, 503, 504}
    last_result = ""

    for attempt in range(1, attempts + 1):
        req = request.Request(
            webhook_url,
            data=payload,
            headers={
                "Content-Type": "application/json; charset=utf-8",
                "User-Agent": "QAQC-Calibration-Log/1.0",
            },
            method="POST",
        )
        try:
            with request.urlopen(req, timeout=30) as response:
                body = response.read().decode("utf-8", errors="replace").strip()
                result = f"Success ({response.status}) - Power Automate accepted request"
                return True, result + (f": {body}" if body else "")
        except error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace").strip()
            last_result = f"HTTP {exc.code}: {detail or exc.reason}"
            if exc.code not in retryable_http_codes or attempt == attempts:
                return False, last_result
        except (error.URLError, TimeoutError, OSError) as exc:
            last_result = str(exc)
            if attempt == attempts:
                return False, (
                    f"Failed after {attempts} attempt(s): {last_result}. "
                    "Check internet, proxy, firewall, and access to the Power Automate webhook."
                )

        time.sleep(retry_delay_seconds * attempt)

    return False, last_result or "Failed to send Teams notification."


def append_teams_notification_log(record_id, row, result, sent_at=None):
    sent_at = sent_at or datetime.now()
    frequency, interval_days = teams_alert_frequency(row)
    entries = read_teams_notification_log()
    entries.append(
        {
            "sent_at": sent_at.isoformat(timespec="seconds"),
            "date_sent": sent_at.date().isoformat(),
            "record_id": str(record_id),
            "equipment": _calibration_equipment_name(row),
            "tag_number_or_id": _calibration_identifier(row),
            "status": teams_alert_status(row),
            "days": int(row.get("Days_Until_Due", 0)),
            "notification_frequency": frequency,
            "next_allowed_on": (sent_at.date() + timedelta(days=interval_days)).isoformat(),
            "teams_delivery_result": str(result),
        }
    )
    _write_teams_notification_log(entries)


def send_calibration_teams_alerts(records, webhook_url=None, force=False):
    if records is None or not isinstance(records, pd.DataFrame) or records.empty:
        return {"configured": bool(get_teams_webhook_url()), "sent": 0, "skipped": 0, "failed": 0, "results": []}

    webhook_url = (webhook_url or get_teams_webhook_url()).strip()
    if not webhook_url:
        return {
            "configured": False,
            "sent": 0,
            "skipped": 0,
            "failed": 0,
            "results": [{"result": "Microsoft Teams webhook is not configured."}],
        }

    results = []
    due_rows = []
    trigger_rows = []
    skipped = 0
    for _, row in records.iterrows():
        if not should_send_teams_alert(row):
            skipped += 1
            continue
        due_rows.append(row)
        record_id = str(row.get("Calibration_ID") or _calibration_identifier(row)).strip()
        status = teams_alert_status(row)
        if not force and teams_alert_recently_sent(record_id, status, row):
            frequency, interval_days = teams_alert_frequency(row)
            results.append(
                {
                    "record_id": record_id,
                    "status": status,
                    "frequency": frequency,
                    "result": f"Included in full alert card; cadence interval is {interval_days} day(s)",
                }
            )
            continue

        trigger_rows.append(row)

    if not due_rows:
        return {"configured": True, "sent": 0, "skipped": skipped, "failed": 0, "results": results}
    if not force and not trigger_rows:
        return {"configured": True, "sent": 0, "skipped": skipped, "failed": 0, "results": results}

    due_records = pd.DataFrame(due_rows)
    batches = list(chunk_dataframe(due_records))
    batch_results = []
    for batch_number, batch in enumerate(batches, start=1):
        ok, result = post_to_teams(
            webhook_url,
            build_teams_calibration_batch_message(
                batch,
                batch_number=batch_number,
                batch_total=len(batches),
            ),
        )
        batch_results.append((ok, result, batch_number, batch))
        if batch_number < len(batches):
            time.sleep(TEAMS_ALERT_BATCH_DELAY_SECONDS)

    sent_count = sum(len(batch) for ok, _, _, batch in batch_results if ok)
    failed_count = sum(len(batch) for ok, _, _, batch in batch_results if not ok)
    results = []
    for ok, result, batch_number, batch in batch_results:
        for _, row in batch.iterrows():
            record_id = str(row.get("Calibration_ID") or _calibration_identifier(row)).strip()
            append_teams_notification_log(record_id, row, f"Batch {batch_number}/{len(batches)}: {result}")
            frequency, _ = teams_alert_frequency(row)
            results.append(
                {
                    "record_id": record_id,
                    "status": teams_alert_status(row),
                    "frequency": frequency,
                    "batch": f"{batch_number}/{len(batches)}",
                    "result": result,
                }
            )

    return {
        "configured": True,
        "sent": int(sent_count),
        "skipped": skipped,
        "failed": int(failed_count),
        "results": results,
    }


def _clean_report_value(value):
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


def _safe_report_filename(title):
    safe = "".join(char if char.isalnum() or char in {"-", "_"} else "_" for char in str(title))
    return safe.strip("_").lower() or "calibration_report"


def _pdf_escape(value):
    return str(value).replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _build_simple_pdf(lines):
    page_width = 842
    page_height = 595
    margin_left = 36
    top = 550
    line_height = 13
    max_chars = 132
    pages = []
    current = []
    y = top

    for line in lines:
        chunks = [line[i : i + max_chars] for i in range(0, len(line), max_chars)] or [""]
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
            content_lines.append(f"({_pdf_escape(text)}) Tj")
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


def generate_calibration_pdf(records, report_title="Calibration Log Report", output_dir=CALIBRATION_REPORT_DIR):
    if not isinstance(records, pd.DataFrame) or records.empty:
        raise RuntimeError("No calibration records are available for PDF export.")

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = pd.Timestamp.now().strftime("%Y%m%d_%H%M%S")
    pdf_path = output_dir / f"{timestamp}_{_safe_report_filename(report_title)}.pdf"

    export = records.copy()
    preferred_columns = [
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
    columns = [column for column in preferred_columns if column in export.columns]
    if not columns:
        columns = list(export.columns[:10])
    export = export[columns].copy()

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
        rows = [[column.replace("_", " ") for column in columns]]
        for _, row in export.iterrows():
            rows.append([Paragraph(_clean_report_value(row.get(column)), cell_style) for column in columns])

        story = [
            Paragraph(report_title, styles["Title"]),
            Paragraph(f"Generated on {date.today().strftime('%Y-%m-%d')} for {len(export)} record(s).", styles["Normal"]),
            Spacer(1, 5 * mm),
        ]
        table = Table(rows, repeatRows=1)
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
    except ImportError:
        lines = [report_title, f"Generated on {date.today().strftime('%Y-%m-%d')} for {len(export)} record(s).", ""]
        lines.append(" | ".join(column.replace("_", " ") for column in columns))
        for _, row in export.iterrows():
            lines.append(" | ".join(_clean_report_value(row.get(column)) for column in columns))
        pdf_path.write_bytes(_build_simple_pdf(lines))

    return pdf_path


# =========================
# THEME
# =========================
def inject_enterprise_theme():
    inject_global_ui()
    return
    st.markdown("""
    <style>

    .main {
        background: #0b1320;
    }

    #MainMenu, footer, header {
        visibility: hidden;
    }

    [data-testid="stSidebarNav"],
    section[data-testid="stSidebar"] nav,
    div[data-testid="stSidebarNavItems"] {
        display: none !important;
    }

    [data-testid="stSidebarNav"],
    section[data-testid="stSidebar"] nav {
        display: none;
    }

    .block-container {
        padding: 1rem 2rem;
    }

    /* KPI CARD */
    .kpi-card {
        padding: 16px;
        border-radius: 14px;
        color: white;
        background: linear-gradient(135deg, #1f2937, #111827);
        box-shadow: 0 8px 20px rgba(0,0,0,0.35);
        transition: all 0.25s ease-in-out;
    }

    /* ✅ THIS is your hover effect (correct place) */
    .kpi-card:hover {
        transform: translateY(-6px) scale(1.03);
        box-shadow: 0 10px 30px rgba(0,0,0,0.4);
    }

    .kpi-title {
        font-size: 13px;
        opacity: 0.8;
    }

    .kpi-value {
        font-size: 26px;
        font-weight: 700;
        margin-top: 5px;
    }

    </style>
    """, unsafe_allow_html=True)
    st.markdown(
        """
    <style>
    :root {
        --qaqc-bg: #f4f7fb;
        --qaqc-surface: #ffffff;
        --qaqc-surface-2: #f8fafc;
        --qaqc-navy: #0f172a;
        --qaqc-blue: #2563eb;
        --qaqc-blue-2: #0ea5e9;
        --qaqc-text: #111827;
        --qaqc-muted: #64748b;
        --qaqc-line: #dbe4ef;
        --qaqc-success: #15803d;
        --qaqc-warning: #b45309;
        --qaqc-danger: #b91c1c;
        --qaqc-radius: 8px;
        --qaqc-shadow: 0 14px 32px rgba(15, 23, 42, 0.10);
        font-family: "Inter", "Segoe UI", Roboto, Arial, sans-serif;
    }

    html, body, .stApp, [class*="css"] {
        font-family: "Inter", "Segoe UI", Roboto, Arial, sans-serif !important;
    }

    .stApp {
        background:
            linear-gradient(180deg, rgba(37, 99, 235, 0.06), transparent 18rem),
            var(--qaqc-bg) !important;
        color: var(--qaqc-text) !important;
    }

    .block-container {
        max-width: 1560px !important;
        padding: 0.9rem 1.25rem 2rem !important;
    }

    #MainMenu, footer, header, [data-testid="stToolbar"], [data-testid="stDecoration"] {
        display: none !important;
        visibility: hidden !important;
    }

    h1, h2, h3, h4, h5, h6, p, label, span, div {
        letter-spacing: 0 !important;
    }

    h1 { color: var(--qaqc-navy) !important; font-size: 1.85rem !important; line-height: 1.18 !important; }
    h2 { color: var(--qaqc-navy) !important; font-size: 1.35rem !important; }
    h3 { color: var(--qaqc-navy) !important; font-size: 1.05rem !important; }

    .app-bar {
        background: var(--qaqc-surface) !important;
        border: 1px solid var(--qaqc-line) !important;
        border-radius: var(--qaqc-radius) !important;
        box-shadow: var(--qaqc-shadow) !important;
        margin: 0 0 0.85rem !important;
        min-height: 4rem !important;
        padding: 0.75rem 1rem !important;
    }

    .app-bar__welcome, .app-bar__eyebrow { color: var(--qaqc-blue) !important; }
    .app-bar__title { color: var(--qaqc-navy) !important; font-size: 1.05rem !important; }
    .app-bar__project, .header-profile__meta { color: var(--qaqc-muted) !important; }
    .header-profile { background: var(--qaqc-surface-2) !important; border-color: var(--qaqc-line) !important; }
    .header-profile__name { color: var(--qaqc-navy) !important; }

    .page-header, .dashboard-hero {
        background: var(--qaqc-surface) !important;
        border: 1px solid var(--qaqc-line) !important;
        border-left: 4px solid var(--qaqc-blue) !important;
        border-radius: var(--qaqc-radius) !important;
        box-shadow: var(--qaqc-shadow) !important;
        margin: 0.25rem 0 1rem !important;
        min-height: auto !important;
        padding: 1.05rem 1.2rem !important;
    }

    .page-header__eyebrow, .hero-eyebrow {
        color: var(--qaqc-blue) !important;
        font-size: 0.72rem !important;
        font-weight: 800 !important;
        text-transform: uppercase !important;
    }

    .page-header h1, .dashboard-hero h1 {
        color: var(--qaqc-navy) !important;
        font-size: 1.75rem !important;
        line-height: 1.18 !important;
        margin: 0.25rem 0 0.35rem !important;
    }

    .page-header p, .dashboard-hero p, .section-caption, .stCaptionContainer {
        color: var(--qaqc-muted) !important;
        font-size: 0.92rem !important;
    }

    section[data-testid="stSidebar"] {
        background: #0f172a !important;
        border-right: 1px solid rgba(255,255,255,0.10) !important;
    }

    section[data-testid="stSidebar"] * {
        color: #e5edf8 !important;
    }

    .side-nav-link {
        align-items: center !important;
        border: 1px solid transparent !important;
        border-radius: 7px !important;
        color: #dbeafe !important;
        display: flex !important;
        font-size: 0.86rem !important;
        font-weight: 700 !important;
        min-height: 2.55rem !important;
        padding: 0.55rem 0.75rem !important;
        text-decoration: none !important;
    }

    .side-nav-link:hover, .side-nav-link:focus-visible {
        background: rgba(37, 99, 235, 0.35) !important;
        border-color: rgba(125, 211, 252, 0.45) !important;
        color: #ffffff !important;
        transform: none !important;
    }

    .kpi-card, div[data-testid="stMetric"], .exec-panel, .tool-card, .standard-card,
    .learning-card, .security-card, div[data-testid="stExpander"] details {
        background: var(--qaqc-surface) !important;
        border: 1px solid var(--qaqc-line) !important;
        border-radius: var(--qaqc-radius) !important;
        box-shadow: var(--qaqc-shadow) !important;
        color: var(--qaqc-text) !important;
    }

    .kpi-card {
        min-height: 118px !important;
        padding: 0.9rem 1rem !important;
    }

    .kpi-card__head { align-items: center; display: flex; justify-content: space-between; gap: 0.75rem; }
    .kpi-card__icon {
        align-items: center;
        background: color-mix(in srgb, var(--accent) 14%, white);
        border: 1px solid color-mix(in srgb, var(--accent) 28%, white);
        border-radius: 999px;
        color: var(--accent);
        display: flex;
        font-size: 0.72rem;
        font-weight: 900;
        height: 2rem;
        justify-content: center;
        width: 2rem;
    }

    .kpi-title, div[data-testid="stMetricLabel"] {
        color: var(--qaqc-muted) !important;
        font-size: 0.76rem !important;
        font-weight: 800 !important;
        text-transform: uppercase !important;
    }

    .kpi-value, div[data-testid="stMetricValue"] {
        color: var(--qaqc-navy) !important;
        font-size: 1.75rem !important;
        font-weight: 850 !important;
        line-height: 1.05 !important;
    }

    .kpi-detail { color: var(--qaqc-muted); font-size: 0.8rem; margin-top: 0.45rem; }

    div[data-testid="stDataFrame"], .stDataFrame {
        background: var(--qaqc-surface) !important;
        border: 1px solid var(--qaqc-line) !important;
        border-radius: var(--qaqc-radius) !important;
        box-shadow: var(--qaqc-shadow) !important;
        overflow: auto !important;
    }

    .stButton button, div[data-testid="stPopover"] button, .stDownloadButton button {
        background: var(--qaqc-blue) !important;
        border: 1px solid #1d4ed8 !important;
        border-radius: 7px !important;
        color: #ffffff !important;
        font-weight: 800 !important;
        min-height: 2.5rem !important;
    }

    .stButton button:hover, div[data-testid="stPopover"] button:hover, .stDownloadButton button:hover {
        background: #1d4ed8 !important;
        border-color: #1e40af !important;
        color: #ffffff !important;
    }

    div[data-baseweb="input"] > div, div[data-baseweb="select"] > div, textarea {
        background: #ffffff !important;
        border-color: var(--qaqc-line) !important;
        border-radius: 7px !important;
        color: var(--qaqc-text) !important;
        min-height: 2.6rem !important;
    }

    div[data-baseweb="select"] span, input, textarea {
        color: var(--qaqc-text) !important;
    }

    .status-badge {
        border-radius: 999px;
        display: inline-flex;
        font-size: 0.74rem;
        font-weight: 800;
        line-height: 1;
        margin-top: 0.5rem;
        padding: 0.38rem 0.56rem;
    }

    .status-badge--open, .status-badge--warning { background: #fff7ed; color: var(--qaqc-warning); border: 1px solid #fed7aa; }
    .status-badge--closed, .status-badge--success { background: #f0fdf4; color: var(--qaqc-success); border: 1px solid #bbf7d0; }
    .status-badge--critical, .status-badge--danger { background: #fef2f2; color: var(--qaqc-danger); border: 1px solid #fecaca; }
    .status-badge--neutral { background: #f1f5f9; color: #475569; border: 1px solid #cbd5e1; }

    .empty-state, .app-alert {
        align-items: flex-start;
        background: var(--qaqc-surface) !important;
        border: 1px solid var(--qaqc-line);
        border-radius: var(--qaqc-radius);
        box-shadow: var(--qaqc-shadow);
        color: var(--qaqc-text);
        display: flex;
        gap: 0.85rem;
        margin: 0.65rem 0;
        padding: 1rem;
    }

    .empty-state__mark {
        align-items: center;
        background: #eff6ff;
        border: 1px solid #bfdbfe;
        border-radius: 999px;
        color: var(--qaqc-blue);
        display: flex;
        flex: 0 0 auto;
        font-weight: 900;
        height: 2rem;
        justify-content: center;
        width: 2rem;
    }

    .empty-state h3 { margin: 0 0 0.2rem !important; }
    .empty-state p { color: var(--qaqc-muted) !important; margin: 0 !important; }

    .app-alert--success { border-left: 4px solid var(--qaqc-success); }
    .app-alert--warning { border-left: 4px solid var(--qaqc-warning); }
    .app-alert--error, .app-alert--danger { border-left: 4px solid var(--qaqc-danger); }
    .app-alert--info { border-left: 4px solid var(--qaqc-blue); }

    @media (max-width: 900px) {
        .block-container { padding: 0.7rem 0.7rem 1.5rem !important; }
        .app-bar { align-items: flex-start !important; flex-direction: column !important; gap: 0.65rem !important; }
        .app-bar__right { flex-wrap: wrap !important; width: 100% !important; }
        .page-header h1, .dashboard-hero h1 { font-size: 1.35rem !important; }
        .kpi-card, div[data-testid="stMetric"] { min-height: auto !important; }
        [data-testid="stHorizontalBlock"] { gap: 0.65rem !important; }
        div[data-testid="stTabs"] div[role="tablist"] { overflow-x: auto !important; white-space: nowrap !important; }
    }
    </style>
    """,
        unsafe_allow_html=True,
    )

# =========================
# HEADER
# =========================
def render_header():
    nlng_src = _image_data_uri(NLNG_LOGO)
    evomec_src = _image_data_uri(EVOMEC_LOGO)
    nlng_logo = f'<img src="{nlng_src}" alt="NLNG">' if nlng_src else '<span>NLNG</span>'
    evomec_logo = f'<img src="{evomec_src}" alt="EVOMEC">' if evomec_src else '<span>EVOMEC</span>'
    user = st.session_state.get("auth") or {}
    st.html(
        f"""
<div class="app-bar">
    <div class="app-brand-lockup">
        <div class="app-logo-img app-logo-img--nlng">{nlng_logo}</div>
        <div>
            <div class="app-bar__eyebrow">Enterprise Quality Management System</div>
            <div class="app-bar__title">EVOMEC QMS</div>
            <div class="app-bar__project">Quality performance, compliance, and field records</div>
        </div>
    </div>
    <div class="app-bar__right">
        <div class="app-capability-strip">
            <span>Portfolio</span>
            <span>Quality Records</span>
            <span>Calibration</span>
            <span>Audit Trail</span>
            <span>Role Access</span>
            <span>Secure</span>
        </div>
        <div class="app-logo-img app-logo-img--evomec">{evomec_logo}</div>
    </div>
</div>
"""
    )



def _render_account_menu(user):
    account_name = str(user.get("name", "User"))
    account_role = str(user.get("role", "user")).replace("_", " ").title()
    account_discipline = str(user.get("discipline") or "QA/QC")
    account_button_label = f"{account_name}\nEVOMEC - Nigeria LNG"
    photo_src = _profile_photo_src(user.get("profile_photo"))
    initials = "".join(part[:1] for part in account_name.split()[:2]).upper() or "U"
    st.markdown(
        """
<style>
.st-key-navigation_account {
    background: linear-gradient(135deg, #0866e8 0%, #1279ff 100%);
    border: 1px solid rgba(147, 197, 253, 0.54);
    border-radius: 8px;
    box-shadow: 0 12px 28px rgba(8, 102, 232, 0.30);
    padding: 0.36rem 0.48rem;
}
.header-account-avatar {
    align-items: center; background: linear-gradient(135deg, #2563eb, #22c55e);
    border: 2px solid rgba(255,255,255,.72); border-radius: 999px; color: #fff;
    display: flex; font-size: .76rem; font-weight: 900; height: 2.72rem;
    justify-content: center; overflow: hidden; width: 2.72rem;
}
.header-account-avatar img { height: 100%; object-fit: cover; width: 100%; }
.st-key-navigation_account [data-testid="stImage"] {
    align-items: center;
    display: flex;
    height: 2.72rem;
    margin: 0 !important;
    width: 2.72rem;
}
.st-key-navigation_account [data-testid="stImage"] img {
    border: 2px solid rgba(255,255,255,.72);
    border-radius: 999px;
    height: 2.72rem !important;
    max-width: none !important;
    object-fit: cover;
    width: 2.72rem !important;
}
.st-key-navigation_account div[data-testid="stHorizontalBlock"] { align-items: center; gap: .35rem; }
.st-key-navigation_account div[data-testid="stPopover"] { max-width: none !important; width: 100% !important; }
.st-key-navigation_account div[data-testid="stPopover"] button {
    background: transparent !important;
    border: 0 !important;
    box-shadow: none !important;
    color: #ffffff !important;
    justify-content: space-between !important;
    max-width: none !important;
    min-height: 2.72rem !important;
    min-width: 0 !important;
    padding: 0 .2rem !important;
    width: 100% !important;
}
.st-key-navigation_account div[data-testid="stPopover"] button p {
    color: #ffffff !important;
    font-size: .72rem !important;
    font-weight: 750 !important;
    line-height: 1.25 !important;
    overflow: hidden;
    text-align: left;
    text-overflow: ellipsis;
    white-space: pre-line !important;
}
.st-key-navigation_account div[data-testid="stPopover"] button p::first-line {
    font-size: .96rem;
    font-weight: 900;
}
.st-key-navigation_account div[data-testid="stPopover"] button svg { color: #ffffff !important; flex: 0 0 auto; }
.st-key-account_menu_panel { min-width: 13.5rem; padding: .2rem; }
.st-key-account_menu_panel [data-testid="stImage"] img {
    border: 1px solid rgba(148, 163, 184, .24);
    border-radius: 6px;
    height: 4.5rem;
    object-fit: cover;
    width: 4.5rem;
}
.st-key-account_menu_panel hr { border-color: rgba(148, 163, 184, .18); margin: .7rem 0; }
div[data-baseweb="popover"]:has(.st-key-account_menu_panel) > div {
    background: #0d1118 !important;
    border: 1px solid rgba(148, 163, 184, .26) !important;
    border-radius: 10px !important;
    box-shadow: 0 18px 44px rgba(0, 0, 0, .42) !important;
    min-width: 15rem !important;
}
div[data-baseweb="popover"]:has(.st-key-account_menu_panel) p,
div[data-baseweb="popover"]:has(.st-key-account_menu_panel) a,
div[data-baseweb="popover"]:has(.st-key-account_menu_panel) span {
    color: #f8fafc !important;
}
div[data-baseweb="popover"]:has(.st-key-account_menu_panel) [data-testid="stCaptionContainer"] p {
    color: #aab2bf !important;
}
</style>
""",
        unsafe_allow_html=True,
    )
    with st.container(key="navigation_account"):
        avatar_col, menu_col = st.columns([0.52, 2.48], gap="small")
        with avatar_col:
            if photo_src:
                st.image(photo_src, width=48)
            else:
                st.markdown(
                    f'<div class="header-account-avatar">{html.escape(initials)}</div>',
                    unsafe_allow_html=True,
                )
        with menu_col:
            with st.popover(account_button_label, width="stretch"):
                with st.container(key="account_menu_panel"):
                    if photo_src:
                        st.image(photo_src, width=72)
                    else:
                        st.markdown(
                            f'<div class="header-account-avatar">{html.escape(initials)}</div>',
                            unsafe_allow_html=True,
                        )
                    st.markdown(f"**{html.escape(account_name)}**")
                    st.caption(f"{account_role} · {account_discipline}")
                    st.divider()
                    st.page_link("pages/User_Profile.py", label="User Profile", width="stretch")
                    if st.button("Sign out", key="header_account_sign_out", width="stretch", type="primary"):
                        import auth

                        auth.sign_out()
                        st.rerun()

            
# =========================
# NAVIGATION (TOP)
# =========================

# =========================
# MOBILE NAV
# =========================
def get_navigation_pages():
    pages_dir = BASE_DIR / "pages"
    label_overrides = {
        "Access_Admin": "Access Admin",
        "Activity_Log": "Activity Log",
        "Audit_Surveillance": "Audit & Surveillance",
        "Calibration_Log": "Calibration Log",
        "Concrete_Tracker": "Concrete Tracker",
        "Customer_Support": "Customer Support",
        "CTQ_Dashboard": "CTQ Dashboard",
        "Daily_Reports": "Daily Reports",
        "Defect_Rework_Tracker": "Defect & Rework",
        "Document_Status": "Document Status",
        "Executive_Dashboard": "Executive Analytics",
        "ITR_Tracker": "ITR Tracker",
        "KPI_KRA_Register": "KPI KRA Register",
        "Learning_Academy": "Learning Academy",
        "Lessons_Learned": "Lessons Learned",
        "Management_Executive_Summary": "Management Summary",
        "NCR_Tracker": "NCR Tracker",
        "OBS_Tracker": "OBS Tracker",
        "Quality_Tools": "Quality Tools",
        "Standards_Library": "Standards Library",
        "User_Profile": "User Profile",
    }
    preferred_order = [
        "Executive Home",
        "Executive Analytics",
        "Quality Tools",
        "Standards Library",
        "Learning Academy",
        "Calibration Log",
        "Concrete Tracker",
        "NCR Tracker",
        "OBS Tracker",
        "Audit & Surveillance",
        "KPI KRA Register",
        "CTQ Dashboard",
        "Daily Reports",
        "ITR Tracker",
        "Document Status",
        "Defect & Rework",
        "Lessons Learned",
        "Management Summary",
        "User Profile",
        "Customer Support",
        "Access Admin",
        "Activity Log",
    ]

    pages = {
        "Executive Home": "app.py",
    }

    if pages_dir.exists():
        for page_file in sorted(pages_dir.glob("*.py")):
            page_key = page_file.stem
            if page_key.startswith("_"):
                continue
            label = label_overrides.get(page_key, page_key.replace("_", " ").title())
            pages[label] = f"pages/{page_file.name}"

    role = st.session_state.get("auth", {}).get("role") or st.session_state.get("role")
    if role != "admin":
        pages.pop("Access Admin", None)
        pages.pop("Activity Log", None)

    ordered = {
        label: pages[label]
        for label in preferred_order
        if label in pages
    }
    for label in sorted(pages):
        if label not in ordered:
            ordered[label] = pages[label]
    return ordered


def render_mobile_nav():
    pages = get_navigation_pages()
    selected = st.selectbox("Quick Navigation", list(pages.keys()))
    st.page_link(pages[selected], label="Open selected page")


def _auth_query_suffix():
    # Authentication material must never be copied into URLs, browser history,
    # referrer headers, screenshots, or proxy access logs.
    return ""


NAVIGATION_GROUPS = {
    "Overview": ["Executive Home", "Executive Analytics", "Management Summary", "KPI KRA Register"],
    "Quality Records": ["NCR Tracker", "OBS Tracker", "ITR Tracker", "Defect & Rework"],
    "Engineering": ["CTQ Dashboard", "Document Status"],
    "Materials and Equipment": ["Concrete Tracker", "Calibration Log"],
    "Audits and Reports": ["Audit & Surveillance", "Daily Reports", "Lessons Learned"],
    "Knowledge and Tools": ["Standards Library", "Learning Academy", "Quality Tools"],
    "Account and Administration": ["User Profile", "Customer Support", "Access Admin", "Activity Log"],
}

NAVIGATION_GROUP_ICONS = {
    "Overview": "⌂",
    "Quality Records": "▦",
    "Engineering": "⚙",
    "Materials and Equipment": "⬡",
    "Audits and Reports": "▤",
    "Knowledge and Tools": "◆",
    "Account and Administration": "●",
    "Other": "•",
}


def grouped_navigation_pages():
    pages = get_navigation_pages()
    grouped = []
    used = set()
    for group, labels in NAVIGATION_GROUPS.items():
        items = [(label, pages[label]) for label in labels if label in pages]
        if items:
            grouped.append((group, items))
            used.update(label for label, _ in items)
    leftovers = [(label, path) for label, path in pages.items() if label not in used]
    if leftovers:
        grouped.append(("Other", leftovers))
    return grouped

# =========================
# KPI CARDS
# =========================
def render_kpi_cards(kpis):
    if not kpis:
        return
    cols = st.columns(min(4, len(kpis)))
    accents = ["#2563eb", "#16a34a", "#d97706", "#dc2626", "#0f766e", "#7c3aed"]

    for i, kpi in enumerate(kpis):
        with cols[i % len(cols)]:
            accent = accents[i % len(accents)]
            detail = kpi.get("detail") or kpi.get("subtitle") or ""
            status = kpi.get("status") or ""
            icon = kpi.get("icon") or "QA"
            st.markdown(
                f"""
<div class="kpi-card" style="--accent: {accent};">
    <div class="kpi-card__topline"></div>
    <div class="kpi-card__head">
        <div class="kpi-title">{html.escape(str(kpi.get('label', 'Metric')))}</div>
        <div class="kpi-card__icon">{html.escape(str(icon))}</div>
    </div>
    <div class="kpi-value">{html.escape(str(kpi.get('value', '0')))}</div>
    <div class="kpi-detail">{html.escape(str(detail))}</div>
    {f'<div class="status-badge status-badge--neutral">{html.escape(str(status))}</div>' if status else ''}
</div>
""",
                unsafe_allow_html=True
            )


    
def build_kpis(filtered_data):
    projects = set()

    for df in filtered_data.values():
        if isinstance(df, pd.DataFrame) and "Project" in df.columns:
            projects.update(df["Project"].dropna().astype(str))

    project_count = len(projects)

    ncr_df = filtered_data.get("NCR Log", pd.DataFrame())
    obs_df = filtered_data.get("OBS Log", pd.DataFrame())
    itr_df = filtered_data.get("ITR Log", pd.DataFrame())
    concrete_df = filtered_data.get("Concrete Tracker", pd.DataFrame())
    audit_df = filtered_data.get("Audit Register", pd.DataFrame())
    surv_df = filtered_data.get("Surveillance Register", pd.DataFrame())
    lessons_df = filtered_data.get("Lessons Learned", pd.DataFrame())

    return [
        {"label": "Total Projects", "value": project_count},
        {"label": "Daily Reports", "value": len(filtered_data.get("Daily Reports", pd.DataFrame()))},

        {"label": "Open NCR", "value": int((ncr_df["Status"] == "Open").sum()) if "Status" in ncr_df.columns else 0},
        {"label": "Closed NCR", "value": int((ncr_df["Status"] == "Closed").sum()) if "Status" in ncr_df.columns else 0},

        {"label": "Open OBS", "value": int((obs_df["Status"] == "Open").sum()) if "Status" in obs_df.columns else 0},
        {"label": "Closed OBS", "value": int((obs_df["Status"] == "Closed").sum()) if "Status" in obs_df.columns else 0},

        {"label": "Open ITR", "value": int((itr_df["Status"] == "Open").sum()) if "Status" in itr_df.columns else 0},
        {"label": "Closed ITR", "value": int((itr_df["Status"] == "Closed").sum()) if "Status" in itr_df.columns else 0},

        {"label": "Concrete Pours", "value": len(concrete_df)},
        {"label": "Audits Planned", "value": len(audit_df)},
        {"label": "Surveillance Planned", "value": len(surv_df)},
        {"label": "Lessons Learned", "value": len(lessons_df)},
    ]

# =========================
# SECTION WRAPPER
# =========================

# =========================
# TABLES
# =========================
SENSITIVE_COLUMN_TOKENS = (
    "password", "hash", "salt", "secret", "token", "webhook", "api_key",
    "apikey", "client_secret", "connection", "filepath", "file_path",
    "session", "internal", "_id", "rowid",
)


def current_user_role():
    return str(
        st.session_state.get("auth", {}).get("role")
        or st.session_state.get("role")
        or "viewer"
    ).strip().lower()


def can_edit_records():
    return current_user_role() in {"admin", "user", "standard", "standard user"}


def can_administer():
    return current_user_role() == "admin"


def sanitize_display_dataframe(df, columns=None, include_internal=False):
    if not isinstance(df, pd.DataFrame):
        return pd.DataFrame()
    display_df = df.copy()
    display_df = display_df.loc[:, ~display_df.columns.astype(str).duplicated()]
    if columns:
        valid_cols = [col for col in columns if col in display_df.columns]
        if valid_cols:
            display_df = display_df[valid_cols]
            display_df = display_df.loc[:, ~display_df.columns.astype(str).duplicated()]
    if not include_internal:
        keep_cols = []
        for col in display_df.columns:
            normalized = str(col).strip().lower()
            if normalized in {"id", "index"}:
                continue
            if any(token in normalized for token in SENSITIVE_COLUMN_TOKENS):
                continue
            keep_cols.append(col)
        display_df = display_df[keep_cols]
    for col in display_df.columns:
        if "date" in str(col).lower() or str(col).lower().endswith("_on"):
            try:
                series = display_df[col]
                if isinstance(series, pd.Series):
                    converted = pd.to_datetime(series, errors="coerce")
                    if converted.notna().any():
                        display_df[col] = converted.dt.strftime("%d %b %Y").fillna("")
            except (TypeError, ValueError, AttributeError):
                continue
    return display_df


def render_empty_state(title="No records found", message="No data is available for the selected filters.", action_label=None):
    action = f'<div class="empty-state__action">{html.escape(action_label)}</div>' if action_label else ""
    st.markdown(
        f"""
<div class="empty-state">
    <div class="empty-state__mark">i</div>
    <div>
        <h3>{html.escape(title)}</h3>
        <p>{html.escape(message)}</p>
        {action}
    </div>
</div>
""",
        unsafe_allow_html=True,
    )


def render_page_header(title, description="", eyebrow="QA/QC Module"):
    st.markdown(
        f"""
<div class="page-header">
    <div class="page-header__eyebrow">{html.escape(eyebrow)}</div>
    <h1>{html.escape(title)}</h1>
    {f'<p>{html.escape(description)}</p>' if description else ''}
</div>
""",
        unsafe_allow_html=True,
    )


def render_alert(message, kind="info"):
    kind = str(kind or "info").lower()
    st.markdown(
        f'<div class="app-alert app-alert--{html.escape(kind)}">{html.escape(str(message))}</div>',
        unsafe_allow_html=True,
    )


def get_theme_mode():
    mode = st.session_state.get("qaqc_theme_mode", "System")
    if mode not in {"System", "Light", "Dark"}:
        mode = "System"
    return mode


def render_theme_selector():
    current = get_theme_mode()
    options = ["System", "Light", "Dark"]
    selected = st.sidebar.selectbox(
        "Appearance",
        options,
        index=options.index(current),
        key="qaqc_theme_mode",
        help="System follows your device or browser light/dark setting.",
    )
    st.sidebar.caption(
        "System follows this device" if selected == "System" else f"{selected} mode is active"
    )


def render_dataframe(display_df, height="auto", use_container_width=True):
    kwargs = {"height": height, "hide_index": True}
    try:
        kwargs["width"] = "stretch" if use_container_width else "content"
        return st.dataframe(display_df, **kwargs)
    except TypeError:
        kwargs.pop("width", None)
        kwargs["use_container_width"] = use_container_width
        try:
            return st.dataframe(display_df, **kwargs)
        except TypeError:
            kwargs.pop("hide_index", None)
            return st.dataframe(display_df, **kwargs)


def render_table(df, height=300, columns=None, empty_message="No records found", include_internal=False):
    display_df = sanitize_display_dataframe(df, columns=columns, include_internal=include_internal)
    if isinstance(display_df, pd.DataFrame) and not display_df.empty:
        render_dataframe(display_df, height=height)
    else:
        render_empty_state("No records found", empty_message)

def render_table_with_details(
    df,
    id_col=None,
    table_columns=None,
    detail_label="Details"
):
    if not isinstance(df, pd.DataFrame) or df.empty:
        st.info("No data available")
        return None

    display_df = sanitize_display_dataframe(df, columns=table_columns, include_internal=can_administer())

    st.subheader(detail_label)
    render_dataframe(display_df)

    if id_col and id_col in df.columns:
        selected_id = st.selectbox(
            f"Select {detail_label} ID",
            df[id_col].dropna().astype(str).unique()
        )

        selected_row = df[df[id_col].astype(str) == selected_id]

        st.write("Selected Record")
        render_dataframe(sanitize_display_dataframe(selected_row, include_internal=can_administer()))

        return selected_row


# =========================
# UTILITIES
# =========================
def _find_image_path(path):
    p = Path(path)
    return str(p) if p.exists() else None

def load_company_logo(path):
    p = Path(path)
    return str(p) if p.exists() else None


def extract_projects(data):
    projects = set()

    for df in data.values():
        if isinstance(df, pd.DataFrame) and "Project" in df.columns:
            projects.update(df["Project"].dropna().astype(str))

    return sorted(projects)

# =========================
# NAV (FULL)
# =========================

def _render_navigation_legacy():
    _record_page_access()
    grouped_pages = grouped_navigation_pages()

    with st.container(key="primary_navigation_row"):
        user = st.session_state.get("auth") or {}
        nav_col, tool_col, account_col = st.columns([0.07, 0.63, 0.30], gap="small")
        with nav_col:
            with st.popover(
                "Open page navigation",
                icon=":material/menu:",
                help="Open page navigation",
                key="page_navigation_popover",
            ):
                query = (
                    st.text_input(
                        "Search pages",
                        placeholder="Search",
                        label_visibility="collapsed",
                        icon=":material/search:",
                        key=f"page_navigation_search_{_current_page_name()}",
                    )
                    or ""
                ).strip().casefold()
                suffix = _auth_query_suffix()
                sections = []
                current_page = _current_page_name()
                for group, items in grouped_pages:
                    visible_items = [
                        (label, page)
                        for label, page in items
                        if not query or query in label.casefold() or query in group.casefold()
                    ]
                    if not visible_items:
                        continue
                    link_markup = []
                    section_is_current = False
                    for label, page in visible_items:
                        href = "/" + suffix if page == "app.py" else "/" + quote(Path(page).stem) + suffix
                        page_name = "app" if page == "app.py" else Path(page).stem
                        is_current = page_name == current_page
                        section_is_current = section_is_current or is_current
                        current_attr = ' aria-current="page"' if is_current else ""
                        link_markup.append(
                            f'<a class="nav-popover-link" href="{href}" target="_self"{current_attr}>'
                            f'{html.escape(label)}</a>'
                        )
                    open_attr = " open" if query or section_is_current else ""
                    sections.append(
                        f'<details class="nav-popover-section"{open_attr}>'
                        f'<summary><span class="nav-popover-section__title">'
                        f'<span class="nav-popover-section__icon">'
                        f'{html.escape(NAVIGATION_GROUP_ICONS.get(group, "•"))}</span>'
                        f'{html.escape(group)}</span></summary>'
                        f'<div class="nav-popover-section__links">{"".join(link_markup)}</div>'
                        f'</details>'
                    )
                if sections:
                    st.markdown(
                        '<div class="nav-popover-menu">' + "".join(sections) + "</div>",
                        unsafe_allow_html=True,
                    )
                else:
                    st.caption("No pages match your search.")
        with tool_col:
            st.markdown(
                '<div class="command-tools command-tools--compact"><span>⌕</span><span>•</span><span>● Online</span></div>',
                unsafe_allow_html=True,
            )
        with account_col:
            if user.get("logged_in"):
                _render_account_menu(user)
    return
    st.markdown("### 🧭 Page Navigation", unsafe_allow_html=True)

    pages = {
        "🏗 Concrete": "pages/Concrete_Tracker.py",
        "📛 NCR": "pages/NCR_Tracker.py",
        "👁 OBS": "pages/OBS_Tracker.py",
        "📋 Audit": "pages/Audit_Surveillance.py",
        "🏠 Executive Dashboard": "app.py",
        "📊 CTQ Dashboard": "pages/CTR_Dashboard.py",
        "📅 Daily Reports": "pages/Daily_Reports.py",
        "🔧 Defect Rework": "pages/Defect_Rework_Tracker.py",
        "📄 Document Status": "pages/Document_Status.py",
        "📊 Executive Summary": "pages/Executive_Summary.py",
        "📦 ITR Tracker": "pages/ITR_Tracker.py",
        "📘 Lessons Learnt": "pages/Lessons_Learnt.py",
        "📋 Management Summary": "pages/Management_Summary.py"
    }

    for label, page in pages.items():
        if st.button(label, key=f"nav_{label}"):
            st.switch_page(page)

 


def render_navigation():
    """Render session-preserving navigation for every dashboard page."""
    _record_page_access()
    grouped_pages = grouped_navigation_pages()

    with st.container(key="primary_navigation_row"):
        user = st.session_state.get("auth") or {}
        nav_col, tool_col, account_col = st.columns([0.07, 0.63, 0.30], gap="small")
        with nav_col:
            with st.popover(
                "Open page navigation",
                icon=":material/menu:",
                help="Open page navigation",
                key="page_navigation_popover",
            ):
                with st.container(key="nav_popover_menu"):
                    query = (
                        st.text_input(
                            "Search pages",
                            placeholder="Search",
                            label_visibility="collapsed",
                            icon=":material/search:",
                            key=f"page_navigation_search_{_current_page_name()}",
                        )
                        or ""
                    ).strip().casefold()
                    current_page = _current_page_name()
                    matches = 0
                    for group, items in grouped_pages:
                        visible_items = [
                            (label, page)
                            for label, page in items
                            if not query or query in label.casefold() or query in group.casefold()
                        ]
                        if not visible_items:
                            continue
                        section_is_current = any(
                            ("app" if page == "app.py" else Path(page).stem) == current_page
                            for _, page in visible_items
                        )
                        group_icon = NAVIGATION_GROUP_ICONS.get(group, "•")
                        with st.expander(
                            f"{group_icon}  {group}",
                            expanded=bool(query or section_is_current),
                        ):
                            for label, page in visible_items:
                                st.page_link(page, label=label, width="stretch")
                                matches += 1
                    if not matches:
                        st.caption("No pages match your search.")
        with tool_col:
            st.markdown(
                '<div class="command-tools command-tools--compact"><span>⌕</span><span>•</span><span>● Online</span></div>',
                unsafe_allow_html=True,
            )
        with account_col:
            if user.get("logged_in"):
                _render_account_menu(user)


def _record_page_access():
    """Record one page view per page/session while avoiding Streamlit rerun noise."""
    user = st.session_state.get("auth") or {}
    if not user.get("logged_in"):
        return
    page = "Executive Home"
    for frame_info in inspect.stack():
        path = Path(frame_info.filename)
        if path.parent.name == "pages":
            page = path.stem.replace("_", " ")
            break
    marker = f"audit_page_view::{page}"
    if st.session_state.get(marker):
        return
    try:
        from database.audit_log import record_activity

        if record_activity("view_page", category="navigation", page=page):
            st.session_state[marker] = True
    except Exception:
        pass


def render_top_nav():
    render_header()

    pages = get_navigation_pages()
    grouped_pages = grouped_navigation_pages()
    user = st.session_state.get("auth")
    nlng_src = _image_data_uri(NLNG_LOGO)
    nlng_brand = f'<img class="side-brand__logo" src="{nlng_src}" alt="NLNG">' if nlng_src else '<div class="side-brand__name">NLNG</div>'

    st.sidebar.markdown(
        f"""
<div class="side-brand">
    {nlng_brand}
    <div>
        <div class="side-brand__name">NLNG</div>
        <div class="side-brand__sub">QA/QC Command Centre</div>
    </div>
</div>
""",
        unsafe_allow_html=True,
    )

    if user:
        photo = user.get("profile_photo")
        photo_html = ""
        photo_src = _profile_photo_src(photo)
        if photo_src:
            photo_html = f'<img class="sidebar-profile__photo" src="{photo_src}" alt="Profile photo">'
        else:
            initials = "".join(part[:1] for part in str(user.get("name", "User")).split()[:2]).upper() or "U"
            photo_html = f'<div class="profile-avatar sidebar-profile__initials">{html.escape(initials)}</div>'
        st.sidebar.markdown(
            f"""
<div class="sidebar-profile">
    {photo_html}
    <div>
        <div class="sidebar-profile__name">{html.escape(str(user.get("name", "User")))}</div>
        <div class="sidebar-profile__meta">{html.escape(str(user.get("role", "user")).title())} | {html.escape(str(user.get("discipline", "QA/QC")))}</div>
    </div>
</div>
""",
            unsafe_allow_html=True,
        )
        if st.sidebar.button("Sign out", key="global_sidebar_sign_out", width="stretch"):
            import auth

            auth.sign_out()
            st.rerun()

    st.sidebar.markdown('<div class="side-menu-title">Appearance</div>', unsafe_allow_html=True)
    render_theme_selector()
    st.sidebar.markdown('<div class="side-menu-title">Menu</div>', unsafe_allow_html=True)

    for group, items in grouped_pages:
        st.sidebar.markdown(f'<div class="side-nav-group">{html.escape(group)}</div>', unsafe_allow_html=True)
        for label, page in items:
            st.sidebar.page_link(page, label=label, width="stretch")

    st.sidebar.markdown(
        f"""
<div class="side-status side-status--footer">
    <strong>Evomec Global</strong><br>
    Services Limited<br><br>
    © 2026 Evomec Global Services Limited.<br>
    All rights reserved.<br>
    {len(pages)} modules available
</div>
""",
        unsafe_allow_html=True,
    )
    
def render_drilldown(df, id_col="ID"):

    if not isinstance(df, pd.DataFrame) or df.empty:
        st.info("No data available")
        return

    if id_col not in df.columns:
        st.error(f"Column '{id_col}' not found")
        return


    # =========================
    # SAFE ID CLEANING
    # =========================
    ids = df[id_col].dropna().astype(str).unique().tolist()

    selected = st.selectbox(
    f"Select {id_col}",
    options=["-- Select --"] + ids,
    key=f"drilldown_{id_col}"
)

    if selected == "-- Select --":
        st.warning("Please select a record to view details")
        return

    # =========================
    # FILTER SAFE MATCH
    # =========================
    selected_row = df[df[id_col].astype(str) == selected]

    # =========================
    # UX IMPROVEMENT: SUMMARY FIRST
    # =========================
    st.subheader("🔎 Record Summary")

    st.dataframe(
        selected_row.head(1),
        width="stretch"
    )

def project_filter_sidebar(projects, page="main"):
    if "global_project" not in st.session_state:
        st.session_state.global_project = "All"

    selected = st.sidebar.selectbox(
        "Project",
        ["All"] + projects,
        index=(
            ["All"] + projects).index(st.session_state.global_project)
            if st.session_state.global_project in projects
            else 0,
        key=f"global_project_filter_{page}"
    )

    st.session_state.global_project = selected
    return selected
# =========================
# UI STYLING
# =========================
def inject_global_ui():
    try:
        import plotly.io as pio
        pio.templates.default = "plotly_dark" if get_theme_mode() == "Dark" else "plotly_white"
    except Exception:
        pass
    st.markdown(
    """
    <style>
    :root {
        --bg: #08111f;
        --panel: #0f1b2d;
        --panel-soft: #13243a;
        --line: rgba(148, 163, 184, 0.18);
        --text: #e5edf8;
        --muted: #94a3b8;
        --accent: #38bdf8;
        --success: #22c55e;
        --warning: #f59e0b;
        --danger: #ef4444;
    }

    #MainMenu, footer, header {
        visibility: hidden;
    }

    [data-testid="stSidebarNav"],
    [data-testid="stSidebarNavItems"],
    [data-testid="stSidebarNavLinkContainer"],
    [data-testid="stSidebarNavLink"] {
        display: none !important;
    }

    .stApp {
        background:
            radial-gradient(circle at top left, rgba(56, 189, 248, 0.16), transparent 34rem),
            linear-gradient(135deg, #07101e 0%, #0b1728 48%, #111827 100%);
        color: var(--text);
    }

    .block-container {
        max-width: 1480px;
        padding: 1.15rem 2.25rem 2.5rem;
    }

    h1, h2, h3, h4, p, label, span {
        letter-spacing: 0;
    }

    h1, h2, h3 {
        color: #f8fafc;
    }

    .app-bar {
        align-items: center;
        background: rgba(15, 27, 45, 0.82);
        border: 1px solid var(--line);
        border-radius: 8px;
        box-shadow: 0 18px 45px rgba(0, 0, 0, 0.26);
        display: flex;
        justify-content: space-between;
        margin-bottom: 0.9rem;
        padding: 0.85rem 1rem;
    }

    .app-bar__eyebrow, .hero-eyebrow {
        color: #7dd3fc;
        font-size: 0.72rem;
        font-weight: 760;
        letter-spacing: 0.06em;
        text-transform: uppercase;
    }

    .app-bar__title {
        color: #f8fafc;
        font-size: 1.05rem;
        font-weight: 780;
        margin-top: 0.12rem;
    }

    .app-bar__status {
        background: rgba(34, 197, 94, 0.12);
        border: 1px solid rgba(34, 197, 94, 0.28);
        border-radius: 999px;
        color: #bbf7d0;
        font-size: 0.78rem;
        font-weight: 700;
        padding: 0.42rem 0.72rem;
        white-space: nowrap;
    }

    .nav-hint {
        align-items: center;
        border: 1px solid var(--line);
        border-radius: 8px;
        color: var(--muted);
        display: flex;
        min-height: 2.65rem;
        padding: 0 0.9rem;
    }

    .dashboard-hero {
        background: linear-gradient(135deg, rgba(15, 27, 45, 0.96), rgba(19, 36, 58, 0.76));
        border: 1px solid var(--line);
        border-radius: 8px;
        box-shadow: 0 22px 55px rgba(0, 0, 0, 0.28);
        min-height: 9.25rem;
        padding: 1.35rem 1.5rem;
    }

    .dashboard-hero h1 {
        color: #f8fafc;
        font-size: 2.2rem;
        font-weight: 800;
        line-height: 1.08;
        margin: 0.35rem 0 0.55rem;
    }

    .dashboard-hero p {
        color: #b6c2d2;
        font-size: 0.98rem;
        margin: 0;
        max-width: 780px;
    }

    .logo-panel {
        align-items: center;
        background: rgba(248, 250, 252, 0.92);
        border: 1px solid rgba(255, 255, 255, 0.34);
        border-radius: 8px;
        display: flex;
        justify-content: center;
        min-height: 9.25rem;
        padding: 1rem;
    }

    .section-heading {
        color: #f8fafc;
        font-size: 1.05rem;
        font-weight: 780;
        margin: 1.25rem 0 0.55rem;
    }

    .section-caption {
        color: var(--muted);
        font-size: 0.86rem;
        margin-top: -0.3rem;
        margin-bottom: 0.65rem;
    }

    .kpi-card {
        background: linear-gradient(180deg, rgba(19, 36, 58, 0.96), rgba(10, 19, 33, 0.98));
        border: 1px solid var(--line);
        border-radius: 8px;
        box-shadow: 0 14px 32px rgba(0, 0, 0, 0.28);
        min-height: 104px;
        overflow: hidden;
        padding: 15px 16px 16px;
        position: relative;
        transition: transform 0.2s ease, border-color 0.2s ease, box-shadow 0.2s ease;
    }

    .kpi-card:hover {
        border-color: var(--accent);
        box-shadow: 0 18px 42px rgba(0, 0, 0, 0.34);
        transform: translateY(-3px);
    }

    .kpi-card__topline {
        background: var(--accent);
        height: 3px;
        left: 0;
        position: absolute;
        right: 0;
        top: 0;
    }

    .kpi-title {
        color: #aab8ca;
        font-size: 0.78rem;
        font-weight: 720;
        margin-top: 0.25rem;
        text-transform: uppercase;
    }

    .kpi-value {
        color: #f8fafc;
        font-size: 1.9rem;
        font-weight: 800;
        line-height: 1;
        margin-top: 0.75rem;
    }

    section[data-testid="stSidebar"] {
        background: linear-gradient(180deg, #0b1628, #101827);
        border-right: 1px solid var(--line);
    }

    section[data-testid="stSidebar"] h1,
    section[data-testid="stSidebar"] h2,
    section[data-testid="stSidebar"] h3,
    section[data-testid="stSidebar"] label,
    section[data-testid="stSidebar"] p,
    section[data-testid="stSidebar"] span {
        color: #e5edf8;
    }

    div[data-testid="stMetric"] {
        background: rgba(15, 27, 45, 0.88);
        border: 1px solid var(--line);
        border-radius: 8px;
        padding: 0.85rem 1rem;
    }

    div[data-testid="stMetricLabel"] {
        color: var(--muted);
    }

    div[data-testid="stDataFrame"] {
        border: 1px solid var(--line);
        border-radius: 8px;
        overflow: hidden;
    }

    .stButton button,
    div[data-testid="stPopover"] button {
        background: linear-gradient(135deg, #0ea5e9, #2563eb);
        border: 1px solid rgba(255, 255, 255, 0.12);
        border-radius: 8px;
        color: white;
        font-weight: 720;
        min-height: 2.45rem;
    }

    .stButton button:hover,
    div[data-testid="stPopover"] button:hover {
        border-color: rgba(125, 211, 252, 0.72);
        color: white;
        filter: brightness(1.06);
    }

    div[data-baseweb="select"] > div {
        background-color: rgba(15, 27, 45, 0.96);
        border-color: var(--line);
        border-radius: 8px;
    }

    div[data-baseweb="select"] span {
        color: #e5edf8;
    }

    .stAlert {
        border-radius: 8px;
    }

    div[role="radiogroup"] {
        display: flex;
        flex-wrap: wrap;
        gap: 0.45rem;
        margin: 0.35rem 0 0.85rem;
    }

    div[role="radiogroup"] label {
        background: rgba(14, 165, 233, 0.12);
        border: 1px solid rgba(56, 189, 248, 0.22);
        border-radius: 999px;
        color: var(--text);
        min-height: 2.35rem;
        padding: 0.35rem 0.65rem;
    }

    @media (max-width: 900px) {
        .block-container {
            padding: 0.8rem 1rem 2rem;
        }

        .app-bar {
            align-items: flex-start;
            flex-direction: column;
            gap: 0.65rem;
        }

        .dashboard-hero h1 {
            font-size: 1.65rem;
        }

        .auth-panel,
        .auth-panel--hero {
            padding: 1rem;
        }

        .auth-panel h1 {
            font-size: 1.45rem;
        }

        div[data-testid="stTabs"] div[role="tablist"] {
            gap: 0.35rem;
            overflow-x: auto;
            white-space: nowrap;
        }

        div[data-testid="stTabs"] button[role="tab"] {
            min-width: max-content;
        }
    }

    .auth-shell {
        margin: 0.25rem 0 1rem;
    }

    .auth-panel,
    .tool-card,
    .standard-card,
    .learning-card,
    .security-card {
        background: color-mix(in srgb, var(--panel) 92%, transparent);
        border: 1px solid var(--line);
        border-radius: 8px;
        box-shadow: 0 16px 38px rgba(2, 8, 23, 0.18);
        padding: 1rem;
    }

    .auth-panel--hero {
        padding: 1.35rem 1.4rem;
    }

    .auth-panel h1 {
        color: var(--text);
        font-size: 2rem;
        line-height: 1.1;
        margin: 0.35rem 0 0.55rem;
    }

    .auth-eyebrow,
    .card-eyebrow {
        color: var(--accent);
        font-size: 0.72rem;
        font-weight: 780;
        letter-spacing: 0.06em;
        text-transform: uppercase;
    }

    .security-list {
        display: flex;
        flex-wrap: wrap;
        gap: 0.5rem;
        margin-top: 1rem;
    }

    .security-list span,
    .standard-tag {
        background: rgba(56, 189, 248, 0.1);
        border: 1px solid rgba(56, 189, 248, 0.24);
        border-radius: 999px;
        color: var(--text);
        font-size: 0.78rem;
        font-weight: 700;
        padding: 0.34rem 0.58rem;
    }

    .profile-avatar {
        align-items: center;
        background: linear-gradient(135deg, #0ea5e9, #22c55e);
        border: 2px solid rgba(255, 255, 255, 0.44);
        border-radius: 999px;
        color: white;
        display: flex;
        font-size: 1.3rem;
        font-weight: 800;
        height: 86px;
        justify-content: center;
        margin-bottom: 0.7rem;
        width: 86px;
    }

    .tool-grid {
        display: grid;
        gap: 0.85rem;
        grid-template-columns: repeat(auto-fit, minmax(230px, 1fr));
        margin: 0.8rem 0 1rem;
    }

    .tool-card h3,
    .standard-card h3,
    .learning-card h3,
    .security-card h3 {
        color: var(--text);
        font-size: 1rem;
        margin: 0.35rem 0 0.35rem;
    }

    .tool-card p,
    .standard-card p,
    .learning-card p,
    .security-card p {
        color: var(--muted);
        font-size: 0.88rem;
        margin: 0;
    }

    .standard-card,
    .learning-card {
        margin-bottom: 0.75rem;
    }

    .spotlight-grid {
        display: grid;
        gap: 0.95rem;
        grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
        margin: 0.95rem 0 1.1rem;
    }

    .spotlight-card {
        background:
            linear-gradient(135deg, rgba(56, 189, 248, 0.16), transparent 46%),
            color-mix(in srgb, var(--panel) 94%, transparent);
        border: 1px solid var(--line);
        border-radius: 8px;
        box-shadow: 0 18px 46px rgba(2, 8, 23, 0.2);
        min-height: 154px;
        overflow: hidden;
        padding: 1.05rem;
        position: relative;
        transition: transform 0.28s ease, box-shadow 0.28s ease, border-color 0.28s ease;
    }

    .spotlight-card::after {
        background: radial-gradient(circle, rgba(255, 255, 255, 0.16), transparent 64%);
        content: "";
        height: 140px;
        position: absolute;
        right: -48px;
        top: -48px;
        transition: transform 0.32s ease, opacity 0.32s ease;
        width: 140px;
    }

    .spotlight-card:hover,
    .tool-card:hover,
    .standard-card:hover,
    .learning-card:hover,
    .security-card:hover {
        border-color: rgba(56, 189, 248, 0.58);
        box-shadow: 0 24px 60px rgba(2, 8, 23, 0.28);
        transform: translateY(-5px);
    }

    .spotlight-card:hover::after {
        opacity: 0.9;
        transform: scale(1.16);
    }

    .spotlight-card h3 {
        color: var(--text);
        font-size: 1.06rem;
        margin: 0.42rem 0 0.42rem;
        position: relative;
        z-index: 1;
    }

    .spotlight-card p {
        color: var(--muted);
        font-size: 0.88rem;
        margin: 0;
        position: relative;
        z-index: 1;
    }

    .interactive-chip {
        background: rgba(14, 165, 233, 0.12);
        border: 1px solid rgba(56, 189, 248, 0.22);
        border-radius: 999px;
        color: var(--text);
        display: inline-flex;
        font-size: 0.78rem;
        font-weight: 720;
        margin: 0.24rem 0.24rem 0 0;
        padding: 0.34rem 0.58rem;
    }

    .smooth-panel {
        animation: panelFadeIn 0.42s ease both;
    }

    @keyframes panelFadeIn {
        from {
            opacity: 0;
            transform: translateY(8px);
        }
        to {
            opacity: 1;
            transform: translateY(0);
        }
    }

    @media (prefers-color-scheme: light) {
        :root {
            --bg: #f6f8fb;
            --panel: #ffffff;
            --panel-soft: #edf3f8;
            --line: rgba(15, 23, 42, 0.12);
            --text: #0f172a;
            --muted: #475569;
            --accent: #0369a1;
            --success: #15803d;
            --warning: #b45309;
            --danger: #b91c1c;
        }

        .stApp {
            background:
                radial-gradient(circle at top left, rgba(14, 165, 233, 0.14), transparent 30rem),
                linear-gradient(135deg, #f8fafc 0%, #edf3f8 52%, #ffffff 100%);
            color: var(--text);
        }

        h1, h2, h3,
        .app-bar__title,
        .dashboard-hero h1,
        .kpi-value,
        .tool-card h3,
        .standard-card h3,
        .learning-card h3 {
            color: var(--text);
        }

        .app-bar,
        .dashboard-hero,
        .kpi-card,
        div[data-testid="stMetric"],
        .auth-panel,
        .tool-card,
        .standard-card,
        .learning-card,
        .security-card {
            background: rgba(255, 255, 255, 0.92);
            box-shadow: 0 14px 34px rgba(15, 23, 42, 0.08);
        }

        .dashboard-hero p,
        .section-caption,
        .kpi-title,
        .nav-hint,
        .tool-card p,
        .standard-card p,
        .learning-card p,
        .security-card p {
            color: var(--muted);
        }

        section[data-testid="stSidebar"] {
            background: linear-gradient(180deg, #ffffff, #eef5fb);
        }

        section[data-testid="stSidebar"] h1,
        section[data-testid="stSidebar"] h2,
        section[data-testid="stSidebar"] h3,
        section[data-testid="stSidebar"] label,
        section[data-testid="stSidebar"] p,
        section[data-testid="stSidebar"] span {
            color: var(--text);
        }
    }

    /* Executive dashboard skin */
    .stApp {
        background: #f3f6fb;
        color: #102033;
    }

    .block-container {
        max-width: 1560px;
        padding: 0.9rem 1.15rem 2rem;
    }

    h1, h2, h3 {
        color: #102033;
    }

    .app-bar {
        background: rgba(255, 255, 255, 0.96);
        border: 1px solid rgba(15, 23, 42, 0.08);
        border-radius: 8px;
        box-shadow: 0 10px 26px rgba(15, 23, 42, 0.08);
        color: #102033;
        margin-bottom: 0.75rem;
    }

    .app-bar__eyebrow {
        color: #0f6eb8;
    }

    .app-bar__title {
        color: #102033;
        font-size: 1.12rem;
    }

    .app-bar__status {
        background: #eef6ff;
        border-color: #cfe7ff;
        color: #0f6eb8;
    }

    section[data-testid="stSidebar"] {
        background: linear-gradient(180deg, #09213b 0%, #06182e 100%);
        border-right: 1px solid rgba(255, 255, 255, 0.08);
    }

    section[data-testid="stSidebar"] .stButton button {
        background: transparent;
        border: 0;
        border-radius: 8px;
        box-shadow: none;
        color: #d7e7f7;
        font-size: 0.88rem;
        font-weight: 650;
        justify-content: flex-start;
        min-height: 2.35rem;
        padding-left: 0.85rem;
        text-align: left;
        width: 100%;
    }

    section[data-testid="stSidebar"] .stButton button:hover {
        background: linear-gradient(135deg, #1d73e8, #1596d4);
        color: #ffffff;
        filter: none;
    }

    section[data-testid="stSidebar"] a,
    section[data-testid="stSidebar"] a:visited,
    section[data-testid="stSidebar"] a span,
    section[data-testid="stSidebar"] [data-testid="stPageLink"] a,
    section[data-testid="stSidebar"] [data-testid="stPageLink"] a:visited,
    section[data-testid="stSidebar"] [data-testid="stPageLink"] a span,
    section[data-testid="stSidebar"] [data-testid="stPageLink"] p {
        color: #eaf6ff !important;
        opacity: 1 !important;
    }

    section[data-testid="stSidebar"] [data-testid="stPageLink"] a {
        border-radius: 8px;
        min-height: 2.35rem;
        padding: 0.45rem 0.7rem;
        transition: background 0.18s ease, box-shadow 0.18s ease, color 0.18s ease, transform 0.18s ease;
    }

    section[data-testid="stSidebar"] [data-testid="stPageLink"] a:hover,
    section[data-testid="stSidebar"] [data-testid="stPageLink"] a[aria-current="page"] {
        background: linear-gradient(135deg, rgba(37, 99, 235, 0.82), rgba(14, 165, 233, 0.82));
        box-shadow: 0 12px 24px rgba(8, 26, 51, 0.34);
        color: #ffffff !important;
        transform: translateX(3px);
    }

    section[data-testid="stSidebar"] [data-testid="stPageLink"] a:hover span,
    section[data-testid="stSidebar"] [data-testid="stPageLink"] a:hover p,
    section[data-testid="stSidebar"] [data-testid="stPageLink"] a[aria-current="page"] span,
    section[data-testid="stSidebar"] [data-testid="stPageLink"] a[aria-current="page"] p {
        color: #ffffff !important;
    }

    .side-brand {
        align-items: center;
        border-bottom: 1px solid rgba(255, 255, 255, 0.1);
        display: flex;
        gap: 0.7rem;
        margin-bottom: 0.9rem;
        padding: 0.35rem 0 0.95rem;
    }

    .side-brand__mark {
        align-items: center;
        background: linear-gradient(135deg, #f97316, #0ea5e9);
        border-radius: 8px;
        color: #ffffff;
        display: flex;
        font-size: 1.1rem;
        font-weight: 900;
        height: 2.35rem;
        justify-content: center;
        width: 2.35rem;
    }

    .side-brand__name {
        color: #ffffff;
        font-size: 1.05rem;
        font-weight: 820;
        letter-spacing: 0.02em;
    }

    .side-brand__sub {
        color: #9fb8d3;
        font-size: 0.72rem;
        margin-top: 0.1rem;
    }

    .side-menu-title {
        color: #6fd3ff;
        font-size: 0.72rem;
        font-weight: 800;
        letter-spacing: 0.08em;
        margin: 0.35rem 0 0.45rem;
        text-transform: uppercase;
    }

    .side-nav-link {
        border-radius: 8px;
        color: #d7e7f7 !important;
        display: block;
        font-size: 0.88rem;
        font-weight: 650;
        margin: 0.08rem 0;
        padding: 0.58rem 0.85rem;
        text-decoration: none !important;
        transition: background 0.18s ease, color 0.18s ease;
    }

    .side-nav-link:hover {
        background: linear-gradient(135deg, #1d73e8, #1596d4);
        color: #ffffff !important;
    }

    .nav-go-link {
        background: linear-gradient(135deg, #0ea5e9, #2563eb);
        border-radius: 8px;
        color: #ffffff !important;
        display: block;
        font-weight: 760;
        margin-top: 0.65rem;
        padding: 0.68rem 0.85rem;
        text-align: center;
        text-decoration: none !important;
    }

    .side-status {
        background: rgba(15, 118, 110, 0.18);
        border: 1px solid rgba(45, 212, 191, 0.24);
        border-radius: 8px;
        color: #b7f5ef;
        font-size: 0.78rem;
        margin-top: 0.9rem;
        padding: 0.75rem;
    }

    .dashboard-shell {
        display: grid;
        gap: 0.9rem;
        grid-template-columns: minmax(0, 1fr) 250px;
    }

    .dashboard-main {
        min-width: 0;
    }

    .dashboard-side {
        min-width: 0;
    }

    .metric-grid {
        display: grid;
        gap: 1rem;
        grid-template-columns: repeat(4, minmax(0, 1fr));
        margin-bottom: 1rem;
        padding-bottom: 0.35rem;
    }

    .exec-metric {
        align-items: center;
        background: linear-gradient(145deg, #ffffff 0%, #f8fbff 100%);
        border: 1px solid rgba(15, 23, 42, 0.12);
        border-radius: 8px;
        box-shadow:
            0 1px 0 rgba(255, 255, 255, 0.98) inset,
            0 4px 0 rgba(148, 163, 184, 0.36),
            0 14px 24px rgba(15, 23, 42, 0.18),
            0 24px 44px rgba(15, 23, 42, 0.09);
        display: flex;
        gap: 0.8rem;
        min-height: 5.6rem;
        padding: 0.85rem;
        position: relative;
        transform: translateY(0);
        transform-style: preserve-3d;
        transition: border-color 0.18s ease, box-shadow 0.18s ease, transform 0.18s ease;
        z-index: 0;
    }

    .exec-metric::after {
        background: linear-gradient(180deg, rgba(148, 163, 184, 0.28), rgba(15, 23, 42, 0.16));
        border-radius: 8px;
        bottom: -0.45rem;
        box-shadow: 0 14px 24px rgba(15, 23, 42, 0.16);
        content: "";
        height: 0.9rem;
        left: 0.5rem;
        position: absolute;
        right: 0.5rem;
        transform: skewX(-8deg);
        transition: background 0.18s ease, box-shadow 0.18s ease, transform 0.18s ease;
        z-index: -1;
    }

    .exec-metric:hover {
        border-color: color-mix(in srgb, var(--metric-color, #2563eb) 34%, rgba(15, 23, 42, 0.08));
        box-shadow:
            0 1px 0 rgba(255, 255, 255, 0.98) inset,
            0 8px 0 color-mix(in srgb, var(--metric-color, #2563eb) 36%, rgba(15, 23, 42, 0.18)),
            0 26px 40px rgba(15, 23, 42, 0.24),
            0 18px 32px color-mix(in srgb, var(--metric-color, #2563eb) 26%, transparent);
        transform: perspective(850px) translateY(-7px) rotateX(3deg);
    }

    .exec-metric:hover::after {
        background: linear-gradient(180deg, color-mix(in srgb, var(--metric-color, #2563eb) 26%, rgba(148, 163, 184, 0.2)), rgba(15, 23, 42, 0.2));
        box-shadow: 0 22px 32px color-mix(in srgb, var(--metric-color, #2563eb) 18%, rgba(15, 23, 42, 0.18));
        transform: translateY(0.18rem) skewX(-8deg);
    }

    .exec-metric__icon {
        align-items: center;
        background: var(--metric-color, #2563eb);
        border-radius: 8px;
        box-shadow:
            0 4px 0 color-mix(in srgb, var(--metric-color, #2563eb) 62%, #0f172a),
            0 12px 22px color-mix(in srgb, var(--metric-color, #2563eb) 32%, transparent);
        color: #ffffff;
        display: flex;
        font-size: 1.15rem;
        font-weight: 900;
        height: 2.7rem;
        justify-content: center;
        transition: box-shadow 0.18s ease, transform 0.18s ease;
        width: 2.7rem;
    }

    .exec-metric:hover .exec-metric__icon {
        box-shadow:
            0 6px 0 color-mix(in srgb, var(--metric-color, #2563eb) 62%, #0f172a),
            0 18px 28px color-mix(in srgb, var(--metric-color, #2563eb) 38%, transparent);
        transform: translateY(-2px) scale(1.04);
    }

    .exec-metric__label {
        color: #1f2f44;
        font-size: 0.78rem;
        font-weight: 800;
    }

    .exec-metric__value {
        color: #0f172a;
        font-size: 1.95rem;
        font-weight: 900;
        line-height: 1;
        margin-top: 0.25rem;
    }

    .exec-metric__sub {
        color: #64748b;
        font-size: 0.72rem;
        margin-top: 0.25rem;
    }

    .exec-panel {
        background: linear-gradient(145deg, #ffffff 0%, #f8fbff 100%);
        border: 1px solid rgba(15, 23, 42, 0.09);
        border-radius: 8px;
        box-shadow:
            0 2px 0 rgba(255, 255, 255, 0.98) inset,
            0 7px 0 rgba(15, 23, 42, 0.08),
            0 24px 38px rgba(15, 23, 42, 0.16),
            inset 0 1px 0 rgba(255, 255, 255, 0.95);
        padding: 0.95rem;
        position: relative;
        transform: translateY(0);
        transform-style: preserve-3d;
        transition: border-color 0.18s ease, box-shadow 0.18s ease, transform 0.18s ease;
    }

    .exec-panel:hover {
        border-color: rgba(14, 165, 233, 0.3);
        box-shadow:
            0 2px 0 rgba(255, 255, 255, 0.98) inset,
            0 11px 0 rgba(14, 165, 233, 0.16),
            0 36px 54px rgba(15, 23, 42, 0.24),
            0 18px 34px rgba(14, 165, 233, 0.16),
            inset 0 1px 0 rgba(255, 255, 255, 0.98);
        transform: perspective(900px) translateY(-7px) rotateX(2deg);
    }

    .exec-panel h3 {
        color: #102033;
        font-size: 0.95rem;
        font-weight: 900;
        margin: 0 0 0.75rem;
        text-transform: uppercase;
    }

    .score-ring {
        align-items: center;
        background:
            radial-gradient(circle at center, #ffffff 55%, transparent 57%),
            conic-gradient(#27ae60 0 83%, #e5edf5 83% 100%);
        box-shadow:
            0 18px 30px rgba(39, 174, 96, 0.18),
            inset 0 0 0 1px rgba(15, 23, 42, 0.04);
        border-radius: 999px;
        color: #102033;
        display: flex;
        flex-direction: column;
        font-size: 2rem;
        font-weight: 900;
        height: 8.25rem;
        justify-content: center;
        margin: 0.6rem auto;
        width: 8.25rem;
    }

    .score-ring span {
        color: #64748b;
        font-size: 0.72rem;
        font-weight: 800;
    }

    .status-row {
        align-items: center;
        border-bottom: 1px solid #edf2f7;
        color: #102033;
        display: flex;
        justify-content: space-between;
        padding: 0.45rem 0;
    }

    .status-row strong {
        color: #0f172a;
    }

    .status-dot {
        border-radius: 999px;
        display: inline-flex;
        height: 0.62rem;
        margin-right: 0.42rem;
        width: 0.62rem;
    }

    .module-grid {
        display: grid;
        gap: 0.75rem;
        grid-template-columns: repeat(5, minmax(0, 1fr));
        margin-top: 0.75rem;
    }

    .module-card {
        background: linear-gradient(145deg, #ffffff 0%, #f8fbff 100%);
        border: 1px solid rgba(15, 23, 42, 0.09);
        border-radius: 8px;
        box-shadow:
            0 2px 0 rgba(255, 255, 255, 0.98) inset,
            0 7px 0 rgba(15, 23, 42, 0.08),
            0 22px 34px rgba(15, 23, 42, 0.16),
            inset 0 1px 0 rgba(255, 255, 255, 0.95);
        min-height: 9.75rem;
        padding: 0.85rem;
        position: relative;
        transform: translateY(0);
        transform-style: preserve-3d;
        transition: border-color 0.18s ease, box-shadow 0.18s ease, transform 0.18s ease;
    }

    .module-card:hover {
        border-color: color-mix(in srgb, var(--module-color, #2563eb) 34%, rgba(15, 23, 42, 0.08));
        box-shadow:
            0 2px 0 rgba(255, 255, 255, 0.98) inset,
            0 11px 0 color-mix(in srgb, var(--module-color, #2563eb) 22%, rgba(15, 23, 42, 0.12)),
            0 34px 48px rgba(15, 23, 42, 0.24),
            0 18px 32px color-mix(in srgb, var(--module-color, #2563eb) 22%, transparent),
            inset 0 1px 0 rgba(255, 255, 255, 0.98);
        transform: perspective(900px) translateY(-8px) rotateX(2deg);
    }

    .module-card h3 {
        color: var(--module-color, #2563eb);
        font-size: 0.78rem;
        font-weight: 900;
        margin: 0 0 0.7rem;
        text-transform: uppercase;
    }

    .module-card__stat {
        align-items: center;
        border: 1px solid #edf2f7;
        border-radius: 8px;
        display: flex;
        justify-content: space-between;
        margin-bottom: 0.45rem;
        padding: 0.42rem 0.5rem;
    }

    .module-card__stat strong {
        color: #0f172a;
        font-size: 1rem;
    }

    .module-card__bar {
        background: #eaf1f8;
        border-radius: 999px;
        height: 0.42rem;
        margin: 0.55rem 0;
        overflow: hidden;
    }

    .module-card__bar div,
    .module-card__bar span {
        background: var(--module-color, #2563eb);
        display: block;
        height: 100%;
    }

    @media (prefers-color-scheme: dark) {
        .exec-metric,
        .exec-panel,
        .module-card {
            background: linear-gradient(145deg, #102033 0%, #0b1727 100%);
            border-color: rgba(148, 163, 184, 0.2);
            box-shadow:
                0 18px 34px rgba(0, 0, 0, 0.35),
                inset 0 1px 0 rgba(255, 255, 255, 0.06);
        }

        .exec-metric__label,
        .exec-panel h3,
        .status-row,
        .module-card__stat,
        .module-card__stat strong,
        .status-row strong,
        .score-ring {
            color: #f8fafc;
        }

        .exec-metric__value {
            color: #ffffff;
        }

        .exec-metric__sub,
        .score-ring span {
            color: #cbd5e1;
        }

        .score-ring {
            background:
                radial-gradient(circle at center, #102033 55%, transparent 57%),
                conic-gradient(#27ae60 0 83%, #334155 83% 100%);
        }

        .status-row {
            border-bottom-color: rgba(148, 163, 184, 0.22);
        }

        .module-card__stat {
            border-color: rgba(148, 163, 184, 0.22);
        }

        .module-card__bar {
            background: #253449;
        }
    }

    @media (max-width: 1180px) {
        .dashboard-shell {
            grid-template-columns: 1fr;
        }

        .metric-grid,
        .module-grid {
            grid-template-columns: repeat(2, minmax(0, 1fr));
        }
    }

    @media (max-width: 760px) {
        .metric-grid,
        .module-grid {
            grid-template-columns: 1fr;
        }

        .app-bar {
            display: block;
        }

        .block-container {
            padding: 0.75rem 0.75rem 1.5rem;
        }
    }

    section[data-testid="stSidebar"] a,
    section[data-testid="stSidebar"] a:visited,
    section[data-testid="stSidebar"] a *,
    section[data-testid="stSidebar"] [role="link"],
    section[data-testid="stSidebar"] [role="link"] *,
    section[data-testid="stSidebar"] [data-testid*="stPageLink"],
    section[data-testid="stSidebar"] [data-testid*="stPageLink"] *,
    section[data-testid="stSidebar"] [data-testid*="stSidebarNavLink"],
    section[data-testid="stSidebar"] [data-testid*="stSidebarNavLink"] * {
        color: #eaf6ff !important;
        opacity: 1 !important;
        text-shadow: 0 1px 1px rgba(0, 0, 0, 0.2);
    }

    section[data-testid="stSidebar"] a,
    section[data-testid="stSidebar"] [role="link"],
    section[data-testid="stSidebar"] [data-testid*="stPageLink"] a {
        border-radius: 8px !important;
        color: #eaf6ff !important;
        transition: background 0.18s ease, box-shadow 0.18s ease, color 0.18s ease, transform 0.18s ease !important;
    }

    section[data-testid="stSidebar"] a[href="/"],
    section[data-testid="stSidebar"] a[href$="localhost:8501/"],
    section[data-testid="stSidebar"] a[href$="/QAQC_Dashboard/"] {
        background: rgba(148, 163, 184, 0.14) !important;
        box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.08) !important;
    }

    section[data-testid="stSidebar"] a:hover,
    section[data-testid="stSidebar"] a:focus-visible,
    section[data-testid="stSidebar"] [role="link"]:hover,
    section[data-testid="stSidebar"] [data-testid*="stPageLink"]:hover,
    section[data-testid="stSidebar"] a[aria-current="page"] {
        background: linear-gradient(135deg, #2563eb 0%, #0ea5e9 100%) !important;
        box-shadow:
            0 2px 0 rgba(255, 255, 255, 0.16) inset,
            0 6px 0 rgba(4, 21, 44, 0.34),
            0 18px 28px rgba(2, 132, 199, 0.28) !important;
        color: #ffffff !important;
        transform: perspective(600px) translateX(5px) translateY(-2px) rotateY(-3deg) !important;
    }

    section[data-testid="stSidebar"] a:hover *,
    section[data-testid="stSidebar"] a:focus-visible *,
    section[data-testid="stSidebar"] [role="link"]:hover *,
    section[data-testid="stSidebar"] [data-testid*="stPageLink"]:hover *,
    section[data-testid="stSidebar"] a[aria-current="page"] * {
        color: #ffffff !important;
    }

    section[data-testid="stSidebar"] {
        background: linear-gradient(180deg, #f3f4f6 0%, #e5e7eb 100%) !important;
        border-right: 1px solid rgba(148, 163, 184, 0.42) !important;
    }

    section[data-testid="stSidebar"] h1,
    section[data-testid="stSidebar"] h2,
    section[data-testid="stSidebar"] h3,
    section[data-testid="stSidebar"] label,
    section[data-testid="stSidebar"] p,
    section[data-testid="stSidebar"] span,
    section[data-testid="stSidebar"] a,
    section[data-testid="stSidebar"] a:visited,
    section[data-testid="stSidebar"] a *,
    section[data-testid="stSidebar"] [role="link"],
    section[data-testid="stSidebar"] [role="link"] * {
        color: #111827 !important;
        opacity: 1 !important;
        text-shadow: none !important;
    }

    .side-brand {
        border-bottom-color: rgba(148, 163, 184, 0.5) !important;
    }

    .side-brand__name {
        color: #0f172a !important;
    }

    .side-brand__sub {
        color: #334155 !important;
    }

    .side-menu-title {
        color: #0369a1 !important;
    }

    .side-nav-link {
        color: #111827 !important;
    }

    .side-nav-link[href="/"] {
        background: rgba(148, 163, 184, 0.28) !important;
        box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.72) !important;
    }

    .side-nav-link:hover,
    .side-nav-link:focus-visible,
    section[data-testid="stSidebar"] a:hover,
    section[data-testid="stSidebar"] a:focus-visible {
        background: linear-gradient(135deg, #2563eb 0%, #0ea5e9 100%) !important;
        color: #ffffff !important;
        text-shadow: none !important;
    }

    .side-nav-link:hover *,
    .side-nav-link:focus-visible *,
    section[data-testid="stSidebar"] a:hover *,
    section[data-testid="stSidebar"] a:focus-visible * {
        color: #ffffff !important;
    }

    .side-status {
        background: rgba(255, 255, 255, 0.62) !important;
        border-color: rgba(148, 163, 184, 0.5) !important;
        color: #0f172a !important;
    }

    @media (prefers-color-scheme: light) {
        .exec-metric,
        .exec-panel,
        .module-card {
            background: linear-gradient(145deg, #ffffff 0%, #f8fbff 100%);
            color: #102033;
        }
    }

    @media (prefers-color-scheme: dark) {
        .exec-metric,
        .exec-panel,
        .module-card {
            background: linear-gradient(145deg, #102033 0%, #0b1727 100%) !important;
            border-color: rgba(148, 163, 184, 0.26) !important;
            box-shadow:
                0 2px 0 rgba(255, 255, 255, 0.08) inset,
                0 7px 0 rgba(0, 0, 0, 0.34),
                0 24px 38px rgba(0, 0, 0, 0.42) !important;
        }

        .exec-metric__label,
        .exec-panel h3,
        .status-row,
        .module-card__stat,
        .module-card__stat strong,
        .status-row strong,
        .score-ring {
            color: #f8fafc !important;
        }

        .exec-metric__value {
            color: #ffffff !important;
        }

        .exec-metric__sub,
        .score-ring span {
            color: #cbd5e1 !important;
        }

        .score-ring {
            background:
                radial-gradient(circle at center, #102033 55%, transparent 57%),
                conic-gradient(#27ae60 0 83%, #334155 83% 100%) !important;
        }

        .status-row,
        .module-card__stat {
            border-color: rgba(148, 163, 184, 0.24) !important;
        }
    }

    /* NLNG-inspired command dashboard skin */
    .stApp {
        background:
            radial-gradient(circle at 18% 0%, rgba(59, 130, 246, 0.14), transparent 26rem),
            radial-gradient(circle at 82% 8%, rgba(34, 197, 94, 0.07), transparent 24rem),
            linear-gradient(135deg, #111827 0%, #1f2937 52%, #0f172a 100%) !important;
        color: #e5edf8 !important;
    }

    .block-container {
        max-width: 1580px !important;
        padding: 0.75rem 1rem 1.4rem !important;
    }

    h1, h2, h3, h4, p, label, span {
        letter-spacing: 0 !important;
    }

    .app-bar {
        align-items: center !important;
        background: rgba(17, 24, 39, 0.88) !important;
        border: 1px solid rgba(148, 163, 184, 0.18) !important;
        border-radius: 0 !important;
        box-shadow: 0 16px 42px rgba(0, 0, 0, 0.34) !important;
        display: flex !important;
        justify-content: space-between !important;
        margin: -0.25rem -0.15rem 0.55rem !important;
        min-height: 4.3rem;
        padding: 0.8rem 1rem !important;
    }

    .app-brand-lockup {
        align-items: center;
        display: flex;
        gap: 0.85rem;
    }

    .app-logo-mark {
        background: linear-gradient(135deg, #2563eb, #0ea5e9);
        border-radius: 8px;
        box-shadow: 0 12px 28px rgba(37, 99, 235, 0.34);
        height: 2.5rem;
        position: relative;
        width: 2.5rem;
    }

    .app-logo-mark::after {
        background: rgba(2, 6, 23, 0.9);
        border-radius: 6px;
        content: "";
        height: 1rem;
        left: 0.72rem;
        position: absolute;
        top: 0.72rem;
        transform: rotate(-35deg);
        width: 1.6rem;
    }

    .app-logo-img {
        align-items: center;
        display: flex;
        justify-content: center;
    }

    .app-logo-img img {
        display: block;
        max-height: 2.85rem;
        object-fit: contain;
        width: auto;
    }

    .app-logo-img--nlng img {
        max-height: 3rem;
        max-width: 8rem;
    }

    .app-logo-img--evomec img {
        max-height: 2.75rem;
        max-width: 10rem;
    }

    .app-bar__right {
        align-items: center;
        display: flex;
        gap: 0.9rem;
    }

    .header-profile {
        align-items: center;
        background: rgba(15, 23, 42, 0.78);
        border: 1px solid rgba(148, 163, 184, 0.2);
        border-radius: 999px;
        display: flex;
        gap: 0.55rem;
        padding: 0.38rem 0.68rem 0.38rem 0.42rem;
    }

    .header-profile__photo,
    .header-profile__initials {
        align-items: center;
        background: linear-gradient(135deg, #2563eb, #22c55e);
        border: 2px solid rgba(96, 165, 250, 0.46);
        border-radius: 999px;
        color: #ffffff;
        display: flex;
        font-size: 0.76rem;
        font-weight: 900;
        height: 2.05rem;
        justify-content: center;
        object-fit: cover;
        width: 2.05rem;
    }

    .header-profile__name {
        color: #ffffff;
        font-size: 0.78rem;
        font-weight: 900;
        line-height: 1.05;
        max-width: 9rem;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
    }

    .header-profile__meta {
        color: #93c5fd;
        font-size: 0.62rem;
        font-weight: 760;
        margin-top: 0.1rem;
    }

    .app-bar__eyebrow {
        color: #ffffff !important;
        font-size: 1.05rem !important;
        font-weight: 900 !important;
    }

    .app-bar__title {
        color: #ffffff !important;
        font-size: 1rem !important;
        font-weight: 900 !important;
        line-height: 1.1;
        text-transform: uppercase;
    }

    .app-bar__project {
        color: #38bdf8;
        font-size: 0.72rem;
        font-weight: 780;
        margin-top: 0.12rem;
        text-transform: uppercase;
    }

    .app-bar__partner {
        color: #ffffff;
        font-size: 1.42rem;
        font-weight: 950;
        letter-spacing: 0.02em;
    }

    .top-module-nav {
        align-items: center;
        background: rgba(8, 17, 31, 0.78);
        border: 1px solid rgba(148, 163, 184, 0.16);
        border-radius: 0;
        display: flex;
        gap: 0.35rem;
        margin: 0 0 0.75rem;
        overflow-x: auto;
        padding: 0.42rem 0.55rem;
        scrollbar-width: thin;
    }

    .top-module-nav a {
        border-bottom: 2px solid transparent;
        color: #cbd5e1 !important;
        flex: 0 0 auto;
        font-size: 0.72rem;
        font-weight: 740;
        padding: 0.48rem 0.62rem;
        text-decoration: none !important;
        transition: color 0.18s ease, border-color 0.18s ease, background 0.18s ease;
    }

    .top-module-nav a:first-child,
    .top-module-nav a:hover {
        background: rgba(37, 99, 235, 0.12);
        border-color: #2563eb;
        color: #ffffff !important;
    }

    section[data-testid="stSidebar"] {
        background:
            radial-gradient(circle at top left, rgba(37, 99, 235, 0.16), transparent 15rem),
            linear-gradient(180deg, #1f2937 0%, #111827 100%) !important;
        border-right: 1px solid rgba(148, 163, 184, 0.16) !important;
    }

    section[data-testid="stSidebar"] h1,
    section[data-testid="stSidebar"] h2,
    section[data-testid="stSidebar"] h3,
    section[data-testid="stSidebar"] label,
    section[data-testid="stSidebar"] p,
    section[data-testid="stSidebar"] span,
    section[data-testid="stSidebar"] a,
    section[data-testid="stSidebar"] a:visited,
    section[data-testid="stSidebar"] a *,
    section[data-testid="stSidebar"] [role="link"],
    section[data-testid="stSidebar"] [role="link"] * {
        color: #dbeafe !important;
        text-shadow: none !important;
    }

    .side-brand {
        border-bottom-color: rgba(148, 163, 184, 0.2) !important;
        padding-top: 0.7rem !important;
    }

    .side-brand__name {
        color: #ffffff !important;
        font-size: 1.05rem !important;
        font-weight: 950 !important;
    }

    .side-brand__logo {
        display: block;
        max-height: 2.4rem;
        object-fit: contain;
        width: 3rem;
    }

    .side-brand__sub {
        color: #93c5fd !important;
    }

    .side-menu-title {
        color: #38bdf8 !important;
    }

    .sidebar-profile {
        align-items: center;
        background: rgba(15, 23, 42, 0.68);
        border: 1px solid rgba(148, 163, 184, 0.18);
        border-radius: 8px;
        display: flex;
        gap: 0.72rem;
        margin: 0.75rem 0 0.8rem;
        padding: 0.72rem;
    }

    .sidebar-profile__photo,
    .sidebar-profile__initials {
        border: 2px solid rgba(96, 165, 250, 0.45);
        border-radius: 999px;
        flex: 0 0 auto;
        height: 3rem !important;
        margin: 0 !important;
        object-fit: cover;
        width: 3rem !important;
    }

    .sidebar-profile__initials {
        font-size: 1rem !important;
    }

    .sidebar-profile__name {
        color: #ffffff;
        font-size: 0.88rem;
        font-weight: 900;
        line-height: 1.15;
    }

    .sidebar-profile__meta {
        color: #93c5fd;
        font-size: 0.68rem;
        font-weight: 720;
        margin-top: 0.18rem;
    }

    .side-nav-link {
        border-radius: 7px !important;
        color: #dbeafe !important;
        display: block !important;
        margin: 0.18rem 0 !important;
        padding: 0.58rem 0.75rem !important;
    }

    .side-nav-link[href="/"],
    .side-nav-link:hover,
    .side-nav-link:focus-visible {
        background: linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%) !important;
        box-shadow: 0 12px 26px rgba(37, 99, 235, 0.28) !important;
        color: #ffffff !important;
        transform: translateX(3px) !important;
    }

    .side-status {
        background: rgba(15, 23, 42, 0.76) !important;
        border-color: rgba(148, 163, 184, 0.22) !important;
        color: #cbd5e1 !important;
    }

    .dashboard-command {
        padding-bottom: 0.6rem;
    }

    .command-topbar {
        align-items: center;
        background: rgba(8, 17, 31, 0.82);
        border: 1px solid rgba(96, 165, 250, 0.16);
        border-radius: 8px;
        box-shadow: 0 14px 34px rgba(0, 0, 0, 0.22);
        display: flex;
        justify-content: space-between;
        margin: -0.1rem 0 0.55rem;
        min-height: 2.4rem;
        padding: 0 0.8rem;
    }

    .command-crumb {
        color: #94a3b8;
        font-size: 0.76rem;
        font-weight: 800;
    }

    .command-crumb span {
        color: #e5edf8 !important;
        margin-left: 0.3rem;
    }

    .command-tools {
        align-items: center;
        color: #cbd5e1;
        display: flex;
        font-size: 0.72rem;
        font-weight: 800;
        gap: 0.75rem;
    }

    .command-tools span:last-child {
        color: #22c55e !important;
    }

    div[data-testid="stPopover"] button {
        background: rgba(8, 17, 31, 0.82) !important;
        border: 1px solid rgba(96, 165, 250, 0.16) !important;
        border-radius: 8px !important;
        box-shadow: 0 14px 34px rgba(0, 0, 0, 0.22) !important;
        color: #e5edf8 !important;
        justify-content: flex-start !important;
        max-width: 15rem !important;
        min-height: 2.4rem !important;
        min-width: 13rem !important;
        padding: 0 0.8rem !important;
        width: fit-content !important;
    }

    div[data-testid="stPopover"] button:hover {
        border-color: rgba(56, 189, 248, 0.38) !important;
        color: #ffffff !important;
    }

    div[data-testid="stPopover"] {
        max-width: 15rem !important;
        width: fit-content !important;
    }

    .command-tools--compact {
        align-items: center;
        background: rgba(8, 17, 31, 0.82);
        border: 1px solid rgba(96, 165, 250, 0.16);
        border-radius: 8px;
        box-shadow: 0 14px 34px rgba(0, 0, 0, 0.22);
        display: flex;
        justify-content: flex-end;
        min-height: 2.4rem;
        padding: 0 0.8rem;
    }

    .nav-popover-menu {
        display: grid;
        gap: 0.16rem;
        max-height: 18rem;
        max-width: 15rem;
        min-width: 13rem;
        overflow-y: auto;
        padding: 0.12rem;
        width: 15rem;
    }

    .nav-popover-link {
        background: rgba(15, 23, 42, 0.72);
        border: 1px solid rgba(148, 163, 184, 0.16);
        border-radius: 6px;
        color: #e5edf8 !important;
        display: block;
        font-size: 0.76rem;
        font-weight: 800;
        line-height: 1.05;
        padding: 0.28rem 0.55rem;
        text-decoration: none !important;
    }

    .nav-popover-link:hover {
        background: linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%);
        color: #ffffff !important;
    }

    .app-bar {
        background:
            linear-gradient(90deg, rgba(10, 25, 47, 0.98), rgba(9, 28, 57, 0.92)),
            radial-gradient(circle at 72% 50%, rgba(14, 165, 233, 0.2), transparent 16rem) !important;
        border-radius: 8px !important;
        min-height: 6.6rem !important;
        overflow: hidden;
        position: relative;
    }

    .app-bar::after {
        background:
            linear-gradient(90deg, transparent, rgba(56, 189, 248, 0.14)),
            repeating-linear-gradient(90deg, rgba(56, 189, 248, 0.18) 0 2px, transparent 2px 10px);
        content: "";
        height: 5.2rem;
        opacity: 0.35;
        position: absolute;
        right: 13rem;
        top: 0.8rem;
        transform: skewX(-12deg);
        width: 21rem;
    }

    .app-bar > * {
        position: relative;
        z-index: 1;
    }

    .app-logo-img--nlng {
        background: #ffffff;
        border-radius: 8px;
        box-shadow: 0 18px 38px rgba(0, 0, 0, 0.28);
        min-height: 3.9rem;
        padding: 0.55rem;
        width: 4.1rem;
    }

    .app-bar__title {
        font-size: 1.55rem !important;
    }

    .metric-grid--six {
        grid-template-columns: repeat(auto-fit, minmax(190px, 1fr)) !important;
        gap: 0.7rem !important;
        margin-bottom: 0.7rem !important;
    }

    .exec-metric,
    .exec-panel,
    .module-card,
    div[data-testid="stVerticalBlockBorderWrapper"] {
        background: var(--qaqc-surface) !important;
        border: 1px solid var(--qaqc-line) !important;
        border-radius: 8px !important;
        box-shadow: var(--qaqc-shadow) !important;
        color: var(--qaqc-text) !important;
    }

    .exec-metric {
        min-height: 6.55rem !important;
        padding: 0.85rem !important;
    }

    .exec-metric::after {
        display: none !important;
    }

    .exec-metric:hover,
    .exec-panel:hover,
    .module-card:hover,
    div[data-testid="stVerticalBlockBorderWrapper"]:hover {
        border-color: color-mix(in srgb, var(--metric-color, #2563eb) 46%, rgba(96, 165, 250, 0.18)) !important;
        box-shadow:
            0 1px 0 rgba(255, 255, 255, 0.1) inset,
            0 22px 46px rgba(0, 0, 0, 0.42),
            0 0 24px color-mix(in srgb, var(--metric-color, #2563eb) 18%, transparent) !important;
        transform: translateY(-4px) !important;
    }

    div[data-testid="stVerticalBlockBorderWrapper"] {
        margin-bottom: 0.75rem !important;
        min-height: 19.4rem !important;
        overflow: hidden !important;
        padding: 0.15rem !important;
        transition: transform 0.22s ease, box-shadow 0.22s ease, border-color 0.22s ease !important;
    }

    .native-panel-title {
        align-items: center;
        color: var(--qaqc-navy) !important;
        display: flex;
        font-size: 0.82rem;
        font-weight: 900;
        justify-content: space-between;
        margin: 0 0 0.35rem;
    }

    .native-panel-title span {
        color: var(--qaqc-muted) !important;
        font-weight: 900;
    }

    .exec-metric__icon {
        border-radius: 8px !important;
        height: 3rem !important;
        width: 3rem !important;
    }

    .exec-metric__label {
        color: var(--qaqc-muted) !important;
        font-size: 0.72rem !important;
        font-weight: 880 !important;
    }

    .exec-metric__value {
        color: var(--qaqc-navy) !important;
        font-size: 1.65rem !important;
        margin-top: 0.3rem !important;
    }

    .exec-metric__sub,
    .exec-metric__delta {
        color: var(--qaqc-muted) !important;
        font-size: 0.66rem !important;
    }

    .exec-metric__delta {
        color: var(--qaqc-blue) !important;
        font-weight: 800;
        margin-top: 0.18rem;
    }

    .exec-panel {
        min-height: 19.4rem;
        padding: 0.85rem !important;
    }

    .exec-panel--html {
        overflow: hidden;
    }

    .exec-chart-grid {
        display: grid;
        gap: 0.75rem;
        grid-template-columns: repeat(3, minmax(0, 1fr));
        margin-bottom: 0.75rem;
    }

    .exec-bottom-grid {
        display: grid;
        gap: 0.75rem;
        grid-template-columns: minmax(280px, 0.9fr) minmax(0, 1.8fr);
        margin-bottom: 0.75rem;
    }

    .inline-chart {
        display: block;
        height: 15.4rem;
        margin-top: 0.2rem;
        overflow: visible;
        width: 100%;
    }

    .inline-chart text {
        fill: #dbeafe;
        font-size: 0.72rem;
        font-weight: 760;
    }

    .inline-chart .axis-label {
        fill: #94a3b8;
        font-size: 0.68rem;
        font-weight: 700;
    }

    .inline-chart .legend text {
        fill: #cbd5e1;
        font-size: 0.68rem;
    }

    .category-bars {
        display: grid;
        gap: 0.74rem;
        padding-top: 0.65rem;
    }

    .category-row {
        align-items: center;
        display: grid;
        gap: 0.65rem;
        grid-template-columns: 8rem minmax(0, 1fr) 2rem;
    }

    .category-label {
        align-items: center;
        color: #dbeafe;
        display: flex;
        font-size: 0.76rem;
        font-weight: 780;
        gap: 0.42rem;
        min-width: 0;
    }

    .category-label span {
        border-radius: 999px;
        flex: 0 0 auto;
        height: 0.62rem;
        width: 0.62rem;
    }

    .category-track {
        background: rgba(148, 163, 184, 0.14);
        border-radius: 999px;
        height: 0.56rem;
        overflow: hidden;
    }

    .category-track i {
        border-radius: 999px;
        display: block;
        height: 100%;
    }

    .category-row strong {
        color: #ffffff;
        font-size: 0.82rem;
        text-align: right;
    }

    .panel-title {
        align-items: center;
        color: #f8fafc;
        display: flex;
        font-size: 0.86rem;
        font-weight: 900;
        justify-content: space-between;
        margin-bottom: 0.35rem;
    }

    .panel-title span {
        color: #94a3b8 !important;
        letter-spacing: 0.12em !important;
    }

    .panel-total {
        background: rgba(15, 23, 42, 0.76);
        border: 1px solid rgba(148, 163, 184, 0.16);
        border-radius: 8px;
        color: #dbeafe;
        font-weight: 800;
        margin-top: 0.35rem;
        padding: 0.55rem;
        text-align: center;
    }

    .exec-empty {
        align-items: center;
        color: #94a3b8;
        display: flex;
        min-height: 14rem;
        justify-content: center;
    }

    .exec-table {
        border-collapse: collapse;
        color: #cbd5e1;
        font-size: 0.72rem;
        width: 100%;
    }

    .exec-table th,
    .exec-table td {
        border-bottom: 1px solid rgba(148, 163, 184, 0.12);
        padding: 0.62rem 0.55rem;
        text-align: left;
    }

    .exec-table th {
        color: #bfdbfe;
        font-size: 0.66rem;
        font-weight: 850;
        text-transform: uppercase;
    }

    .status-badge {
        border-radius: 5px;
        display: inline-flex;
        font-size: 0.68rem;
        font-weight: 820;
        padding: 0.2rem 0.4rem;
    }

    .status-badge--open {
        background: rgba(239, 68, 68, 0.12);
        border: 1px solid rgba(239, 68, 68, 0.42);
        color: #fca5a5;
    }

    .status-badge--closed {
        background: rgba(34, 197, 94, 0.12);
        border: 1px solid rgba(34, 197, 94, 0.42);
        color: #86efac;
    }

    .module-grid--compact {
        grid-template-columns: repeat(4, minmax(0, 1fr)) !important;
        margin-top: 0.75rem !important;
    }

    .module-card {
        min-height: 7.3rem !important;
    }

    .module-card__stat {
        background: var(--qaqc-surface-2);
        border-color: var(--qaqc-line) !important;
        color: var(--qaqc-muted) !important;
    }

    .module-card__stat strong {
        color: var(--qaqc-navy) !important;
    }

    .quick-access-panel {
        background: linear-gradient(145deg, rgba(31, 41, 55, 0.96), rgba(17, 24, 39, 0.9));
        border: 1px solid rgba(96, 165, 250, 0.16);
        border-radius: 8px;
        box-shadow: 0 14px 34px rgba(0, 0, 0, 0.28);
        margin-top: 0.75rem;
        padding: 0.85rem;
    }

    .quick-access-title {
        color: #f8fafc;
        font-size: 0.82rem;
        font-weight: 900;
        margin-bottom: 0.65rem;
        text-transform: uppercase;
    }

    .quick-access-grid {
        display: grid;
        gap: 0.55rem;
        grid-template-columns: repeat(7, minmax(0, 1fr));
    }

    .quick-link {
        align-items: center;
        background: rgba(15, 23, 42, 0.64);
        border: 1px solid rgba(148, 163, 184, 0.16);
        border-radius: 7px;
        color: #e5edf8 !important;
        display: flex;
        font-size: 0.74rem;
        font-weight: 840;
        gap: 0.45rem;
        min-height: 2.55rem;
        padding: 0.35rem 0.6rem;
        text-decoration: none !important;
    }

    .quick-link:hover {
        border-color: var(--quick-color, #2563eb);
        box-shadow: 0 12px 28px color-mix(in srgb, var(--quick-color, #2563eb) 22%, transparent);
        color: #ffffff !important;
        transform: translateY(-2px);
    }

    .quick-link span {
        align-items: center;
        background: var(--quick-color, #2563eb);
        border-radius: 6px;
        color: #ffffff !important;
        display: flex;
        flex: 0 0 auto;
        font-size: 0.68rem;
        font-weight: 900;
        height: 1.35rem;
        justify-content: center;
        width: 1.35rem;
    }

    .quick-link--all {
        border-color: rgba(37, 99, 235, 0.46);
        color: #38bdf8 !important;
        justify-content: center;
    }

    .dashboard-security-strip {
        align-items: center;
        color: #94a3b8;
        display: flex;
        font-size: 0.72rem;
        font-weight: 780;
        gap: 1.6rem;
        justify-content: center;
        padding: 0.75rem 0 0.1rem;
    }

    .dashboard-security-strip span::before {
        color: #22c55e;
        content: "◆";
        font-size: 0.6rem;
        margin-right: 0.42rem;
    }

    .app-bar__welcome {
        color: #f8fafc;
        font-size: 0.78rem;
        font-weight: 850;
        margin-bottom: 0.38rem;
    }

    .app-bar__welcome span {
        color: #22d3ee !important;
    }

    .side-status--footer {
        background:
            radial-gradient(circle at 50% 0%, rgba(14, 165, 233, 0.18), transparent 7rem),
            rgba(15, 23, 42, 0.76) !important;
        margin-top: 1.2rem !important;
        padding-top: 3.6rem !important;
    }

    .analytics-hero {
        align-items: center;
        background:
            linear-gradient(90deg, rgba(8, 17, 31, 0.96), rgba(10, 35, 68, 0.72)),
            radial-gradient(circle at 72% 30%, rgba(14, 165, 233, 0.28), transparent 18rem);
        border: 1px solid rgba(96, 165, 250, 0.18);
        border-radius: 8px;
        box-shadow: 0 18px 44px rgba(0, 0, 0, 0.28);
        display: flex;
        gap: 1rem;
        margin-bottom: 0.75rem;
        min-height: 5.6rem;
        overflow: hidden;
        padding: 0.9rem 1.05rem;
    }

    .analytics-hero__logo {
        align-items: center;
        background: #ffffff;
        border-radius: 8px;
        color: #063c63;
        display: flex;
        font-size: 0.72rem;
        font-weight: 950;
        height: 3.8rem;
        justify-content: center;
        width: 4.2rem;
    }

    .analytics-hero h1 {
        color: #ffffff !important;
        font-size: 1.48rem;
        font-weight: 950;
        line-height: 1.1;
        margin: 0;
        text-transform: uppercase;
    }

    .analytics-hero p {
        color: #b7c9dd !important;
        font-size: 0.78rem;
        font-weight: 760;
        margin: 0.3rem 0 0;
    }

    .analytics-metric-grid {
        display: grid;
        gap: 0.65rem;
        grid-template-columns: repeat(auto-fit, minmax(175px, 1fr));
        margin-bottom: 0.7rem;
    }

    .analytics-metric {
        align-items: center;
        background: var(--qaqc-surface);
        border: 1px solid var(--qaqc-line);
        border-radius: 8px;
        box-shadow: var(--qaqc-shadow);
        color: var(--qaqc-text);
        display: flex;
        gap: 0.65rem;
        min-height: 5.45rem;
        padding: 0.72rem;
    }

    .analytics-metric__icon {
        align-items: center;
        background: var(--metric-color, #2563eb);
        border-radius: 8px;
        box-shadow: 0 14px 28px color-mix(in srgb, var(--metric-color, #2563eb) 36%, transparent);
        color: #ffffff;
        display: flex;
        flex: 0 0 auto;
        font-weight: 950;
        height: 2.45rem;
        justify-content: center;
        width: 2.45rem;
    }

    .analytics-metric__label {
        color: var(--qaqc-muted);
        font-size: 0.68rem;
        font-weight: 900;
    }

    .analytics-metric__value {
        color: var(--qaqc-navy);
        font-size: 1.45rem;
        font-weight: 950;
        line-height: 1;
        margin-top: 0.22rem;
    }

    .analytics-metric__sub,
    .analytics-metric__trend {
        color: var(--qaqc-muted);
        font-size: 0.62rem;
        margin-top: 0.2rem;
    }

    .analytics-metric__trend {
        color: var(--qaqc-blue);
        font-weight: 850;
    }

    .analytics-metric__trend--down {
        color: #ef4444;
    }

    .analytics-panel-title {
        align-items: center;
        color: var(--qaqc-navy);
        display: flex;
        font-size: 0.78rem;
        font-weight: 900;
        justify-content: space-between;
        margin: 0 0 0.35rem;
    }

    .analytics-panel-title span {
        color: var(--qaqc-muted) !important;
    }

    div[data-testid="stDataFrame"] {
        background: rgba(15, 23, 42, 0.64) !important;
        border: 1px solid rgba(148, 163, 184, 0.14) !important;
        border-radius: 8px !important;
        overflow: hidden !important;
    }

    .stMarkdown hr {
        border-color: rgba(96, 165, 250, 0.14) !important;
        margin: 0.7rem 0 !important;
    }

    [data-testid="stMetric"] {
        background: linear-gradient(145deg, rgba(31, 41, 55, 0.96), rgba(17, 24, 39, 0.9)) !important;
        border: 1px solid rgba(96, 165, 250, 0.16) !important;
        border-radius: 8px !important;
        box-shadow: 0 14px 34px rgba(0, 0, 0, 0.24) !important;
        padding: 0.85rem !important;
    }

    @media (max-width: 1320px) {
        .metric-grid--six {
            grid-template-columns: repeat(3, minmax(0, 1fr)) !important;
        }

        .analytics-metric-grid {
            grid-template-columns: repeat(4, minmax(0, 1fr));
        }

        .exec-chart-grid,
        .exec-bottom-grid,
        .quick-access-grid {
            grid-template-columns: 1fr !important;
        }
    }

    @media (max-width: 760px) {
        .metric-grid--six,
        .module-grid--compact,
        .analytics-metric-grid {
            grid-template-columns: 1fr !important;
        }

        .top-module-nav {
            margin-left: -0.25rem;
            margin-right: -0.25rem;
        }

        .app-bar {
            align-items: flex-start !important;
            display: flex !important;
            flex-direction: column !important;
            gap: 0.9rem;
            min-height: auto !important;
        }

        .app-bar::after {
            display: none;
        }

        .app-bar__right {
            width: 100%;
        }

        .command-tools {
            display: none;
        }
    }

    /* Final global shell override for Streamlit's visible containers */
    html,
    body,
    #root,
    .stApp,
    [data-testid="stApp"],
    [data-testid="stAppViewContainer"],
    [data-testid="stMain"],
    [data-testid="stMainBlockContainer"] {
        background:
            radial-gradient(circle at 18% 0%, rgba(59, 130, 246, 0.13), transparent 28rem),
            linear-gradient(135deg, #111827 0%, #1f2937 55%, #111827 100%) !important;
        color: #e5edf8 !important;
    }

    [data-testid="stHeader"],
    header[data-testid="stHeader"] {
        background: rgba(17, 24, 39, 0.82) !important;
    }

    [data-testid="stSidebarContent"] {
        background:
            radial-gradient(circle at top left, rgba(37, 99, 235, 0.16), transparent 16rem),
            linear-gradient(180deg, #1f2937 0%, #111827 100%) !important;
    }

    .stButton button,
    section[data-testid="stSidebar"] .stButton button {
        border-radius: 8px !important;
        font-weight: 800 !important;
    }

    section[data-testid="stSidebar"] .stButton button {
        background: rgba(15, 23, 42, 0.78) !important;
        border: 1px solid rgba(148, 163, 184, 0.22) !important;
        color: #dbeafe !important;
    }

    section[data-testid="stSidebar"] .stButton button:hover {
        background: linear-gradient(135deg, #ef4444 0%, #b91c1c 100%) !important;
        border-color: rgba(248, 113, 113, 0.42) !important;
        color: #ffffff !important;
    }

    .auth-panel,
    div[data-testid="stForm"],
    div[data-testid="stExpander"] {
        background: rgba(31, 41, 55, 0.92) !important;
        border-color: rgba(148, 163, 184, 0.18) !important;
        color: #e5edf8 !important;
    }

    .auth-panel h1,
    .auth-panel h2,
    .auth-panel h3,
    div[data-testid="stForm"] label,
    div[data-testid="stForm"] p {
        color: #f8fafc !important;
    }

    .auth-page {
        margin: -0.7rem -1.7rem -2.5rem;
        min-height: calc(100vh - 1rem);
        padding: 2.2rem 2.25rem 1rem;
        background:
            radial-gradient(circle at 8% 16%, rgba(30, 144, 255, 0.18), transparent 20rem),
            radial-gradient(circle at 86% 12%, rgba(37, 99, 235, 0.42), transparent 32rem),
            linear-gradient(135deg, #061225 0%, #071a34 48%, #082a59 100%);
        color: #e5edf8;
    }

    .auth-page + div,
    .auth-page ~ div {
        position: relative;
    }

    div[data-testid="column"]:has(.auth-card-head) {
        align-self: center;
        background:
            linear-gradient(145deg, rgba(16, 32, 55, 0.86), rgba(10, 23, 42, 0.94));
        border: 1px solid rgba(148, 163, 184, 0.34);
        border-radius: 8px;
        box-shadow: 0 28px 80px rgba(0, 0, 0, 0.32);
        min-height: 31rem;
        padding: 1.9rem 2rem 1.65rem;
    }

    div[data-testid="column"]:has(.auth-hero-panel) {
        align-self: center;
    }

    .auth-hero-panel {
        padding: 0.2rem 0 0;
    }

    .auth-logo {
        display: block;
        height: 3.6rem;
        margin: 0 0 2.2rem;
        object-fit: contain;
        object-position: left center;
        width: auto;
    }

    .auth-logo-text {
        color: #ffffff;
        font-size: 1.8rem;
        font-weight: 800;
        letter-spacing: 0.08em;
        margin-bottom: 2.3rem;
    }

    .auth-eyebrow--pill {
        align-items: center;
        background: rgba(37, 99, 235, 0.22);
        border: 1px solid rgba(59, 130, 246, 0.28);
        border-radius: 999px;
        color: #60a5fa;
        display: inline-flex;
        font-size: 0.7rem;
        gap: 0.35rem;
        margin-bottom: 0.9rem;
        padding: 0.36rem 0.72rem;
    }

    .auth-eyebrow--pill::before {
        content: "◆";
        color: #3b82f6;
        font-size: 0.66rem;
    }

    .auth-hero-panel h1 {
        color: #f8fafc !important;
        font-size: clamp(2.15rem, 4vw, 3.6rem);
        font-weight: 850;
        line-height: 1.05;
        margin: 0 0 1.1rem;
    }

    .auth-hero-panel h1 span {
        color: #2f86ff !important;
    }

    .auth-hero-panel p {
        color: #c3cfdf !important;
        font-size: 1rem;
        line-height: 1.65;
        margin: 0;
        max-width: 34rem;
    }

    .auth-feature-grid {
        display: grid;
        gap: 1.15rem 1.3rem;
        grid-template-columns: repeat(2, minmax(0, 1fr));
        margin: 1.8rem 0 1.7rem;
        max-width: 38rem;
    }

    .auth-feature {
        min-height: 4.4rem;
        padding-left: 3.15rem;
        position: relative;
    }

    .auth-feature::before,
    .auth-access-note::before {
        align-items: center;
        background: rgba(37, 99, 235, 0.22);
        border: 1px solid rgba(59, 130, 246, 0.38);
        border-radius: 999px;
        color: #38bdf8;
        content: "✓";
        display: flex;
        font-weight: 900;
        height: 2.25rem;
        justify-content: center;
        left: 0;
        position: absolute;
        top: 0.05rem;
        width: 2.25rem;
    }

    .auth-feature:nth-child(2)::before {
        background: rgba(16, 185, 129, 0.18);
        border-color: rgba(16, 185, 129, 0.32);
        color: #34d399;
    }

    .auth-feature:nth-child(3)::before {
        background: rgba(124, 58, 237, 0.2);
        border-color: rgba(124, 58, 237, 0.36);
        color: #a78bfa;
    }

    .auth-feature:nth-child(4)::before {
        background: rgba(234, 179, 8, 0.15);
        border-color: rgba(234, 179, 8, 0.32);
        color: #facc15;
    }

    .auth-feature b {
        color: #f8fafc;
        display: block;
        font-size: 0.9rem;
        line-height: 1.25;
        margin-bottom: 0.32rem;
    }

    .auth-feature small {
        color: #b4c1d2;
        display: block;
        font-size: 0.78rem;
        line-height: 1.45;
    }

    .auth-access-note {
        background: rgba(22, 50, 88, 0.58);
        border: 1px solid rgba(96, 165, 250, 0.26);
        border-radius: 8px;
        max-width: 38rem;
        min-height: 5.35rem;
        padding: 1rem 1rem 1rem 4.2rem;
        position: relative;
    }

    .auth-access-note::before {
        height: 2.7rem;
        left: 1rem;
        top: 1.15rem;
        width: 2.7rem;
    }

    .auth-access-note b,
    .auth-access-note span {
        display: block;
    }

    .auth-access-note b {
        color: #7dd3fc;
        font-size: 0.88rem;
        margin-bottom: 0.35rem;
    }

    .auth-access-note span {
        color: #b8c4d4;
        font-size: 0.78rem;
        line-height: 1.55;
    }

    .auth-card-head {
        text-align: center;
    }

    .auth-shield {
        align-items: center;
        background: radial-gradient(circle, rgba(37, 99, 235, 0.28), rgba(15, 23, 42, 0.92));
        border: 1px solid rgba(59, 130, 246, 0.44);
        border-radius: 999px;
        box-shadow: 0 0 34px rgba(37, 99, 235, 0.36);
        color: #38bdf8;
        display: inline-flex;
        font-size: 1.9rem;
        font-weight: 900;
        height: 4.2rem;
        justify-content: center;
        margin-bottom: 1rem;
        width: 4.2rem;
    }

    .auth-card-head h2 {
        color: #f8fafc !important;
        font-size: 1.55rem;
        font-weight: 850;
        line-height: 1.15;
        margin: 0 0 0.35rem;
    }

    .auth-card-head p {
        color: #b7c2d2 !important;
        font-size: 0.86rem;
        margin: 0 0 1.15rem;
    }

    div[data-testid="column"]:has(.auth-card-head) div[role="radiogroup"] {
        background: rgba(30, 50, 78, 0.74);
        border: 1px solid rgba(148, 163, 184, 0.14);
        border-radius: 8px;
        display: grid;
        gap: 0;
        grid-template-columns: repeat(2, minmax(0, 1fr));
        margin: 0 0 1rem;
        overflow: hidden;
        padding: 0;
    }

    div[data-testid="column"]:has(.auth-card-head) div[role="radiogroup"] label {
        background: transparent;
        border: 0;
        border-radius: 0;
        color: #d7e2f0 !important;
        justify-content: center;
        margin: 0;
        min-height: 2.8rem;
        padding: 0.55rem 0.7rem;
    }

    div[data-testid="column"]:has(.auth-card-head) div[role="radiogroup"] label:has(input:checked) {
        background: linear-gradient(180deg, rgba(59, 130, 246, 0.22), rgba(14, 165, 233, 0.14));
        border-bottom: 2px solid #38bdf8;
        color: #7dd3fc !important;
    }

    div[data-testid="column"]:has(.auth-card-head) label,
    div[data-testid="column"]:has(.auth-card-head) p,
    div[data-testid="column"]:has(.auth-card-head) span {
        color: #dbe7f5 !important;
    }

    div[data-testid="column"]:has(.auth-card-head) div[data-baseweb="input"] > div,
    div[data-testid="column"]:has(.auth-card-head) div[data-baseweb="select"] > div {
        background: rgba(9, 20, 38, 0.74) !important;
        border: 1px solid rgba(148, 163, 184, 0.26) !important;
        border-radius: 8px !important;
        min-height: 2.75rem;
    }

    div[data-testid="column"]:has(.auth-card-head) input {
        color: #e5edf8 !important;
    }

    div[data-testid="column"]:has(.auth-card-head) input::placeholder {
        color: #7f8fa3 !important;
    }

    div[data-testid="column"]:has(.auth-card-head) .stCheckbox {
        margin-top: -0.15rem;
    }

    .auth-forgot {
        color: #38bdf8;
        font-size: 0.78rem;
        margin: -2.05rem 0 1.45rem;
        pointer-events: none;
        text-align: right;
    }

    div[data-testid="column"]:has(.auth-card-head) .stButton button,
    div[data-testid="column"]:has(.auth-card-head) div[data-testid="stFormSubmitButton"] button {
        background: linear-gradient(135deg, #2388ff 0%, #2563eb 100%) !important;
        border: 1px solid rgba(96, 165, 250, 0.32) !important;
        border-radius: 8px !important;
        box-shadow: 0 18px 38px rgba(37, 99, 235, 0.22);
        color: #ffffff !important;
        min-height: 2.9rem;
    }

    .auth-card-foot {
        border-top: 1px solid rgba(148, 163, 184, 0.18);
        color: #8ea0b5;
        font-size: 0.78rem;
        margin-top: 1.55rem;
        padding-top: 0.85rem;
        text-align: center;
    }

    .auth-footer {
        align-items: center;
        border-top: 1px solid rgba(148, 163, 184, 0.1);
        color: #9fb0c3;
        display: flex;
        font-size: 0.78rem;
        justify-content: space-between;
        margin: 1.35rem -2.25rem -1rem;
        padding: 1rem 2.25rem 0;
    }

    .auth-footer b,
    .auth-footer span {
        display: block;
    }

    .auth-footer b {
        color: #f8fafc;
        margin-bottom: 0.32rem;
    }

    @media (max-width: 900px) {
        .auth-page {
            margin: -0.8rem -1rem -2rem;
            padding: 1.3rem 1rem 0.8rem;
        }

        div[data-testid="column"]:has(.auth-card-head) {
            margin-top: 1rem;
            min-height: auto;
            padding: 1.35rem 1rem;
        }

        .auth-logo {
            height: 3rem;
            margin-bottom: 1.35rem;
        }

        .auth-hero-panel h1 {
            font-size: 2.2rem;
        }

        .auth-feature-grid {
            grid-template-columns: 1fr;
            margin: 1.3rem 0;
        }

        .auth-access-note {
            padding-right: 0.85rem;
        }

        .auth-forgot {
            margin-top: 0;
            text-align: left;
        }

        .auth-footer {
            align-items: flex-start;
            flex-direction: column;
            gap: 0.8rem;
            margin-left: -1rem;
            margin-right: -1rem;
            padding-left: 1rem;
            padding-right: 1rem;
        }
    }

    /* Login reference screen override */
    .auth-page {
        background:
            radial-gradient(circle at 15% 8%, rgba(37, 99, 235, 0.2), transparent 25rem),
            radial-gradient(circle at 88% 10%, rgba(37, 99, 235, 0.3), transparent 30rem),
            linear-gradient(135deg, #061329 0%, #071d3d 50%, #082c5f 100%) !important;
        margin: -0.75rem -1rem 0 !important;
        min-height: auto !important;
        padding: 0.9rem 2.15rem 0.75rem !important;
    }

    .auth-page .stHorizontalBlock {
        align-items: center;
        gap: 4.7rem !important;
        max-width: 1380px;
        margin: 0 auto;
    }

    .auth-logo {
        height: 4rem !important;
        margin-bottom: 2.45rem !important;
    }

    .auth-eyebrow--pill {
        background: rgba(37, 99, 235, 0.26) !important;
        border-color: rgba(59, 130, 246, 0.28) !important;
        color: #38bdf8 !important;
        margin-bottom: 1.05rem !important;
    }

    .auth-hero-panel h1 {
        color: #ffffff !important;
        font-size: clamp(2.65rem, 4.2vw, 3.9rem) !important;
        font-weight: 900 !important;
        line-height: 1.06 !important;
        margin-bottom: 1.05rem !important;
    }

    .auth-hero-panel h1 span {
        color: #2f86ff !important;
    }

    .auth-hero-panel p {
        color: #c9d5e5 !important;
        font-size: 1rem !important;
        line-height: 1.7 !important;
        max-width: 34.5rem !important;
    }

    .auth-feature-grid {
        gap: 1.55rem 2.05rem !important;
        margin: 1.95rem 0 1.75rem !important;
        max-width: 40rem !important;
    }

    .auth-feature {
        min-height: 4.3rem !important;
        padding-left: 3.8rem !important;
    }

    .auth-feature::before,
    .auth-access-note::before {
        content: "▣" !important;
        font-size: 1rem;
        height: 2.7rem !important;
        width: 2.7rem !important;
    }

    .auth-feature b {
        font-size: 0.86rem !important;
    }

    .auth-feature small {
        color: #c0ccdc !important;
        font-size: 0.77rem !important;
    }

    .auth-access-note {
        background: rgba(16, 43, 79, 0.76) !important;
        border-color: rgba(96, 165, 250, 0.32) !important;
        max-width: 40rem !important;
        min-height: 5.9rem !important;
        padding: 1rem 1.35rem 1rem 4.95rem !important;
    }

    .auth-access-note::before {
        content: "✓" !important;
        left: 1rem !important;
        top: 1.45rem !important;
    }

    .auth-access-note b {
        color: #7dd3fc !important;
        font-size: 0.9rem !important;
    }

    div[data-testid="column"]:has(.auth-card-head) {
        background:
            radial-gradient(circle at 50% 6%, rgba(37, 99, 235, 0.16), transparent 14rem),
            linear-gradient(145deg, rgba(15, 32, 56, 0.92), rgba(9, 21, 39, 0.96)) !important;
        border: 1px solid rgba(148, 163, 184, 0.3) !important;
        border-radius: 12px !important;
        box-shadow: 0 28px 90px rgba(0, 0, 0, 0.34) !important;
        max-width: 38.8rem;
        min-height: auto !important;
        padding: 1.55rem 2.55rem 1.35rem !important;
    }

    .auth-shield {
        background:
            radial-gradient(circle, rgba(37, 99, 235, 0.3), rgba(15, 23, 42, 0.92)) !important;
        border-color: rgba(59, 130, 246, 0.48) !important;
        color: #2f86ff !important;
        font-size: 2.2rem !important;
        height: 5rem !important;
        margin-bottom: 1.25rem !important;
        width: 5rem !important;
    }

    .auth-card-head h2 {
        font-size: 1.75rem !important;
        margin-bottom: 0.45rem !important;
    }

    .auth-card-head p {
        color: #b8c5d7 !important;
        margin-bottom: 1.45rem !important;
    }

    div[data-testid="column"]:has(.auth-card-head) div[role="radiogroup"] {
        margin-bottom: 1.25rem !important;
    }

    div[data-testid="column"]:has(.auth-card-head) div[role="radiogroup"] label {
        min-height: 3rem !important;
    }

    div[data-testid="column"]:has(.auth-card-head) div[data-baseweb="input"] > div {
        min-height: 3rem !important;
    }

    div[data-testid="column"]:has(.auth-card-head) .stButton button {
        min-height: 3.25rem !important;
        margin-top: 0.55rem !important;
    }

    .auth-forgot {
        color: #38bdf8 !important;
        margin-bottom: 1.35rem !important;
    }

    .auth-card-foot {
        color: #9aaac0 !important;
        margin-top: 1.95rem !important;
    }

    .auth-footer {
        background: rgba(7, 20, 40, 0.3);
        margin: 0.95rem -2.15rem 0 !important;
        padding: 0.85rem 2.15rem 0.75rem !important;
    }

    @media (max-width: 900px) {
        .auth-page {
            padding: 1rem !important;
        }

        .auth-page .stHorizontalBlock {
            gap: 1rem !important;
        }

        div[data-testid="column"]:has(.auth-card-head) {
            max-width: none;
            min-height: auto !important;
            padding: 1.4rem 1rem !important;
        }
    }
    </style>
    """, unsafe_allow_html=True)
    mode = get_theme_mode()
    dark_vars = css_variables(DARK_THEME)
    light_vars = css_variables(LIGHT_THEME)
    system_dark = f"@media (prefers-color-scheme: dark) {{ :root {{ {dark_vars} }} }}" if mode == "System" else ""
    selected_vars = dark_vars if mode == "Dark" else light_vars
    page_background = _page_background_source()
    st.markdown(
        f"""
    <style>
    :root {{
        {selected_vars}
        --qaqc-radius: 8px;
    }}

    {system_dark}

    .stApp {{
        background:
            linear-gradient(180deg, color-mix(in srgb, var(--qaqc-blue) 8%, transparent), transparent 18rem),
            var(--qaqc-bg) !important;
        color: var(--qaqc-text) !important;
    }}

    h1, h2, h3, h4, h5, h6,
    p, label, span, div,
    .stMarkdown, .stCaptionContainer {{
        color: inherit;
    }}

    h1, h2, h3,
    .app-bar__title,
    .header-profile__name,
    .page-header h1,
    .dashboard-hero h1,
    .kpi-value,
    div[data-testid="stMetricValue"] {{
        color: var(--qaqc-navy) !important;
    }}

    .app-bar,
    .page-header,
    .dashboard-hero,
    .kpi-card,
    div[data-testid="stMetric"],
    .exec-panel,
    .tool-card,
    .standard-card,
    .learning-card,
    .security-card,
    div[data-testid="stExpander"] details,
    .empty-state,
    .app-alert {{
        background: var(--qaqc-surface) !important;
        border-color: var(--qaqc-line) !important;
        box-shadow: var(--qaqc-shadow) !important;
        color: var(--qaqc-text) !important;
    }}

    .header-profile,
    .side-status,
    .module-card__stat,
    div[data-testid="stDataFrame"],
    .stDataFrame {{
        background: var(--qaqc-surface-2) !important;
        border-color: var(--qaqc-line) !important;
        color: var(--qaqc-text) !important;
    }}

    .app-bar__project,
    .header-profile__meta,
    .page-header p,
    .dashboard-hero p,
    .section-caption,
    .kpi-title,
    .kpi-detail,
    div[data-testid="stMetricLabel"],
    .empty-state p {{
        color: var(--qaqc-muted) !important;
    }}

    .app-bar__welcome,
    .app-bar__eyebrow,
    .page-header__eyebrow,
    .hero-eyebrow,
    .side-menu-title {{
        color: var(--qaqc-blue) !important;
    }}

    section[data-testid="stSidebar"] {{
        background: var(--qaqc-sidebar-bg) !important;
        border-right-color: rgba(148, 163, 184, 0.22) !important;
    }}

    section[data-testid="stSidebar"],
    section[data-testid="stSidebar"] * {{
        color: var(--qaqc-sidebar-text) !important;
    }}

    div[data-baseweb="input"] > div,
    div[data-baseweb="select"] > div,
    textarea {{
        background: var(--qaqc-input-bg) !important;
        border-color: var(--qaqc-line) !important;
        color: var(--qaqc-text) !important;
    }}

    input,
    textarea,
    div[data-baseweb="select"] span {{
        color: var(--qaqc-text) !important;
    }}

    input::placeholder,
    textarea::placeholder {{
        color: var(--qaqc-muted) !important;
        opacity: 0.78;
    }}

    .stButton button,
    div[data-testid="stPopover"] button,
    .stDownloadButton button {{
        background: var(--qaqc-blue) !important;
        border-color: color-mix(in srgb, var(--qaqc-blue) 72%, #0f172a) !important;
        color: #ffffff !important;
    }}

    .status-badge--open,
    .status-badge--warning {{
        background: color-mix(in srgb, var(--qaqc-warning) 14%, var(--qaqc-surface)) !important;
        border-color: color-mix(in srgb, var(--qaqc-warning) 36%, var(--qaqc-line)) !important;
        color: var(--qaqc-warning) !important;
    }}

    .status-badge--closed,
    .status-badge--success {{
        background: color-mix(in srgb, var(--qaqc-success) 14%, var(--qaqc-surface)) !important;
        border-color: color-mix(in srgb, var(--qaqc-success) 36%, var(--qaqc-line)) !important;
        color: var(--qaqc-success) !important;
    }}

    .status-badge--critical,
    .status-badge--danger {{
        background: color-mix(in srgb, var(--qaqc-danger) 14%, var(--qaqc-surface)) !important;
        border-color: color-mix(in srgb, var(--qaqc-danger) 36%, var(--qaqc-line)) !important;
        color: var(--qaqc-danger) !important;
    }}

    .status-badge--neutral {{
        background: var(--qaqc-surface-2) !important;
        border-color: var(--qaqc-line) !important;
        color: var(--qaqc-muted) !important;
    }}

    .js-plotly-plot,
    .js-plotly-plot .plotly,
    .js-plotly-plot .main-svg {{
        background: transparent !important;
    }}

    .js-plotly-plot .bg {{
        fill: var(--qaqc-surface-2) !important;
    }}

    .js-plotly-plot text {{
        fill: var(--qaqc-text) !important;
    }}

    /* Reference mockup alignment: dark enterprise shell with crisp data canvases. */
    .stApp {{
        background:
            radial-gradient(circle at 16% 0%, rgba(41, 112, 255, 0.22), transparent 30rem),
            radial-gradient(circle at 88% 6%, rgba(14, 165, 233, 0.12), transparent 26rem),
            linear-gradient(135deg, #071426 0%, #0b1f36 52%, #04101f 100%) !important;
    }}

    html,
    body,
    #root,
    .stApp,
    [data-testid="stApp"] {{
        background-color: #071426 !important;
        background-image:
            linear-gradient(135deg, rgba(3, 12, 25, 0.62), rgba(5, 22, 43, 0.52)),
            url("{page_background}") !important;
        background-position: center, center right !important;
        background-repeat: no-repeat, no-repeat !important;
        background-size: cover, cover !important;
        background-attachment: fixed, fixed !important;
    }}

    [data-testid="stAppViewContainer"],
    [data-testid="stMain"],
    [data-testid="stMainBlockContainer"],
    main,
    .main,
    .block-container {{
        background: transparent !important;
    }}

    .block-container {{
        max-width: 1560px !important;
        padding: 0.85rem 1rem 1.35rem !important;
    }}

    .app-bar {{
        background:
            linear-gradient(135deg, rgba(7, 20, 38, 0.98), rgba(11, 31, 54, 0.96)) !important;
        border: 1px solid rgba(209, 233, 255, 0.16) !important;
        border-radius: 8px !important;
        box-shadow: 0 14px 36px rgba(0, 0, 0, 0.28) !important;
        color: #ffffff !important;
        min-height: 4.25rem !important;
    }}

    .app-bar *,
    .app-bar__title,
    .app-bar__welcome,
    .app-bar__eyebrow,
    .app-bar__project,
    .header-profile__name,
    .header-profile__meta {{
        color: #ffffff !important;
    }}

    .header-profile {{
        background: rgba(255, 255, 255, 0.08) !important;
        border-color: rgba(209, 233, 255, 0.18) !important;
    }}

    .app-capability-strip {{
        align-items: center;
        display: flex;
        flex-wrap: wrap;
        gap: 0.38rem;
        justify-content: flex-end;
        max-width: 34rem;
    }}

    .app-capability-strip span {{
        background: rgba(255, 255, 255, 0.08);
        border: 1px solid rgba(209, 233, 255, 0.16);
        border-radius: 999px;
        color: #eaf2ff !important;
        font-size: 0.72rem;
        font-weight: 800;
        min-height: 1.75rem;
        padding: 0.34rem 0.56rem;
        white-space: nowrap;
    }}

    .page-header,
    .dashboard-hero,
    .kpi-card,
    div[data-testid="stMetric"],
    .exec-panel,
    .tool-card,
    .standard-card,
    .learning-card,
    .security-card,
    .empty-state,
    .app-alert,
    div[data-testid="stExpander"] details {{
        border-radius: 8px !important;
        outline: 1px solid rgba(23, 43, 77, 0.02);
    }}

    .page-header,
    .dashboard-hero {{
        margin-top: 0 !important;
        padding: 0.95rem 1.15rem 0.95rem 1.45rem !important;
        position: relative !important;
    }}

    .page-header::before,
    .dashboard-hero::before {{
        background: linear-gradient(180deg, var(--qaqc-blue), var(--qaqc-blue-2));
        border-radius: 999px;
        content: "";
        display: block;
        height: calc(100% - 1.4rem);
        left: 0.72rem;
        position: absolute;
        top: 0.7rem;
        width: 0.32rem;
    }}

    .page-header h1,
    .dashboard-hero h1 {{
        font-size: clamp(1.35rem, 2vw, 1.85rem) !important;
    }}

    .kpi-card,
    div[data-testid="stMetric"] {{
        min-height: 96px !important;
    }}

    .kpi-card:hover,
    div[data-testid="stMetric"]:hover,
    .exec-panel:hover,
    .tool-card:hover,
    .standard-card:hover,
    .learning-card:hover {{
        border-color: color-mix(in srgb, var(--qaqc-blue) 34%, var(--qaqc-line)) !important;
        box-shadow: 0 16px 34px rgba(15, 23, 42, 0.14) !important;
        transform: translateY(-1px) !important;
    }}

    div[data-testid="stDataFrame"] {{
        border-radius: 8px !important;
        box-shadow: 0 12px 28px rgba(15, 23, 42, 0.08) !important;
    }}

    div[data-testid="stDataFrame"] [role="gridcell"],
    div[data-testid="stDataFrame"] [role="columnheader"] {{
        min-height: 2.25rem !important;
    }}

    div[data-testid="stDataFrame"] [role="columnheader"] {{
        background: color-mix(in srgb, var(--qaqc-blue) 7%, var(--qaqc-surface)) !important;
        color: var(--qaqc-navy) !important;
        font-weight: 850 !important;
    }}

    section[data-testid="stSidebar"] {{
        background:
            radial-gradient(circle at 12% 0%, rgba(41, 112, 255, 0.22), transparent 16rem),
            linear-gradient(180deg, #071426 0%, #061120 100%) !important;
    }}

    .side-brand {{
        background: rgba(255, 255, 255, 0.04);
        border: 1px solid rgba(209, 233, 255, 0.12) !important;
        border-radius: 8px;
        margin: 0.45rem 0 0.65rem;
        padding: 0.75rem !important;
    }}

    .side-nav-link {{
        background: rgba(255, 255, 255, 0.02) !important;
        border-color: rgba(209, 233, 255, 0.08) !important;
    }}

    .side-nav-link:hover,
    .side-nav-link:focus-visible {{
        background: #155eef !important;
        border-color: #2970ff !important;
        color: #ffffff !important;
    }}

    .side-nav-group {{
        border-top: 1px solid rgba(209, 233, 255, 0.10);
        padding-top: 0.55rem;
    }}

    div[data-testid="stTabs"] div[role="tablist"] {{
        background: var(--qaqc-surface) !important;
        border: 1px solid var(--qaqc-line) !important;
        border-radius: 8px !important;
        padding: 0.22rem !important;
    }}

    div[data-testid="stTabs"] button[role="tab"] {{
        border-radius: 6px !important;
        min-height: 2.35rem !important;
    }}

    div[data-testid="stTabs"] button[aria-selected="true"] {{
        background: color-mix(in srgb, var(--qaqc-blue) 12%, var(--qaqc-surface)) !important;
        color: var(--qaqc-blue) !important;
    }}

    .side-nav-group,
    .nav-popover-group {{
        color: color-mix(in srgb, var(--qaqc-sidebar-text) 72%, var(--qaqc-blue)) !important;
        font-size: 0.68rem !important;
        font-weight: 850 !important;
        letter-spacing: 0.04em !important;
        margin: 0.85rem 0 0.28rem !important;
        text-transform: uppercase !important;
    }}

    .st-key-page_navigation_popover {{
        max-width: 3rem !important;
        width: 3rem !important;
    }}

    .st-key-page_navigation_popover div[data-testid="stPopover"] {{
        max-width: 3rem !important;
        width: 3rem !important;
    }}

    .st-key-page_navigation_popover div[data-testid="stPopover"] button {{
        background: #60a5fa !important;
        border: 1px solid rgba(147, 197, 253, 0.68) !important;
        box-shadow: 0 10px 24px rgba(30, 64, 175, 0.25) !important;
        color: #ffffff !important;
        justify-content: center !important;
        max-width: 3rem !important;
        min-height: 3rem !important;
        min-width: 3rem !important;
        padding: 0 !important;
        width: 3rem !important;
    }}

    .st-key-page_navigation_popover div[data-testid="stPopover"] button p {{
        clip: rect(0 0 0 0);
        clip-path: inset(50%);
        height: 1px;
        overflow: hidden;
        position: absolute;
        white-space: nowrap;
        width: 1px;
    }}

    .st-key-page_navigation_popover div[data-testid="stPopover"] button svg {{
        display: none !important;
    }}

    .st-key-page_navigation_popover [data-testid="stIconMaterial"] {{
        color: #ffffff !important;
        font-size: 1.65rem !important;
    }}

    div[data-baseweb="popover"]:has(.nav-popover-menu) > div,
    div[data-baseweb="popover"]:has(.st-key-nav_popover_menu) > div {{
        background: #031326 !important;
        border: 1px solid rgba(96, 165, 250, 0.30) !important;
        border-radius: 9px !important;
        box-shadow: 0 20px 48px rgba(0, 0, 0, 0.42) !important;
        min-width: 21.25rem !important;
    }}

    div[data-baseweb="popover"]:has(.nav-popover-menu) [data-testid="stTextInput"] input,
    div[data-baseweb="popover"]:has(.st-key-nav_popover_menu) [data-testid="stTextInput"] input {{
        background: #020c19 !important;
        border-color: rgba(148, 163, 184, 0.24) !important;
        color: #ffffff !important;
    }}

    div[data-baseweb="popover"]:has(.nav-popover-menu) [data-testid="stTextInput"] input::placeholder,
    div[data-baseweb="popover"]:has(.st-key-nav_popover_menu) [data-testid="stTextInput"] input::placeholder {{
        color: #cbd5e1 !important;
    }}

    .st-key-nav_popover_menu {{
        max-height: 30rem;
        min-width: 20.25rem;
        overflow-y: auto;
        padding: 0.08rem;
        width: 20.25rem;
    }}

    .st-key-nav_popover_menu div[data-testid="stExpander"] details {{
        background: #06182e !important;
        border: 1px solid rgba(96, 165, 250, 0.18) !important;
        border-radius: 0 !important;
        box-shadow: none !important;
        overflow: hidden;
    }}

    .st-key-nav_popover_menu div[data-testid="stExpander"] summary {{
        background: #07284c !important;
        min-height: 3.15rem !important;
        padding: 0.55rem 0.7rem !important;
    }}

    .st-key-nav_popover_menu div[data-testid="stExpander"] summary p,
    .st-key-nav_popover_menu div[data-testid="stExpander"] summary span,
    .st-key-nav_popover_menu div[data-testid="stExpander"] summary svg {{
        color: #ffffff !important;
        fill: #ffffff !important;
        font-size: 0.9rem !important;
        font-weight: 850 !important;
    }}

    .st-key-nav_popover_menu a[data-testid="stPageLink-NavLink"] {{
        background: #020c19 !important;
        border: 1px solid rgba(148, 163, 184, 0.14) !important;
        border-radius: 6px !important;
        color: #dbeafe !important;
        margin: 0.16rem 0 !important;
        min-height: 2.35rem !important;
        padding: 0.45rem 0.65rem !important;
    }}

    .st-key-nav_popover_menu a[data-testid="stPageLink-NavLink"]:hover {{
        background: #155eef !important;
        border-color: #60a5fa !important;
        color: #ffffff !important;
    }}

    .nav-popover-menu {{
        display: grid;
        gap: 0.38rem;
        max-height: 24rem;
        max-width: 20.25rem;
        min-width: 20.25rem;
        overflow-y: auto;
        padding: 0.12rem;
        width: 20.25rem;
    }}

    .nav-popover-section {{
        background: #06182e;
        border: 1px solid rgba(96, 165, 250, 0.18);
        border-radius: 7px;
        overflow: hidden;
    }}

    .nav-popover-section summary {{
        align-items: center;
        background: #07284c;
        color: #ffffff !important;
        cursor: pointer;
        display: flex;
        font-size: 0.8rem;
        font-weight: 850;
        justify-content: space-between;
        list-style: none;
        min-height: 2.55rem;
        padding: 0.5rem 0.65rem;
    }}

    .nav-popover-section summary::-webkit-details-marker {{ display: none; }}
    .nav-popover-section__title {{ align-items: center; display: flex; gap: 0.55rem; }}
    .nav-popover-section__icon {{
        align-items: center;
        color: #ffffff !important;
        display: inline-flex;
        font-size: 1rem;
        justify-content: center;
        width: 1.15rem;
    }}
    .nav-popover-section summary::after {{
        color: #bfdbfe;
        content: "⌄";
        font-size: 0.95rem;
        transition: transform 0.18s ease;
    }}
    .nav-popover-section[open] summary::after {{ transform: rotate(180deg); }}
    .nav-popover-section__links {{ display: grid; gap: 0.22rem; padding: 0.34rem; }}

    .nav-popover-link {{
        align-items: center;
        background: rgba(2, 12, 25, 0.72);
        border: 1px solid rgba(148, 163, 184, 0.14);
        border-radius: 6px;
        color: #dbeafe !important;
        display: flex;
        font-size: 0.84rem;
        font-weight: 700;
        min-height: 2.35rem;
        padding: 0.45rem 0.65rem;
        text-decoration: none !important;
    }}

    .nav-popover-link:hover,
    .nav-popover-link:focus-visible {{
        background: #155eef;
        border-color: #60a5fa;
        color: #ffffff !important;
    }}

    .nav-popover-link[aria-current="page"] {{
        background: rgba(37, 99, 235, 0.36);
        border-color: rgba(96, 165, 250, 0.62);
        color: #ffffff !important;
    }}

    section[data-testid="stSidebar"] div[data-testid="stSelectbox"] {{
        margin-bottom: 0.4rem;
    }}

    div[data-testid="stDataFrame"] * {{
        font-size: 0.82rem !important;
    }}

    .stButton button:focus-visible,
    .stDownloadButton button:focus-visible,
    div[data-testid="stTabs"] button[role="tab"]:focus-visible,
    div[data-testid="stExpander"] summary:focus-visible,
    div[data-baseweb="select"]:focus-within,
    a:focus-visible,
    input:focus-visible,
    textarea:focus-visible {{
        outline: 3px solid color-mix(in srgb, var(--qaqc-blue) 48%, transparent) !important;
        outline-offset: 2px !important;
    }}

    /* Shared hover language across every page and Streamlit surface. */
    .page-header,
    .dashboard-hero,
    .kpi-card,
    div[data-testid="stMetric"],
    .exec-panel,
    .module-card,
    .tool-card,
    .standard-card,
    .learning-card,
    .security-card,
    .analytics-metric,
    .cal-metric,
    .cal-action-panel,
    div[data-testid="stVerticalBlockBorderWrapper"],
    div[data-testid="stExpander"] details,
    div[data-testid="stDataFrame"] {{
        backdrop-filter: blur(12px) saturate(118%);
        transform-style: preserve-3d;
        transition: transform 0.2s ease, box-shadow 0.2s ease, border-color 0.2s ease, filter 0.2s ease !important;
        will-change: transform;
    }}

    .page-header,
    .dashboard-hero,
    .kpi-card,
    div[data-testid="stMetric"],
    .exec-panel,
    .module-card,
    .tool-card,
    .standard-card,
    .learning-card,
    .security-card,
    .analytics-metric,
    .cal-metric,
    .cal-action-panel,
    div[data-testid="stExpander"] details {{
        background-color: color-mix(in srgb, var(--qaqc-surface) 84%, transparent) !important;
    }}

    .page-header:hover,
    .dashboard-hero:hover,
    .kpi-card:hover,
    div[data-testid="stMetric"]:hover,
    .exec-panel:hover,
    .module-card:hover,
    .tool-card:hover,
    .standard-card:hover,
    .learning-card:hover,
    .security-card:hover,
    .analytics-metric:hover,
    .cal-metric:hover,
    .cal-action-panel:hover,
    div[data-testid="stVerticalBlockBorderWrapper"]:hover,
    div[data-testid="stExpander"] details:hover,
    div[data-testid="stDataFrame"]:hover {{
        border-color: color-mix(in srgb, var(--qaqc-blue) 54%, var(--qaqc-line)) !important;
        box-shadow: 0 24px 46px rgba(2, 12, 27, 0.30), 0 10px 22px color-mix(in srgb, var(--qaqc-blue) 16%, transparent) !important;
        filter: brightness(1.025);
        transform: perspective(950px) translateY(-5px) rotateX(1.25deg) rotateY(-0.7deg) !important;
    }}

    .stButton button,
    .stDownloadButton button,
    div[data-testid="stPopover"] button,
    div[data-testid="stTabs"] button[role="tab"],
    .side-nav-link,
    .nav-popover-link {{
        transition: transform 0.18s ease, box-shadow 0.18s ease, background 0.18s ease, border-color 0.18s ease !important;
    }}

    .stButton button:hover,
    .stDownloadButton button:hover,
    div[data-testid="stPopover"] button:hover,
    div[data-testid="stTabs"] button[role="tab"]:hover,
    .side-nav-link:hover,
    .nav-popover-link:hover {{
        box-shadow: 0 10px 24px rgba(21, 94, 239, 0.28) !important;
        transform: perspective(700px) translateY(-2px) rotateX(2deg) !important;
    }}

    div[data-testid="stDataFrame"] [role="row"]:hover [role="gridcell"] {{
        background-color: color-mix(in srgb, var(--qaqc-blue) 10%, var(--qaqc-surface-2)) !important;
    }}

    /* Progressive scroll-entry motion; unsupported browsers keep the static layout. */
    @supports (animation-timeline: view()) {{
        @keyframes qaqc-scroll-reveal {{
            from {{
                opacity: 0.35;
                transform: perspective(950px) translateY(24px) rotateX(2deg);
            }}
            to {{
                opacity: 1;
                transform: perspective(950px) translateY(0) rotateX(0);
            }}
        }}

        [data-testid="stMainBlockContainer"] > div > div,
        .page-header,
        .dashboard-hero,
        .exec-metric,
        .analytics-metric,
        .cal-metric,
        .cal-action-panel {{
            animation: qaqc-scroll-reveal both linear;
            animation-range: entry 0% cover 22%;
            animation-timeline: view();
        }}
    }}

    @media (max-width: 768px) {{
        html,
        body,
        #root,
        .stApp,
        [data-testid="stApp"] {{
            background-attachment: scroll, scroll !important;
        }}

        .app-capability-strip {{
            justify-content: flex-start;
            max-width: 100%;
        }}

        .app-capability-strip span {{
            font-size: 0.68rem;
        }}

        section[data-testid="stSidebar"] {{
            width: min(88vw, 22rem) !important;
        }}

        .side-nav-link {{
            min-height: 2.9rem !important;
        }}

        div[data-testid="stDataFrame"] {{
            max-width: calc(100vw - 1.4rem) !important;
        }}

        .app-logo-img--evomec img,
        .app-logo-img--nlng img {{
            max-height: 2.15rem !important;
        }}
    }}

    /* Final responsive contract for desktop, tablet, and phone layouts. */
    .st-key-primary_navigation_row {{
        margin: 0.45rem 0 0.75rem;
        width: 100%;
    }}

    .st-key-primary_navigation_row div[data-testid="stHorizontalBlock"] {{
        align-items: center;
    }}

    .st-key-primary_navigation_row div[data-testid="column"],
    .st-key-navigation_account div[data-testid="column"] {{
        min-width: 0 !important;
    }}

    .st-key-navigation_account div[data-testid="stPopover"] button {{
        max-width: 100%;
        overflow: hidden;
        text-overflow: ellipsis;
    }}

    img, svg, canvas {{
        max-width: 100%;
    }}

    div[data-testid="stDataFrame"],
    div[data-testid="stTable"],
    .element-container:has(table) {{
        max-width: 100%;
        overflow-x: auto !important;
    }}

    @media (max-width: 1024px) {{
        .block-container {{
            max-width: 100% !important;
            padding: 0.7rem 0.8rem 1.25rem !important;
        }}

        .app-capability-strip {{
            gap: 0.25rem !important;
        }}

        .app-capability-strip span:nth-child(-n+3) {{
            display: none;
        }}

        .st-key-primary_navigation_row > div > div[data-testid="stHorizontalBlock"] {{
            gap: 0.5rem !important;
        }}
    }}

    @media (max-width: 768px) {{
        .block-container {{
            padding: 0.55rem 0.55rem 1rem !important;
        }}

        .app-bar {{
            gap: 0.55rem !important;
            padding: 0.72rem !important;
        }}

        .app-bar__eyebrow {{
            font-size: 0.78rem !important;
        }}

        .app-bar__title {{
            font-size: 0.9rem !important;
            line-height: 1.2 !important;
        }}

        .app-bar__project,
        .app-capability-strip,
        .command-tools {{
            display: none !important;
        }}

        .st-key-primary_navigation_row > div > div[data-testid="stHorizontalBlock"] {{
            align-items: stretch !important;
            flex-wrap: nowrap !important;
        }}

        .st-key-primary_navigation_row > div > div[data-testid="stHorizontalBlock"] > div[data-testid="column"]:first-child {{
            flex: 0 0 3rem !important;
            width: 3rem !important;
        }}

        .st-key-primary_navigation_row > div > div[data-testid="stHorizontalBlock"] > div[data-testid="column"]:nth-child(2) {{
            display: none !important;
        }}

        .st-key-primary_navigation_row > div > div[data-testid="stHorizontalBlock"] > div[data-testid="column"]:last-child {{
            flex: 1 1 auto !important;
            width: auto !important;
        }}

        .st-key-navigation_account div[data-testid="stHorizontalBlock"] {{
            display: flex !important;
            flex-wrap: nowrap !important;
        }}

        .header-account-avatar {{
            height: 2.25rem !important;
            width: 2.25rem !important;
        }}

        .st-key-navigation_account div[data-testid="stPopover"] button,
        .st-key-primary_navigation_row div[data-testid="stPopover"] button {{
            font-size: 0.76rem !important;
            min-height: 2.45rem !important;
            padding-left: 0.55rem !important;
            padding-right: 0.55rem !important;
        }}

        .st-key-page_navigation_popover div[data-testid="stPopover"] button {{
            min-height: 3rem !important;
            padding: 0 !important;
        }}

        .page-header,
        .dashboard-hero {{
            padding: 0.8rem 0.8rem 0.8rem 1.25rem !important;
        }}

        .page-header h1,
        .dashboard-hero h1 {{
            font-size: 1.25rem !important;
        }}

        div[data-testid="stForm"],
        div[data-testid="stExpander"],
        .security-card,
        .exec-panel {{
            max-width: 100% !important;
        }}

        input, textarea, select {{
            font-size: 16px !important;
        }}

        .stButton button,
        .stDownloadButton button,
        div[data-testid="stFormSubmitButton"] button {{
            min-height: 2.75rem !important;
        }}

        .js-plotly-plot,
        .plot-container,
        .svg-container {{
            max-width: calc(100vw - 1.1rem) !important;
            width: 100% !important;
        }}
    }}

    @media (max-width: 430px) {{
        .app-logo-img--evomec {{ display: none !important; }}
        .app-brand-lockup {{ gap: 0.5rem !important; }}
        .app-bar__title {{ font-size: 0.82rem !important; }}
        .st-key-navigation_account div[data-testid="stPopover"] button {{ font-size: 0.7rem !important; }}
        div[data-baseweb="popover"]:has(.nav-popover-menu) > div,
        div[data-baseweb="popover"]:has(.st-key-nav_popover_menu) > div {{
            max-width: calc(100vw - 1rem) !important;
            min-width: calc(100vw - 1rem) !important;
            width: calc(100vw - 1rem) !important;
        }}
        .st-key-nav_popover_menu {{
            max-height: 65vh;
            min-width: 0;
            width: 100%;
        }}
        .nav-popover-menu {{
            max-height: 65vh;
            max-width: none;
            min-width: 0;
            overflow-y: auto;
            width: 100%;
        }}
    }}

    @media (hover: none), (pointer: coarse) {{
        .exec-metric:hover,
        .page-header:hover,
        .dashboard-hero:hover,
        .kpi-card:hover,
        div[data-testid="stMetric"]:hover,
        .exec-panel:hover,
        .module-card:hover,
        .tool-card:hover,
        .standard-card:hover,
        .learning-card:hover,
        .security-card:hover,
        .analytics-metric:hover,
        .cal-metric:hover,
        .cal-action-panel:hover,
        div[data-testid="stVerticalBlockBorderWrapper"]:hover,
        div[data-testid="stExpander"] details:hover,
        div[data-testid="stDataFrame"]:hover,
        .stButton button:hover,
        .stDownloadButton button:hover,
        div[data-testid="stPopover"] button:hover {{
            transform: none !important;
        }}
    }}

    @media (prefers-reduced-motion: reduce) {{
        *, *::before, *::after {{
            animation-duration: 0.01ms !important;
            animation-iteration-count: 1 !important;
            scroll-behavior: auto !important;
            transition-duration: 0.01ms !important;
        }}

        .exec-metric:hover,
        .page-header:hover,
        .dashboard-hero:hover,
        .kpi-card:hover,
        div[data-testid="stMetric"]:hover,
        .exec-panel:hover,
        .module-card:hover,
        .tool-card:hover,
        .standard-card:hover,
        .learning-card:hover,
        .security-card:hover,
        .analytics-metric:hover,
        .cal-metric:hover,
        .cal-action-panel:hover,
        div[data-testid="stVerticalBlockBorderWrapper"]:hover,
        div[data-testid="stExpander"] details:hover,
        div[data-testid="stDataFrame"]:hover,
        .stButton button:hover,
        .stDownloadButton button:hover,
        div[data-testid="stPopover"] button:hover {{
            transform: none !important;
        }}
    }}
    </style>
    """,
        unsafe_allow_html=True,
    )


# =========================
# IMAGE FINDER
# =========================


def style_chart(fig):
    dark = get_theme_mode() == "Dark"
    fig.update_layout(
        template="plotly_dark" if dark else "plotly_white",
        paper_bgcolor="rgba(255, 255, 255, 0)" if not dark else "rgba(17, 24, 39, 0)",
        plot_bgcolor="rgba(248, 250, 252, 0.72)" if not dark else "rgba(15, 23, 42, 0.72)",
        colorway=(CHART_COLORS_DARK if dark else CHART_COLORS_LIGHT),
        font=dict(color="#e5edf8" if dark else "#111827", family="Inter, Segoe UI, Arial, sans-serif", size=12),
        title=dict(font=dict(size=16, color="#f8fafc" if dark else "#0f172a"), x=0.02, xanchor="left"),
        margin=dict(l=34, r=24, t=56, b=38),
        legend=dict(bgcolor="rgba(0,0,0,0)", font=dict(color="#cbd5e1" if dark else "#475569"), orientation="h", yanchor="bottom", y=1.02),
    )
    fig.update_xaxes(
        gridcolor="rgba(148, 163, 184, 0.18)" if dark else "rgba(148, 163, 184, 0.22)",
        linecolor="rgba(148, 163, 184, 0.28)" if dark else "rgba(148, 163, 184, 0.35)",
        zerolinecolor="rgba(148, 163, 184, 0.22)" if dark else "rgba(148, 163, 184, 0.25)",
        title_font=dict(color="#cbd5e1" if dark else "#475569"),
    )
    fig.update_yaxes(
        gridcolor="rgba(148, 163, 184, 0.18)" if dark else "rgba(148, 163, 184, 0.22)",
        linecolor="rgba(148, 163, 184, 0.28)" if dark else "rgba(148, 163, 184, 0.35)",
        zerolinecolor="rgba(148, 163, 184, 0.22)" if dark else "rgba(148, 163, 184, 0.25)",
        title_font=dict(color="#cbd5e1" if dark else "#475569"),
    )
    return fig


def render_line_chart(df, x, y, title="Trend"):
    if df.empty:
        st.info("No data for chart")
        return

    fig = px.line(df, x=x, y=y, title=title, markers=True)
    fig.update_traces(line=dict(color="#38bdf8", width=3), marker=dict(size=7))
    style_chart(fig)
    st.plotly_chart(fig, width="stretch")


def render_bar_chart(df, x, y, title="Bar Chart"):
    if df.empty:
        st.info("No data for chart")
        return

    fig = px.bar(df, x=x, y=y, title=title)
    fig.update_traces(marker_color="#22c55e")
    style_chart(fig)
    st.plotly_chart(fig, width="stretch")


def render_pie_chart(df, names, values, title="Distribution"):
    if df.empty:
        st.info("No data for chart")
        return

    fig = px.pie(df, names=names, values=values, title=title)
    fig.update_traces(
        marker=dict(colors=["#38bdf8", "#22c55e", "#f59e0b", "#ef4444", "#a78bfa"])
    )
    style_chart(fig)
    st.plotly_chart(fig, width="stretch")


# =========================
# FILTERS (SAFE)
# =========================
def global_filter_sidebar(data):
    st.sidebar.header("Global Filters")

    if not isinstance(data, dict):
        return data

    projects = set()

    for df in data.values():
        if isinstance(df, pd.DataFrame) and "Project" in df.columns:
            projects.update(df["Project"].dropna().astype(str).unique())

    projects = sorted(list(projects))

    if "global_project" not in st.session_state:
        st.session_state.global_project = "All"

    selected_project = st.sidebar.selectbox(
        "Project",
        ["All"] + projects,
        index=0,
        key="global_project_selectbox"
    )

    st.session_state.global_project = selected_project

    # ✅ IMPORTANT FIX STARTS HERE
    if selected_project == "All":
        return data

    filtered = {}

    for k, df in data.items():
        if isinstance(df, pd.DataFrame) and "Project" in df.columns:
            filtered[k] = df[df["Project"] == selected_project]
        else:
            filtered[k] = df

    return filtered   # 🔥 THIS WAS MISSING


def apply_filters(df, filters=None, date_column=None):

    if not isinstance(df, pd.DataFrame):
        return df

    filtered_df = df.copy()

    if isinstance(filters, dict):
        for col, value in filters.items():
            if value is not None and col in filtered_df.columns:
                filtered_df = filtered_df[
                    filtered_df[col] == value
                ]

    if date_column and date_column in filtered_df.columns:
        filtered_df[date_column] = pd.to_datetime(
            filtered_df[date_column],
            errors="coerce"
        )
        filtered_df = filtered_df.dropna(
            subset=[date_column]
        )

    return filtered_df
