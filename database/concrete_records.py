"""Persistent manual concrete-volume entry support."""

from datetime import datetime, timezone
from pathlib import Path
import shutil
import tempfile
from urllib.request import urlopen
import uuid

from openpyxl import load_workbook

from database.cloudinary_storage import (
    DEFAULT_MASTER_WORKBOOK_PUBLIC_ID,
    get_master_workbook_reference,
    upload_master_workbook,
)
from database.settings import get_setting


BASE_DIR = Path(__file__).resolve().parents[1]
LOCAL_WORKBOOK = BASE_DIR / "data" / "QAQC_Master.xlsx"
SHEET_NAME = "Concrete Tracker"
REQUIRED_COLUMNS = [
    "Pour_ID", "Project", "Date", "Location", "Volume",
    "Entered_By", "Entered_At", "Entry_Notes",
]


def _download_current_workbook(destination):
    cloudinary_configured = bool(str(get_setting("CLOUDINARY_URL", "")).strip())
    public_id = str(
        get_setting("QAQC_MASTER_WORKBOOK_PUBLIC_ID", DEFAULT_MASTER_WORKBOOK_PUBLIC_ID)
    ).strip() or DEFAULT_MASTER_WORKBOOK_PUBLIC_ID
    if cloudinary_configured:
        try:
            reference = get_master_workbook_reference(public_id)
            with urlopen(reference["url"], timeout=30) as response, destination.open("wb") as output:
                shutil.copyfileobj(response, output)
            return True, public_id
        except Exception:
            pass
    if not LOCAL_WORKBOOK.exists():
        raise RuntimeError("The QA/QC master workbook is unavailable.")
    shutil.copy2(LOCAL_WORKBOOK, destination)
    return cloudinary_configured, public_id


def append_concrete_volume(*, entry_date, project, location, volume, username, notes=""):
    project = str(project or "").strip()
    location = str(location or "").strip()
    username = str(username or "admin").strip()
    notes = str(notes or "").strip()
    volume = float(volume)
    if not project:
        raise ValueError("Project is required.")
    if not location:
        raise ValueError("Location or work area is required.")
    if volume <= 0:
        raise ValueError("Concrete volume must be greater than zero.")

    entered_at = datetime.now(timezone.utc)
    pour_id = f"P-MAN-{entry_date:%Y%m%d}-{uuid.uuid4().hex[:6].upper()}"
    record = {
        "Pour_ID": pour_id,
        "Project": project,
        "Date": datetime.combine(entry_date, datetime.min.time()),
        "Location": location,
        "Volume": volume,
        "Entered_By": username,
        "Entered_At": entered_at.replace(tzinfo=None),
        "Entry_Notes": notes,
    }

    with tempfile.TemporaryDirectory(prefix="qaqc-concrete-") as temp_dir:
        workbook_path = Path(temp_dir) / "QAQC_Master.xlsx"
        upload_to_cloud, public_id = _download_current_workbook(workbook_path)
        workbook = load_workbook(workbook_path)
        worksheet = workbook[SHEET_NAME] if SHEET_NAME in workbook.sheetnames else workbook.create_sheet(SHEET_NAME)

        headers = {}
        for cell in worksheet[1]:
            if cell.value:
                headers[str(cell.value).strip()] = cell.column
        for column in REQUIRED_COLUMNS:
            if column not in headers:
                next_column = max(headers.values(), default=0) + 1
                worksheet.cell(row=1, column=next_column, value=column)
                headers[column] = next_column

        row_number = worksheet.max_row + 1
        for column, value in record.items():
            worksheet.cell(row=row_number, column=headers[column], value=value)
        worksheet.cell(row=row_number, column=headers["Date"]).number_format = "yyyy-mm-dd"
        worksheet.cell(row=row_number, column=headers["Entered_At"]).number_format = "yyyy-mm-dd hh:mm:ss"
        workbook.save(workbook_path)

        storage = "local"
        if upload_to_cloud:
            upload_master_workbook(workbook_path, public_id=public_id)
            storage = "cloudinary"
        try:
            shutil.copy2(workbook_path, LOCAL_WORKBOOK)
        except OSError:
            # Hosted deployments can be read-only; the Cloudinary version is authoritative.
            pass

    record["Date"] = record["Date"].date().isoformat()
    record["Entered_At"] = entered_at.isoformat()
    return record, storage
