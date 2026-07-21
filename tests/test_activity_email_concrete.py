import sys
import tempfile
import unittest
from datetime import date, datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from openpyxl import Workbook, load_workbook


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import auth
from database import audit_log, concrete_records
from scripts import upload_dashboard_backup


class FakeSMTP:
    sent_message = None

    def __init__(self, host, port, timeout):
        self.host = host
        self.port = port
        self.timeout = timeout

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def starttls(self):
        return None

    def login(self, username, password):
        self.credentials = (username, password)

    def send_message(self, message):
        type(self).sent_message = message


class FakeAuditCollection:
    def __init__(self):
        self.inserted = None
        self.updates = []

    def insert_one(self, document):
        self.inserted = dict(document)
        return SimpleNamespace(inserted_id="mongo-id")

    def update_one(self, query, update):
        self.updates.append((query, update))


class DashboardFeatureTests(unittest.TestCase):
    def test_activity_archive_configures_cloudinary_directly(self):
        upload_result = {
            "secure_url": "https://cloudinary.example/event.json",
            "public_id": "qaqc-dashboard/activity-logs/2026/07/21/event.json",
        }
        record = {
            "event_id": "event",
            "occurred_at": datetime(2026, 7, 21, 14, 5, tzinfo=timezone.utc),
            "action": "test",
        }
        with patch.object(
            audit_log,
            "get_setting",
            return_value="cloudinary://api-key:api-secret@cloud-name",
        ), patch.object(
            audit_log.cloudinary.uploader,
            "upload",
            return_value=upload_result,
        ) as upload:
            archive = audit_log._upload_activity_record(record)

        self.assertEqual(archive["public_id"], upload_result["public_id"])
        self.assertEqual(upload.call_args.kwargs["type"], "authenticated")
        self.assertEqual(upload.call_args.kwargs["resource_type"], "raw")

    def test_admin_approval_sends_email_and_records_delivery(self):
        users = {
            "requestor": {
                "username": "requestor",
                "email": "requestor@example.com",
                "name": "QA Requestor",
                "role": "user",
                "status": "pending",
            }
        }
        smtp_settings = {
            "QAQC_SMTP_HOST": "smtp.example.com",
            "QAQC_SMTP_PORT": "587",
            "QAQC_SMTP_USER": "mailer@example.com",
            "QAQC_SMTP_PASSWORD": "app-password",
            "QAQC_SMTP_FROM": "QAQC <mailer@example.com>",
            "QAQC_SMTP_STARTTLS": "1",
            "QAQC_SMTP_SSL": "0",
            "QAQC_APP_URL": "https://qaqc.example.com",
        }
        snapshots = []
        with patch.object(auth, "_load_users", return_value=users), \
             patch.object(auth, "current_user", return_value={"username": "admin", "role": "admin"}), \
             patch.object(auth, "_try_save_users", side_effect=lambda value: snapshots.append(dict(value["requestor"])) or True), \
             patch.object(auth, "get_setting", side_effect=lambda name, default="": smtp_settings.get(name, default)), \
             patch.object(auth.smtplib, "SMTP", FakeSMTP), \
             patch.object(auth, "record_activity") as activity:
            ok, message = auth.approve_user("requestor", "viewer")

        self.assertTrue(ok)
        self.assertEqual(message, "Approved and email sent.")
        self.assertEqual(FakeSMTP.sent_message["To"], "requestor@example.com")
        self.assertIn("access approved", FakeSMTP.sent_message["Subject"].lower())
        body = FakeSMTP.sent_message.get_content()
        self.assertIn("Assigned role: Viewer", body)
        self.assertIn("https://qaqc.example.com", body)
        self.assertIsNotNone(snapshots[-1]["approval_email_sent_at"])
        self.assertIsNone(snapshots[-1]["approval_email_error"])
        activity.assert_called_once()

    def test_activity_is_saved_to_mongodb_and_cloudinary_without_secrets(self):
        collection = FakeAuditCollection()
        archive = {
            "url": "https://cloudinary.example/activity.json",
            "public_id": "qaqc-dashboard/activity-logs/2026/07/21/event.json",
        }
        with patch.object(audit_log, "ensure_activity_log", return_value=collection), \
             patch.object(audit_log, "_upload_activity_record", return_value=archive):
            saved = audit_log.record_activity(
                "update_record",
                actor={"username": "tester", "name": "Test User", "role": "user"},
                details={"record": "NCR-1", "password": "must-not-be-stored"},
            )

        self.assertTrue(saved)
        self.assertEqual(collection.inserted["username"], "tester")
        self.assertNotIn("password", collection.inserted["details"])
        self.assertEqual(collection.updates[-1][1]["$set"]["cloud_archive_status"], "archived")

    def test_admin_can_append_daily_concrete_volume(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            workbook_path = Path(temp_dir) / "QAQC_Master.xlsx"
            workbook = Workbook()
            worksheet = workbook.active
            worksheet.title = "Concrete Tracker"
            worksheet.append(["Pour_ID", "Project", "Date", "Location", "Volume"])
            workbook.save(workbook_path)

            with patch.object(concrete_records, "LOCAL_WORKBOOK", workbook_path), \
                 patch.object(concrete_records, "get_setting", return_value=""):
                record, storage = concrete_records.append_concrete_volume(
                    entry_date=date(2026, 7, 21),
                    project="NLNG",
                    location="Tank foundation",
                    volume=42.5,
                    username="admin",
                    notes="Daily total",
                )

            saved_workbook = load_workbook(workbook_path, data_only=True)
            saved_sheet = saved_workbook["Concrete Tracker"]
            headers = [cell.value for cell in saved_sheet[1]]
            row = {headers[index]: value for index, value in enumerate(next(saved_sheet.iter_rows(min_row=2, max_row=2, values_only=True)))}
            self.assertEqual(storage, "local")
            self.assertEqual(row["Project"], "NLNG")
            self.assertEqual(row["Volume"], 42.5)
            self.assertEqual(row["Entered_By"], "admin")
            self.assertEqual(record["Location"], "Tank foundation")

    def test_dashboard_backup_excludes_standards_and_secrets(self):
        self.assertFalse(upload_dashboard_backup.should_include(ROOT_DIR / "assets" / "standards" / "example.pdf"))
        self.assertFalse(upload_dashboard_backup.should_include(ROOT_DIR / ".env"))
        self.assertFalse(upload_dashboard_backup.should_include(ROOT_DIR / "data" / "users.json"))
        self.assertFalse(upload_dashboard_backup.should_include(ROOT_DIR / "data" / "profile_photos" / "user.png"))
        self.assertFalse(upload_dashboard_backup.should_include(ROOT_DIR / "tmp" / "report.pdf"))
        self.assertTrue(upload_dashboard_backup.should_include(ROOT_DIR / "auth.py"))


if __name__ == "__main__":
    unittest.main()
