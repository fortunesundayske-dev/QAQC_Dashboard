import ctypes
import sys
from pathlib import Path

import pandas as pd


BASE_DIR = Path(__file__).resolve().parents[1]
EXCEL_FILE = BASE_DIR / "data" / "QAQC_Master.xlsx"

if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from utils import get_calibration_reminders, get_teams_webhook_url, send_calibration_teams_alerts


def load_calibration_data():
    if not EXCEL_FILE.exists():
        return {"Calibration Log": pd.DataFrame()}
    try:
        return {"Calibration Log": pd.read_excel(EXCEL_FILE, sheet_name="Calibration Log")}
    except Exception:
        return {"Calibration Log": pd.DataFrame()}


def clean_text(value):
    if pd.isna(value):
        return ""
    return str(value).strip()


def popup_message_from_records(records, limit=8):
    if records is None or records.empty:
        return "No active calibration reminders today."

    overdue = int((records["Days_Until_Due"] < 0).sum())
    due_soon = int(((records["Days_Until_Due"] >= 0) & (records["Days_Until_Due"] <= 21)).sum())
    lines = [
        f"{len(records)} calibration reminder(s)",
        f"Overdue: {overdue}",
        f"Due within 21 days: {due_soon}",
        "",
    ]

    for _, row in records.head(limit).iterrows():
        equipment = clean_text(row.get("Equipment_Type", "Equipment")) or "Equipment"
        identifier = clean_text(row.get("Tag_Number", "")) or clean_text(row.get("Serial_No", "")) or clean_text(row.get("Calibration_ID", "N/A"))
        due_date = pd.to_datetime(row.get("Next_Due_Date"), errors="coerce")
        due_text = "N/A" if pd.isna(due_date) else due_date.strftime("%Y-%m-%d")
        days = int(row.get("Days_Until_Due", 0))
        status = f"Overdue by {abs(days)} day(s)" if days < 0 else f"Due in {days} day(s)"
        lines.append(f"- {equipment} | ID: {identifier} | Due: {due_text} | {status}")

    if len(records) > limit:
        lines.append(f"- plus {len(records) - limit} more")
    return "\n".join(lines)


def show_desktop_prompt(message):
    try:
        ctypes.windll.user32.MessageBoxW(None, str(message), "Calibration Reminder", 0x40)
    except (AttributeError, OSError):
        return


def main():
    data = load_calibration_data()
    records = get_calibration_reminders(data)
    if records.empty:
        return

    show_desktop_prompt(popup_message_from_records(records))
    result = send_calibration_teams_alerts(records)
    if not get_teams_webhook_url():
        print("Microsoft Teams webhook is not configured. Teams alerts were skipped.")
    elif result.get("failed"):
        print(f"Teams calibration alerts completed with {result['failed']} failed delivery attempt(s).")
    else:
        print(f"Teams calibration alerts sent: {result['sent']}. Skipped: {result['skipped']}.")


if __name__ == "__main__":
    main()
