"""Cloudinary file storage used by the customer-support UI."""

from pathlib import Path

from dotenv import load_dotenv


load_dotenv(Path(__file__).resolve().parents[1] / ".env")

import cloudinary.uploader  # noqa: E402
import cloudinary.api  # noqa: E402

from database.settings import get_setting  # noqa: E402


cloudinary_url = str(get_setting("CLOUDINARY_URL", "")).strip()
if cloudinary_url:
    cloudinary.config(cloudinary_url=cloudinary_url)

DEFAULT_MASTER_WORKBOOK_PUBLIC_ID = "qaqc-dashboard/data/QAQC_Master.xlsx"


MAX_ATTACHMENT_BYTES = 10 * 1024 * 1024
ALLOWED_ATTACHMENT_TYPES = ["png", "jpg", "jpeg", "pdf", "doc", "docx", "xls", "xlsx", "csv", "txt"]


def upload_support_attachment(uploaded_file):
    """Upload a Streamlit UploadedFile-compatible object to Cloudinary."""
    if uploaded_file.size > MAX_ATTACHMENT_BYTES:
        raise ValueError("The attachment is larger than 10 MB.")
    suffix = Path(uploaded_file.name).suffix.lower().lstrip(".")
    if suffix not in ALLOWED_ATTACHMENT_TYPES:
        raise ValueError("This attachment type is not supported.")
    result = cloudinary.uploader.upload(
        uploaded_file.getvalue(),
        resource_type="auto",
        folder="qaqc-dashboard/support",
        use_filename=True,
        unique_filename=True,
        filename_override=uploaded_file.name,
    )
    return {
        "name": uploaded_file.name,
        "content_type": uploaded_file.type or "application/octet-stream",
        "bytes": int(result.get("bytes") or uploaded_file.size),
        "url": result["secure_url"],
        "public_id": result["public_id"],
        "resource_type": result.get("resource_type", "raw"),
    }


def delete_attachment(attachment):
    if not attachment or not attachment.get("public_id"):
        return False
    result = cloudinary.uploader.destroy(
        attachment["public_id"],
        resource_type=attachment.get("resource_type", "image"),
        invalidate=True,
    )
    return result.get("result") in {"ok", "not found"}


def upload_profile_photo(uploaded_file, username):
    if uploaded_file.size > 5 * 1024 * 1024:
        raise ValueError("Profile photos must be 5 MB or smaller.")
    suffix = Path(uploaded_file.name).suffix.lower().lstrip(".")
    if suffix not in {"png", "jpg", "jpeg"}:
        raise ValueError("Profile photos must be PNG or JPEG files.")
    result = cloudinary.uploader.upload(
        uploaded_file.getvalue(),
        resource_type="image",
        folder="qaqc-dashboard/profiles",
        public_id=username,
        overwrite=True,
        invalidate=True,
        transformation=[{"width": 512, "height": 512, "crop": "fill", "gravity": "face"}],
    )
    return {
        "url": result["secure_url"],
        "public_id": result["public_id"],
        "resource_type": "image",
        "bytes": int(result.get("bytes") or uploaded_file.size),
        "updated_at": result.get("created_at"),
    }


def upload_master_workbook(path, public_id=DEFAULT_MASTER_WORKBOOK_PUBLIC_ID):
    path = Path(path)
    if not path.exists() or path.suffix.lower() != ".xlsx":
        raise ValueError("A valid .xlsx master workbook is required.")
    result = cloudinary.uploader.upload(
        str(path),
        resource_type="raw",
        public_id=public_id,
        overwrite=True,
        invalidate=True,
    )
    return {
        "url": result["secure_url"],
        "public_id": result["public_id"],
        "version": int(result["version"]),
        "bytes": int(result.get("bytes") or path.stat().st_size),
        "updated_at": result.get("created_at"),
    }


def get_master_workbook_reference(public_id=DEFAULT_MASTER_WORKBOOK_PUBLIC_ID):
    result = cloudinary.api.resource(public_id, resource_type="raw")
    return {
        "url": result["secure_url"],
        "public_id": result["public_id"],
        "version": int(result["version"]),
        "bytes": int(result.get("bytes") or 0),
        "updated_at": result.get("updated_at") or result.get("created_at"),
    }
