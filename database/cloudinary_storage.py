"""Cloudinary file storage used by the customer-support UI."""

from pathlib import Path

from dotenv import load_dotenv


load_dotenv(Path(__file__).resolve().parents[1] / ".env")

import cloudinary.uploader  # noqa: E402


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
