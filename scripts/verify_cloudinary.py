"""Verify Cloudinary upload -> MongoDB ticket persistence, then clean up."""

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from database.cloudinary_storage import delete_attachment, upload_support_attachment  # noqa: E402
from database.mongo_support import create_ticket, ensure_support_schema  # noqa: E402


class TestUpload:
    def __init__(self, path):
        self.path = Path(path)
        self.name = "cloudinary-ui-backend-test.png"
        self.type = "image/png"
        self.size = self.path.stat().st_size

    def getvalue(self):
        return self.path.read_bytes()


def main():
    attachment = None
    ticket = None
    collection = ensure_support_schema()
    try:
        attachment = upload_support_attachment(TestUpload(ROOT_DIR / "assets" / "evomec_logo.png"))
        ticket = create_ticket(
            "system-e2e-test",
            "test@evomec.local",
            "Cloudinary upload verification",
            "Technical issue",
            "Automated front-end upload backend verification.",
            attachment=attachment,
        )
        saved = collection.find_one({"ticket_id": ticket["ticket_id"]}, {"_id": 0})
        assert saved and saved["attachment"]["url"].startswith("https://res.cloudinary.com/")
        assert saved["attachment"]["public_id"] == attachment["public_id"]
        print("Cloudinary upload, secure URL, and MongoDB attachment persistence verified.")
    finally:
        if ticket:
            collection.delete_one({"ticket_id": ticket["ticket_id"]})
        if attachment and not delete_attachment(attachment):
            raise RuntimeError("Cloudinary verification asset cleanup failed.")
        collection.delete_many({"username": "system-e2e-test"})


if __name__ == "__main__":
    main()
